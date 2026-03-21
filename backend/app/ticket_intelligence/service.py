from __future__ import annotations

import logging
import re
import time
from typing import Any

import psycopg2
import requests
from langchain_core.messages import HumanMessage
from psycopg2.extras import Json, execute_batch

from app.core.config import Settings
from app.llm.strategy import ModelStrategyFactory

logger = logging.getLogger(__name__)


class TicketIntelligenceService:
    def __init__(self, settings: Settings, model_factory: ModelStrategyFactory) -> None:
        self._settings = settings
        self._llm = model_factory.build_chat_model(temperature=0)

    @property
    def _ticket_table(self) -> str:
        return f"{self._settings.ticket_schema}.freshdesk_tickets"

    @property
    def _schema_prompt(self) -> str:
        return f"""
        Database: PostgreSQL
        Table: {self._ticket_table}
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
        - Use ONLY {self._ticket_table}
        - Always apply cleaning rules and filter LeadInsights
        - Lower case subject filtering: LOWER(subject)
        - Array filtering: To check if a tag exists, use 'tag_name' = ANY(tags). To exclude, use NOT ('spam' = ANY(tags)).
        """.strip()

    def get_db_connection(self):
        return psycopg2.connect(
            host=self._settings.pg_host,
            port=self._settings.pg_port,
            dbname=self._settings.pg_database,
            user=self._settings.pg_user,
            password=self._settings.pg_password,
            options=f"-c search_path={self._settings.ticket_schema},public",
        )

    def _call_llm(self, prompt: str) -> str:
        response = self._llm.invoke([HumanMessage(content=prompt)])
        content = getattr(response, "content", response)
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
        prompt = f"""
        Classify the question. Categories: SQL_ANALYTICS or SEMANTIC_SEARCH. Return ONLY one word.
        Examples:
        How many tickets last month -> SQL_ANALYTICS
        Average resolution time -> SQL_ANALYTICS
        Most repeated tickets -> SEMANTIC_SEARCH
        Summarize ticket problems -> SEMANTIC_SEARCH

        Question: {question}
        """
        return self._call_llm(prompt).strip()

    def extract_sql(self, text: str) -> str:
        match = re.search(r"```(?:sql)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()

        match_select = re.search(r"(SELECT\s+.*)", text, re.DOTALL | re.IGNORECASE)
        if match_select:
            return match_select.group(1).strip()

        return text.strip()

    def generate_sql(self, question: str) -> str:
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
        sql_lower = sql.lower().strip()
        if not sql_lower.startswith("select"):
            return False

        banned = [
            r"\bdelete\b",
            r"\bdrop\b",
            r"\bupdate\b",
            r"\binsert\b",
            r"\btruncate\b",
            r"\balter\b",
        ]
        return not any(re.search(pattern, sql_lower) for pattern in banned)

    def run_query(self, sql: str, params: tuple[Any, ...] | None = None) -> list[Any]:
        with self.get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchall()

    def extract_search_terms(self, question: str) -> list[str]:
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
            return terms[:6]

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

    def vector_search(self, question: str) -> list[Any]:
        terms = self.extract_search_terms(question)
        if not terms:
            terms = [question]

        patterns = [f"%{term.lower()}%" for term in terms]
        subject_filters = " OR ".join(["LOWER(subject) LIKE %s"] * len(patterns))
        description_filters = " OR ".join(
            ["LOWER(COALESCE(structured_description, '')) LIKE %s"] * len(patterns)
        )
        tag_filters = " OR ".join(
            ["LOWER(COALESCE(array_to_string(tags, ' '), '')) LIKE %s"] * len(patterns)
        )

        sql = f"""
            SELECT subject, structured_description, created_at, status
            FROM {self._ticket_table}
            WHERE support_email = %s
              AND NOT ('spam' = ANY(COALESCE(tags, ARRAY[]::text[])))
              AND LOWER(COALESCE(subject, '')) NOT LIKE '%%automatic reply%%'
              AND LOWER(COALESCE(subject, '')) NOT LIKE '%%respuesta automática%%'
              AND LOWER(COALESCE(subject, '')) NOT LIKE '%%réponse automatique%%'
              AND LOWER(COALESCE(subject, '')) NOT LIKE '%%export of tickets%%'
              AND ({subject_filters} OR {description_filters} OR {tag_filters})
            ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST
            LIMIT 10
        """
        params = (
            self._settings.ticket_support_email,
            *patterns,
            *patterns,
            *patterns,
        )
        return self.run_query(sql, params)

    def semantic_answer(self, question: str, tickets: list[Any]) -> str:
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

        Format the output as a concise bulleted list based only on the result data.
        Do not explain how the query was generated.
        """
        return self._call_llm(prompt)

    def fix_sql(self, question: str, bad_sql: str, error: str) -> str:
        prompt = f"""
        The following SQL is invalid.
        Question: {question}
        Bad SQL: {bad_sql}
        Error: {error}

        Fix it and return ONLY the corrected SQL.
        """
        return self.extract_sql(self._call_llm(prompt))

    def process_query(self, question: str):
        query_type = self.classify_question(question)
        if "SQL_ANALYTICS" in query_type:
            sql = self.generate_sql(question)
            if not self.is_safe_sql(sql):
                return (
                    "SQL_ANALYTICS",
                    "Unsafe SQL generated by AI, query blocked for security.",
                    [],
                    sql,
                )

            try:
                rows = self.run_query(sql)
            except Exception as exc:
                logger.warning("Initial ticket SQL failed, attempting auto-fix: %s", exc)
                fixed_sql = self.fix_sql(question, sql, str(exc))
                rows = self.run_query(fixed_sql)
                sql = fixed_sql

            return (
                "SQL_ANALYTICS",
                self.explain_result(question, sql, rows),
                rows,
                sql,
            )

        tickets = self.vector_search(question)
        return (
            "SEMANTIC_SEARCH",
            self.semantic_answer(question, tickets),
            tickets,
            None,
        )


class TicketIngestionService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._per_page = 100
        self._max_retries = 3
        self._base_url = None
        if settings.freshdesk_domain:
            self._base_url = (
                f"https://{settings.freshdesk_domain}.freshdesk.com/api/v2/tickets"
            )

    def get_db_connection(self):
        return psycopg2.connect(
            host=self._settings.pg_host,
            port=self._settings.pg_port,
            dbname=self._settings.pg_database,
            user=self._settings.pg_user,
            password=self._settings.pg_password,
        )

    def fetch_tickets(self, page: int) -> list[dict[str, Any]]:
        if not self._base_url or not self._settings.freshdesk_api_key:
            raise ValueError("Freshdesk credentials are not configured.")

        url = f"{self._base_url}?page={page}&per_page={self._per_page}"
        for attempt in range(self._max_retries):
            response = requests.get(
                url,
                auth=(self._settings.freshdesk_api_key, "X"),
                timeout=30,
            )
            if response.status_code == 200:
                return response.json()
            if response.status_code == 429:
                logger.warning("Freshdesk rate limit hit on attempt %s. Sleeping 10 seconds.", attempt + 1)
                time.sleep(10)
                continue

            logger.error("Freshdesk API error: %s", response.text)
            time.sleep(5)
        return []

    def transform_ticket(self, ticket: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": ticket.get("id"),
            "email_config_id": ticket.get("email_config_id"),
            "group_id": ticket.get("group_id"),
            "priority": ticket.get("priority"),
            "requester_id": ticket.get("requester_id"),
            "responder_id": ticket.get("responder_id"),
            "source": ticket.get("source"),
            "company_id": ticket.get("company_id"),
            "status": ticket.get("status"),
            "product_id": ticket.get("product_id"),
            "subject": ticket.get("subject"),
            "support_email": ticket.get("support_email"),
            "type": ticket.get("type"),
            "association_type": ticket.get("association_type"),
            "fr_escalated": ticket.get("fr_escalated"),
            "spam": ticket.get("spam"),
            "is_escalated": ticket.get("is_escalated"),
            "created_at": ticket.get("created_at"),
            "updated_at": ticket.get("updated_at"),
            "due_by": ticket.get("due_by"),
            "fr_due_by": ticket.get("fr_due_by"),
            "associated_tickets_count": ticket.get("associated_tickets_count"),
            "cc_emails": ticket.get("cc_emails"),
            "fwd_emails": ticket.get("fwd_emails"),
            "reply_cc_emails": ticket.get("reply_cc_emails"),
            "ticket_cc_emails": ticket.get("ticket_cc_emails"),
            "ticket_bcc_emails": ticket.get("ticket_bcc_emails"),
            "to_emails": ticket.get("to_emails"),
            "tags": ticket.get("tags"),
            "structured_description": ticket.get("description_text"),
            "custom_fields": Json(ticket.get("custom_fields")),
            "raw_payload": Json(ticket),
            "embedding": None,
        }

    def insert_batch(self, cursor, tickets: list[dict[str, Any]]) -> None:
        insert_query = f"""
        INSERT INTO {self._ticket_table} (
            id, email_config_id, group_id, priority, requester_id, responder_id, source, company_id,
            status, product_id, subject, support_email, type, association_type, fr_escalated, spam,
            is_escalated, created_at, updated_at, due_by, fr_due_by, associated_tickets_count,
            cc_emails, fwd_emails, reply_cc_emails, ticket_cc_emails, ticket_bcc_emails, to_emails,
            tags, structured_description, custom_fields, raw_payload, embedding
        )
        VALUES (
            %(id)s, %(email_config_id)s, %(group_id)s, %(priority)s, %(requester_id)s, %(responder_id)s, %(source)s, %(company_id)s,
            %(status)s, %(product_id)s, %(subject)s, %(support_email)s, %(type)s, %(association_type)s, %(fr_escalated)s, %(spam)s,
            %(is_escalated)s, %(created_at)s, %(updated_at)s, %(due_by)s, %(fr_due_by)s, %(associated_tickets_count)s,
            %(cc_emails)s, %(fwd_emails)s, %(reply_cc_emails)s, %(ticket_cc_emails)s, %(ticket_bcc_emails)s, %(to_emails)s,
            %(tags)s, %(structured_description)s, %(custom_fields)s, %(raw_payload)s, %(embedding)s
        )
        ON CONFLICT (id) DO UPDATE
        SET
            email_config_id = EXCLUDED.email_config_id,
            group_id = EXCLUDED.group_id,
            priority = EXCLUDED.priority,
            requester_id = EXCLUDED.requester_id,
            responder_id = EXCLUDED.responder_id,
            source = EXCLUDED.source,
            company_id = EXCLUDED.company_id,
            status = EXCLUDED.status,
            product_id = EXCLUDED.product_id,
            subject = EXCLUDED.subject,
            support_email = EXCLUDED.support_email,
            type = EXCLUDED.type,
            association_type = EXCLUDED.association_type,
            fr_escalated = EXCLUDED.fr_escalated,
            spam = EXCLUDED.spam,
            is_escalated = EXCLUDED.is_escalated,
            created_at = EXCLUDED.created_at,
            updated_at = EXCLUDED.updated_at,
            due_by = EXCLUDED.due_by,
            fr_due_by = EXCLUDED.fr_due_by,
            associated_tickets_count = EXCLUDED.associated_tickets_count,
            cc_emails = EXCLUDED.cc_emails,
            fwd_emails = EXCLUDED.fwd_emails,
            reply_cc_emails = EXCLUDED.reply_cc_emails,
            ticket_cc_emails = EXCLUDED.ticket_cc_emails,
            ticket_bcc_emails = EXCLUDED.ticket_bcc_emails,
            to_emails = EXCLUDED.to_emails,
            tags = EXCLUDED.tags,
            structured_description = EXCLUDED.structured_description,
            custom_fields = EXCLUDED.custom_fields,
            raw_payload = EXCLUDED.raw_payload,
            embedding = EXCLUDED.embedding
        """
        execute_batch(cursor, insert_query, tickets, page_size=100)

    def run_pipeline(self) -> dict[str, Any]:
        logger.info("Starting Freshdesk ingestion pipeline.")
        conn = self.get_db_connection()
        cursor = conn.cursor()

        page = 1
        total_inserted = 0
        try:
            while True:
                tickets = self.fetch_tickets(page)
                if not tickets:
                    break

                transformed = []
                for ticket in tickets:
                    data = self.transform_ticket(ticket)
                    transformed.append(data)

                self.insert_batch(cursor, transformed)
                conn.commit()
                total_inserted += len(transformed)
                page += 1
                time.sleep(1)
        finally:
            cursor.close()
            conn.close()

        logger.info("Freshdesk ingestion complete. Inserted %s tickets.", total_inserted)
        return {
            "status": "success",
            "message": "Pipeline finished successfully.",
            "tickets_ingested": total_inserted,
        }
