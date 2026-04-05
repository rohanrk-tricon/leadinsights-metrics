import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.ticket_intelligence.services.runtime import build_ingestion_service, build_ticket_runtime


class TicketRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.settings = object()
        self.chat_model = object()
        self.model_factory = SimpleNamespace(
            build_chat_model=lambda temperature=0: self.chat_model
        )
        self.request = SimpleNamespace(
            app=SimpleNamespace(
                state=SimpleNamespace(
                    settings=self.settings,
                    model_factory=self.model_factory,
                )
            )
        )

    @patch("app.ticket_intelligence.services.runtime._runtime_dependencies")
    @patch("app.ticket_intelligence.services.runtime.get_use_case_config")
    def test_build_ticket_runtime_wires_dependencies(
        self,
        mock_get_use_case_config,
        mock_runtime_dependencies,
    ):
        config = object()
        db_service = object()
        llm_helper = object()
        orchestrator = object()
        query_service = object()
        export_service = object()
        mock_db_service = Mock(return_value=db_service)
        mock_llm_helper = Mock(return_value=llm_helper)
        mock_orchestrator = Mock(return_value=orchestrator)
        mock_query_service = Mock(return_value=query_service)
        mock_export_service = Mock(return_value=export_service)

        mock_get_use_case_config.return_value = config
        mock_runtime_dependencies.return_value = (
            mock_db_service,
            mock_llm_helper,
            mock_orchestrator,
            mock_query_service,
            mock_export_service,
        )

        runtime = build_ticket_runtime(self.request, "leadinsights")

        self.assertIs(runtime.settings, self.settings)
        self.assertIs(runtime.config, config)
        self.assertIs(runtime.db_service, db_service)
        self.assertIs(runtime.llm_helper, llm_helper)
        self.assertIs(runtime.orchestrator, orchestrator)
        self.assertIs(runtime.query_service, query_service)
        self.assertIs(runtime.export_service, export_service)

        mock_get_use_case_config.assert_called_once_with("leadinsights")
        mock_db_service.assert_called_once_with(self.settings)
        mock_llm_helper.assert_called_once_with(self.chat_model)
        mock_orchestrator.assert_called_once()
        mock_query_service.assert_called_once_with(orchestrator)
        mock_export_service.assert_called_once_with(db_service, llm_helper, config, self.settings)

    @patch("app.ticket_intelligence.services.runtime._ingestion_dependencies")
    def test_build_ingestion_service_uses_request_settings(self, mock_ingestion_dependencies):
        db_service = object()
        service = object()
        mock_db_service = Mock(return_value=db_service)
        mock_ingestion_service = Mock(return_value=service)
        mock_ingestion_dependencies.return_value = (mock_db_service, mock_ingestion_service)

        result = build_ingestion_service(self.request)

        self.assertIs(result, service)
        mock_db_service.assert_called_once_with(self.settings)
        mock_ingestion_service.assert_called_once_with(self.settings, db_service)


if __name__ == "__main__":
    unittest.main()
