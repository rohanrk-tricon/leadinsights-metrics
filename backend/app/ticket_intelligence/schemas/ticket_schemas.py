from typing import Any

from pydantic import BaseModel, Field


class TicketQueryRequest(BaseModel):
    use_case: str = Field("leadinsights", description="The registered use-case to query against")
    question: str = Field(..., min_length=3, max_length=2000)


class TicketQueryResponse(BaseModel):
    query_type: str = Field(..., description="SQL_ANALYTICS or SEMANTIC_SEARCH")
    response: str = Field(..., description="LLM-generated answer")
    raw_data: list[Any] | None = Field(None, description="Query result rows or tickets")
    sql_query: str | None = Field(None, description="Executed SQL when applicable")


class TicketIngestResponse(BaseModel):
    status: str = Field(..., description="Pipeline trigger status")
    message: str = Field(..., description="Background ingestion status message")
    tickets_ingested: int | None = Field(None, description="Tickets ingested if known")

class TicketExportRequest(BaseModel):
    use_case: str = Field("leadinsights", description="The registered use-case to query against")

