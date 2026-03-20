import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from app.ticket_intelligence.schemas import (
    TicketIngestResponse,
    TicketQueryRequest,
    TicketQueryResponse,
)
from app.ticket_intelligence.service import (
    TicketIngestionService,
    TicketIntelligenceService,
)

router = APIRouter(tags=["ticket-intelligence"])
logger = logging.getLogger(__name__)


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/ingest", response_model=TicketIngestResponse)
def ingest_data(background_tasks: BackgroundTasks, request: Request) -> TicketIngestResponse:
    service = TicketIngestionService(request.app.state.settings)
    background_tasks.add_task(service.run_pipeline)
    return TicketIngestResponse(
        status="in_progress",
        message="Ticket ingestion started in the background.",
        tickets_ingested=None,
    )


@router.post("/query", response_model=TicketQueryResponse)
def query_ticket_intelligence(
    payload: TicketQueryRequest, request: Request
) -> TicketQueryResponse:
    service = TicketIntelligenceService(
        settings=request.app.state.settings,
        model_factory=request.app.state.model_factory,
    )
    try:
        query_type, response_text, raw_data, sql_query = service.process_query(
            payload.question
        )
        return TicketQueryResponse(
            query_type=query_type,
            response=response_text,
            raw_data=raw_data,
            sql_query=sql_query,
        )
    except Exception as exc:
        logger.exception("Ticket Intelligence query failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
