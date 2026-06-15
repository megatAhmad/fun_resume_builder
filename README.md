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

## Architecture & How It Works

The system is designed as a single-user, local-first application to ensure your career data remains private and under your control. The architecture is composed of four primary layers:

### 1. Frontend (React / Vite)
The user interface is built with React, TypeScript, and Tailwind CSS. It communicates with the backend via two protocols:
- **REST APIs**: Used for fetching standard data like the list of saved experiences, projects, and application settings.
- **WebSockets**: Used for real-time, interactive agent workflows. When you add a new experience or align a job description, the React app opens a WebSocket connection. This allows the backend agents to "block" and ask you clarifying questions, stream responses, and request confirmations in real-time.

### 2. Backend API (FastAPI)
The FastAPI layer serves as the entry point for all operations. It exposes the REST endpoints and mounts the WebSocket handlers. The backend runs completely locally on your machine.

### 3. Agentic Layer
This system features two core "Agents" written in Python:
- **Clarifier Agent (`agents/clarifier.py`)**: Triggered when you add a new work experience or project. It walks you through a guided ingestion process. Crucially, it parses your raw input bullets and uses a heuristic check to see if they contain quantifiable metrics. If a bullet lacks metrics, the agent stops and asks you to clarify via the WebSocket interface.
- **Gap Bridge Agent (`agents/gap_bridge.py`)**: Triggered when you run the JD Alignment workflow.
  - It takes the raw text of a Job Description and makes an external call to **OpenRouter** (the only external network call in the system) to extract the core requirements using an LLM.
  - It then takes those requirements and searches your local `Experience Store`.
  - For "potential" matches (where you might have transferable experience but it isn't a direct 1:1 match), the agent uses the LLM to generate a hypothesis connecting your past work to the new requirement.
  - It presents this hypothesis to you and asks, *"Does this sound right?"* If you confirm, it asks for specific details, drafts a brand new, highly targeted resume bullet, and saves it to your profile.

### 4. Experience Store & Embeddings
The data layer is a local **SQLite database** (`resume.db`). It enforces a strict "append-only" philosophy—nothing is ever hard-deleted, and all changes are recorded in an `audit_log`.

- **Embeddings**: When an experience or project is saved, its entire text (role, company, active bullets, skills) is concatenated. The backend uses the `sentence-transformers/all-MiniLM-L6-v2` Python library to generate a 384-dimensional vector embedding of that text locally.
- **Semantic Search**: During JD alignment, the Gap Bridge agent embeds the extracted job requirements and uses cosine similarity to find the closest matching experiences in your SQLite database. The thresholds for "Strong" (>0.72) and "Potential" (>0.42) matches are strictly defined to ensure high-quality recommendations.
