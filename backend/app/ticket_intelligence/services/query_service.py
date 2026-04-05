from dataclasses import dataclass
from typing import Any


@dataclass
class TicketQueryResult:
    query_type: str
    response_text: str
    raw_data: list[Any] | None
    sql_query: str | None


class TicketQueryService:
    def __init__(self, orchestrator: Any):
        self._orchestrator = orchestrator

    def execute(self, question: str) -> TicketQueryResult:
        query_type, response_text, raw_data, sql_query = self._orchestrator.process_query(question)
        return TicketQueryResult(
            query_type=query_type,
            response_text=response_text,
            raw_data=raw_data,
            sql_query=sql_query,
        )
