import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import FileResponse

from app.ticket_intelligence.schemas.ticket_schemas import (
    TicketIngestResponse,
    TicketQueryRequest,
    TicketQueryResponse,
    TicketExportRequest,
)
from app.ticket_intelligence.services.db_service import TicketDBService
from app.ticket_intelligence.services.ingestion_service import TicketIngestionService
from app.ticket_intelligence.services.export_service import TicketExportService
from app.ticket_intelligence.agents.orchestrator import TicketIntelligenceOrchestrator
from app.ticket_intelligence.utils.helpers import LLMHelper
from app.ticket_intelligence.config.use_cases import get_use_case_config

router = APIRouter(tags=["ticket-intelligence"])
logger = logging.getLogger(__name__)

@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

@router.post("/ingest", response_model=TicketIngestResponse)
def ingest_data(background_tasks: BackgroundTasks, request: Request) -> TicketIngestResponse:
    print("Received request to ingest tickets")
    db_service = TicketDBService(request.app.state.settings)
    service = TicketIngestionService(request.app.state.settings, db_service)
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
    try:
        settings = request.app.state.settings
        model_factory = request.app.state.model_factory
        
        db_service = TicketDBService(settings)
        llm = model_factory.build_chat_model(temperature=0)
        llm_helper = LLMHelper(llm)

        config = get_use_case_config(payload.use_case)

        orchestrator = TicketIntelligenceOrchestrator(
            llm_helper=llm_helper,
            db_service=db_service,
            settings=settings,
            config=config
        )

        query_type, response_text, raw_data, sql_query = orchestrator.process_query(
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

@router.post("/export")
def export_ticket_intelligence(payload: TicketExportRequest, request: Request):
    try:
        settings = request.app.state.settings
        model_factory = request.app.state.model_factory
        
        db_service = TicketDBService(settings)
        llm = model_factory.build_chat_model(temperature=0)
        llm_helper = LLMHelper(llm)

        config = get_use_case_config(payload.use_case)
        
        export_svc = TicketExportService(db_service, llm_helper, config, settings)
        file_path = export_svc.generate_report(output_path=f"/tmp/{payload.use_case}_metrics_export.xlsx")
        
        return FileResponse(
            path=file_path,
            filename=f"{payload.use_case}_metrics_export.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as exc:
        logger.exception("Export failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
