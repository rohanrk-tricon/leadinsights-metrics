---
marp: true
theme: default
paginate: true
---

# Lead Insights & Ticket Intelligence
## Project Presentation

---

## Products & Achievements Overview

**Products under the Programme**:
- **LeadDB Assistant**: A responsive workspace streaming SQL-planning events through an MCP database server.
- **Ticket Intelligence**: A Freshdesk analytics and data ingestion workflow enabling natural language conversations with support ticket data.

**Key Achievements**:
- **Intelligent Hybrid Query System**: Successfully implemented an LLM-driven routing engine that classifies user intents into deterministic PostgreSQL analytics or unstructured semantic vector searches.
- **Enterprise-Ready AI Integration**: Unified text reasoning and vector embedding through **AWS Bedrock** (Claude 3 Haiku), shifting away from local models for better performance and scale.
- **Self-Healing SQL Generation**: Engineered an auto-correcting loop that intercepts bad LLM-generated SQL, modifies it based on database error logs, and ensures smooth execution.
- **High-Performance Architecture**: Consolidated dual applications into a robust FastAPI backend service, fronted by a lightweight, decoupled Alpine.js SPA for instant rendering.

---

## Live Demo
*(4-5 minutes)*

- **Data Sync**: Showcasing seamless background ticket ingestion from the Freshdesk API.
- **Interactive QA**: Demonstrating natural language queries on complex ticket reporting.
- **Under the Hood**: Highlighting side-by-side SQL execution logic and Semantic Vector Search (pgvector) resolution paths.

---

## High Level Solution Overview

**Core Architecture Stack**:
- **Frontend Client**: Declarative **Alpine.js** Single Page Application handling high-speed data bindings and dynamic LLM markdown rendering.
- **Backend Service Engine**: Powered by **FastAPI**, managing background data syncing (`IngestionService`) and intelligent conversational routing (`QueryAgentService`).
- **Data & Vector DB**: **PostgreSQL** with `pgvector` extension to unifiedly store relational metrics and high-dimensional text embeddings.
- **LLM Orchestration**: **LangChain** tightly integrated with **AWS Bedrock** for schema-aware text-to-SQL translation and semantic synthesis.

**End-to-End Query Flow**:
1. **Ingest**: API Fetch → Compute Vector Embeddings → PostgreSQL Upsert.
2. **Classify**: Natural language is segmented into `SQL_ANALYTICS` or `SEMANTIC_SEARCH`.
3. **Execute & Synthesize**: System queries DB/vectors and summarizes raw data into human-readable insights using Claude 3.
