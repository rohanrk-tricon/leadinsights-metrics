import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api.routes import router as api_router
from app.ticket_intelligence.routes.ticket_routes import router as ticket_router


def _make_temp_file(suffix: str = ".xlsx") -> str:
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    with open(path, "wb") as handle:
        handle.write(b"test-content")
    return path


def _parse_sse_events(payload: str) -> list[dict]:
    events = []
    for block in payload.strip().split("\n\n"):
        if not block.strip():
            continue
        lines = block.splitlines()
        event = next(line.replace("event: ", "", 1) for line in lines if line.startswith("event: "))
        data = next(line.replace("data: ", "", 1) for line in lines if line.startswith("data: "))
        events.append({"event": event, "data": json.loads(data)})
    return events


class FakeLeadOrchestrator:
    async def healthcheck(self):
        return {"status": "ok", "database": "reachable"}

    async def stream(self, question: str):
        yield {"event": "status", "data": {"stage": "accepted", "message": "accepted"}}
        yield {"event": "status", "data": {"stage": "planning", "message": "planning"}}
        yield {"event": "sql_generated", "data": {"sql": "select 1", "reasoning": "reason", "expected_result_shape": "rows"}}
        yield {"event": "status", "data": {"stage": "executing", "message": "executing"}}
        yield {"event": "query_executed", "data": {"sql": "select 1", "columns": ["total"], "rows": [{"total": 1}]}}
        yield {"event": "status", "data": {"stage": "validating", "message": "validating"}}
        yield {
            "event": "complete",
            "data": {"answer": f"Answer for {question}", "confidence": "high", "rationale": "ok", "total_ms": 1.5},
        }


class RouteContractTests(unittest.TestCase):
    def setUp(self):
        self.lead_app = FastAPI()
        self.lead_app.include_router(api_router, prefix="/api")
        self.lead_app.state.orchestrator = FakeLeadOrchestrator()
        self.lead_client = TestClient(self.lead_app)

        self.ticket_app = FastAPI()
        self.ticket_app.include_router(ticket_router, prefix="/api/ticket-intelligence")
        self.ticket_client = TestClient(self.ticket_app)

    def tearDown(self):
        self.lead_client.close()
        self.ticket_client.close()

    def test_health_route_preserves_payload_shape(self):
        response = self.lead_client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "database": "reachable"})

    def test_chat_stream_preserves_sse_sequence_and_payload_shape(self):
        response = self.lead_client.post("/api/chat/stream", json={"question": "How many leads?"})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("text/event-stream"))
        events = _parse_sse_events(response.text)
        self.assertEqual(
            [event["event"] for event in events],
            ["status", "status", "sql_generated", "status", "query_executed", "status", "complete"],
        )
        self.assertEqual(events[0]["data"]["stage"], "accepted")
        self.assertEqual(events[1]["data"]["stage"], "planning")
        self.assertIn("sql", events[2]["data"])
        self.assertIn("rows", events[4]["data"])
        self.assertIn("answer", events[6]["data"])

    def test_export_metrics_preserves_headers_and_filename(self):
        temp_path = _make_temp_file()
        try:
            with patch("app.api.routes.resolve_date_filter", return_value=("2026-04-01", "2026-04-30")):
                with patch("app.api.routes.LeadMetricsExportService.generate_report", new=AsyncMock(return_value=temp_path)):
                    response = self.lead_client.post("/api/export-metrics", json={"use_case": "leadinsights"})

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["x-applied-start-date"], "2026-04-01")
            self.assertEqual(response.headers["x-applied-end-date"], "2026-04-30")
            self.assertIn('filename="leadinsights_metrics_export.xlsx"', response.headers["content-disposition"])
        finally:
            os.unlink(temp_path)

    def test_export_metrics_rejects_unsupported_use_case(self):
        response = self.lead_client.post("/api/export-metrics", json={"use_case": "other"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {"detail": "export-metrics only supports the leadinsights use case"},
        )

    def test_ticket_health_route_preserves_payload_shape(self):
        response = self.ticket_client.get("/api/ticket-intelligence/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_ticket_ingest_preserves_response_shape(self):
        service = SimpleNamespace(run_pipeline=Mock())
        with patch("app.ticket_intelligence.routes.ticket_routes.build_ingestion_service", return_value=service):
            response = self.ticket_client.post("/api/ticket-intelligence/ingest")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "status": "in_progress",
                "message": "Ticket ingestion started in the background.",
                "tickets_ingested": None,
            },
        )
        service.run_pipeline.assert_called_once_with()

    def test_ticket_query_preserves_response_fields(self):
        runtime = SimpleNamespace(
            query_service=SimpleNamespace(
                execute=Mock(
                    return_value=SimpleNamespace(
                        query_type="SQL_ANALYTICS",
                        response_text="42 tickets",
                        raw_data=[{"count": 42}],
                        sql_query="select count(*) from tickets",
                    )
                )
            )
        )
        with patch("app.ticket_intelligence.routes.ticket_routes.build_ticket_runtime", return_value=runtime):
            response = self.ticket_client.post(
                "/api/ticket-intelligence/query",
                json={"use_case": "leadinsights", "question": "How many tickets?"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "query_type": "SQL_ANALYTICS",
                "response": "42 tickets",
                "raw_data": [{"count": 42}],
                "sql_query": "select count(*) from tickets",
            },
        )

    def test_ticket_export_preserves_headers_and_filename(self):
        temp_path = _make_temp_file()
        runtime = SimpleNamespace(
            export_service=SimpleNamespace(
                prepare_export=Mock(
                    return_value=SimpleNamespace(
                        file_path=temp_path,
                        filename="leadinsights_metrics_export.xlsx",
                        headers={
                            "X-Applied-Start-Date": "2026-03-01",
                            "X-Applied-End-Date": "2026-03-31",
                        },
                    )
                )
            )
        )
        try:
            with patch("app.ticket_intelligence.routes.ticket_routes.build_ticket_runtime", return_value=runtime):
                response = self.ticket_client.post(
                    "/api/ticket-intelligence/export",
                    json={"use_case": "leadinsights", "dateDuration": "Last Month"},
                )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["x-applied-start-date"], "2026-03-01")
            self.assertEqual(response.headers["x-applied-end-date"], "2026-03-31")
            self.assertIn('filename="leadinsights_metrics_export.xlsx"', response.headers["content-disposition"])
        finally:
            os.unlink(temp_path)

    def test_ticket_export_propagates_http_contract_errors(self):
        runtime = SimpleNamespace(
            export_service=SimpleNamespace(
                prepare_export=Mock(
                    side_effect=HTTPException(status_code=400, detail="startDate must be less than or equal to endDate")
                )
            )
        )
        with patch("app.ticket_intelligence.routes.ticket_routes.build_ticket_runtime", return_value=runtime):
            response = self.ticket_client.post(
                "/api/ticket-intelligence/export",
                json={"use_case": "leadinsights", "startDate": "2026-04-02", "endDate": "2026-04-01"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {"detail": "startDate must be less than or equal to endDate"},
        )


if __name__ == "__main__":
    unittest.main()
