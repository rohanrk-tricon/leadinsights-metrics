import logging
import time
from typing import Any
import requests
from psycopg2.extras import Json, execute_batch

from app.core.config import Settings
from app.ticket_intelligence.services.db_service import TicketDBService

logger = logging.getLogger(__name__)

class TicketIngestionService:
    def __init__(self, settings: Settings, db_service: TicketDBService) -> None:
        self._settings = settings
        self._db_service = db_service
        self._per_page = 100
        self._max_retries = 3
        self._base_url = None

        logger.info("Initializing TicketIngestionService")

        if settings.freshdesk_domain:
            self._base_url = (
                f"https://{settings.freshdesk_domain}.freshdesk.com/api/v2/tickets"
            )
            logger.info("Freshdesk base URL configured")
        else:
            logger.warning("Freshdesk domain not provided")

    def fetch_tickets(self, page: int) -> list[dict[str, Any]]:
        if not self._base_url or not self._settings.freshdesk_api_key:
            logger.error("Freshdesk credentials missing")
            raise ValueError("Freshdesk credentials are not configured.")

        url = f"{self._base_url}?page={page}&per_page={self._per_page}"
        logger.debug(f"Fetching tickets from URL: {url}")

        for attempt in range(self._max_retries):
            try:
                response = requests.get(
                    url,
                    auth=(self._settings.freshdesk_api_key, "X"),
                    timeout=30,
                )

                logger.debug(f"Freshdesk response status: {response.status_code}")

                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Fetched {len(data)} tickets from page {page}")
                    return data

                if response.status_code == 429:
                    logger.warning(
                        f"Rate limit hit (attempt {attempt + 1}/{self._max_retries}). Retrying in 10s..."
                    )
                    time.sleep(10)
                    continue

                logger.error(
                    f"Freshdesk API error (status {response.status_code}): {response.text}"
                )

            except requests.RequestException:
                logger.exception("Request to Freshdesk failed")

            time.sleep(5)

        logger.error(f"Failed to fetch tickets after {self._max_retries} retries (page {page})")
        return []

    def transform_ticket(self, ticket: dict[str, Any]) -> dict[str, Any]:
        try:
            transformed = {
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

            logger.debug(f"Transformed ticket ID: {transformed['id']}")
            return transformed

        except Exception:
            logger.exception(f"Failed to transform ticket: {ticket.get('id')}")
            raise

    def fetch_embedding(self, text):
        if not text.strip():
            logger.debug("Skipping embedding for empty text")
            return None

        try:
            embedding = self._db_service.embeddings.embed_query(text)
            logger.debug("Embedding generated successfully")
            return embedding
        except Exception:
            logger.exception("Bedrock embedding error")
            return None

    def insert_batch(self, cursor, tickets: list[dict[str, Any]]) -> None:
        logger.info(f"Inserting batch of {len(tickets)} tickets into DB")

        insert_query = f"""
        INSERT INTO {self._settings.ticket_schema}.freshdesk_tickets (
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

    def run_pipeline(self):
        logger.info("Starting ingestion pipeline...")

        try:
            conn = self._db_service.get_db_connection()
            cursor = conn.cursor()
        except Exception as e:
            return {
                "status": "error",
                "message": f"DB Connection failed: {e}",
                "tickets_ingested": 0,
            }

        page = 1
        total_inserted = 0

        while True:
            logger.info(f"Processing page {page}")

            tickets = self.fetch_tickets(page)
            if not tickets:
                logger.info("No more tickets to fetch. Ending pipeline.")
                break

            transformed = []

            for t in tickets:
                try:
                    data = self.transform_ticket(t)

                    text_to_embed = f"{data.get('subject') or ''} {data.get('structured_description') or ''}"
                    data["embedding"] = self.fetch_embedding(text_to_embed)

                    transformed.append(data)
                except Exception:
                    logger.exception(f"Skipping failed ticket ID: {t.get('id')}")

            try:
                self.insert_batch(cursor, transformed)
                conn.commit()
                logger.info(f"Committed page {page} to database")
            except Exception:
                logger.exception("Transaction failed, rolling back")
                conn.rollback()
                break

            total_inserted += len(transformed)
            logger.info(
                f"Page {page} complete | Inserted: {len(transformed)} | Total: {total_inserted}"
            )

            page += 1
            time.sleep(1)

        cursor.close()
        conn.close()

        logger.info(f"Ingestion complete. Total tickets ingested: {total_inserted}")

        return {
            "status": "success",
            "message": "Pipeline finished successfully",
            "tickets_ingested": total_inserted,
        }
