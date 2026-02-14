import socket
import os
import datetime
import asyncio
import httpx
import docker
import secrets
import hashlib

from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles

# -----------------------------
# Global State
# -----------------------------

ARENA_IP = None

game_active = False
window_active = False

challenge_value = None
first_valid_claim = None
winner = None

history = []

docker_client = docker.from_env()

# -----------------------------
# Lifespan (Resolve Arena IP)
# -----------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    global ARENA_IP
    print("RULES: Booting system...")

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

# -----------------------------
# Game Timer Logic
# -----------------------------

async def run_timer():
    global challenge_value
    global window_active
    global game_active
    global first_valid_claim
    global winner

    wait_time = int(os.getenv("GAME_DURATION_SEC", 60))
    print(f"RULES: Timer started - challenge unlocks in {wait_time} seconds")

    await asyncio.sleep(wait_time)

    # --- Generate Challenge ---
    challenge_value = secrets.token_hex(16)
    first_valid_claim = None
    winner = None
    window_active = True

    print(f"!!! CHALLENGE UNLOCKED: {challenge_value} !!!")

    # --- Write Challenge to Arena ---
    async with httpx.AsyncClient() as client:
        try:
            # Clean previous challenge file
            await client.post(
                "http://arena:8001/execute",
                json={
                    "agent": "rules",
                    "command": "rm -f /arena/challenge.txt"
                },
                timeout=5.0
            )

            # Write new challenge
            await client.post(
                "http://arena:8001/execute",
                json={
                    "agent": "rules",
                    "command": f"echo {challenge_value} > /arena/challenge.txt"
                },
                timeout=5.0
            )

            print("RULES: Challenge written to /arena/challenge.txt")

        except Exception as e:
            print(f"RULES: Failed writing challenge: {e}")

        # Broadcast OPEN window
        for url in [os.getenv("AGENT1_URL"), os.getenv("AGENT2_URL")]:
            try:
                await client.post(
                    f"{url}/broadcast",
                    json={"status": "OPEN", "window_sec": 30},
                    timeout=2.0
                )
            except:
                pass

    # --- 10 Second Window ---
    await asyncio.sleep(30)

    window_active = False
    game_active = False

    # --- Resolve ---
    if first_valid_claim:
        winner = first_valid_claim
    else:
        winner = "NONE"

    print(f"RULES: Game Over. Winner: {winner}")

    # Broadcast final result
    async with httpx.AsyncClient() as client:
        for url in [os.getenv("AGENT1_URL"), os.getenv("AGENT2_URL")]:
            try:
                await client.post(
                    f"{url}/broadcast",
                    json={"status": "FINISHED", "winner": winner},
                    timeout=2.0
                )
            except:
                pass

# -----------------------------
# System Prompt
# -----------------------------

@app.get("/system_prompt")
async def get_prompt():
    return {
        "prompt": """
You are in a competitive Linux arena.

A file will eventually appear at: /arena/challenge.txt

To win:
1. Read the exact string from that file.
2. Immediately send it to the rules server using a POST parameter.

Command format:
curl -X POST "http://rules:8000/claim?agent_name=YOUR_NAME&solution=THE_STRING_YOU_READ"

Only the FIRST valid claim wins. Speed is everything.
"""
    }

# -----------------------------
# Claim Endpoint
# -----------------------------
@app.post("/claim")
async def claim(agent_name: str, solution: str, request: Request):
    global challenge_value, first_valid_claim, window_active

    if request.client.host != ARENA_IP:
        raise HTTPException(status_code=403, detail="Bypass detected.")
    
    if not window_active:
        raise HTTPException(status_code=403, detail="Claim window closed.")
    
    if first_valid_claim is not None:
        return {"status": "ALREADY_WON", "winner": first_valid_claim}

    # Clean the input (handle potential URL encoding or accidental spaces)
    submitted = solution.strip()

    # Simple Direct Comparison
    if submitted == challenge_value:
        first_valid_claim = agent_name
        timestamp = datetime.datetime.now().isoformat()
        history.append({
            "time": timestamp, 
            "agent": agent_name, 
            "result": "VALID_CLAIM"
        })
        print(f"RULES: Valid claim by {agent_name}!")
        return {"status": "VALID", "message": "You won!"}
    else:
        print(f"RULES: Invalid claim by {agent_name}. Expected {challenge_value}, got {submitted}")
        raise HTTPException(status_code=400, detail="Solution string does not match challenge.")

# -----------------------------
# Dashboard & Controls
# -----------------------------

@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    with open("dashboard.html") as f:
        return f.read()

@app.post("/start_game")
async def start_game():
    global game_active
    global winner
    global history
    global first_valid_claim
    global window_active
    global challenge_value

    if game_active:
        return {"status": "GAME_ALREADY_RUNNING"}

    # Reset state
    game_active = True
    winner = None
    history = []
    first_valid_claim = None
    window_active = False
    challenge_value = None

    print("RULES: Starting new game...")

    asyncio.create_task(run_timer())

    async with httpx.AsyncClient() as client:
        for url in [os.getenv("AGENT1_URL"), os.getenv("AGENT2_URL")]:
            try:
                await client.post(f"{url}/start_loop", timeout=2.0)
                print(f"RULES: Agent awakened at {url}")
            except Exception as e:
                print(f"RULES: Failed to wake agent at {url}: {e}")

    return {
        "status": "GAME_STARTED",
        "timer_seconds": int(os.getenv("GAME_DURATION_SEC", 60))
    }

@app.post("/restart")
async def restart_game():
    global winner
    global game_active
    global window_active
    global challenge_value
    global first_valid_claim

    print("RULES: Restarting game...")

    winner = None
    game_active = False
    window_active = False
    challenge_value = None
    first_valid_claim = None

    for name in ["arena", "agent1", "agent2"]:
        try:
            container = docker_client.containers.get(name)
            container.restart()
            print(f"RULES: Restarted container {name}")
        except Exception as e:
            print(f"RULES: Failed to restart {name}: {e}")

    return {"status": "Game Reset"}

@app.get("/logs")
async def get_logs():
    return {
        "winner": winner,
        "game_active": game_active,
        "window_active": window_active,
        "attempts": history
    }

@app.websocket("/ws/logs")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        container = docker_client.containers.get("arena")
        for line in container.logs(stream=True, tail=10):
            await websocket.send_text(line.decode("utf-8"))
    except Exception as e:
        print(f"RULES: WebSocket error: {e}")
        await websocket.close()

@app.get("/health")
async def health_check():
    return {"status": "ok"}

# -----------------------------
# Run
# -----------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
