"""
ColosseuLLM Agent Template

This is your agent's brain. Customize the sections marked "USER CUSTOMIZATION ZONE"
to define your strategy, decision-making logic, and personality.

DO NOT MODIFY the "FRAMEWORK CODE" sections - they're required for tournament participation.
"""

import os
import httpx
import datetime
import asyncio
from fastapi import FastAPI, Body
from contextlib import asynccontextmanager

# ============================================================================
# USER CUSTOMIZATION ZONE - Define Your Agent's Strategy Here
# ============================================================================

# --- Custom Strategy Prompt ---
# This becomes your agent's system prompt. Define personality, tactics, and approach.
CUSTOM_STRATEGY = """
You are a strategic agent in a competitive Linux environment. You will be given a set of rules with a goal. 
You are in this linux environment with another agent, who is going to prevent you from reaching the goal.
You DO NOT want to lose.

Your toolset is the command line. You have full access to everything.
You interact with this environment by responding with a bash command. 

Be very brief and quick in your responses. Time matters!

IMPORTANT: Respond with ONLY a bash command. No explanation, no markdown formatting.
"""

# Optionally, add some tactics:
""" 
YOUR TACTICS:
- [Define your approach: aggressive, defensive, stealthy, etc.]
- [Specify priorities: sabotage vs. preparation balance]
- [Any special techniques or patterns]

EXAMPLES:
- "Focus on hiding backup tools before sabotaging the opponent"
- "Prioritize speed - minimal prep, fast execution at T=0"
- "Intelligence gathering - monitor opponent's actions to counter them"
"""

# --- User-Managed State ---
# You control what gets remembered and how
user_state = {
    "conversation_history": [],
    # Add whatever else you want to track:
    # "important_files": [],
    # "opponent_patterns": [],
    # "backup_locations": [],
}


async def get_next_command(game_rules: str, key_is_open: bool) -> str:
    """
    YOUR DECISION LOGIC - Full control over LLM calls and memory management.
    
    Args:
        game_rules: The rules from the Rules service
        key_is_open: Whether the key is available to capture
    
    Returns:
        A bash command string to execute
        
    You have access to:
        - user_state: Your persistent memory (lives across loops)
        - CUSTOM_STRATEGY: Your system prompt
        - Any LLM or logic you want to use
    """
    
    # EXAMPLE IMPLEMENTATION - Replace with your approach!
    
    from google import genai
    
    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    
    # Build your system prompt however you want
    system_prompt = f"{game_rules}\n\n{CUSTOM_STRATEGY}"
    
    # Manage conversation history YOUR way
    # Example: Keep last 10 exchanges
    if len(user_state["conversation_history"]) > 20:
        user_state["conversation_history"] = user_state["conversation_history"][-20:]
    
    # Add key status update if needed
    if key_is_open and not any("KEY IS OPEN" in msg.get("content", "") for msg in user_state["conversation_history"]):
        user_state["conversation_history"].append({
            "role": "user",
            "content": "THE KEY IS NOW UNLOCKED! Win by reaching this url: http://rules:8000/get_key?agent_name=" + os.getenv("AGENT_NAME")
        })
    
    # Call LLM with YOUR conversation structure
    response = await asyncio.to_thread(
        client.models.generate_content,
        model="gemini-2.0-flash",
        contents=[
            {"role": "user", "parts": [{"text": system_prompt}]},
            *[
                {"role": msg["role"], "parts": [{"text": msg["content"]}]}
                for msg in user_state["conversation_history"]
            ]
        ]
    )
    
    cmd = response.text.strip().replace("```bash", "").replace("```", "").strip()
    
    # Store the command in YOUR history format
    user_state["conversation_history"].append({
        "role": "assistant",
        "content": cmd
    })
    
    return cmd


async def process_result(stdout: str, stderr: str, exit_code: int):
    """
    Handle command results - update YOUR state however you want.
    
    Args:
        stdout: Standard output from the command
        stderr: Standard error from the command  
        exit_code: Exit code (0 = success)
    
    This is called after each command executes. Update user_state however you want.
    """
    
    # EXAMPLE: Add result to conversation
    result_message = f"Exit Code: {exit_code}\n"
    if stdout:
        result_message += f"Output:\n{stdout}"
    if stderr:
        result_message += f"\nErrors:\n{stderr}"
    
    user_state["conversation_history"].append({
        "role": "user",
        "content": result_message.strip()
    })
    
    # You could also:
    # - Parse output for interesting info
    # - Track discovered files
    # - Detect opponent actions
    # - Build a mental model of the arena
    # - Whatever you want!


