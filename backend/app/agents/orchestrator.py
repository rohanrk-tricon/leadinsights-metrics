import logging
from time import perf_counter

from app.agents.sql_policy import build_policy_feedback
from app.agents.sql_executor import SQLExecutionAgent
from app.agents.sql_generator import SQLGeneratorAgent
from app.agents.validator import ResponseValidatorAgent
from app.core.config import Settings

logger = logging.getLogger(__name__)


class QueryOrchestrator:
    def __init__(
        self,
        generator: SQLGeneratorAgent,
        executor: SQLExecutionAgent,
        validator: ResponseValidatorAgent,
        settings: Settings,
    ) -> None:
        self._generator = generator
        self._executor = executor
        self._validator = validator
        self._settings = settings

    async def healthcheck(self) -> dict:
        return await self._executor.healthcheck()

    async def stream(self, question: str):
        started_at = perf_counter()
        logger.info(
            "Lead query stream started",
            extra={"question_length": len(question)},
        )
        yield {
            "event": "status",
            "data": {
                "stage": "accepted",
                "message": "Question accepted. Preparing schema context.",
            },
        }

        try:
            schema_context = await self._executor.get_schema_context()
            yield {
                "event": "status",
                "data": {
                    "stage": "planning",
                    "message": "Generating SQL from schema context.",
                },
            }

            plan = None
            feedback = None
            for attempt in range(1, 4):
                plan = await self._generator.generate(question, schema_context, feedback)
                policy_feedback = build_policy_feedback(question, plan.sql)
                if not policy_feedback:
                    break

                yield {
                    "event": "status",
                    "data": {
                        "stage": "refining_sql",
                        "message": f"SQL refinement pass {attempt}: {policy_feedback}",
                    },
                }
                logger.info(
                    "Lead query SQL refinement requested",
                    extra={"attempt": attempt, "question_length": len(question)},
                )
                feedback = policy_feedback
                if attempt == 3:
                    raise ValueError(policy_feedback)

            if plan is None:
                raise ValueError("The SQL generator did not produce a query.")
            yield {
                "event": "sql_generated",
                "data": {
                    "sql": plan.sql,
                    "reasoning": plan.reasoning,
                    "expected_result_shape": plan.expected_result_shape,
                },
            }

            yield {
                "event": "status",
                "data": {
                    "stage": "executing",
                    "message": "Executing SQL through the MCP database tool.",
                },
            }
            execution = await self._executor.execute(plan.sql)
            yield {
                "event": "query_executed",
                "data": execution.model_dump(),
            }

            yield {
                "event": "status",
                "data": {
                    "stage": "validating",
                    "message": "Validating the result and preparing the final answer.",
                },
            }
            validation = await self._validator.validate(question, execution)

            if not validation.is_valid and validation.follow_up_sql:
                policy_feedback = build_policy_feedback(question, validation.follow_up_sql)
                if policy_feedback:
                    raise ValueError(policy_feedback)
                yield {
                    "event": "status",
                    "data": {
                        "stage": "retrying",
                        "message": "Validator requested a follow-up SQL query.",
                    },
                }
                execution = await self._executor.execute(validation.follow_up_sql)
                yield {
                    "event": "query_executed",
                    "data": execution.model_dump(),
                }
                validation = await self._validator.validate(question, execution)

            if not validation.is_valid:
                raise ValueError(validation.rationale or "The validator could not produce a reliable final answer.")

            total_ms = round((perf_counter() - started_at) * 1000, 2)
            logger.info(
                "Lead query stream completed",
                extra={
                    "question_length": len(question),
                    "total_ms": total_ms,
                    "confidence": validation.confidence,
                },
            )
            answer = validation.final_answer or validation.rationale
            yield {
                "event": "complete",
                "data": {
                    "answer": answer,
                    "confidence": validation.confidence,
                    "rationale": validation.rationale,
                    "total_ms": total_ms,
                },
            }
        except Exception as exc:
            logger.exception(
                "Lead query stream failed",
                extra={"question_length": len(question), "error_type": type(exc).__name__},
            )
            yield {
                "event": "error",
                "data": {
                    "message": str(exc),
                },
            }
