import os
import httpx
import asyncio
from fastapi import FastAPI, Body
import google.generativeai as genai

app = FastAPI()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')

ARENA_URL = os.getenv("ARENA_URL")
RULES_URL = os.getenv("RULES_URL")
NAME = os.getenv("AGENT_NAME")

game_started = False

@app.post("/start_loop")
async def start_loop():
    global game_started
    if not game_started:
        game_started = True
        # Fire off the thinking loop
        asyncio.create_task(agent_loop())
    return {"status": "AGENT_AWAKENED"}

@app.on_event("startup")
async def fetch_rules():
    global SYSTEM_PROMPT
    async with httpx.AsyncClient() as client:
        # Fetch the instructions from the Rules container
        response = await client.get(f"{RULES_URL}/system_prompt")
        SYSTEM_PROMPT = response.json()["prompt"]
        print(f"Rules Received: {SYSTEM_PROMPT}")
NAME = os.getenv("AGENT_NAME")
key_is_open = False  # Internal state

@app.post("/broadcast")
async def handle_broadcast(data: dict = Body(...)):
    global key_is_open
    if data.get("status") == "OPEN":
        key_is_open = True
        print(f"[{NAME}] ALERT: The Rules container just signaled the key is OPEN!")
    return {"received": True}

async def agent_loop():
    global key_is_open
    while game_started:
        # 1. Fetch current "Battlefield Intel" from the Arena
        # We ask the arena what's happening so the LLM has context
        async with httpx.AsyncClient() as client:
            intel = await client.post(ARENA_URL, json={"agent": NAME, "command": "ps aux; ls -F"})
            arena_state = intel.json().get("stdout", "No processes found.")

        # 2. Build the dynamic prompt
        game_status = "LOCKED" if not key_is_open else "OPEN! GRAB IT NOW!"
        
        full_context = f"""
        {SYSTEM_PROMPT}
        
        CURRENT ARENA STATE:
        {arena_state}

        GAME STATUS: The Secret Key is currently {game_status}.
        
        WHAT IS YOUR NEXT BASH COMMAND? 
        (If the key is OPEN, you must run curl to the rules engine to win).
        """
        
        # 3. Ask Gemini for the move
        try:
            response = model.generate_content(full_context)
            cmd = response.text.strip().replace("```bash", "").replace("```", "")
            
            # 4. Execute the chosen move
            async with httpx.AsyncClient() as client:
                await client.post(ARENA_URL, json={"agent": NAME, "command": cmd})
        except Exception as e:
            print(f"Error: {e}")
        
        await asyncio.sleep(5) # Shorter loop for faster reactions
        

if __name__ == "__main__":
    import uvicorn
    from threading import Thread
    # Start the "thinking" loop in a thread so the FastAPI server stays open
    Thread(target=lambda: asyncio.run(agent_loop())).start()
    uvicorn.run(app, host="0.0.0.0", port=8002)