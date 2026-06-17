from __future__ import annotations
import uuid
import datetime
from fastapi import WebSocket, WebSocketDisconnect
from models import Experience, Project, Bullet
from store import ExperienceStore

# Metric keywords for heuristic checking
METRIC_KEYWORDS = [
    "increased", "decreased", "reduced", "improved", "grew", "saved", "generated",
    "led", "managed", "%", "$", "x ", "times", "within", "across", "over", "team of", "budget"
]

def _has_metric(text: str) -> bool:
    lower_text = text.lower()
    return any(keyword in lower_text for keyword in METRIC_KEYWORDS)

def _parse_raw_bullets(raw_context: str) -> list[Bullet]:
    bullets = []
    lines = raw_context.strip().split("\n")
    for line in lines:
        cleaned = line.strip()
        if cleaned.startswith("-") or cleaned.startswith("*"):
            cleaned = cleaned[1:].strip()
        if not cleaned:
            continue

        has_metric = _has_metric(cleaned)
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        bullets.append(Bullet(
            id=str(uuid.uuid4()),
            text=cleaned,
            has_metric=has_metric,
            source="user_raw",
            created_at=now
        ))
    return bullets

async def _send(websocket: WebSocket, msg_type: str, payload: dict) -> None:
    await websocket.send_json({"type": msg_type, "payload": payload})

async def _ask(websocket: WebSocket, question: str, required: bool = True) -> str | None:
    await _send(websocket, "question", {"question": question, "required": required})
    while True:
        try:
            data = await websocket.receive_json()
            if data.get("type") == "answer":
                answer = data.get("payload", {}).get("answer", "").strip()
                if not answer and required:
                    await _send(websocket, "error", {"message": "This field is required."})
                    continue
                return answer if answer else None
        except WebSocketDisconnect:
            raise

async def _ask_confirm(websocket: WebSocket, question: str) -> bool:
    await _send(websocket, "confirm", {"question": question})
    while True:
        try:
            data = await websocket.receive_json()
            if data.get("type") == "confirm_answer":
                return bool(data.get("payload", {}).get("answer"))
        except WebSocketDisconnect:
            raise

async def _probe_for_metrics(websocket: WebSocket, bullets: list[Bullet]) -> list[Bullet]:
    for bullet in bullets:
        if not bullet.has_metric:
            clarification = await _ask(
                websocket,
                f"This bullet lacks a metric: '{bullet.text}'.\nCan you add numbers (%, $, time, scale) or hit 'skip'?",
                required=False
            )
            if clarification and clarification.lower() != 'skip':
                bullet.text = clarification
                bullet.has_metric = _has_metric(clarification)
    return bullets

async def run_clarifier_experience(websocket: WebSocket, store: ExperienceStore) -> None:
    """Runs the interactive experience ingestion via WebSocket."""
    try:
        role = await _ask(websocket, "What was your role/title?")
        if not role: return
        company = await _ask(websocket, "What company did you work for?")
        if not company: return
        team = await _ask(websocket, "Team or division? (optional)", required=False)
        start_date = await _ask(websocket, "Start date? (e.g. 2022-03) (optional)", required=False)
        end_date = await _ask(websocket, "End date? (e.g. 2024-01, blank if current) (optional)", required=False)
        industry = await _ask(websocket, "Industry? (optional)", required=False)
        employment_type_raw = await _ask(websocket, "Employment type (full_time, contract, internship, part_time)?")

        emp_type = "full_time"
        if employment_type_raw in ["full_time", "contract", "internship", "part_time"]:
            emp_type = employment_type_raw

        raw_context = await _ask(websocket, "Paste your raw bullet points or narrative about what you did:")
        if not raw_context: return

        bullets = _parse_raw_bullets(raw_context)
        bullets = await _probe_for_metrics(websocket, bullets)

        skills_raw = await _ask(websocket, "What skills/tools did you use? (comma separated)", required=False)
        skills = [s.strip() for s in skills_raw.split(",")] if skills_raw else []

        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        exp = Experience(
            id=str(uuid.uuid4()),
            role=role,
            company=company,
            team_or_division=team,
            start_date=start_date,
            end_date=end_date,
            industry=industry,
            employment_type=emp_type, # type: ignore
            bullets=bullets,
            skills=skills,
            created_at=now,
            updated_at=now
        )

        await _send(websocket, "preview", {"entity": exp.model_dump()})
        confirm = await _ask_confirm(websocket, "Save this experience?")
        if confirm:
            store.save_experience(exp, triggered_by="user")
            await _send(websocket, "success", {"message": "Experience saved successfully."})
        else:
            await _send(websocket, "info", {"message": "Discarded."})

    except WebSocketDisconnect:
        # Client disconnected early, abort silently
        pass

async def run_clarifier_project(websocket: WebSocket, store: ExperienceStore) -> None:
    """Runs the interactive project ingestion via WebSocket."""
    try:
        name = await _ask(websocket, "Project name?")
        if not name: return
        description = await _ask(websocket, "One-paragraph description?")
        if not description: return
        url = await _ask(websocket, "Project URL? (optional)", required=False)
        status_raw = await _ask(websocket, "Status (active, completed, paused, archived)?")

        status = "completed"
        if status_raw in ["active", "completed", "paused", "archived"]:
            status = status_raw

        raw_context = await _ask(websocket, "Paste your raw bullet points or achievements:")
        if not raw_context: return

        bullets = _parse_raw_bullets(raw_context)
        bullets = await _probe_for_metrics(websocket, bullets)

        skills_raw = await _ask(websocket, "What skills/tools did you use? (comma separated)", required=False)
        skills = [s.strip() for s in skills_raw.split(",")] if skills_raw else []

        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        proj = Project(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            url=url,
            status=status, # type: ignore
            bullets=bullets,
            skills=skills,
            created_at=now,
            updated_at=now
        )

        await _send(websocket, "preview", {"entity": proj.model_dump()})
        confirm = await _ask_confirm(websocket, "Save this project?")
        if confirm:
            store.save_project(proj, triggered_by="user")
            await _send(websocket, "success", {"message": "Project saved successfully."})
        else:
            await _send(websocket, "info", {"message": "Discarded."})

    except WebSocketDisconnect:
        pass
