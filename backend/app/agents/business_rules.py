DEFAULT_EXCLUDED_EMAIL_DOMAINS = (
    "@triconinfotech.com",
    "@test.com",
    "@informa.com",
)

BUSINESS_RULES_PROMPT = """
Business rules you must follow:
- The database schema is leadinsights. Prefer schema-qualified tables such as leadinsights.campaign.
- leadinsights.lead_txn_davc is the fact table for lead generation and lead activity.
- leadinsights.lead_davc is the lead dimension table and should be joined for lead questions so email filtering can be applied.
- For time-bounded lead-generation questions, anchor the time logic with leadinsights.campaign.start_date and/or leadinsights.campaign.end_date.
- For lead questions, do not rely on lead_davc.created_on alone to infer campaign-generated leads.
- Unless the user explicitly asks to include internal or test addresses, exclude emails ending with @triconinfotech.com, @test.com, and @informa.com.
- When answering lead-related counts or lists, join lead_txn_davc to campaign and lead_davc so campaign semantics and email exclusions are both respected.
""".strip()
