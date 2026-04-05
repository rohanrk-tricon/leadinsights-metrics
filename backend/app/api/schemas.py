from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


class LeadMetricsExportRequest(BaseModel):
    use_case: str = Field("leadinsights", description="Lead assistant export use case")
