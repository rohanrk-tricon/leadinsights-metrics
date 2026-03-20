from langchain_core.prompts import ChatPromptTemplate

from app.agents.business_rules import BUSINESS_RULES_PROMPT
from app.agents.models import SQLPlan
from app.llm.strategy import ModelStrategyFactory

GENERATOR_SYSTEM_PROMPT = """
You are the SQL generation agent for a PostgreSQL analytics assistant.

Your job:
- Generate exactly one safe read-only PostgreSQL query.
- Use only the tables and columns present in the schema context.
- Prefer explicit column names.
- Add filtering, grouping, ordering, and joins only when required.
- Use ILIKE for flexible text matching where useful.
- Keep the result set compact. If the question asks for raw rows, include a LIMIT.
- Respect the business rules provided below.
- Never generate INSERT, UPDATE, DELETE, ALTER, DROP, TRUNCATE, CREATE, GRANT, REVOKE, or COPY.
- Do not use multiple statements.

{business_rules}

Return a structured response only.
""".strip()


class SQLGeneratorAgent:
    def __init__(self, factory: ModelStrategyFactory) -> None:
        self._factory = factory
        self._model = None
        self._prompt = ChatPromptTemplate.from_messages(
            [
                ("system", GENERATOR_SYSTEM_PROMPT),
                (
                    "human",
                    """
Question:
{question}

Schema:
{schema_context}

Additional enforcement feedback:
{feedback}

Return one read-only PostgreSQL query that best answers the question.
""".strip(),
                ),
            ]
        )

    async def generate(
        self,
        question: str,
        schema_context: str,
        feedback: str | None = None,
    ) -> SQLPlan:
        if self._model is None:
            self._model = self._factory.build_chat_model().with_structured_output(SQLPlan)
        chain = self._prompt | self._model
        return await chain.ainvoke(
            {
                "business_rules": BUSINESS_RULES_PROMPT,
                "question": question,
                "schema_context": schema_context,
                "feedback": feedback or "No additional corrections.",
            }
        )
