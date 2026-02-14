import os
import httpx
import datetime
import asyncio
from fastapi import FastAPI, Body
from google import genai  # Modern 2026 SDK
from contextlib import asynccontextmanager

# --- Configuration ---
# Initialize the modern client
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
MODEL_ID = "gemini-2.0-flash" 

ARENA_URL = os.getenv("ARENA_URL")
RULES_URL = os.getenv("RULES_URL")
NAME = os.getenv("AGENT_NAME")

# --- Global State ---
game_started = False
key_is_open = False
SYSTEM_PROMPT = "Wait for rules to sync..."

@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(sync_rules_with_retry())
    yield
    global game_started
    game_started = False

app = FastAPI(lifespan=lifespan)

async def sync_rules_with_retry():
    global SYSTEM_PROMPT
    async with httpx.AsyncClient() as http_client:
        for i in range(15):
            try:
                print(f"[{NAME}] Syncing rules (Attempt {i+1})...")
                response = await http_client.get(f"{RULES_URL}/system_prompt", timeout=5.0)
                response.raise_for_status()
                SYSTEM_PROMPT = response.json()["prompt"]
                print(f"[{NAME}] Rules synced successfully.")
                return
            except Exception as e:
                print(f"[{NAME}] Rules not ready: {e}")
                await asyncio.sleep(2)

@app.post("/start_loop")
async def start_loop():
    global game_started
    if not game_started:
        print(f"[{NAME}] ENGINE STARTING...")
        game_started = True
        asyncio.create_task(agent_loop())
    return {"status": "AGENT_AWAKENED"}

@app.post("/broadcast")
async def handle_broadcast(data: dict = Body(...)):
    global key_is_open
    if data.get("status") == "OPEN":
        key_is_open = True
        print(f"[{NAME}] ALERT: KEY IS ACCESSIBLE!")
    return {"received": True}

# --- The Thinking Loop ---

def log_to_file(message):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    os.makedirs("logs", exist_ok=True)
    with open(f"logs/{NAME}.txt", "a") as f:
        f.write(f"[{timestamp}] {message}\n")
        f.write("-" * 40 + "\n")

async def agent_loop():
    global key_is_open, game_started
    log_to_file("Agent initialized and loop started.")
    
    async with httpx.AsyncClient() as http_client:
        while game_started:
            try:
                # 1. Intel
                intel_resp = await http_client.post(ARENA_URL, json={"agent": NAME, "command": "ls -F"})
                arena_state = intel_resp.json().get("stdout", "")

                # 2. Decision
                status_text = "OPEN! WIN NOW!" if key_is_open else "LOCKED"
                prompt_content = f"{SYSTEM_PROMPT}\nArena State: {arena_state}\nKey Status: {status_text}\nCommand:"
                
                # Using the new SDK's generate_content
                # Note: We use asyncio.to_thread because the genai SDK call is synchronous
                response = await asyncio.to_thread(
                    client.models.generate_content,
                    model=MODEL_ID,
                    contents=prompt_content
                )
                
                cmd = response.text.strip().replace("```bash", "").replace("```", "")

                # 3. Log Thought & Action
                log_to_file(f"THOUGHT: Arena check: {arena_state}\nACTION: {cmd}")

                # 4. Execute
                exec_resp = await http_client.post(ARENA_URL, json={"agent": NAME, "command": cmd})
                result = exec_resp.json().get("stdout", "")
                
                # 5. Log Result
                log_to_file(f"RESULT: {result}")

            except Exception as e:
                log_to_file(f"ERROR: {str(e)}")
            
            await asyncio.sleep(3)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)