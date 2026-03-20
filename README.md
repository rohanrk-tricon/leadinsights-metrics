# Lead Insights Workspace

This branch merges two applications into one repo:

- `LeadDB Assistant`: a React + FastAPI workspace that streams SQL-planning events through the MCP database server.
- `Ticket Intelligence`: a Freshdesk analytics and ingestion workflow that runs alongside the LeadDB API under a separate namespace.

## Repo Layout

```text
.
├── backend
│   ├── app
│   │   ├── agents
│   │   ├── api
│   │   ├── core
│   │   ├── db
│   │   ├── llm
│   │   ├── mcp
│   │   └── ticket_intelligence
│   ├── main.py
│   └── requirements.txt
├── frontend
│   ├── src
│   ├── package.json
│   └── vite.config.js
└── pipeline
```

## API Surface

- `GET /api/health`
- `POST /api/chat/stream`
- `GET /api/ticket-intelligence/health`
- `POST /api/ticket-intelligence/query`
- `POST /api/ticket-intelligence/ingest`

## Setup

1. Copy env files.

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env
```

2. Install backend dependencies.

```bash
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r backend/requirements.txt
```

3. Install frontend dependencies.

```bash
cd frontend
npm install
```

## Run

Backend:

```bash
cd backend
../.venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Frontend:

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173`.

## Notes

- The LeadDB flow uses the MCP-backed SQL orchestration in `backend/app`.
- The ticket workflow uses the same FastAPI app but is routed under `/api/ticket-intelligence`.
- `pipeline/` is retained for the cloned repo's experimental data workflows.
- Ticket Intelligence now uses the configured app model provider for query reasoning and SQL-based retrieval instead of requiring Ollama.
