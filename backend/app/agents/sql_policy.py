import re

from app.agents.business_rules import DEFAULT_EXCLUDED_EMAIL_DOMAINS

YEAR_PATTERN = re.compile(r"\b20\d{2}\b")


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
    needs_campaign_window = is_lead_question and (
        "generated" in question_lower
        or "campaign" in question_lower
        or "between" in question_lower
        or "during" in question_lower
        or "year" in question_lower
        or "month" in question_lower
        or "quarter" in question_lower
        or bool(YEAR_PATTERN.search(question_lower))
    )

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
                "Use leadinsights.campaign.start_date and/or end_date to anchor the campaign window for generated-lead questions."
            )

    if not feedback:
        return None
    return " ".join(feedback)
