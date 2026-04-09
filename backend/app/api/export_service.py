import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font

from app.agents.orchestrator import QueryOrchestrator

logger = logging.getLogger(__name__)


@dataclass
class LeadMetricRow:
    metric: str
    description: str
    sponsor_count: str


class LeadMetricsExportService:
    def __init__(self, orchestrator: QueryOrchestrator):
        self._orchestrator = orchestrator

    async def _run_sql_query(self, sql: str) -> dict[str, Any]:
        logger.info(
            "Lead metrics export SQL execution started",
            extra={"sql_length": len(sql)},
        )
        execution = await self._orchestrator.execute_readonly_sql(sql)
        result: dict[str, Any] = {
            "answer": "",
            "sql": sql,
            "rows": execution.rows,
            "columns": execution.columns,
        }
        logger.info(
            "Lead metrics export SQL execution completed",
            extra={
                "sql_length": len(sql),
                "row_count": len(result["rows"]),
                "column_count": len(result["columns"]),
            },
        )
        return result

    @staticmethod
    def _build_metrics_sql(start_date: str, end_date: str) -> dict[str, str]:
        active_campaign_predicate = (
            f"c.start_date::date <= DATE '{end_date}' "
            f"AND (c.end_date IS NULL OR c.end_date::date >= DATE '{start_date}')"
        )
        sponsor_count_expr = "COUNT(DISTINCT tsc.sponsor_id)"

        return {
            "campaign_count": f"""
                SELECT COUNT(*) AS campaign_count
                FROM leadinsights.campaign c
                WHERE {active_campaign_predicate};
            """.strip(),
            "sponsors_per_campaign": f"""
                SELECT
                    c.name AS campaign_name,
                    {sponsor_count_expr} AS sponsor_count
                FROM leadinsights.campaign c
                LEFT JOIN leadinsights.tenant_sponsor_campaign tsc
                    ON tsc.campaign_id = c.id
                    AND tsc.deleted_on IS NULL
                WHERE {active_campaign_predicate}
                GROUP BY c.id, c.name
                ORDER BY sponsor_count DESC, c.name ASC;
            """.strip(),
            "top_campaigns": f"""
                SELECT
                    c.name AS campaign_name,
                    {sponsor_count_expr} AS sponsor_count
                FROM leadinsights.campaign c
                LEFT JOIN leadinsights.tenant_sponsor_campaign tsc
                    ON tsc.campaign_id = c.id
                    AND tsc.deleted_on IS NULL
                WHERE {active_campaign_predicate}
                GROUP BY c.id, c.name
                ORDER BY sponsor_count DESC, c.name ASC
                LIMIT 5;
            """.strip(),
        }

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

    async def build_metrics_rows(self, start_date: str, end_date: str) -> list[LeadMetricRow]:
        sql_queries = self._build_metrics_sql(start_date, end_date)

        campaign_count_result = await self._run_sql_query(sql_queries["campaign_count"])
        sponsors_result = await self._run_sql_query(sql_queries["sponsors_per_campaign"])
        top_campaigns_result = await self._run_sql_query(sql_queries["top_campaigns"])

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
                metric="Campaigns active this month",
                description=campaign_count,
                sponsor_count="",
            ),
            LeadMetricRow(
                metric="Sponsors per active campaign this month",
                description=sponsors_description,
                sponsor_count=sponsors_count,
            ),
            LeadMetricRow(
                metric="Top 5 active campaigns by sponsor volume",
                description=top_description,
                sponsor_count=top_count,
            ),
        ]

    async def generate_report(
        self,
        output_path: str = "/tmp/lead_assistant_metrics_export.xlsx",
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> str:
        logger.info("Lead metrics workbook generation started", extra={"output_path": output_path})
        if not start_date or not end_date:
            raise ValueError("start_date and end_date are required for lead metrics export.")

        rows = await self.build_metrics_rows(start_date, end_date)

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
        logger.info(
            "Lead metrics workbook generation completed",
            extra={"output_path": str(destination), "row_count": len(rows)},
        )
        return str(destination)
