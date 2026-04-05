from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agents.orchestrator import QueryOrchestrator
from app.agents.sql_executor import SQLExecutionAgent
from app.agents.sql_generator import SQLGeneratorAgent
from app.agents.validator import ResponseValidatorAgent
from app.api.routes import router
from app.core.config import get_settings
from app.llm.strategy import ModelStrategyFactory
from app.mcp.client import MCPDatabaseClient
from app.ticket_intelligence.routes.ticket_routes import router as ticket_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    mcp_client = MCPDatabaseClient(settings)
    await mcp_client.connect()

    factory = ModelStrategyFactory(settings)
    app.state.settings = settings
    app.state.model_factory = factory
    executor = SQLExecutionAgent(mcp_client, settings)
    generator = SQLGeneratorAgent(factory)
    validator = ResponseValidatorAgent(factory)
    app.state.orchestrator = QueryOrchestrator(
        generator=generator,
        executor=executor,
        validator=validator,
        settings=settings,
    )
    try:
        yield
    finally:
        await mcp_client.close()


app = FastAPI(title=settings.api_title, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api")
app.include_router(ticket_router, prefix="/api/ticket-intelligence")
