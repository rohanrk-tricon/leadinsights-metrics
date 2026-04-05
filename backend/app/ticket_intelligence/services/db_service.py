import logging
import psycopg2
from typing import Any
from langchain_aws import BedrockEmbeddings
import boto3

from app.core.config import Settings

logger = logging.getLogger(__name__)

class TicketDBService:
    def __init__(self, settings: Settings):
        self._settings = settings
        
        session = boto3.Session(
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            aws_session_token=settings.aws_session_token,
            region_name="us-east-1"
        )
        self.embeddings = BedrockEmbeddings(
            client=session.client("bedrock-runtime"),
            model_id=settings.bedrock_embedding_model
        )

    def get_db_connection(self):
        logger.debug("Opening PostgreSQL connection")
        return psycopg2.connect(
            host=self._settings.pg_host,
            port=self._settings.pg_port,
            dbname=self._settings.pg_database,
            user=self._settings.pg_user,
            password=self._settings.pg_password,
            sslmode="disable",
            gssencmode="disable",
            options=f"-c search_path={self._settings.ticket_schema},public",
        )

    def run_query(self, sql: str, params: tuple[Any, ...] | None = None) -> list[Any]:
        logger.info("Executing SQL query")
        logger.debug("SQL: %s", sql)

        with self.get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                results = cur.fetchall()

        logger.info("Query executed successfully, rows fetched: %d", len(results))
        return results

    def vector_search(self, question: str, top_k: int = 100) -> list[Any]:
        logger.info("Performing vector search")

        try:
            question_embedding = self.embeddings.embed_query(question)
            logger.debug("Embedding generated successfully")
        except Exception as e:
            logger.error("Failed to embed question: %s", e)
            raise

        emb_str = "[" + ",".join(map(str, question_embedding)) + "]"

        sql = """
            SELECT id, subject, structured_description
            FROM freshdesk_tickets
            WHERE embedding IS NOT NULL AND NOT ('spam' = ANY(tags))
            AND subject !~* 'automatic reply|respuesta automática|réponse automatique|export of tickets'
            AND type != 'Spam/Automated Email'
            ORDER BY embedding <-> %s
            LIMIT %s
        """

        try:
            with self.get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (emb_str, top_k))
                    results = cur.fetchall()

            logger.info("Vector search completed, results: %d", len(results))
            return results

        except Exception as e:
            logger.error("DB Vector search error: %s", e)
            raise
