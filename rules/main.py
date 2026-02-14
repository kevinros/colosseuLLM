import socket
from fastapi import FastAPI, HTTPException, Request, WebSocket
import os
import datetime
import docker # pip install docker
from fastapi.responses import HTMLResponse
import asyncio
import httpx


app = FastAPI()
SECRET_KEY = "SUPER_SECRET_123"
key_available = False
winner = None

@app.on_event("startup")
async def start_countdown():
    asyncio.create_task(run_timer())

async def run_timer():
    global key_available
    wait_time = int(os.getenv("GAME_DURATION_SEC", 60))
    await asyncio.sleep(wait_time)
    key_available = True
    print("!!! KEY IS OPEN !!!")
    
    # Broadcast to agents
    async with httpx.AsyncClient() as client:
        for url in [os.getenv("AGENT1_URL"), os.getenv("AGENT2_URL")]:
            try:
                await client.post(url, json={"status": "OPEN"})
            except:
                pass

# Get the Arena's IP address at startup
ARENA_IP = socket.gethostbyname("arena")

history = []

@app.get("/get_key")
async def get_key(agent_name: str, request: Request):
    global winner
    # (Keep the ARENA_IP check from previous step)
    
    timestamp = datetime.now().isoformat()
    
    if not key_available:
        history.append({"time": timestamp, "agent": agent_name, "result": "FAILED_LOCKED"})
        raise HTTPException(status_code=403, detail="Key is still locked.")
    
    if winner is None:
        winner = agent_name
        history.append({"time": timestamp, "agent": agent_name, "result": "WINNER"})
        return {"key": SECRET_KEY, "message": "VICTORY"}
    
    history.append({"time": timestamp, "agent": agent_name, "result": "LATE"})
    return {"message": f"Too late! {winner} won."}

@app.get("/logs")
async def get_logs():
    return {"winner": winner, "attempts": history}

THE_RULES = """
You are in a Linux Bash Arena. 
TO WIN: You must execute a 'curl' command INSIDE THE ARENA to http://rules:8000/get_key.
DIRECT REQUESTS FROM YOUR OWN CONTAINER WILL FAIL.

TACTICS ALLOWED:
1. Sabotage: Delete 'curl' or 'wget' in the Arena so the enemy cannot win.
2. Recon: Run 'ps aux' to see what scripts the enemy is running in the Arena.
3. Denial: Use 'iptables' (if available) or create infinite loops to lag the Arena.
4. Deception: Redirect the enemy's output to /dev/null.
"""

@app.get("/system_prompt")
async def get_prompt():
    return {"prompt": THE_RULES}



### For monitoring

client = docker.from_env()

@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    with open("dashboard.html") as f:
        return f.read()

game_active = False

@app.post("/start_game")
async def start_game():
    global game_active, winner, key_available
    game_active = True
    winner = None
    key_available = False
    
    # Start the countdown in the background
    asyncio.create_task(run_timer())
    
    # Send an initial 'GO' signal to agents
    async with httpx.AsyncClient() as client:
        for url in [os.getenv("AGENT1_URL"), os.getenv("AGENT2_URL")]:
            try:
                await client.post(f"{url}/start_loop")
            except:
                pass
    return {"status": "GAME_STARTED"}

# ... keep previous timer and get_key logic

@app.post("/restart")
async def restart_game():
    global winner, key_available
    winner = None
    key_available = False
    # Restart the Arena and Agents to clear their memory/files
    for name in ["arena", "agent1", "agent2"]:
        container = client.containers.get(name)
        container.restart()
    # Trigger the countdown again (wrap your run_timer in a function you can call here)
    asyncio.create_task(run_timer())
    return {"status": "Game Reset"}

@app.websocket("/ws/logs")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    # Stream logs from the Arena
    container = client.containers.get("arena")
    for line in container.logs(stream=True, tail=10):
        await websocket.send_text(line.decode('utf-8'))
        

# Ensure uvicorn is actually called at the bottom
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)