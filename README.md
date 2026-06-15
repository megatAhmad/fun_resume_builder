# Resume Lifecycle Repository

A local-first, agentic system for managing career data and generating targeted resumes based on job descriptions.

This repository implements the v0.2 specification featuring a **FastAPI Backend** and a **React (Vite) Frontend** communicating via WebSockets and REST APIs.

## Features

- **Experience Store**: Persistent local SQLite storage with built-in semantic search using `sentence-transformers`.
- **Interactive Agents**:
  - *Clarifier Agent*: An interactive WebSocket wizard that ingests new work experiences and automatically probes for missing metrics.
  - *Gap Bridge Agent*: Uses LLMs to extract requirements from a Job Description (JD), detect transferable experiences, and interactively help you draft enriched resume bullets tailored to the role.
- **Configurable**: Easily manage LLM retry behavior and wait times directly from the UI.
- **Local First**: All data is stored locally in `resume.db`. The only network requests made are to the OpenRouter API for LLM reasoning.

## Getting Started

Please see the [GETTING_STARTED.md](./GETTING_STARTED.md) guide for detailed setup, installation, and usage instructions.

## Technical Stack

- **Backend**: Python 3.12, FastAPI, SQLite, Pydantic v2
- **Frontend**: React, TypeScript, Vite, Tailwind CSS
- **AI/ML**: `sentence-transformers/all-MiniLM-L6-v2` (Local Embeddings), OpenRouter API (LLM)
- **Testing**: `pytest`

## Architecture overview

The system operates strictly locally except for LLM inference:

1. The **React UI** communicates with the **FastAPI Backend** over REST (for CRUD operations) and WebSockets (for interactive agents).
2. The **Experience Store** handles all database and embedding operations, including maintaining a robust audit log and append-only versioning.
3. The **Agents** manage stateful, multi-turn interactions with the user to refine career data without writing directly to the database without explicit user confirmation.
