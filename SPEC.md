# SPEC.md — Resume Lifecycle Repository
## Technical Specification v0.2

**Status:** In development — Experience Store module complete. Render engine and orchestration layer planned.
**Scope:** Personal use only. Single user, local-first, no network services except OpenRouter for LLM inference.
**Last updated:** 2025

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture](#2-architecture)
3. [Data Models](#3-data-models)
4. [SQLite Schema](#4-sqlite-schema)
5. [Subsystem Specifications](#5-subsystem-specifications)
   - 5.1 Experience Store
   - 5.2 Clarification Agent
   - 5.3 Gap Bridge Agent
6. [Embedding Strategy](#6-embedding-strategy)
7. [LLM Interface](#7-llm-interface)
8. [Operational Guardrails](#8-operational-guardrails)
9. [CLI Reference](#9-cli-reference)
10. [Planned Features (Not Yet Built)](#10-planned-features-not-yet-built)
11. [Design Decisions Log](#11-design-decisions-log)

---

## 1. System Overview

The Resume Lifecycle Repository is a local agentic system that:
- Maintains a structured, versioned, single-source-of-truth for all career data.
- Ingests raw, informal professional updates and extracts structured bullets with metrics.
- Performs semantic alignment between a job description and the stored profile.
- Detects transferable experience not directly matched by a JD requirement and asks the user to confirm and enrich it.
- Compiles targeted resumes via deterministic document templates (planned).

**Non-goals:**
- Multi-user support
- Cloud storage or sync
- Real-time data (no web scraping)
- Automated job applications
- Replacing human judgment on career decisions

---

## 2. Architecture

### Current state (v0.2)

```
┌──────────────────────────────────────────────────────────┐
│                        CLI (main.py)                      │
│         add-experience │ add-project │ list │ align-jd    │
└────────────┬───────────────────────────────┬─────────────┘
             │                               │
             ▼                               ▼
┌─────────────────────┐          ┌─────────────────────────┐
│  Clarification Agent │          │    Gap Bridge Agent      │
│  (agents/clarifier) │          │  (agents/gap_bridge.py)  │
│                     │          │                          │
│ • Guided ingestion  │          │ • JD requirement extract │
│ • Metric probing    │          │ • Semantic ranking       │
│ • Inline ask()      │          │ • Hypothesis generation  │
└────────┬────────────┘          │ • Interactive confirm    │
         │                       │ • Bullet generation      │
         │ Experience / Project  └────────────┬────────────┘
         │                                    │ enriched bullets
         ▼                                    ▼
┌──────────────────────────────────────────────────────────┐
│                    Experience Store                       │
│                      (store.py)                          │
│                                                          │
│  SQLite tables: experiences │ projects │ jd_sessions     │
│                             │ audit_log                  │
│  Embeddings: stored as BLOB │ queried via cosine dot     │
└──────────────────────────────────────────────────────────┘
             │
             ▼
┌──────────────────────┐
│  embeddings.py        │
│  all-MiniLM-L6-v2    │  ← 100% local, no external calls
│  384-dim float32      │
└──────────────────────┘
```

### Planned state (v1.0)

```
                    ┌──────────────────────┐
                    │  AutoGen / LangGraph  │
                    │  Orchestration Layer  │
                    └──────┬───────────────┘
                           │ routes to
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
   Clarification     Gap Bridge      Raw Context
      Agent            Agent         Uplift Agent
          │                ▼
          └──────► Experience Store ◄──── JD Alignment
                           │
                           ▼
                   ┌───────────────┐
                   │ Render Engine  │
                   │ python-docx   │
                   │ Jinja2+HTML   │
                   └───────────────┘
```

---

## 3. Data Models

All models are defined in `models.py` using Pydantic v2.
All entities use **append-only versioning**: `is_active` flag + `version` integer.
Hard deletes are never performed.

---

### 3.1 Bullet

The atomic unit of career evidence. Always owned by an `Experience` or `Project`.

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | `str` (UUID4) | auto | Primary key |
| `text` | `str` | yes | Full bullet text |
| `skills_demonstrated` | `list[str]` | no | Skill tags derived from this bullet |
| `has_metric` | `bool` | auto | True if text contains a quantified outcome |
| `source` | `Literal` | auto | `user_raw` / `agent_uplifted` / `gap_enriched` |
| `is_active` | `bool` | auto | False = soft-deleted |
| `created_at` | `str` (ISO) | auto | UTC timestamp |

**Invariant:** A bullet with `source = gap_enriched` must have a corresponding `GapDiscovery`
record with `user_confirmed = True` and a non-null `enriched_bullet`. The agent must never
write a `gap_enriched` bullet without user confirmation.

---

### 3.2 Experience

A professional role at a company.

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | `str` (UUID4) | auto | Primary key |
| `role` | `str` | yes | Job title |
| `company` | `str` | yes | Employer name |
| `team_or_division` | `Optional[str]` | no | Sub-org context |
| `start_date` | `Optional[str]` | no | ISO month string, e.g. `"2022-03"` |
| `end_date` | `Optional[str]` | no | `None` = current role |
| `bullets` | `list[Bullet]` | no | Achievement bullets |
| `skills` | `list[str]` | no | Flat list of skill/tool names |
| `team_size` | `Optional[int]` | no | Approximate team size |
| `direct_reports` | `Optional[int]` | no | Number of direct reports |
| `industry` | `Optional[str]` | no | Industry vertical |
| `employment_type` | `Literal` | auto | `full_time` / `contract` / `internship` / `part_time` |
| `is_active` | `bool` | auto | False = soft-deleted |
| `version` | `int` | auto | Incremented on every save |
| `created_at` | `str` (ISO) | auto | |
| `updated_at` | `str` (ISO) | auto | Updated on every save |

**`all_text()` method:** Returns a flat concatenation of role, company, team, active bullet texts,
skills, and industry. This is the string that gets embedded and stored as the BLOB.
Any change to bullets or skills must trigger a re-embed via `save_experience()`.

---

### 3.3 Project

A personal, open-source, academic, or side project.

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | `str` (UUID4) | auto | Primary key |
| `name` | `str` | yes | Project name |
| `description` | `str` | yes | One-paragraph description |
| `bullets` | `list[Bullet]` | no | Key achievements |
| `skills` | `list[str]` | no | Technologies / tools used |
| `url` | `Optional[str]` | no | Repo or live URL |
| `status` | `Literal` | auto | `active` / `completed` / `paused` / `archived` |
| `is_active` | `bool` | auto | |
| `version` | `int` | auto | |
| `created_at` | `str` (ISO) | auto | |
| `updated_at` | `str` (ISO) | auto | |

---

### 3.4 GapDiscovery

One instance of the Gap Bridge detecting a transferable experience for a JD requirement.
Immutable after creation — the interaction is recorded as-is regardless of outcome.

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | `str` (UUID4) | auto | |
| `jd_requirement_snippet` | `str` | yes | The JD text that triggered this |
| `agent_hypothesis` | `str` | yes | The agent's stated assumption, shown to user |
| `suspected_entity_id` | `str` | yes | UUID of the Experience or Project that triggered the match |
| `suspected_entity_type` | `Literal` | yes | `"experience"` or `"project"` |
| `similarity_score` | `float` | yes | Cosine similarity score at time of detection |
| `user_confirmed` | `Optional[bool]` | no | `None` = not yet asked; `True`/`False` = outcome |
| `user_clarification` | `Optional[str]` | no | Raw typed response from user |
| `enriched_bullet` | `Optional[Bullet]` | no | Generated bullet if confirmed and provided |
| `created_at` | `str` (ISO) | auto | |

---

### 3.5 JDSession

One complete JD alignment run. Created each time `align-jd` is executed.

| Field | Type | Description |
|---|---|---|
| `id` | `str` (UUID4) | |
| `jd_raw` | `str` | Full original JD text as pasted by user |
| `jd_role_title` | `Optional[str]` | Extracted role title (future) |
| `jd_company` | `Optional[str]` | Extracted company name (future) |
| `strong_matches` | `list[str]` | Entity IDs with similarity ≥ 0.72 |
| `potential_matches` | `list[str]` | Entity IDs with similarity 0.42–0.72 |
| `gap_discoveries` | `list[GapDiscovery]` | All gap bridge interactions in this session |
| `created_at` | `str` (ISO) | |

---

### 3.6 AuditEntry

Append-only log of every store mutation.

| Field | Type | Description |
|---|---|---|
| `entity_type` | `Literal` | `"experience"` / `"project"` / `"bullet"` |
| `entity_id` | `str` | UUID of the entity |
| `action` | `Literal` | `created` / `updated` / `deactivated` / `bullet_added` / `gap_enriched` |
| `before_snapshot` | `Optional[str]` | JSON of prior state, null on creation |
| `after_snapshot` | `str` | JSON of new state |
| `triggered_by` | `Literal` | `"user"` or `"agent"` |
| `created_at` | `str` (ISO) | |

---

## 4. SQLite Schema

Database file: `resume.db` (path overridable via `RESUME_DB_PATH` env var).

```sql
CREATE TABLE IF NOT EXISTS experiences (
    id          TEXT PRIMARY KEY,
    data        TEXT NOT NULL,       -- Full JSON serialization of Experience model
    embedding   BLOB,                -- Serialized numpy float32 array (1536 bytes for 384-dim)
    is_active   INTEGER DEFAULT 1,
    version     INTEGER DEFAULT 1,
    created_at  TEXT,
    updated_at  TEXT
);

CREATE TABLE IF NOT EXISTS projects (
    id          TEXT PRIMARY KEY,
    data        TEXT NOT NULL,
    embedding   BLOB,
    is_active   INTEGER DEFAULT 1,
    version     INTEGER DEFAULT 1,
    created_at  TEXT,
    updated_at  TEXT
);

CREATE TABLE IF NOT EXISTS jd_sessions (
    id          TEXT PRIMARY KEY,
    data        TEXT NOT NULL,       -- Full JSON serialization of JDSession model
    created_at  TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    data        TEXT NOT NULL,       -- Full JSON serialization of AuditEntry model
    created_at  TEXT
);
```

**Schema notes:**
- `data` columns store the full Pydantic model as JSON. This is intentional: it keeps
  the SQLite schema stable even as model fields evolve. The model is the schema contract.
- `embedding` is stored redundantly alongside `data` for query performance — avoids
  deserializing the JSON just to compute similarities.
- `is_active` and `version` are denormalized from `data` for fast indexed queries.
- No foreign keys are enforced at the SQLite level. Referential integrity is enforced
  in application code (Pydantic + `ExperienceStore` methods).

---

## 5. Subsystem Specifications

### 5.1 Experience Store (`store.py`)

**Class:** `ExperienceStore`

**Responsibilities:**
- All SQLite read/write operations
- Embedding generation on every save
- Semantic search across all active entities
- Audit logging on every write
- Version increment on update

**Key methods:**

| Method | Description |
|---|---|
| `save_experience(exp, triggered_by)` | Upsert + re-embed + audit |
| `get_experience(exp_id)` | Fetch by UUID |
| `list_experiences(active_only)` | All experiences, ordered by `created_at DESC` |
| `save_project(proj, triggered_by)` | Upsert + re-embed + audit |
| `get_project(proj_id)` | Fetch by UUID |
| `list_projects(active_only)` | All projects |
| `semantic_search(query_text, top_k, active_only)` | Ranked similarity search across all entities |
| `save_jd_session(session)` | Upsert JDSession |
| `list_jd_sessions()` | All sessions, desc |
| `add_bullet_to_experience(exp_id, bullet, triggered_by)` | Append bullet + re-embed + audit |
| `add_bullet_to_project(proj_id, bullet, triggered_by)` | Append bullet + re-embed + audit |

**`semantic_search()` return format:**

```python
[
    {
        "entity": Experience | Project,
        "entity_type": "experience" | "project",
        "score": float,           # cosine similarity, 0.0–1.0
        "classification": "strong" | "potential" | "gap"
    },
    ...
]
```

Results are sorted descending by score. The caller (Gap Bridge) uses `classification`
to route each result to the correct handling path.

**Write ordering contract:**
1. Compute new embedding
2. Write audit entry (before state)
3. Write entity (upsert)
4. `conn.commit()`

Steps 2–4 are in the same implicit transaction. If the process dies between 1 and 4,
the database is unchanged. Audit entries are never committed without the corresponding entity write.

---

### 5.2 Clarification Agent (`agents/clarifier.py`)

**Responsibilities:**
- Walk the user through structured experience/project ingestion (`ingest_experience`, `ingest_project`)
- Probe for missing metrics on every bullet lacking a quantified outcome
- Provide `request_clarification()` as a blocking prompt for other agents to call
- Never call the LLM — all prompts are deterministic CLI questions

**Ingestion flow for `ingest_experience()`:**

```
1. Collect required fields: role, company
2. Collect optional fields: team, dates, industry, employment_type, team_size, direct_reports
3. Collect raw_context via ask_multiline()
4. _parse_raw_bullets(raw_context) → list[Bullet]
5. _probe_for_metrics(bullets) → list[Bullet]  [one ask per metric-less bullet]
6. Collect skills (comma-separated)
7. Build Experience object
8. _preview_experience(exp) → rich panel
9. ask_confirm("Save?") → if False, raise KeyboardInterrupt
10. Return Experience (caller saves to store)
```

**Metric detection heuristic (`_has_metric`):**

Checks for the presence of any of these strings (case-insensitive) in bullet text:
`increased`, `decreased`, `reduced`, `improved`, `grew`, `saved`, `generated`, `led`,
`managed`, `%`, `$`, `x `, `times`, `within`, `across`, `over`, `team of`, `budget`

This is a keyword heuristic, not NLP. It will produce false positives (e.g. "led to confusion")
and false negatives (e.g. "4x throughput improvement" without the word "improved"). This is
intentional for v0.2 — the prompt asks the user to verify. An LLM-based classifier is planned
for v1.0 (Raw Context Uplift Agent).

**`request_clarification(context, question)` contract:**
- Displays both context and question in a rich Panel
- Blocks until user types a response
- Returns the raw string — caller is responsible for interpreting it
- Never modifies the store — purely input collection

---

### 5.3 Gap Bridge Agent (`agents/gap_bridge.py`)

**Responsibilities:**
- Extract discrete skill/experience requirements from a JD via LLM
- Rank each requirement against all stored entities via semantic search
- Route each result to: silent record (strong) / interactive bridge (potential) / gap log (none)
- Generate a human-readable hypothesis connecting a JD requirement to existing experience
- Collect user confirmation and clarification details
- Generate a polished resume bullet from the clarification
- Write the bullet to the store (only after two explicit confirmations)
- Persist the complete JDSession including all GapDiscovery records

**`run_gap_bridge()` pipeline:**

```
Input: jd_text (str), store, openrouter_api_key, model

A. _extract_jd_requirements(jd_text) → list[str]
   └── LLM call: parse JD → top-k requirement phrases

B. For each requirement:
   └── store.semantic_search(requirement, top_k=3)
       ├── top score ≥ 0.72 (strong):
       │   └── session.strong_matches.append(entity.id)
       │       [log to console, no user interaction]
       │
       ├── top score 0.42–0.72 (potential):
       │   └── _run_interactive_gap_bridge(...)
       │       ├── _generate_hypothesis(requirement, entity) [LLM call]
       │       ├── Display hypothesis in rich Panel
       │       ├── ask_confirm("Does this sound right?")
       │       │   └── No → GapDiscovery(confirmed=False), return
       │       ├── request_clarification(context, question)
       │       ├── _generate_enriched_bullet(jd_req, entity, clarification) [LLM call]
       │       ├── Display bullet to user
       │       ├── ask_confirm("Add this bullet?")
       │       │   └── No → GapDiscovery(confirmed=True, no bullet), return
       │       └── store.add_bullet_to_experience/project(bullet)
       │           └── GapDiscovery(confirmed=True, enriched_bullet=bullet)
       │
       └── top score < 0.42 (gap):
           └── Log as true skill gap [no user interaction]

C. store.save_jd_session(session)
D. _print_session_summary(session)
```

**LLM prompt contracts:**

`_extract_jd_requirements(jd_text)`:
- Input: first 4000 characters of JD text
- Output: JSON array of up to `top_k` short requirement phrases (5–15 words each)
- If JSON parsing fails: fallback to newline-split

`_generate_hypothesis(jd_requirement, entity)`:
- Input: requirement snippet + `entity.all_text()[:800]`
- Output: 2–3 sentence plain text connecting the entity to the requirement
- Persona: career coach, second person ("Your work on X suggests...")
- Honest framing: if the connection is a stretch, the prompt instructs the model to say so

`_generate_enriched_bullet(jd_requirement, entity_label, user_clarification)`:
- Input: requirement, entity name, user's raw clarification
- Output: single resume bullet, max 25 words
- Constraints enforced in prompt: strong action verb, no "responsible for",
  exact metrics only (never invented), no preamble or quotes in output

---

## 6. Embedding Strategy

**Model:** `sentence-transformers/all-MiniLM-L6-v2`
- Dimensionality: 384
- Storage per entity: 384 × 4 bytes = 1,536 bytes BLOB
- Normalization: unit-normalized at generation time (`normalize_embeddings=True`)
- Similarity metric: dot product (equivalent to cosine on normalized vectors)
- Model loading: lazy, cached via `@lru_cache(maxsize=1)`, ~90MB on first download

**What gets embedded:** `entity.all_text()` — role/name, company/description, all active bullet texts,
all skill tags, industry. This concatenation is regenerated and re-embedded on every save.

**What does NOT get embedded individually:**
- Single bullets (they contribute to the parent entity's embedding)
- JD requirement phrases (these are generated at query time, not stored)
- Raw user input before it is parsed into structured bullets

**Privacy:** All embedding computation is local. The sentence-transformers model runs
entirely in-process. No text is transmitted externally for embedding.

**Similarity thresholds (defined in `embeddings.py`):**

| Constant | Value | Rationale |
|---|---|---|
| `STRONG_MATCH_THRESHOLD` | `0.72` | At this score, the semantic overlap is high enough to treat as a direct match for MiniLM. Empirically: roles with shared domain vocabulary typically score 0.75–0.90. |
| `GAP_BRIDGE_THRESHOLD` | `0.42` | Below this, the connection is too weak to present a credible hypothesis. Above it, there is enough shared vocabulary to suggest a potential transfer. |

These values were chosen for MiniLM-L6-v2 specifically. They are not universal.
If the model is changed, re-calibrate with real data before deploying.

---

## 7. LLM Interface

**Gateway:** OpenRouter (`https://openrouter.ai/api/v1/chat/completions`)
**Default model:** `anthropic/claude-3-haiku` (via `RESUME_MODEL` env var)
**Auth:** Bearer token from `OPENROUTER_API_KEY` env var

**All LLM calls are in `agents/gap_bridge.py._llm_call()`.**

Request shape:
```json
{
  "model": "<model>",
  "messages": [
    {"role": "system", "content": "<optional system prompt>"},
    {"role": "user",   "content": "<prompt>"}
  ],
  "max_tokens": 600
}
```

Error handling:
- `requests.HTTPError` is raised on 4xx/5xx
- Timeout: 30 seconds
- No retry logic in v0.2 — caller handles failure

**Data transmitted to OpenRouter per call:**

| Call | Data sent |
|---|---|
| `_extract_jd_requirements` | First 4000 chars of JD (public text) |
| `_generate_hypothesis` | JD snippet + `entity.all_text()[:800]` |
| `_generate_enriched_bullet` | JD snippet + entity label + user's typed clarification |

**Data never transmitted:**
- Full raw JD beyond 4000 chars
- SQLite database contents
- Company names combined with employment dates or salary info
- Anything the user has not explicitly provided as narrative

---

## 8. Operational Guardrails

### 8.1 Append-only writes
`ExperienceStore` never issues `DELETE` SQL. Deactivation sets `is_active = 0`.
Version history is preserved in `data` JSON + `audit_log`.

### 8.2 Agent write gates
The Gap Bridge agent enforces two sequential `ask_confirm()` gates before any store write:
1. "Does the hypothesis sound right?" — confirms the agent's interpretation
2. "Add this bullet to your profile?" — confirms the specific generated text

Passing gate 1 does not imply gate 2. The user can reject the generated bullet even after
confirming the hypothesis and providing clarification.

### 8.3 State conflict prevention
`save_experience()` checks for an existing row before writing.
On update: reads current `version`, writes `version + 1`.
On insert: writes `version = 1`.
There is no optimistic locking because this is a single-user, single-process system.

### 8.4 LLM scope boundary
Agents produce text. The store writes structured data.
No LLM call ever directly mutates the database. The pipeline is always:
`LLM produces text → user confirms → Python code writes to SQLite`.

### 8.5 Privacy data classification

| Data class | Examples | Handling |
|---|---|---|
| Public narrative | Bullet text, skill names, project descriptions | May be sent to OpenRouter |
| Contextual metadata | Role, company, industry | Sent as entity label only |
| Personal identifiers | Name, address, phone | Never enter the system |
| Sensitive professional | Salary, equity, NDA-covered details | Never enter the system — user must sanitize |

---

## 9. CLI Reference

Entry point: `python main.py <command>`

| Command | Description | Key flags |
|---|---|---|
| `add-experience` | Interactive wizard to ingest a work experience | none |
| `add-project` | Interactive wizard to ingest a project | none |
| `list` | Display all active experiences and projects | none |
| `align-jd` | Run JD alignment + gap bridge | `--jd-file PATH`, `--jd-text STR` |
| `history` | Print last 50 audit log entries | none |

Environment variables:

| Variable | Default | Required |
|---|---|---|
| `OPENROUTER_API_KEY` | — | Yes, for `align-jd` |
| `RESUME_DB_PATH` | `resume.db` | No |
| `RESUME_MODEL` | `anthropic/claude-3-haiku` | No |

---

## 10. Planned Features (Not Yet Built)

These are specified here for design continuity but have no implementation yet.
Do not begin implementation without explicit instruction.

### 10.1 Raw Context Uplift Agent
**Purpose:** Transform informal user notes into polished, metrics-driven bullets via LLM,
replacing the current keyword-heuristic metric check in the Clarification Agent.

**Input:** Raw text block from user (same as current `ask_multiline()` output)
**Output:** list of uplifted `Bullet` objects with `source = "agent_uplifted"`
**LLM prompt contract:** Will include a system prompt with bullet formatting rules
(STAR structure, action verb first, max 25 words, no "responsible for").
**Requires user review before store write.** User sees each bullet before it is saved.

### 10.2 Render Engine
**Purpose:** Compile a targeted resume from matched profile nodes into a deterministic
document file, bypassing LLM for all layout decisions.

**Output targets:**
- `python-docx` for `.docx` (primary)
- Jinja2 + WeasyPrint for `.pdf` (secondary)
- Jinja2 + plain HTML for `.txt` ATS mode (tertiary)

**Key constraint:** The render engine receives only finalized text strings.
It performs zero LLM calls. All formatting is template-driven.

**Input:** An ordered list of `Bullet` objects (selected by JD alignment), structured
into sections by entity type and date order.

### 10.3 Career Narrative Branching
**Purpose:** Allow distinct thematic "tracks" of bullet selection from the same profile.
Example tracks: `generalist_execution`, `strategic_management`, `technical_ic`.

**Implementation:** A `track` tag on each `Bullet` or a separate `BulletTrackMap` entity.
The render engine takes a `track` parameter and filters bullets accordingly.

### 10.4 AutoGen / LangGraph Orchestration
**Purpose:** Wire subsystems into a coherent pipeline callable as a single command.
**Current preference:** LangGraph over AutoGen for this workflow pattern
(directed pipeline, not debate-style multi-agent). See Design Decisions Log.

### 10.5 Skills Gap Analyzer
**Purpose:** After JD alignment, diff the JD's required skill vocabulary against
all skills stored in the profile. Surface skills present in the JD but absent from profile.

**Implementation:** Requires skill extraction from JD (reuse `_extract_jd_requirements`
with a skill-focused prompt) + set intersection against `Experience.skills` + `Project.skills`.

### 10.6 Application Tracker
**Purpose:** Log each job application with the JDSession ID, resume version used,
application date, and outcome.

**Schema (planned):**
```
applications: id, jd_session_id, resume_version_path, company, role,
              status, applied_date, last_updated
```

### 10.7 LinkedIn Export Parser
**Purpose:** Bootstrap the experience store from a LinkedIn data export.
**Input:** The `Positions.csv` file from LinkedIn's data export.
**Output:** Draft `Experience` objects, surfaced for user review before saving.

---

## 11. Design Decisions Log

### Why SQLite instead of Neo4j (for v0.2)
Neo4j provides genuine value for graph traversal queries (e.g. "which skills connect
to which outcomes across multiple roles"). However, for a personal tool with fewer than
~100 entities, the JVM overhead, Cypher query complexity, and daemon management cost
outweigh the benefit. SQLite with JSON columns and local embedding search covers
all retrieval needs in v0.2. The interface design does not preclude a future migration.

### Why LangGraph is preferred over AutoGen for the orchestration layer
AutoGen's actor model excels when agents need to negotiate or debate.
This system's pipeline is directed: clarify → store → align → bridge → render.
LangGraph's state machine model maps more naturally to this shape and makes
state transitions explicit and testable. AutoGen remains viable if the future
multi-agent design requires genuine agent-to-agent negotiation.

### Why embeddings are at the entity level, not the bullet level
Bullet-level embeddings would allow finer-grained JD matching but would require
storing and querying many more vectors (one per bullet × N experiences).
For v0.2, entity-level embeddings are sufficient: the Gap Bridge retrieves the
entity, and the LLM hypothesis generation reads the full entity text to reason
about specific bullets. Bullet-level search is a planned enhancement for v1.0
and will require a new `bullet_embeddings` table.

### Why two confirmation gates in the Gap Bridge
One gate ("does the hypothesis sound right?") filters bad interpretations before
the user spends time typing clarification. The second gate ("add this bullet?") lets
the user reject a generated bullet that is technically correct but phrased poorly.
Merging them into one gate would either force premature commitment or waste user
effort on a hypothesis they already doubt.

### Why `all_text()` concatenates rather than weighs
A weighted embedding (e.g. role title gets 3× weight) would require a custom pooling
strategy incompatible with sentence-transformers' standard encoding. Concatenation is
simpler, reproducible, and easy to audit. Weights can be explored in v1.0 by
repeating high-signal fields in the concatenation string.
