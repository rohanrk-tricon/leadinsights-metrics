import re

from app.agents.business_rules import DEFAULT_EXCLUDED_EMAIL_DOMAINS

YEAR_PATTERN = re.compile(r"\b20\d{2}\b")
ISO_DATE_PATTERN = re.compile(r"\b20\d{2}-\d{2}-\d{2}\b")

TIME_WINDOW_TERMS = (
    "today",
    "yesterday",
    "this week",
    "last week",
    "this month",
    "last month",
    "this quarter",
    "last quarter",
    "this year",
    "last year",
    "current month",
    "current quarter",
    "current year",
    "between",
    "during",
    "from ",
    "to ",
    "before",
    "after",
    "monthly",
    "quarterly",
    "yearly",
)


def _needs_campaign_window(question_lower: str) -> bool:
    return any(term in question_lower for term in TIME_WINDOW_TERMS) or bool(
        YEAR_PATTERN.search(question_lower) or ISO_DATE_PATTERN.search(question_lower)
    )


def build_policy_feedback(question: str, sql: str) -> str | None:
    question_lower = question.lower()
    sql_lower = sql.lower()
    feedback: list[str] = []

    is_lead_question = "lead" in question_lower
    explicitly_include_internal = (
        "include internal" in question_lower
        or "include test" in question_lower
        or any(domain in question_lower for domain in DEFAULT_EXCLUDED_EMAIL_DOMAINS)
    )
    needs_campaign_window = is_lead_question and _needs_campaign_window(question_lower)

    if not is_lead_question:
        return None

    if "lead_txn_davc" not in sql_lower:
        feedback.append(
            "Use leadinsights.lead_txn_davc as the fact table for lead-generation and lead-activity questions."
        )

    if "lead_davc" not in sql_lower:
        feedback.append(
            "Join leadinsights.lead_davc for lead questions so default email exclusions can be applied."
        )

    if not explicitly_include_internal and any(
        domain not in sql_lower for domain in DEFAULT_EXCLUDED_EMAIL_DOMAINS
    ):
        feedback.append(
            "Exclude emails ending in @triconinfotech.com, @test.com, and @informa.com unless the user explicitly asks to include them."
        )

    if needs_campaign_window:
        if "campaign" not in sql_lower:
            feedback.append(
                "Join leadinsights.campaign for time-bounded lead-generation questions."
            )
        if "start_date" not in sql_lower and "end_date" not in sql_lower:
            feedback.append(
                "Use leadinsights.campaign.start_date and/or leadinsights.campaign.end_date directly in a join or WHERE predicate. "
                "Example pattern: JOIN leadinsights.campaign c ON c.id = leadinsights.lead_txn_davc.campaign_id "
                "WHERE c.start_date <= CURRENT_DATE AND (c.end_date IS NULL OR c.end_date >= CURRENT_DATE)."
            )

    if not feedback:
        return None
    return " ".join(feedback)
