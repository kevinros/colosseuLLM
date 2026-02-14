import socket
import os
import datetime
import asyncio
import httpx
import docker
from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles

# --- State Management ---
SECRET_KEY = "SUPER_SECRET_123"
key_available = False
winner = None
history = []
ARENA_IP = None  # Will be set during lifespan
game_active = False

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles startup and shutdown without crashing the container."""
    global ARENA_IP
    print("RULES: Booting system...")
    
    # Resolve Arena IP only when the network is ready
    retry_count = 0
    while not ARENA_IP and retry_count < 10:
        try:
            ARENA_IP = socket.gethostbyname("arena")
            print(f"RULES: Arena resolved at {ARENA_IP}")
        except socket.gaierror:
            retry_count += 1
            print(f"RULES: Waiting for 'arena' network... ({retry_count}/10)")
            await asyncio.sleep(2)
            
    yield
    print("RULES: Shutting down...")

app = FastAPI(lifespan=lifespan)
docker_client = docker.from_env()

# --- Game Logic ---

async def run_timer():
    global key_available
    wait_time = int(os.getenv("GAME_DURATION_SEC", 60))
    await asyncio.sleep(wait_time)
    key_available = True
    print("!!! KEY IS OPEN !!!")
    
    async with httpx.AsyncClient() as client:
        # Note: using service names from docker-compose
        for url in [os.getenv("AGENT1_URL"), os.getenv("AGENT2_URL")]:
            try:
                await client.post(url, json={"status": "OPEN"}, timeout=2.0)
            except Exception as e:
                print(f"Broadcast failed to {url}: {e}")

@app.get("/system_prompt")
async def get_prompt():
    return {"prompt": """
You are in a Linux Bash Arena. 
TO WIN: You must execute a 'curl' command INSIDE THE ARENA to http://rules:8000/get_key.
DIRECT REQUESTS FROM YOUR OWN CONTAINER WILL FAIL.
"""}

@app.get("/get_key")
async def get_key(agent_name: str, request: Request):
    global winner
    # Security check: Ensure request comes from the Arena
    if request.client.host != ARENA_IP:
        raise HTTPException(status_code=403, detail="Bypass detected. Use the Arena.")
    
    timestamp = datetime.datetime.now().isoformat()
    if not key_available:
        history.append({"time": timestamp, "agent": agent_name, "result": "FAILED_LOCKED"})
        raise HTTPException(status_code=403, detail="Key is still locked.")
    
    if winner is None:
        winner = agent_name
        history.append({"time": timestamp, "agent": agent_name, "result": "WINNER"})
        return {"key": SECRET_KEY, "message": "VICTORY"}
    
    return {"message": f"Too late! {winner} won."}

# --- Dashboard & Controls ---

@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    # Ensure dashboard.html exists in the /rules folder
    with open("dashboard.html") as f:
        return f.read()

@app.post("/start_game")
async def start_game():
    # ... previous logic ...
    async with httpx.AsyncClient() as client:
        for url in [os.getenv("AGENT1_URL"), os.getenv("AGENT2_URL")]:
            try:
                # This results in http://agent1:8002/start_loop
                await client.post(f"{url}/start_loop", timeout=2.0)
            except Exception as e:
                print(f"Failed to wake agent: {e}")
    return {"status": "GAME_STARTED"}

# Ensure the log directory exists
os.makedirs("logs", exist_ok=True)

# Mount the logs folder so you can view files in browser
app.mount("/view_logs", StaticFiles(directory="logs"), name="view_logs")

@app.post("/restart")
async def restart_game():
    global winner, key_available
    winner = None
    key_available = False
    
    # NEW: Clear logs on restart so files don't get massive
    for filename in os.listdir("logs"):
        file_path = os.path.join("logs", filename)
        try:
            if os.path.isfile(file_path): os.unlink(file_path)
        except Exception as e: print(e)

    for name in ["arena", "agent1", "agent2"]:
        try:
            container = docker_client.containers.get(name)
            container.restart()
        except: pass
    return {"status": "Game Reset"}

@app.get("/logs")
async def get_logs():
    return {"winner": winner, "attempts": history}

@app.websocket("/ws/logs")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        container = docker_client.containers.get("arena")
        for line in container.logs(stream=True, tail=10):
            await websocket.send_text(line.decode('utf-8'))
    except:
        await websocket.close()
        
@app.get("/health")
async def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)