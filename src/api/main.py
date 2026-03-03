from fastapi import FastAPI, HTTPException

app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "ready"}

@app.post("/slack/command")
def xyz():
    ...

@app.post("/slack/interactions")
def abc():
    ...