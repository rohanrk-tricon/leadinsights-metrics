from __future__ import annotations

import logging
import re
import time
from typing import Any

import psycopg2
import requests
import boto3
from langchain_core.messages import HumanMessage
from langchain_aws import BedrockEmbeddings
from psycopg2.extras import Json, execute_batch

from app.core.config import Settings
from app.llm.strategy import ModelStrategyFactory

logger = logging.getLogger(__name__)


class TicketIntelligenceService:
    def __init__(self, settings: Settings, model_factory: ModelStrategyFactory) -> None:
        logger.info("Initializing TicketIntelligenceService")

        self._settings = settings
        self._llm = model_factory.build_chat_model(temperature=0)

        session = boto3.Session(
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            aws_session_token=settings.aws_session_token,
            region_name=settings.aws_region
        )

        logger.info("Initializing Bedrock embeddings client")
        self.embeddings = BedrockEmbeddings(
            client=session.client("bedrock-runtime"),
            model_id=settings.bedrock_embedding_model
        )

    @property
    def _ticket_table(self) -> str:
        return f"{self._settings.ticket_schema}.freshdesk_tickets"

    @property
    def _schema_prompt(self) -> str:
        return f"""
        Database: PostgreSQL
        Table: "{self._settings.ticket_schema}.freshdesk_tickets"
        Columns:
        id BIGINT
        support_email TEXT
        group_id BIGINT
        priority INTEGER
        requester_id BIGINT
        responder_id BIGINT
        status INTEGER
        subject TEXT
        created_at TIMESTAMPTZ
        updated_at TIMESTAMPTZ
        due_by TIMESTAMPTZ
        fr_due_by TIMESTAMPTZ
        tags TEXT[]
        structured_description TEXT

        Status Codes:
        2 = Open, 3 = Pending, 4 = Resolved, 5 = Closed

        Business Rules:
        1. Filter LeadInsights using: support_email = '{self._settings.ticket_support_email}'
        2. Closed tickets include statuses IN (4,5)
        3. Resolution time only calculated for resolved/closed tickets.

        Cleaning Rules (Exclusions):
        - tags array contains 'spam' (e.g. 'spam' = ANY(tags))
        - subject contains: 'automatic reply', 'respuesta automática', 'réponse automatique', 'export of tickets'

        SQL Rules:
        - Use ONLY f"{self._settings.ticket_schema}.freshdesk_tickets"
        - Always apply cleaning rules and filter LeadInsights
        - Lower case subject filtering: LOWER(subject)
        - Array filtering: To check if a tag exists, use 'tag_name' = ANY(tags). To exclude, use NOT ('spam' = ANY(tags)).
        """.strip()

    def get_db_connection(self):
        logger.debug("Opening PostgreSQL connection")
        return psycopg2.connect(
            host=self._settings.pg_host,
            port=self._settings.pg_port,
            dbname=self._settings.pg_database,
            user=self._settings.pg_user,
            password=self._settings.pg_password,
            options=f"-c search_path={self._settings.ticket_schema},public",
        )

    def _call_llm(self, prompt: str) -> str:
        logger.debug("Calling LLM with prompt (truncated): %s", prompt[:200])

        response = self._llm.invoke([HumanMessage(content=prompt)])
        content = getattr(response, "content", response)

        logger.debug("LLM response received")

        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    parts.append(str(item.get("text") or item.get("content") or item))
                else:
                    parts.append(str(getattr(item, "text", item)))
            return "\n".join(part for part in parts if part)
        return str(content)

    def classify_question(self, question: str) -> str:
        logger.info("Classifying question: %s", question)
        prompt = f"""
        Classify the question. Categories: SQL_ANALYTICS or SEMANTIC_SEARCH. Return ONLY one word.
        Examples:
        How many tickets last month -> SQL_ANALYTICS
        Average resolution time -> SQL_ANALYTICS
        Most repeated tickets -> SEMANTIC_SEARCH
        Summarize ticket problems -> SEMANTIC_SEARCH

        Question: {question}
        """
        result = self._call_llm(prompt).strip()
        logger.info("Classification result: %s", result)
        return result

    def extract_sql(self, text: str) -> str:
        logger.debug("Extracting SQL from LLM response")

        match = re.search(r"```(?:sql)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()

        match_select = re.search(r"(SELECT\s+.*)", text, re.DOTALL | re.IGNORECASE)
        if match_select:
            return match_select.group(1).strip()

        return text.strip()

    def generate_sql(self, question: str) -> str:
        logger.info("Generating SQL for question: %s", question)
        prompt = f"""
        You are a PostgreSQL expert.
        Database schema: {self._schema_prompt}

        Rules:
        - Only SELECT queries.
        - PostgreSQL syntax.
        - Always filter LeadInsights tickets.
        - Apply cleaning rules.
        - Return ONLY the SQL code. Start immediately with SELECT.

        Question: {question}
        """
        return self.extract_sql(self._call_llm(prompt))

    def is_safe_sql(self, sql: str) -> bool:
        logger.debug("Running basic SQL safety check")

        sql_lower = sql.lower().strip()
        if not sql_lower.startswith("select"):
            logger.warning("SQL does not start with SELECT")
            return False

        banned = [r";\s*delete\b", r"\bdrop\b", r"\bupdate\b", r"\binsert\b", r"\btruncate\b", r"\balter\b"]
        is_safe = not any(re.search(pattern, sql_lower) for pattern in banned)

        if not is_safe:
            logger.warning("SQL contains potentially dangerous patterns")

        return is_safe

    def run_query(self, sql: str, params: tuple[Any, ...] | None = None) -> list[Any]:
        logger.info("Executing SQL query")
        logger.debug("SQL: %s", sql)

        with self.get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                results = cur.fetchall()

        logger.info("Query executed successfully, rows fetched: %d", len(results))
        return results

    def extract_search_terms(self, question: str) -> list[str]:
        logger.info("Extracting search terms")
        prompt = f"""
        Extract up to 6 short search terms or phrases from this ticket-support question.
        Return one term per line with no numbering or extra commentary.

        Question: {question}
        """
        raw_terms = self._call_llm(prompt)

        terms = [
            term.strip(" -*")
            for term in raw_terms.splitlines()
            if term.strip(" -*")
        ]

        if terms:
            logger.debug("Extracted terms: %s", terms[:6])
            return terms[:6]

        logger.warning("LLM failed to extract terms, using fallback")

        fallback_terms = re.findall(r"[a-zA-Z0-9][a-zA-Z0-9_-]{2,}", question.lower())
        stopwords = {
            "what",
            "which",
            "when",
            "where",
            "have",
            "with",
            "that",
            "this",
            "from",
            "were",
            "your",
            "about",
            "ticket",
            "tickets",
        }
        deduped = []
        for term in fallback_terms:
            if term in stopwords or term in deduped:
                continue
            deduped.append(term)
        return deduped[:6]

    def vector_search(self, question: str):
        logger.info("Performing vector search")

        try:
            question_embedding = self.embeddings.embed_query(question)
            logger.debug("Embedding generated successfully")
        except Exception as e:
            logger.error("Failed to embed question: %s", e)
            raise

        emb_str = "[" + ",".join(map(str, question_embedding)) + "]"

        sql = """
            SELECT subject, structured_description
            FROM freshdesk_tickets
            WHERE embedding IS NOT NULL
            ORDER BY embedding <-> %s
            LIMIT 10
        """

        try:
            with self.get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (emb_str,))
                    results = cur.fetchall()

            logger.info("Vector search completed, results: %d", len(results))
            return results

        except Exception as e:
            logger.error("DB Vector search error: %s", e)
            raise

    def semantic_answer(self, question: str, tickets: list[Any]) -> str:
        logger.info("Generating semantic answer")
        prompt = f"""
        User question: {question}
        Relevant tickets: {tickets}

        Identify common themes and explain them clearly.
        Format the response using concise markdown with short headings and bullet points.
        """
        return self._call_llm(prompt)

    def explain_result(self, question: str, sql: str, rows: list[Any]) -> str: 
        prompt = f""" 
        User question: {question} 
        Result data: {rows} 
        SQL used: {sql} 

        Format the output as a concise bulleted list based only on the result data. Do not explain how the query was generated. """
        return self._call_llm(prompt)


    def validate_sql_with_llm(self, question: str, sql: str) -> str:
        logger.info("Validating SQL with LLM")

        prompt = f"""
        You are a security and SQL validation expert.
        Review the following SQL query to ensure it safely and correctly answers the user's question.
        
        Question: {question}
        Original SQL: {sql}
        Database Schema: {self._schema_prompt}

        Validation Rules:
        1. NO destructive operations (DROP, DELETE, ALTER, UPDATE, INSERT, TRUNCATE). Only SELECT is allowed. (Note: The word 'delete' is allowed in string literals to search for textual matches).
        2. NO SQL injection patterns (e.g., OR 1=1, UNION SELECT).
        3. Must be perfectly formed PostgreSQL syntax.
        4. Query MUST match the user's intent based on the Question and the Schema.

        If the Original SQL is safe and perfectly answers the question, output ONLY the Original SQL. DO NOT include any conversational text.
        If the Original SQL violates any rules, or doesn't match the intent, rewrite it to be safe and correct. Output ONLY the rewritten SQL. DO NOT include any conversational text like "Here is the fixed query". Start immediately with SELECT.
        """
        validated = self.extract_sql(self._call_llm(prompt))

        logger.debug("Validated SQL: %s", validated)
        return validated

    def fix_sql(self, question: str, bad_sql: str, error: str) -> str:
        logger.warning("Fixing SQL after failure. Error: %s", error)

        prompt = f"""
        You are a PostgreSQL expert debugging a failed query.
        
        Question: {question}
        Database schema: {self._schema_prompt}
        Bad SQL: {bad_sql}
        Error message from database: {error}
        
        Step 1: Reason about the error. Why did this query fail in PostgreSQL based on the schema? Think step-by-step.
        Step 2: Act. Write the corrected SQL query that fixes the problem and answers the question.
        
        Output format:
        Reasoning: [your analysis here]
        ```sql
        [your corrected SQL query here]
        ```
        """
        fixed_sql = self.extract_sql(self._call_llm(prompt))

        logger.debug("Fixed SQL: %s", fixed_sql)
        return fixed_sql

    def process_query(self, question: str):
        logger.info("Processing query: %s", question)

        qtype = self.classify_question(question)

        if "SQL_ANALYTICS" in qtype:
            logger.info("Routing to SQL analytics pipeline")

            sql = self.generate_sql(question)

            max_retries = 3
            attempt = 0
            last_error = ""
            current_sql = sql

            while attempt < max_retries:
                attempt += 1
                logger.info("SQL attempt %d/%d", attempt, max_retries)

                if not self.is_safe_sql(current_sql):
                    logger.warning("Initial SQL failed safety check")

                validated_sql = self.validate_sql_with_llm(question, current_sql)

                if not self.is_safe_sql(validated_sql):
                    logger.error("SQL unsafe after validation")
                    return "SQL_ANALYTICS", "Security violation detected", [], validated_sql

                current_sql = validated_sql

                try:
                    rows = self.run_query(current_sql)
                    explanation = self.explain_result(question, current_sql, rows)

                    logger.info("SQL pipeline succeeded")
                    return "SQL_ANALYTICS", explanation, rows, current_sql

                except Exception as e:
                    last_error = str(e)
                    logger.warning("SQL failed attempt %d: %s", attempt, last_error)

                    if attempt < max_retries:
                        current_sql = self.fix_sql(question, current_sql, last_error)
                    else:
                        logger.error("Max retries reached")

            explanation = f"Query failed after {max_retries} attempts. Error: {last_error}"
            return "SQL_ANALYTICS", explanation, [], current_sql

        else:
            logger.info("Routing to semantic search pipeline")

            tickets = self.vector_search(question)
            answer = self.semantic_answer(question, tickets)

            logger.info("Semantic search completed")
            return "SEMANTIC_SEARCH", answer, tickets, None