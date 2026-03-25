import logging
from app.ticket_intelligence.utils.helpers import LLMHelper
from app.ticket_intelligence.utils.config_prompts import TicketPrompts
from app.ticket_intelligence.config.use_cases import UseCaseConfig

logger = logging.getLogger(__name__)

class TicketSQLAgent:
    def __init__(self, llm_helper: LLMHelper, schema_prompt: str, config: UseCaseConfig):
        self._llm_helper = llm_helper
        self._schema_prompt = schema_prompt
        self._config = config

    def generate_sql(self, question: str) -> str:
        logger.info("Generating SQL for question: %s", question)
        prompt = TicketPrompts.generate_sql_prompt(question, self._schema_prompt, self._config)
        response_text = self._llm_helper.call_llm(prompt)
        return self._llm_helper.extract_sql(response_text)

    def validate_sql_with_llm(self, question: str, sql: str) -> str:
        logger.info("Validating SQL with LLM")
        prompt = TicketPrompts.validate_sql_prompt(question, sql, self._schema_prompt)
        response_text = self._llm_helper.call_llm(prompt)
        validated = self._llm_helper.extract_sql(response_text)
        logger.debug("Validated SQL: %s", validated)
        return validated

    def fix_sql(self, question: str, bad_sql: str, error: str) -> str:
        logger.warning("Fixing SQL after failure. Error: %s", error)
        prompt = TicketPrompts.fix_sql_prompt(question, bad_sql, error, self._schema_prompt)
        response_text = self._llm_helper.call_llm(prompt)
        fixed_sql = self._llm_helper.extract_sql(response_text)
        logger.debug("Fixed SQL: %s", fixed_sql)
        return fixed_sql

    def explain_result(self, question: str, sql: str, rows: list) -> str:
        logger.info("Explaining the SQL result")
        prompt = TicketPrompts.explain_result_prompt(question, sql, rows)
        return self._llm_helper.call_llm(prompt)
