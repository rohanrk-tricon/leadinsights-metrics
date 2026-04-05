import logging
from app.ticket_intelligence.utils.helpers import LLMHelper
from app.ticket_intelligence.utils.config_prompts import TicketPrompts
from app.ticket_intelligence.config.use_cases import UseCaseConfig

logger = logging.getLogger(__name__)

class TicketSemanticAgent:
    def __init__(self, llm_helper: LLMHelper, config: UseCaseConfig):
        self._llm_helper = llm_helper
        self._config = config

    def semantic_answer(self, question: str, tickets: list) -> str:
        logger.info("Generating semantic answer")
        prompt = TicketPrompts.semantic_answer_prompt(question, tickets, self._config)
        return self._llm_helper.call_llm(prompt)
