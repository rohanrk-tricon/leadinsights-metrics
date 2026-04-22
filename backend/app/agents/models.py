from typing import Literal

from pydantic import BaseModel, Field


class SQLPlan(BaseModel):
    sql: str = Field(description="A single read-only PostgreSQL query.")
    reasoning: str = Field(description="Short explanation of why this query answers the question.")
    expected_result_shape: str = Field(description="Expected result columns and cardinality.")


class QueryExecution(BaseModel):
    original_sql: str
    executed_sql: str
    columns: list[str]
    rows: list[dict]
    row_count: int
    execution_ms: float


class ValidationResult(BaseModel):
    is_valid: bool = Field(description="Whether the answer is sufficient for the user question.")
    confidence: Literal["low", "medium", "high"]
    final_answer: str = Field(
        default="",
        description="Natural-language answer for the user. Use an empty string when a follow-up query is needed.",
    )
    rationale: str = Field(default="", description="Short validation rationale.")
    follow_up_sql: str | None = Field(
        default=None,
        description="Optional improved read-only SQL query if a retry is needed.",
    )
