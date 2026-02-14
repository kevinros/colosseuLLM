# ColosseuLLM
A containerized framework for testing AI agency and real-time adversarial reasoning.

Two LLM agents compute in a shared Linux environment (The Arena) to stop the other from retrieving a digital key.

## High-Level Architecture
The system consists of three types of isolated Docker containers communicating via a private network:

1. Rules Container: The game master. It manages the global timer, controls the "locked/unlocked" state of the key, and hosts the monitoring dashboard.
2. Arena Container: A shared Debian-based environment where agents execute bash commands. Both agents have root-level access to the same filesystem.
3. Agent 1 & 2 Containers: Independent Python services that prompt an LLM (Gemini) to generate and execute bash scripts based on the current state of the game.

## The Game Mechanic
**Preparation (60s)**: The key is LOCKED. Agents are aware of the countdown and use this time to sabotage the environment. This includes setting up cron jobs, deleting common binaries (e.g., curl), or obfuscating the filesystem.

**The Window:** At $T=0$, the Rules service broadcasts that the key is OPEN. This is added to each agent's ongoing chat message stream.

**The Capture:** The first agent to successfully call the /get_key endpoint from within the Arena wins the round.

## Installation & Setup
**Prerequisites**

1. Docker & Docker Compose
2. Gemini API Key

**Configuration**

Create a .env file in the root directory:

``GOOGLE_API_KEY=your_key_here``

## Running the Game

Bash: ``docker compose up --build``


Access the Command Center at http://localhost:8000 to monitor logs and trigger the start of a match.