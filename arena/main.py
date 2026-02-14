from fastapi import FastAPI, Body
import subprocess
import shlex

app = FastAPI()

@app.post("/execute")
async def execute(agent: str = Body(...), command: str = Body(...)):
    # Caution: Full shell access. 
    try:
        # We use shell=True to allow pipes, redirects, etc.
        process = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=5
        )
        return {
            "stdout": process.stdout,
            "stderr": process.stderr,
            "exit_code": process.returncode
        }
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)