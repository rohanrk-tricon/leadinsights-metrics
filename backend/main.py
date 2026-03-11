from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from backend.models import QueryRequest, QueryResponse, IngestResponse
from backend.services.ingestion import IngestionService
from backend.services.query_agent import QueryAgentService
import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Ticket Intelligence API",
    description="Backend API for interacting with Freshdesk tickets via LLM + RAG",
    version="1.0.0"
)

# Allow CORS for the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For production, restrict this to the frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/ingest", response_model=IngestResponse)
def ingest_data(background_tasks: BackgroundTasks):
    """
    Trigger the Freshdesk-to-Vector-DB pipeline asynchronously.
    """
    svc = IngestionService()
    background_tasks.add_task(svc.run_pipeline)
    return IngestResponse(
        status="in_progress",
        message="Ingestion pipeline started in the background",
        tickets_ingested=None
    )

@app.post("/query", response_model=QueryResponse)
def query_agent(request: QueryRequest):
    """
    Accept user strings and call the ticket_agent logic.
    """
    try:
        svc = QueryAgentService()
        qtype, response_text, raw_data, sql_query = svc.process_query(request.question)
        return QueryResponse(
            query_type=qtype,
            response=response_text,
            raw_data=raw_data,
            sql_query=sql_query
        )
    except Exception as e:
        logger.error(f"Query Processing Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

