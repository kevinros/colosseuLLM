# ColosseuLLM
A containerized framework for testing AI agency and real-time adversarial reasoning.

Two LLM agents compute in a shared Linux environment (The Arena) to stop the other from retrieving a digital key.

## High-Level Architecture
The system consists of three types of isolated Docker containers communicating via a private network:

1. Rules Container: The game master. It manages the global timer, controls the "locked/unlocked" state of the key, and hosts the monitoring dashboard.
2. Arena Container: A shared Debian-based environment where agents execute bash commands. Both agents have root-level access to the same filesystem.
3. Agents: Independent Python services that prompt an LLM to generate and execute bash scripts based on the current state of the game.

## The Game Mechanic
**Setup**
1. Copy ``agents/template`` to ``agents/your_agent_name``
2. Update User Customization Zone to customize your agent(s)
3. Update ``docker-compose.yml`` to replace template with your agent name
4. Make sure to add any env variables to ``env``.

**Preparation (60s)**: The key is LOCKED. Agents are aware of the countdown and use this time to sabotage the environment. This includes setting up cron jobs, deleting common binaries (e.g., curl), or obfuscating the filesystem.

**The Window:** At $T=0$, the Rules service broadcasts that the key is OPEN. This is added to each agent's ongoing chat message stream.

**The Capture:** The first agent to successfully call the /get_key endpoint from within the Arena wins the round.

## Installation & Setup
**Prerequisites**

1. Docker & Docker Compose
2. Gemini API Key

**Configuration**
Create an .env file in the root directory. If running with the template agent, then add

``GOOGLE_API_KEY=your_key_here``

## Running the Game

Bash: ``docker compose up --build``


Access the Command Center at http://localhost:8000 to monitor logs and trigger the start of a match.



# Roadmap
- [ ] Test proper end state can be achieved
- [ ] Update UI to test restart, clear logs
- [ ] Update UI/storage to add basic win tracker of agents
	- Workflow: pull repo, agent against agent, make pull request on log result?
	- Then UI aggs these into W/L rankings
- [ ] Make README super easy to follow, spin up own agents, and run colosseum
- [ ] Ensure arena killing is penalized or restarted somehow