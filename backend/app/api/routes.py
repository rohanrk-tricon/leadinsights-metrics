import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse

from app.api.export_service import LeadMetricsExportService
from app.api.schemas import ChatRequest, LeadMetricsExportRequest
from app.core.streaming import format_sse_event
from app.ticket_intelligence.utils.date_utils import resolve_date_filter

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health")
async def health(request: Request) -> dict:
    return await request.app.state.orchestrator.healthcheck()


@router.post("/chat/stream")
async def stream_chat(payload: ChatRequest, request: Request) -> StreamingResponse:
    logger.info(
        "Lead stream request accepted",
        extra={"question_length": len(payload.question)},
    )

    async def event_stream():
        async for event in request.app.state.orchestrator.stream(payload.question):
            if await request.is_disconnected():
                logger.info(
                    "Lead stream client disconnected",
                    extra={"question_length": len(payload.question)},
                )
                break
            yield format_sse_event(event["event"], event["data"])

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/export-metrics")
async def export_metrics(payload: LeadMetricsExportRequest, request: Request):
    try:
        if payload.use_case.lower() != "leadinsights":
            raise HTTPException(status_code=400, detail="export-metrics only supports the leadinsights use case")

        logger.info(
            "Lead metrics export requested",
            extra={"use_case": payload.use_case.lower()},
        )
        start_date, end_date = resolve_date_filter("This Month")
        export_service = LeadMetricsExportService(request.app.state.orchestrator)
        file_path = await export_service.generate_report(
            "/tmp/leadinsights_metrics_export.xlsx",
            start_date=start_date,
            end_date=end_date,
        )
        logger.info(
            "Lead metrics export generated",
            extra={
                "use_case": payload.use_case.lower(),
                "start_date": start_date,
                "end_date": end_date,
                "filename": "leadinsights_metrics_export.xlsx",
            },
        )
        return FileResponse(
            path=file_path,
            filename="leadinsights_metrics_export.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "X-Applied-Start-Date": start_date,
                "X-Applied-End-Date": end_date,
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "Lead metrics export failed",
            extra={"use_case": payload.use_case.lower(), "error_type": type(exc).__name__},
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc
