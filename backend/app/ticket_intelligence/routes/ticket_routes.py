import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import FileResponse

from app.ticket_intelligence.schemas.ticket_schemas import (
    TicketIngestResponse,
    TicketQueryRequest,
    TicketQueryResponse,
    TicketExportRequest,
)
from app.ticket_intelligence.services.runtime import build_ingestion_service, build_ticket_runtime

router = APIRouter(tags=["ticket-intelligence"])
logger = logging.getLogger(__name__)

@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

@router.post("/ingest", response_model=TicketIngestResponse)
def ingest_data(background_tasks: BackgroundTasks, request: Request) -> TicketIngestResponse:
    logger.info("Ticket ingestion requested")
    service = build_ingestion_service(request)
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
        logger.info(
            "Ticket query requested",
            extra={"use_case": payload.use_case, "question_length": len(payload.question)},
        )
        runtime = build_ticket_runtime(request, payload.use_case)
        result = runtime.query_service.execute(payload.question)
        return TicketQueryResponse(
            query_type=result.query_type,
            response=result.response_text,
            raw_data=result.raw_data,
            sql_query=result.sql_query,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "Ticket Intelligence query failed",
            extra={
                "use_case": payload.use_case,
                "question_length": len(payload.question),
                "error_type": type(exc).__name__,
            },
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@router.post("/export")
def export_ticket_intelligence(payload: TicketExportRequest, request: Request):
    try:
        logger.info(
            "Ticket export requested",
            extra={
                "use_case": payload.use_case,
                "has_date_duration": bool(payload.dateDuration),
                "has_start_date": bool(payload.startDate),
                "has_end_date": bool(payload.endDate),
            },
        )
        runtime = build_ticket_runtime(request, payload.use_case)
        result = runtime.export_service.prepare_export(payload)

        return FileResponse(
            path=result.file_path,
            filename=result.filename,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers=result.headers,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "Ticket export failed",
            extra={"use_case": payload.use_case, "error_type": type(exc).__name__},
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc
