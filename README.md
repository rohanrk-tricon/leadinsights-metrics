# Ticket Intelligence Platform

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Alpine.js](https://img.shields.io/badge/Alpine.js-8BC0D0?style=for-the-badge&logo=alpine.js&logoColor=white)](https://alpinejs.dev/)

A production-grade intelligent retrieval-augmented generation application.

## Overview

Ticket Intelligence is designed to connect a Freshdesk support center with a PostgreSQL database and provide semantic querying and SQL analysis using AWS Bedrock (Claude 3 Haiku) through the LangChain orchestration framework. 

*This replaces the original `embed_tickets.py` and `ticket_agent.py` prototype.*

## Getting Started

### Prerequisites

- Python 3.10+
- PostgreSQL
- Ollama (running locally with `nomic-embed-text`)
- AWS API keys with Bedrock invocation permissions

### Installation & Setup

1. **Clone the Repo (or move into the root folder)**
    ```bash
    cd /path/to/project
    ```

2. **Configure Environment Variables**
    ```bash
    cp .env.example .env
    # Edit .env with your specific AWS, Freshdesk, and PG Database configurations
    ```

3. **Install Backend Dependencies**
    ```bash
    cd backend
    python -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

4. **Run the API Backend Server**
     ```bash
     uvicorn main:app --reload
     ```
     > The backend will spin up on `http://127.0.0.1:8000`. Full API schema documentation is available automatically at `/docs` (Swagger UI).

5. **Run the Frontend Client**
     In a new terminal, serve the frontend HTML.
     ```bash
     cd frontend
     python -m http.server 3000
     ```
     > Access the UI at `http://127.0.0.1:3000`

## System Architecture

See [`docs/architecture.md`](docs/architecture.md) for the detailed pipeline structure and Mermaid diagrams.

## API Endpoints

- `GET /health` : Verify system connectivity.
- `POST /ingest` : Triggers the asynchronous background pipeline to fetch tickets.
- `POST /query` : Submit questions to the ChatBedrock agent and receive categorized textual responses. Request payload expects `{"question": "string"}`.
