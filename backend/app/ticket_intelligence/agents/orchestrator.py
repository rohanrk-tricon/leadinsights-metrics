import logging
from app.ticket_intelligence.agents.sql_agent import TicketSQLAgent
from app.ticket_intelligence.agents.semantic_agent import TicketSemanticAgent
from app.ticket_intelligence.services.db_service import TicketDBService
from app.ticket_intelligence.utils.helpers import LLMHelper
from app.ticket_intelligence.utils.config_prompts import TicketPrompts
from app.ticket_intelligence.config.use_cases import UseCaseConfig
from app.core.config import Settings
from app.ticket_intelligence.services.reranker import get_reranker

logger = logging.getLogger(__name__)

class TicketIntelligenceOrchestrator:
    def __init__(
        self,
        llm_helper: LLMHelper,
        db_service: TicketDBService,
        settings: Settings,
        config: UseCaseConfig
    ):
        self._llm_helper = llm_helper
        self._db_service = db_service
        self._settings = settings
        self._config = config

        schema_prompt = TicketPrompts.get_schema_prompt(
            settings.ticket_schema, settings.ticket_support_email, config
        )

        self._sql_agent = TicketSQLAgent(llm_helper, schema_prompt, config)
        self._semantic_agent = TicketSemanticAgent(llm_helper, config)

    def classify_question(self, question: str) -> str:
        logger.info("Classifying question: %s", question)
        prompt = TicketPrompts.classify_question_prompt(question)
        result = self._llm_helper.call_llm(prompt).strip()
        logger.info("Classification result: %s", result)
        return result

    def process_query(self, question: str):
        logger.info("Processing query: %s", question)

        qtype = self.classify_question(question)

        if "SQL_ANALYTICS" in qtype:
            logger.info("Routing to SQL analytics pipeline")

            sql = self._sql_agent.generate_sql(question)

            max_retries = 3
            attempt = 0
            last_error = ""
            current_sql = sql

            while attempt < max_retries:
                attempt += 1
                logger.info("SQL attempt %d/%d", attempt, max_retries)

                if not self._llm_helper.is_safe_sql(current_sql):
                    logger.warning("Initial SQL failed safety check")

                validated_sql = self._sql_agent.validate_sql_with_llm(question, current_sql)

                if not self._llm_helper.is_safe_sql(validated_sql):
                    logger.error("SQL unsafe after validation")
                    return "SQL_ANALYTICS", "Security violation detected", [], validated_sql

                current_sql = validated_sql

                try:
                    rows = self._db_service.run_query(current_sql)
                    explanation = self._sql_agent.explain_result(question, current_sql, rows)

                    logger.info("SQL pipeline succeeded")
                    return "SQL_ANALYTICS", explanation, rows, current_sql

                except Exception as e:
                    last_error = str(e)
                    logger.warning("SQL failed attempt %d: %s", attempt, last_error)

                    if attempt < max_retries:
                        current_sql = self._sql_agent.fix_sql(question, current_sql, last_error)
                    else:
                        logger.error("Max retries reached")

            explanation = f"Query failed after {max_retries} attempts. Error: {last_error}"
            return "SQL_ANALYTICS", explanation, [], current_sql

        else:
            logger.info("Routing to semantic search pipeline")

            # 1. Candidate Retrieval (Recall Phase - Top 100 via vector bounds)
            candidates = self._db_service.vector_search(question, top_k=100)
            
            # 2. Precision Reranking via Cross-Encoder (Precision Phase - Top 5)
            reranker = get_reranker()
            tickets = reranker.rerank(question, candidates, top_k=5)

            # 3. Deterministic safe LLM Synthesis
            answer = self._semantic_agent.semantic_answer(question, tickets)

            logger.info("Semantic search completed")
            return "SEMANTIC_SEARCH", answer, tickets, None
