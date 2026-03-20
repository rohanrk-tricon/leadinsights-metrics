import json

from langchain_core.prompts import ChatPromptTemplate

from app.agents.business_rules import BUSINESS_RULES_PROMPT
from app.agents.models import QueryExecution, ValidationResult
from app.llm.strategy import ModelStrategyFactory

VALIDATOR_SYSTEM_PROMPT = """
You are the answer validation agent for a PostgreSQL assistant.

Your job:
- Decide whether the SQL result fully answers the user's question.
- If it does, produce a concise final answer grounded in the returned rows.
- If it does not, set is_valid to false and provide a better follow_up_sql query.
- Never invent data that is not present in the rows.
- Enforce the business rules below when judging whether the SQL was correct.
- Keep follow_up_sql to one safe read-only PostgreSQL statement.

{business_rules}

Return a structured response only.
""".strip()


class ResponseValidatorAgent:
    def __init__(self, factory: ModelStrategyFactory) -> None:
        self._factory = factory
        self._model = None
        self._prompt = ChatPromptTemplate.from_messages(
            [
                ("system", VALIDATOR_SYSTEM_PROMPT),
                (
                    "human",
                    """
Question:
{question}

SQL:
{sql}

Execution summary:
- columns: {columns}
- row_count: {row_count}
- execution_ms: {execution_ms}

Rows preview:
{rows_preview}

Validate the answer quality and either return the final answer or a better follow-up SQL query.
""".strip(),
                ),
            ]
        )

    async def validate(self, question: str, execution: QueryExecution) -> ValidationResult:
        if self._model is None:
            self._model = self._factory.build_chat_model().with_structured_output(ValidationResult)
        chain = self._prompt | self._model
        rows_preview = json.dumps(execution.rows[:25], default=str, indent=2)
        return await chain.ainvoke(
            {
                "business_rules": BUSINESS_RULES_PROMPT,
                "question": question,
                "sql": execution.original_sql,
                "columns": execution.columns,
                "row_count": execution.row_count,
                "execution_ms": execution.execution_ms,
                "rows_preview": rows_preview,
            }
        )
