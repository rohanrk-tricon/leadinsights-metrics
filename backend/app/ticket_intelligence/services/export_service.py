import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List

import pandas as pd
from fastapi import HTTPException

from app.core.config import Settings
from app.ticket_intelligence.config.use_cases import UseCaseConfig
from app.ticket_intelligence.schemas.ticket_schemas import TicketExportRequest
from app.ticket_intelligence.services.db_service import TicketDBService
from app.ticket_intelligence.utils.date_utils import DATEDURATION_CHOICES, resolve_date_filter
from app.ticket_intelligence.utils.helpers import LLMHelper

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from app.ticket_intelligence.agents.orchestrator import TicketIntelligenceOrchestrator


@dataclass
class TicketPreparedExport:
    file_path: str
    filename: str
    headers: dict[str, str]


def _orchestrator_class() -> type["TicketIntelligenceOrchestrator"]:
    from app.ticket_intelligence.agents.orchestrator import TicketIntelligenceOrchestrator

    return TicketIntelligenceOrchestrator


class TicketExportService:
    def __init__(
        self,
        db_service: TicketDBService,
        llm_helper: LLMHelper,
        config: UseCaseConfig,
        settings: Settings,
    ):
        self._db_service = db_service
        self._llm_helper = llm_helper
        self._config = config
        self._settings = settings

        self._orchestrator = _orchestrator_class()(
            llm_helper=llm_helper,
            db_service=db_service,
            settings=settings,
            config=config,
        )

    def prepare_export(self, payload: TicketExportRequest) -> TicketPreparedExport:
        logger.info(
            "Ticket export preparation started",
            extra={
                "use_case": payload.use_case,
                "has_date_duration": bool(payload.dateDuration),
                "has_start_date": bool(payload.startDate),
                "has_end_date": bool(payload.endDate),
            },
        )
        if payload.dateDuration and payload.dateDuration.strip().title() not in DATEDURATION_CHOICES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid dateDuration. Choose from: {DATEDURATION_CHOICES}",
            )

        if not payload.dateDuration and payload.startDate and payload.endDate:
            if payload.startDate > payload.endDate:
                raise HTTPException(status_code=400, detail="startDate must be less than or equal to endDate")

        start_date, end_date = resolve_date_filter(
            payload.dateDuration,
            payload.startDate,
            payload.endDate,
        )
        filename = f"{payload.use_case}_metrics_export.xlsx"
        file_path = self.generate_report(
            start_date=start_date,
            end_date=end_date,
            output_path=f"/tmp/{filename}",
        )
        logger.info(
            "Ticket export preparation completed",
            extra={
                "use_case": payload.use_case,
                "start_date": start_date,
                "end_date": end_date,
                "filename": filename,
            },
        )

        return TicketPreparedExport(
            file_path=file_path,
            filename=filename,
            headers={
                "X-Applied-Start-Date": start_date,
                "X-Applied-End-Date": end_date,
            },
        )

    def generate_report(
        self,
        start_date: str,
        end_date: str,
        output_path: str = "/tmp/ticket_export.xlsx",
    ) -> str:
        logger.info(
            "Generating dynamic Excel report using LLM Orchestrator",
            extra={
                "start_date": start_date,
                "end_date": end_date,
                "metric_count": len(self._config.export_metrics),
            },
        )
        import json

        main_report_data = []
        analytics_data = []

        for metric in self._config.export_metrics:
            m_name = metric.get("name", "Unknown Metric")
            base_question = metric.get("question", "")

            logger.info("Exporting metric: %s", m_name)
            if not base_question:
                continue

            m_question = (
                f"{base_question} strictly filtering for tickets created_at between "
                f"{start_date} and {end_date} inclusive."
            )

            try:
                q_type, response_text, raw_data, sql = self._orchestrator.process_query(m_question)

                format_prompt = f"""
                    You are a data formatting assistant formatting data for an Excel report.
                    Metric Name: {m_name}
                    Question: {m_question}
                    Pipeline Used: {q_type}
                    Raw Data: {raw_data}
                    AI Explanation: {response_text}

                    Format the answer into a strict JSON list of rows for the report.
                    Each object MUST have exact keys: "Description" and "count" (use strings for values).
                    Do not create a "Metrics" key, this will be handled automatically.
                    If there are multiple categories (like Count by Category), return a list of objects, one for each category.
                    If there is only one value (like Total Tickets), return one object where Description explains what it is.

                    Only return valid parseable JSON. No markdown ticks. Example:
                    [
                    {{"Description": "Company Accounts - Issue", "count": "1"}}
                    ]
                    """
                try:
                    format_response = self._llm_helper.call_llm(format_prompt).strip()
                    if format_response.startswith("```json"):
                        format_response = format_response[7:-3].strip()
                    elif format_response.startswith("```"):
                        format_response = format_response[3:-3].strip()

                    parsed_rows = json.loads(format_response)

                    if not isinstance(parsed_rows, list):
                        parsed_rows = [parsed_rows]

                    for i, row in enumerate(parsed_rows):
                        main_report_data.append({
                            "Metrics": m_name if i == 0 else "",
                            "Description": row.get("Description", ""),
                            "count": row.get("count", ""),
                        })

                except Exception as json_e:
                    logger.error(
                        "Failed to parse formatted ticket export metric",
                        extra={"metric_name": m_name, "error_type": type(json_e).__name__},
                    )
                    main_report_data.append({
                        "Metrics": m_name,
                        "Description": "Error parsing JSON",
                        "count": str(json_e),
                    })

                analytics_data.append({
                    "Metrics": m_name,
                    "Question Asked": m_question,
                    "Pipeline Used": q_type,
                    "Generated SQL": sql if sql else "N/A",
                    "AI Explanation": response_text,
                })

            except Exception as exc:
                logger.error(
                    "Failed to generate ticket export metric",
                    extra={"metric_name": m_name, "error_type": type(exc).__name__},
                )
                main_report_data.append({
                    "Metrics": m_name,
                    "Description": m_question,
                    "count": str(exc),
                })
                analytics_data.append({
                    "Metrics": m_name,
                    "Pipeline Used": "ERROR",
                    "AI Explanation": str(exc),
                })

        analytics_data.insert(0, {
            "Metrics": "Report Metadata",
            "Question Asked": f"Applied Date Filter: {start_date} to {end_date}",
            "Pipeline Used": "SYSTEM",
            "Generated SQL": "N/A",
            "AI Explanation": "Metadata block reflecting the date bounds applied to all metrics below.",
        })

        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            df_main = pd.DataFrame(main_report_data)
            df_main.to_excel(writer, sheet_name="Report", index=False)

            df_analytics = pd.DataFrame(analytics_data)
            df_analytics.to_excel(writer, sheet_name="Analytics & SQL", index=False)

        logger.info("Ticket Excel report saved", extra={"output_path": output_path})
        return output_path
