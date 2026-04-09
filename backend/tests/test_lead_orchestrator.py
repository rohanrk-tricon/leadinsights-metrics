import sys
import types
import unittest

from app.agents.models import QueryExecution, ValidationResult

sql_executor_stub = types.ModuleType("app.agents.sql_executor")
sql_executor_stub.SQLExecutionAgent = object
sys.modules.setdefault("app.agents.sql_executor", sql_executor_stub)

sql_generator_stub = types.ModuleType("app.agents.sql_generator")
sql_generator_stub.SQLGeneratorAgent = object
sys.modules.setdefault("app.agents.sql_generator", sql_generator_stub)

validator_stub = types.ModuleType("app.agents.validator")
validator_stub.ResponseValidatorAgent = object
sys.modules.setdefault("app.agents.validator", validator_stub)

config_stub = types.ModuleType("app.core.config")
config_stub.Settings = object
sys.modules.setdefault("app.core.config", config_stub)

from app.agents.orchestrator import QueryOrchestrator


class _FakeGenerator:
    def __init__(self, plans):
        self._plans = list(plans)
        self.feedback_history = []

    async def generate(self, question: str, schema_context: str, feedback: str | None = None):
        self.feedback_history.append(feedback)
        return self._plans.pop(0)


class _FakeExecutor:
    def __init__(self, executions):
        self._executions = list(executions)
        self.executed_sql = []

    async def get_schema_context(self):
        return "schema"

    async def execute(self, sql: str):
        self.executed_sql.append(sql)
        return self._executions.pop(0)


class _FakeValidator:
    def __init__(self, results):
        self._results = list(results)

    async def validate(self, question: str, execution: QueryExecution):
        return self._results.pop(0)


class _Settings:
    pass


class LeadOrchestratorTests(unittest.IsolatedAsyncioTestCase):
    async def test_validation_result_allows_missing_final_answer_for_retry(self):
        result = ValidationResult.model_validate(
            {
                "is_valid": False,
                "confidence": "low",
                "rationale": "Need a better grouped query.",
                "follow_up_sql": "SELECT 2 AS total;",
            }
        )

        self.assertEqual(result.final_answer, "")
        self.assertEqual(result.follow_up_sql, "SELECT 2 AS total;")

    async def test_stream_retries_when_validator_requests_follow_up_sql(self):
        initial_execution = QueryExecution(
            original_sql="SELECT 1 AS total;",
            executed_sql="SELECT 1 AS total;",
            columns=["total"],
            rows=[{"total": 1}],
            row_count=1,
            execution_ms=5.0,
        )
        retry_execution = QueryExecution(
            original_sql="SELECT 2 AS total;",
            executed_sql="SELECT 2 AS total;",
            columns=["total"],
            rows=[{"total": 2}],
            row_count=1,
            execution_ms=4.0,
        )
        generator = _FakeGenerator(
            [
                type(
                    "Plan",
                    (),
                    {
                        "sql": "SELECT 1 AS total;",
                        "reasoning": "Initial plan",
                        "expected_result_shape": "one row",
                    },
                )()
            ]
        )
        executor = _FakeExecutor([initial_execution, retry_execution])
        validator = _FakeValidator(
            [
                ValidationResult.model_validate(
                    {
                        "is_valid": False,
                        "confidence": "low",
                        "rationale": "Need a corrected query.",
                        "follow_up_sql": "SELECT 2 AS total;",
                    }
                ),
                ValidationResult.model_validate(
                    {
                        "is_valid": True,
                        "confidence": "high",
                        "final_answer": "There are 2 records.",
                        "rationale": "Validated against the retry result.",
                        "follow_up_sql": None,
                    }
                ),
            ]
        )

        orchestrator = QueryOrchestrator(generator, executor, validator, _Settings())

        events = []
        async for event in orchestrator.stream("How many sponsors were onboarded?"):
            events.append(event)

        self.assertIn(
            {
                "event": "status",
                "data": {
                    "stage": "retrying",
                    "message": "Validator requested a follow-up SQL query.",
                },
            },
            events,
        )
        self.assertEqual(executor.executed_sql, ["SELECT 1 AS total;", "SELECT 2 AS total;"])
        self.assertEqual(events[-1]["event"], "complete")
        self.assertEqual(events[-1]["data"]["answer"], "There are 2 records.")


if __name__ == "__main__":
    unittest.main()
