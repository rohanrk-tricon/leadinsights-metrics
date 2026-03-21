from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.api.schemas import ChatRequest
from app.core.streaming import format_sse_event

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
