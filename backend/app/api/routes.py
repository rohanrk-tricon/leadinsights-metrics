from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse

from app.api.export_service import LeadMetricsExportService
from app.api.schemas import ChatRequest, LeadMetricsExportRequest
from app.core.streaming import format_sse_event
from app.ticket_intelligence.utils.date_utils import resolve_date_filter

router = APIRouter()


@router.get("/health")
async def health(request: Request) -> dict:
    return await request.app.state.orchestrator.healthcheck()


@router.post("/chat/stream")
async def stream_chat(payload: ChatRequest, request: Request) -> StreamingResponse:
    async def event_stream():
        async for event in request.app.state.orchestrator.stream(payload.question):
            if await request.is_disconnected():
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

        start_date, end_date = resolve_date_filter("This Month")
        export_service = LeadMetricsExportService(request.app.state.orchestrator)
        file_path = await export_service.generate_report("/tmp/leadinsights_metrics_export.xlsx")
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
        raise HTTPException(status_code=500, detail=str(exc)) from exc
