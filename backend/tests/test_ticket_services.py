import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException

from app.ticket_intelligence.schemas.ticket_schemas import TicketExportRequest
from app.ticket_intelligence.services.export_service import TicketExportService
from app.ticket_intelligence.services.query_service import TicketQueryService
from app.ticket_intelligence.utils.date_utils import DATEDURATION_CHOICES


class TicketQueryServiceTests(unittest.TestCase):
    def test_execute_returns_orchestrator_result_fields(self):
        orchestrator = Mock()
        orchestrator.process_query.return_value = (
            "SQL_ANALYTICS",
            "answer text",
            [{"count": 1}],
            "select 1",
        )

        service = TicketQueryService(orchestrator)
        result = service.execute("How many tickets?")

        self.assertEqual(result.query_type, "SQL_ANALYTICS")
        self.assertEqual(result.response_text, "answer text")
        self.assertEqual(result.raw_data, [{"count": 1}])
        self.assertEqual(result.sql_query, "select 1")
        orchestrator.process_query.assert_called_once_with("How many tickets?")


class TicketExportServiceTests(unittest.TestCase):
    def setUp(self):
        self.db_service = object()
        self.llm_helper = Mock()
        self.config = Mock(export_metrics=[])
        self.settings = object()

    @patch("app.ticket_intelligence.services.export_service._orchestrator_class")
    def test_prepare_export_returns_same_headers_and_filename(self, mock_orchestrator_class):
        mock_orchestrator_class.return_value = Mock()
        service = TicketExportService(self.db_service, self.llm_helper, self.config, self.settings)
        payload = TicketExportRequest(use_case="leadinsights", dateDuration="Last Month")

        with patch(
            "app.ticket_intelligence.services.export_service.resolve_date_filter",
            return_value=("2026-03-01", "2026-03-31"),
        ) as mock_resolve_date_filter:
            with patch.object(
                service,
                "generate_report",
                return_value="/tmp/leadinsights_metrics_export.xlsx",
            ) as mock_generate_report:
                result = service.prepare_export(payload)

        mock_resolve_date_filter.assert_called_once_with("Last Month", None, None)
        mock_generate_report.assert_called_once_with(
            start_date="2026-03-01",
            end_date="2026-03-31",
            output_path="/tmp/leadinsights_metrics_export.xlsx",
        )
        self.assertEqual(result.file_path, "/tmp/leadinsights_metrics_export.xlsx")
        self.assertEqual(result.filename, "leadinsights_metrics_export.xlsx")
        self.assertEqual(
            result.headers,
            {
                "X-Applied-Start-Date": "2026-03-01",
                "X-Applied-End-Date": "2026-03-31",
            },
        )

    @patch("app.ticket_intelligence.services.export_service._orchestrator_class")
    def test_prepare_export_rejects_invalid_named_date_duration(self, mock_orchestrator_class):
        mock_orchestrator_class.return_value = Mock()
        service = TicketExportService(self.db_service, self.llm_helper, self.config, self.settings)
        payload = TicketExportRequest(use_case="leadinsights", dateDuration="invalid")

        with self.assertRaises(HTTPException) as context:
            service.prepare_export(payload)

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(
            context.exception.detail,
            f"Invalid dateDuration. Choose from: {DATEDURATION_CHOICES}",
        )

    @patch("app.ticket_intelligence.services.export_service._orchestrator_class")
    def test_prepare_export_rejects_inverted_manual_date_range(self, mock_orchestrator_class):
        mock_orchestrator_class.return_value = Mock()
        service = TicketExportService(self.db_service, self.llm_helper, self.config, self.settings)
        payload = TicketExportRequest(
            use_case="leadinsights",
            startDate="2026-04-02",
            endDate="2026-04-01",
        )

        with self.assertRaises(HTTPException) as context:
            service.prepare_export(payload)

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(
            context.exception.detail,
            "startDate must be less than or equal to endDate",
        )


if __name__ == "__main__":
    unittest.main()
