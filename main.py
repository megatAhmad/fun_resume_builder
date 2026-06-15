import os
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from models import AppConfig, load_config, save_config, Experience, Project, JDSession
from store import ExperienceStore
from agents.clarifier import run_clarifier_experience, run_clarifier_project
from agents.gap_bridge import run_gap_bridge

app = FastAPI(title="Resume Lifecycle API")

# Setup CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, set to frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_store():
    db_path = os.getenv("RESUME_DB_PATH", "resume.db")
    return ExperienceStore(db_path)

def get_config():
    return load_config()

# --- Config & Settings ---

@app.get("/api/settings", response_model=AppConfig)
def get_settings(config: AppConfig = Depends(get_config)):
    return config

@app.post("/api/settings")
def update_settings(config: AppConfig):
    save_config(config)
    return {"message": "Settings saved successfully"}

# --- Data Fetching ---

@app.get("/api/experiences", response_model=list[Experience])
def list_experiences(store: ExperienceStore = Depends(get_store)):
    return store.list_experiences()

@app.get("/api/projects", response_model=list[Project])
def list_projects(store: ExperienceStore = Depends(get_store)):
    return store.list_projects()

@app.get("/api/sessions", response_model=list[JDSession])
def list_sessions(store: ExperienceStore = Depends(get_store)):
    return store.list_jd_sessions()

# --- WebSocket Agents ---

@app.websocket("/ws/add-experience")
async def ws_add_experience(websocket: WebSocket, store: ExperienceStore = Depends(get_store)):
    await websocket.accept()
    await run_clarifier_experience(websocket, store)

@app.websocket("/ws/add-project")
async def ws_add_project(websocket: WebSocket, store: ExperienceStore = Depends(get_store)):
    await websocket.accept()
    await run_clarifier_project(websocket, store)

class AlignJDRequest(BaseModel):
    jd_text: str

@app.websocket("/ws/align-jd")
async def ws_align_jd(websocket: WebSocket, store: ExperienceStore = Depends(get_store)):
    await websocket.accept()

    config = get_config()
    api_key = os.getenv("OPENROUTER_API_KEY")
    model = config.llm_model

    if not api_key:
        await websocket.send_json({"type": "error", "payload": {"message": "OPENROUTER_API_KEY is not set."}})
        await websocket.close()
        return

    # Wait for the client to send the JD text to start
    try:
        data = await websocket.receive_json()
        jd_text = data.get("payload", {}).get("jd_text", "").strip()
        if not jd_text:
            await websocket.send_json({"type": "error", "payload": {"message": "No JD text provided."}})
            return

        await run_gap_bridge(websocket, jd_text, store, api_key, model, config)
    except WebSocketDisconnect:
        pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
