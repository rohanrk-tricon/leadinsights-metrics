from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font

from app.agents.orchestrator import QueryOrchestrator


@dataclass
class LeadMetricRow:
    metric: str
    description: str
    sponsor_count: str


class LeadMetricsExportService:
    def __init__(self, orchestrator: QueryOrchestrator):
        self._orchestrator = orchestrator

    async def _run_stream_question(self, question: str) -> dict[str, Any]:
        result: dict[str, Any] = {
            "answer": "",
            "sql": None,
            "rows": [],
            "columns": [],
        }
        async for event in self._orchestrator.stream(question):
            event_name = event["event"]
            data = event["data"]
            if event_name == "sql_generated":
                result["sql"] = data.get("sql")
            elif event_name == "query_executed":
                result["rows"] = data.get("rows", [])
                result["columns"] = data.get("columns", [])
            elif event_name == "complete":
                result["answer"] = data.get("answer", "")
            elif event_name == "error":
                raise RuntimeError(data.get("message", "Lead export stream failed"))
        return result

    @staticmethod
    def _extract_first_number(row: dict[str, Any]) -> str:
        for value in row.values():
            if value is None:
                continue
            if isinstance(value, (int, float)):
                return str(int(value) if isinstance(value, bool) is False and float(value).is_integer() else value)
            value_text = str(value).strip()
            if value_text.isdigit():
                return value_text
        return ""

    @staticmethod
    def _extract_name_and_count(row: dict[str, Any]) -> tuple[str, str]:
        name = ""
        count = ""
        for key, value in row.items():
            key_lower = key.lower()
            if not name and ("campaign" in key_lower or "name" in key_lower):
                name = "" if value is None else str(value)
            if not count and "count" in key_lower:
                count = "" if value is None else str(value)

        values = ["" if value is None else str(value) for value in row.values()]
        if not name and values:
            name = values[0]
        if not count and len(values) > 1:
            count = values[1]
        return name, count

    @staticmethod
    def _stack_rows(rows: list[dict[str, Any]], empty_message: str) -> tuple[str, str]:
        if not rows:
            return empty_message, ""
        names: list[str] = []
        counts: list[str] = []
        for row in rows:
            name, count = LeadMetricsExportService._extract_name_and_count(row)
            if name:
                names.append(name)
            if count:
                counts.append(count)
        return "\n".join(names), "\n".join(counts)

    async def build_metrics_rows(self) -> list[LeadMetricRow]:
        questions = {
            "campaign_count": (
                "How many campaigns were onboarded this month? "
                "Return a single row with one numeric count."
            ),
            "sponsors_per_campaign": (
                "List sponsors onboarded per campaign this month. "
                "Return one row per campaign with columns campaign_name and sponsor_count."
            ),
            "top_campaigns": (
                "What are the top 5 campaigns by sponsor volume? "
                "Return exactly five rows with columns campaign_name and sponsor_count."
            ),
        }

        campaign_count_result = await self._run_stream_question(questions["campaign_count"])
        sponsors_result = await self._run_stream_question(questions["sponsors_per_campaign"])
        top_campaigns_result = await self._run_stream_question(questions["top_campaigns"])

        campaign_count = ""
        if campaign_count_result["rows"]:
            campaign_count = self._extract_first_number(campaign_count_result["rows"][0])
        if not campaign_count:
            campaign_count = campaign_count_result["answer"]

        sponsors_description, sponsors_count = self._stack_rows(
            sponsors_result["rows"],
            "No sponsors onboarded for any campaign this month",
        )
        top_description, top_count = self._stack_rows(
            top_campaigns_result["rows"],
            "No campaign sponsor volume found",
        )

        return [
            LeadMetricRow(
                metric="Campaigns onboarded this month",
                description=campaign_count,
                sponsor_count="",
            ),
            LeadMetricRow(
                metric="Sponsors onboarded per campaign this month",
                description=sponsors_description,
                sponsor_count=sponsors_count,
            ),
            LeadMetricRow(
                metric="Top 5 Campaigns by sponsor volume",
                description=top_description,
                sponsor_count=top_count,
            ),
        ]

    async def generate_report(
        self,
        output_path: str = "/tmp/lead_assistant_metrics_export.xlsx",
    ) -> str:
        rows = await self.build_metrics_rows()

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Metrics Report"
        sheet.append(["Metrics", "Description", "Sponsor count"])

        header_font = Font(bold=True)
        for cell in sheet[1]:
            cell.font = header_font
            cell.alignment = Alignment(vertical="top")

        for row in rows:
            sheet.append([row.metric, row.description, row.sponsor_count])

        for row in sheet.iter_rows(min_row=2):
            for cell in row:
                cell.alignment = Alignment(wrap_text=True, vertical="top")

        sheet.column_dimensions["A"].width = 40
        sheet.column_dimensions["B"].width = 55
        sheet.column_dimensions["C"].width = 18

        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        workbook.save(destination)
        workbook.close()
        return str(destination)
