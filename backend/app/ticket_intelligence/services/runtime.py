from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from fastapi import Request

from app.core.config import Settings
from app.ticket_intelligence.config.use_cases import UseCaseConfig, get_use_case_config

if TYPE_CHECKING:
    from app.ticket_intelligence.agents.orchestrator import TicketIntelligenceOrchestrator
    from app.ticket_intelligence.services.db_service import TicketDBService
    from app.ticket_intelligence.services.export_service import TicketExportService
    from app.ticket_intelligence.services.ingestion_service import TicketIngestionService
    from app.ticket_intelligence.services.query_service import TicketQueryService
    from app.ticket_intelligence.utils.helpers import LLMHelper


@dataclass
class TicketRuntime:
    settings: Settings
    config: UseCaseConfig
    db_service: Any
    llm_helper: Any
    orchestrator: Any
    query_service: Any
    export_service: Any


def _runtime_dependencies() -> tuple[type[Any], type[Any], type[Any], type[Any], type[Any]]:
    from app.ticket_intelligence.agents.orchestrator import TicketIntelligenceOrchestrator
    from app.ticket_intelligence.services.db_service import TicketDBService
    from app.ticket_intelligence.services.export_service import TicketExportService
    from app.ticket_intelligence.services.query_service import TicketQueryService
    from app.ticket_intelligence.utils.helpers import LLMHelper

    return TicketDBService, LLMHelper, TicketIntelligenceOrchestrator, TicketQueryService, TicketExportService


def _ingestion_dependencies() -> tuple[type[Any], type[Any]]:
    from app.ticket_intelligence.services.db_service import TicketDBService
    from app.ticket_intelligence.services.ingestion_service import TicketIngestionService

    return TicketDBService, TicketIngestionService


def build_ticket_runtime(request: Request, use_case: str) -> TicketRuntime:
    settings = request.app.state.settings
    model_factory = request.app.state.model_factory
    config = get_use_case_config(use_case)
    (
        TicketDBService,
        LLMHelper,
        TicketIntelligenceOrchestrator,
        TicketQueryService,
        TicketExportService,
    ) = _runtime_dependencies()

    db_service = TicketDBService(settings)
    llm = model_factory.build_chat_model(temperature=0)
    llm_helper = LLMHelper(llm)
    orchestrator = TicketIntelligenceOrchestrator(
        llm_helper=llm_helper,
        db_service=db_service,
        settings=settings,
        config=config,
    )
    query_service = TicketQueryService(orchestrator)
    export_service = TicketExportService(db_service, llm_helper, config, settings)

    return TicketRuntime(
        settings=settings,
        config=config,
        db_service=db_service,
        llm_helper=llm_helper,
        orchestrator=orchestrator,
        query_service=query_service,
        export_service=export_service,
    )


def build_ingestion_service(request: Request) -> Any:
    settings = request.app.state.settings
    TicketDBService, TicketIngestionService = _ingestion_dependencies()
    db_service = TicketDBService(settings)
    return TicketIngestionService(settings, db_service)
