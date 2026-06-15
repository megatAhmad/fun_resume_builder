# CLAUDE.md — Resume Lifecycle Repository

This file is read by Claude Code before any operation on this codebase.
Follow every rule here exactly. When in doubt, read the relevant source file before acting.

---

## What this project is

A local-first, agentic system for managing career data and generating targeted resumes.
It is a **personal tool — not a service**. There is one user, one SQLite database, no auth layer.
This project uses a **FastAPI Backend** and a **React (Vite) Frontend**.

The system has three active subsystems:
- `store.py` — persistent SQLite store with local embeddings
- `agents/clarifier.py` — interactive agent for ingesting new experience (WebSocket)
- `agents/gap_bridge.py` — JD alignment and transferable-experience detection (WebSocket)

The render engine (python-docx / Jinja2 output) and AutoGen orchestration layer
are **planned but not yet built**. Do not add stubs for them without being asked.

---

## Commands to know

```bash
# Install dependencies
pip install -r requirements.txt
cd frontend && npm install

# Start Backend
uvicorn main:app --reload

# Start Frontend
cd frontend && npm run dev
```

Required environment variables:
```bash
export OPENROUTER_API_KEY=sk-or-...   # required for align-jd
export RESUME_DB_PATH=resume.db        # optional, default: resume.db
export RESUME_MODEL=anthropic/claude-3-haiku  # optional
```

---

## Repository layout

```
resume_system/
├── CLAUDE.md               ← you are here
├── SPEC.md                 ← full technical specification
├── README.md               ← end-user setup guide
├── requirements.txt
├── main.py                 ← FastAPI entry point
├── models.py               ← all Pydantic schemas (source of truth for data shape)
├── store.py                ← ExperienceStore class, SQLite + embedding CRUD
├── embeddings.py           ← embed(), cosine_similarity(), threshold constants
├── agents/
│   ├── clarifier.py        ← ingestion wizard, metric probing
│   └── gap_bridge.py       ← JD requirement extraction, gap detection, LLM calls
└── frontend/               ← React + Vite frontend
```

No other files exist yet. Do not create files outside this structure without being asked.

---

## Inviolable rules — read before every write

### 1. Never hard-delete from the store
All writes to `experiences` and `projects` must go through `ExperienceStore.save_experience()`
or `ExperienceStore.save_project()`. These methods set `is_active=0` and bump `version`.
Direct `DELETE FROM` SQL is forbidden. Use `is_active = False` + save.

### 2. All agent writes require prior user confirmation
The gap bridge writes a bullet only after two explicit `ask_confirm()` calls return `True`.
If you add any new agent that writes to the store, the same pattern is required:
show what will be written, get confirmation, then write. Never write silently.

### 3. Embeddings must be regenerated on every entity update
Any time a bullet is added or an entity field changes, call `embed(entity.all_text())`
and persist the new blob. The `save_experience()` and `save_project()` methods do this
automatically — always route updates through them, never raw SQL UPDATE.

### 4. LLM calls only in `agents/gap_bridge.py`
All OpenRouter API calls live in `_llm_call()` inside `gap_bridge.py`.
Do not add LLM calls to `store.py`, `models.py`, `embeddings.py`, or `main.py`.
If a new agent needs LLM access, create a new file under `agents/`.

### 5. No sensitive data in LLM prompts
Before adding any new LLM prompt, check what personal data it includes.
Only the following are acceptable to send to OpenRouter:
- Extracted JD requirement snippets (public text)
- `entity.all_text()` output (bullets and skills — already sanitized text)
- User's typed clarification response

Never include: company names concatenated with financial figures, dates of employment
combined with salary info, raw personal PII, or anything the user has not explicitly
provided as career narrative.

### 6. `models.py` is the schema contract
When changing any model, update `SPEC.md § Data Models` in the same commit.
Never add fields to a model that are not documented in the spec.
If the spec doesn't have it, discuss it with the user first.

### 7. Audit every write
Every `save_experience()` and `save_project()` call automatically writes to `audit_log`.
Do not bypass this. If you add a new entity type, implement the same audit pattern
in `store.py` before exposing save methods for it.

---

## Code conventions

### Python style
- Python 3.11+. Use `from __future__ import annotations` in every file.
- Pydantic v2 only. Use `.model_dump_json()` and `.model_validate_json()`, never `.json()` or `.parse_raw()`.
- Type hints on all function signatures. No bare `dict` or `list` — always parameterized.
- `Optional[X]` not `X | None` for consistency with the existing codebase.
- Line length: 100 characters.

### Naming
- Store methods: `save_*`, `get_*`, `list_*`, `add_bullet_to_*`
- Agent functions: verb-first, snake_case (`run_gap_bridge`, `ingest_experience`)
- Private helpers: underscore prefix (`_llm_call`, `_parse_raw_bullets`)
- Constants: UPPER_SNAKE (`STRONG_MATCH_THRESHOLD`, `GAP_BRIDGE_THRESHOLD`)

### Error handling
- Catch `requests.HTTPError` specifically around every `_llm_call()` invocation.
- Never silently swallow exceptions in store writes — let them propagate.
- `KeyboardInterrupt` is the canonical signal that a user cancelled an interactive wizard.
  `main.py` catches it at the top level; agent functions may raise it to cancel.

### Tests (when adding)
- Place under `tests/`. Mirror the module structure: `tests/test_store.py`, etc.
- Use a temp SQLite file (`tmp_path` fixture) — never the real `resume.db`.
- Mock `_llm_call` in all gap bridge tests; never make real API calls in tests.
- Do not add a test framework without asking — `pytest` is the assumed default.

---

## Similarity thresholds — do not change without updating SPEC.md

Defined in `embeddings.py`:

| Constant | Value | Meaning |
|---|---|---|
| `STRONG_MATCH_THRESHOLD` | `0.72` | Direct match — used as-is |
| `GAP_BRIDGE_THRESHOLD` | `0.42` | Potential transferable — triggers interactive loop |
| below `GAP_BRIDGE_THRESHOLD` | — | True skill gap — logged, surfaced to user |

If you change these values, update the spec and leave a comment explaining why.

---

## What is not built yet (do not implement without explicit instruction)

- Resume render engine (python-docx / Jinja2 / WeasyPrint)
- Raw Context Uplift agent (transforms raw notes into polished bullets via LLM)
- AutoGen or LangGraph orchestration layer
- Career Narrative Branching (generalist vs. strategic track)
- Semantic JD Alignment output formatter (post-gap-bridge resume assembly)
- Skills Gap Analyzer (diff JD skills vs. profile skills)
- Application Tracker (log of submissions + outcomes)
- Cover letter generation
- LinkedIn data import parser

---

## Dependency policy

Do not add any new dependency without asking. Current allowed set:

| Package | Purpose |
|---|---|
| `pydantic>=2.0` | Data models and validation |
| `sentence-transformers>=2.7.0` | Local embedding generation |
| `numpy>=1.26` | Vector math |
| `rich>=13.0` | Terminal formatting |
| `requests>=2.31` | OpenRouter API calls |
| `sqlite3` | stdlib, no install needed |

---

## When you are unsure

1. Read the relevant source file before changing it.
2. Check `SPEC.md` for the intended design.
3. If the spec and the code disagree, flag it — do not silently pick one.
4. If the user's instruction would violate an inviolable rule above, say so explicitly
   before proceeding, and ask for clarification.
