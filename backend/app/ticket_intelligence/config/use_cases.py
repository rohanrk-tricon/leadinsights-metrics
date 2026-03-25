from typing import Any, Dict, List
from pydantic import BaseModel, Field

class UseCaseConfig(BaseModel):
    name: str = Field(..., description="Unique identifier for the use case")
    description: str = Field(..., description="Human-readable description")
    table_name: str = Field(..., description="PostgreSQL table name without schema")
    categories: List[str] = Field(default_factory=list, description="List of issue categories")
    filter_criteria_instruction: str | None = Field(None, description="Instruction for filtering, e.g. 'Only consider records...'")
    exclusion_rules_text: str = Field(..., description="Textual rules for excluding records")
    exclusion_rules_sql: str = Field(..., description="SQL implications of the exclusion rules")
    sql_rules: str = Field(..., description="Specific SQL generation rules for this use case")
    export_metrics: List[Dict[str, Any]] = Field(default_factory=list, description="Definitions for the Excel export")

LEAD_INSIGHTS_CONFIG = UseCaseConfig(
    name="leadinsights",
    description="LeadInsights (LI) ticket intelligence",
    table_name="freshdesk_tickets",
    categories=[
        "Company Accounts - Issue", "Company Accounts - New", "Data Issue - Iris",
        "Data Issue - LI Team", "Exporting Leads", "Feature Requests",
        "Forwarded to Other Team", "GDPR Queries", "Interaction Import",
        "Login Issue", "Platform Downtime / Bug", "Platform Query",
        "Revoking Access", "Scanning Leads", "Session Mapping",
        "User Accounts - Issue", "User Accounts - New", "Investor Insights"
    ],
    filter_criteria_instruction="Only consider records when asked about leadinsights or LI where: `support_email = '{support_email}'`",
    exclusion_rules_text="- tags array contains 'spam' (e.g. 'spam' = ANY(tags))\n        - subject contains: 'automatic reply', 'respuesta automática', 'réponse automatique', 'export of tickets'",
    exclusion_rules_sql="- Array filtering: To check if a tag exists, use 'tag_name' = ANY(tags). To exclude, use NOT ('spam' = ANY(tags)).\n        - Lower case subject filtering: LOWER(subject)",
    sql_rules="- Always apply cleaning rules and filter LeadInsights",
    export_metrics=[
        {
            "name": "Total Tickets Raised",
            "question": "What is the total number of tickets raised for LeadInsights? Include only valid emails based on our rules."
        },
        {
            "name": "Tickets by Category",
            "question": "Group the LeadInsights tickets by category and provide the count for each category. Explain the counts."
        },
        {
            "name": "Average Resolution Time per Category",
            "question": "What is the average resolution time (in hours) per category for closed or resolved LeadInsights tickets?"
        },
        {
            "name": "First Response SLA Compliance (%)",
            "question": "What is the First Response SLA Compliance percentage for LeadInsights tickets? This is the percentage where fr_escalated is false."
        },
        {
            "name": "Percentage of Tickets Closed / Resolved",
            "question": "What percentage of LeadInsights tickets are closed (status 5), and what percentage are resolved (status 4)?"
        },
        {
            "name": "Top 5 Repeated Issues",
            "question": "What are the top 5 most repeated ticket issues/categories for LeadInsights by volume?"
        },
        {
            "name": "Tickets Requiring Escalation (%)",
            "question": "What percentage of LeadInsights tickets required escalation (where is_escalated is true)?"
        }
    ]
)

USE_CASES: Dict[str, UseCaseConfig] = {
    "leadinsights": LEAD_INSIGHTS_CONFIG
}

def get_use_case_config(name: str) -> UseCaseConfig:
    config = USE_CASES.get(name.lower())
    if not config:
        raise ValueError(f"Unknown use case configuration: {name}")
    return config
