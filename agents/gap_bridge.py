from __future__ import annotations
import json
import uuid
import datetime
import time
import requests
from fastapi import WebSocket, WebSocketDisconnect

from models import AppConfig, GapDiscovery, JDSession, Bullet
from store import ExperienceStore

async def _send(websocket: WebSocket, msg_type: str, payload: dict) -> None:
    await websocket.send_json({"type": msg_type, "payload": payload})

async def _ask_confirm(websocket: WebSocket, question: str) -> bool:
    await _send(websocket, "confirm", {"question": question})
    while True:
        try:
            data = await websocket.receive_json()
            if data.get("type") == "confirm_answer":
                return bool(data.get("payload", {}).get("answer"))
        except WebSocketDisconnect:
            raise

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

def _llm_call(messages: list[dict], api_key: str, model: str, config: AppConfig) -> str:
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 600
    }

    retries = 0
    while retries <= config.llm_retry_max:
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except (requests.HTTPError, requests.Timeout, KeyError) as e:
            retries += 1
            if retries > config.llm_retry_max:
                raise RuntimeError(f"LLM call failed after {retries} attempts: {str(e)}")
            time.sleep(config.llm_wait_time)

    raise RuntimeError("LLM call failed")

def _extract_jd_requirements(jd_text: str, api_key: str, model: str, config: AppConfig) -> list[str]:
    system_prompt = "You extract distinct job requirements from a job description. Output ONLY a valid JSON array of strings (5-15 words each). Return max 5 requirements."
    user_prompt = jd_text[:4000]

    content = _llm_call([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ], api_key, model, config)

    try:
        # Strip codeblock markdown if model returned it
        if content.startswith("```json"):
            content = content[7:-3].strip()
        elif content.startswith("```"):
            content = content[3:-3].strip()

        reqs = json.loads(content)
        if isinstance(reqs, list):
            return reqs
        return []
    except json.JSONDecodeError:
        # Fallback to splitting by newlines if JSON parsing fails
        return [line.strip() for line in content.split("\n") if line.strip() and len(line.split()) >= 3]

def _generate_hypothesis(jd_requirement: str, entity_text: str, api_key: str, model: str, config: AppConfig) -> str:
    system_prompt = "You are a career coach. Explain to the user how their past experience connects to a job requirement. Speak directly to the user (second person). Be honest if it's a stretch. Keep it to 2-3 sentences."
    user_prompt = f"Job Requirement: {jd_requirement}\n\nUser Experience:\n{entity_text[:800]}"

    return _llm_call([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ], api_key, model, config)

def _generate_enriched_bullet(jd_requirement: str, entity_label: str, user_clarification: str, api_key: str, model: str, config: AppConfig) -> str:
    system_prompt = "You write resume bullets. Output ONLY the bullet text. Max 25 words. Start with a strong action verb. Do not use 'responsible for'. Include the exact metrics provided by the user, do not invent any."
    user_prompt = f"Requirement: {jd_requirement}\nEntity: {entity_label}\nUser Clarification: {user_clarification}"

    return _llm_call([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ], api_key, model, config)

async def _run_interactive_gap_bridge(
    websocket: WebSocket,
    store: ExperienceStore,
    jd_req: str,
    entity: dict,
    api_key: str,
    model: str,
    config: AppConfig
) -> GapDiscovery:
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    entity_obj = entity["entity"]
    entity_type = entity["entity_type"]
    label = entity_obj.role if entity_type == "experience" else entity_obj.name

    await _send(websocket, "info", {"message": f"Analyzing potential connection for requirement: '{jd_req}' with {label}..."})

    hypothesis = _generate_hypothesis(jd_req, entity_obj.all_text(), api_key, model, config)

    await _send(websocket, "info", {"message": hypothesis})

    confirmed = await _ask_confirm(websocket, "Does this sound right?")
    if not confirmed:
        return GapDiscovery(
            id=str(uuid.uuid4()),
            jd_requirement_snippet=jd_req,
            agent_hypothesis=hypothesis,
            suspected_entity_id=entity_obj.id,
            suspected_entity_type=entity_type,
            similarity_score=entity["score"],
            user_confirmed=False,
            created_at=now
        )

    clarification = await _ask(websocket, "Provide specific metrics or details about how you did this:")
    if not clarification:
        # Fallback if user cancels out
        return GapDiscovery(
            id=str(uuid.uuid4()),
            jd_requirement_snippet=jd_req,
            agent_hypothesis=hypothesis,
            suspected_entity_id=entity_obj.id,
            suspected_entity_type=entity_type,
            similarity_score=entity["score"],
            user_confirmed=True,
            user_clarification=None,
            created_at=now
        )

    await _send(websocket, "info", {"message": "Drafting bullet..."})
    bullet_text = _generate_enriched_bullet(jd_req, label, clarification, api_key, model, config)

    await _send(websocket, "info", {"message": f"Drafted bullet: {bullet_text}"})
    add_bullet = await _ask_confirm(websocket, "Add this bullet to your profile?")

    enriched_bullet = None
    if add_bullet:
        enriched_bullet = Bullet(
            id=str(uuid.uuid4()),
            text=bullet_text,
            has_metric=True, # Generated from clarification which we asked metrics for
            source="gap_enriched",
            created_at=datetime.datetime.now(datetime.timezone.utc).isoformat()
        )
        if entity_type == "experience":
            store.add_bullet_to_experience(entity_obj.id, enriched_bullet, "agent")
        else:
            store.add_bullet_to_project(entity_obj.id, enriched_bullet, "agent")

        await _send(websocket, "success", {"message": "Bullet added!"})

    return GapDiscovery(
        id=str(uuid.uuid4()),
        jd_requirement_snippet=jd_req,
        agent_hypothesis=hypothesis,
        suspected_entity_id=entity_obj.id,
        suspected_entity_type=entity_type, # type: ignore
        similarity_score=entity["score"],
        user_confirmed=True,
        user_clarification=clarification,
        enriched_bullet=enriched_bullet,
        created_at=now
    )

async def run_gap_bridge(
    websocket: WebSocket,
    jd_text: str,
    store: ExperienceStore,
    api_key: str,
    model: str,
    config: AppConfig
) -> None:
    try:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        session = JDSession(
            id=str(uuid.uuid4()),
            jd_raw=jd_text,
            created_at=now
        )

        await _send(websocket, "info", {"message": "Extracting job requirements..."})
        try:
            reqs = _extract_jd_requirements(jd_text, api_key, model, config)
        except RuntimeError as e:
            await _send(websocket, "error", {"message": f"Failed to extract requirements: {str(e)}"})
            return

        await _send(websocket, "info", {"message": f"Found {len(reqs)} requirements."})

        for req in reqs:
            results = store.semantic_search(req, top_k=3)
            if not results:
                continue

            top_result = results[0]
            if top_result["classification"] == "strong":
                session.strong_matches.append(top_result["entity"].id)
                await _send(websocket, "info", {"message": f"Strong match found for '{req}'."})

            elif top_result["classification"] == "potential":
                session.potential_matches.append(top_result["entity"].id)
                discovery = await _run_interactive_gap_bridge(
                    websocket, store, req, top_result, api_key, model, config
                )
                session.gap_discoveries.append(discovery)

            else:
                await _send(websocket, "info", {"message": f"True gap identified for '{req}'."})

        store.save_jd_session(session)
        await _send(websocket, "success", {"message": "JD Alignment complete!"})

    except WebSocketDisconnect:
        pass
