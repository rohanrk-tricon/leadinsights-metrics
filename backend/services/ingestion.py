import requests
import psycopg2
import time
import ollama
from psycopg2.extras import execute_batch, Json
import logging
from backend.config import Config

logger = logging.getLogger(__name__)

class IngestionService:
    def __init__(self):
        self.db_config = Config.get_db_config()
        if not Config.FRESHDESK_DOMAIN or not Config.FRESHDESK_API_KEY:
             logger.warning("Freshdesk credentials not fully configured in env.")
        self.base_url = f"https://{Config.FRESHDESK_DOMAIN}.freshdesk.com/api/v2/tickets"
        self.per_page = 100
        self.max_retries = 3

    def get_db_connection(self):
        return psycopg2.connect(**self.db_config)

    def fetch_tickets(self, page):
        url = f"{self.base_url}?page={page}&per_page={self.per_page}"
        for attempt in range(self.max_retries):
            response = requests.get(url, auth=(Config.FRESHDESK_API_KEY, "X"))
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                logger.warning("Rate limit hit. Sleeping 10 seconds...")
                time.sleep(10)
            else:
                logger.error(f"API error: {response.text}")
                time.sleep(5)
        return []

    def transform_ticket(self, ticket):
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
            "embedding": None # Placeholder for embedding
        }

    def fetch_embedding(self, text):
        if not text.strip():
             return None
        try:
            response = ollama.embeddings(
                model=Config.OLLAMA_MODEL,
                prompt=text
            )
            return response.get("embedding")
        except Exception as e:
             logger.error(f"Ollama error: {e}")
             return None

    def insert_batch(self, cursor, tickets):
        insert_query = """
        INSERT INTO freshdesk_tickets (
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
            conn = self.get_db_connection()
            cursor = conn.cursor()
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            return {"status": "error", "message": f"DB Connection failed: {e}", "tickets_ingested": 0}

        page = 1
        total_inserted = 0

        while True:
            logger.info(f"Fetching page {page}...")
            tickets = self.fetch_tickets(page)
            if not tickets:
                logger.info("No more tickets to fetch.")
                break
            
            transformed = []
            for t in tickets:
                data = self.transform_ticket(t)
                # create embedding right away
                text_to_embed = f"{data.get('subject') or ''} {data.get('structured_description') or ''}"
                data["embedding"] = self.fetch_embedding(text_to_embed)
                transformed.append(data)
                
            self.insert_batch(cursor, transformed)
            conn.commit()
            
            total_inserted += len(transformed)
            logger.info(f"Inserted page {page} ({len(transformed)} tickets). Total: {total_inserted}")
            page += 1
            time.sleep(1)  # avoid API rate limits

        cursor.close()
        conn.close()
        logger.info("Ingestion complete.")
        return {"status": "success", "message": "Pipeline finished successfully", "tickets_ingested": total_inserted}