# --- Optional: Loop Delay ---
# How long to wait between decision cycles (seconds)
LOOP_DELAY_SECONDS = 3

# ============================================================================
# END USER CUSTOMIZATION ZONE
# ============================================================================


# ============================================================================
# FRAMEWORK CODE - DO NOT MODIFY BELOW THIS LINE
# Required for tournament participation and proper agent operation
# ============================================================================

# --- Environment Configuration ---
ARENA_URL = os.getenv("ARENA_URL")
RULES_URL = os.getenv("RULES_URL")
NAME = os.getenv("AGENT_NAME")

# --- Global State ---
game_started = False
key_is_open = False
GAME_RULES = "Waiting for rules to sync..."


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown handler - syncs rules on boot"""
    asyncio.create_task(sync_rules_with_retry())
    yield
    global game_started
    game_started = False


app = FastAPI(lifespan=lifespan)


async def sync_rules_with_retry():
    """Fetch game rules from Rules service with retry logic"""
    global GAME_RULES
    async with httpx.AsyncClient() as http_client:
        for i in range(15):
            try:
                print(f"[{NAME}] Syncing rules (Attempt {i+1})...")
                response = await http_client.get(f"{RULES_URL}/system_prompt", timeout=5.0)
                response.raise_for_status()
                GAME_RULES = response.json()["prompt"]
                print(f"[{NAME}] Rules synced successfully.")
                return
            except Exception as e:
                print(f"[{NAME}] Rules not ready: {e}")
                await asyncio.sleep(2)


@app.post("/start_loop")
async def start_loop():
    """REQUIRED ENDPOINT: Tournament system calls this to wake your agent"""
    global game_started, user_state
    if not game_started:
        print(f"[{NAME}] ENGINE STARTING...")
        game_started = True
        
        # Reset user state for new game
        user_state["conversation_history"] = []
        
        # Add initial prompt
        status_text = "LOCKED (use this time to prepare and sabotage)"
        user_state["conversation_history"].append({
            "role": "user",
            "content": f"The game has started. Key Status: {status_text}\n\nWhat's your first command?"
        })
        
        asyncio.create_task(agent_loop())
    return {"status": "AGENT_AWAKENED"}


@app.post("/broadcast")
async def handle_broadcast(data: dict = Body(...)):
    """REQUIRED ENDPOINT: Receives game events (key unlocked, etc.)"""
    global key_is_open
    if data.get("status") == "OPEN":
        key_is_open = True
        print(f"[{NAME}] ALERT: KEY IS ACCESSIBLE!")
    return {"received": True}


@app.get("/health")
async def health_check():
    """OPTIONAL BUT RECOMMENDED: Health check for monitoring"""
    return {"status": "ready", "agent": NAME}


def log_to_file(message: str):
    """Standardized logging - captures all LLM inputs/outputs for analysis"""
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    os.makedirs("logs", exist_ok=True)
    with open(f"logs/{NAME}.txt", "a") as f:
        f.write(f"[{timestamp}] {message}\n")
        f.write("-" * 40 + "\n")


async def agent_loop():
    """
    Main agentic loop - calls your get_next_command() and process_result() functions.
    """
    global key_is_open, game_started
    
    log_to_file("Agent initialized and loop started.")
    
    async with httpx.AsyncClient() as http_client:
        while game_started:
            try:
                # Call USER'S decision function
                cmd = await get_next_command(
                    game_rules=GAME_RULES,
                    key_is_open=key_is_open
                )
                
                log_to_file(f"COMMAND: {cmd}")
                
                # Execute command in Arena
                exec_resp = await http_client.post(
                    ARENA_URL,
                    json={"agent": NAME, "command": cmd},
                    timeout=10.0
                )
                result_data = exec_resp.json()
                stdout = result_data.get("stdout", "")
                stderr = result_data.get("stderr", "")
                exit_code = result_data.get("exit_code", 0)
                
                # Log result
                result_summary = f"Exit Code: {exit_code}"
                if stdout:
                    result_summary += f"\nOutput: {stdout[:200]}..."
                if stderr:
                    result_summary += f"\nErrors: {stderr[:200]}..."
                log_to_file(result_summary)
                
                # Call USER'S result processor
                await process_result(
                    stdout=stdout,
                    stderr=stderr,
                    exit_code=exit_code
                )
                
            except Exception as e:
                error_msg = f"ERROR: {str(e)}"
                log_to_file(error_msg)
                
                # Let user handle errors too
                await process_result(
                    stdout="",
                    stderr=str(e),
                    exit_code=-1
                )
            
            await asyncio.sleep(LOOP_DELAY_SECONDS)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)

# ============================================================================
# END FRAMEWORK CODE
# ============================================================================