# ColosseuLLM

Battlebots, but for LLMs!

Two LLM agents compute in a shared Linux environment (The Arena) to stop the other from retrieving a digital key.

Quickstart:

1. Create and add your Gemini key to ``.env``
2. ``docker compose up --build``
3. Visit ``http://localhost:8000/``
4. Click ``Start Match``
5. Open the ``game_logs/*.txt`` files to see what the agents do!


## High-Level Overview
### Architecture
The system consists of three types of isolated Docker containers communicating via a private network:

1. Rules Container: The game master. It manages the global timer, controls the "locked/unlocked" state of the key, and hosts the monitoring dashboard.
2. Arena Container: A shared Debian-based environment where agents execute bash commands. Both agents have access to the same filesystem.
3. Agents: Independent Python services that prompt an LLM to generate and execute bash scripts based on the current state of the game.

###  The Game Mechanics
Once ``Start Match`` is clicked, the Rules container broadcasts to the Agents containers. This broadcast includes the instructions for the game.

Then, the Agents are free to send any bash command they want to the Arena. The Arena consists of a single endpoint that will execute this bash command and send the result back to the Agent.

After 60 seconds, another broadcast is sent by the Rules to notify the agents that the key is available. The Agents then have 10 seconds to access the key. Accesses are logged, and the outcome is determined according to the following scenarios:

1. Both Agents access the key: Draw
2. One Agent accesses the key: that Agent wins, the other Agent loses
3. Neither Agent accesses the key: Draw


### Customization
#### Making or Selecting the Agent
To create an Agent, 

1. Copy ``agents/template`` to ``agents/your_agent_name``
2. Update the User Customization Zone to customize your Agent

Then, once you create it (or decide which Agent to select),
3. Update ``docker-compose.yml`` to replace the template Agent(s) with the Agent name
4. Make sure to add any env variables to ``env``.

### Making or Selecting the Arena
You can either select an existing Arena or create your own custom Arena. 

To create an Arena,
1. Copy ``arena/template`` to ``arena/your_arena_name``
2. Update anything (like packages available, etc.)

Then once you create it (or decide which Arena to select),
3. Update ``docker-compose.yml`` to replace the template Arena with the Arena name