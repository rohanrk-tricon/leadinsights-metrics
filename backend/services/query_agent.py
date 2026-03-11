import re
import psycopg2
import logging
from langchain_aws import ChatBedrock
from langchain_core.messages import HumanMessage
from backend.config import Config

logger = logging.getLogger(__name__)

class QueryAgentService:
    SCHEMA_PROMPT = """
    Database: PostgreSQL
    Table: freshdesk_tickets
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
    1. Filter LeadInsights using: support_email = 'informacomleadinsights@leadinsights.freshdesk.com'
    2. Closed tickets include statuses IN (4,5)
    3. Resolution time only calculated for resolved/closed tickets.

    Cleaning Rules (Exclusions):
    - tags array contains 'spam' (e.g., 'spam' = ANY(tags))
    - subject contains: 'automatic reply', 'respuesta automática', 'réponse automatique', 'export of tickets'

    SQL Rules:
    - Use ONLY freshdesk_tickets
    - Always apply cleaning rules and filter LeadInsights
    - Lower case subject filtering: LOWER(subject)
    - Array filtering: To check if a tag exists, use `'tag_name' = ANY(tags)`. To exclude, use `NOT ('spam' = ANY(tags))`.
    """

    def __init__(self):
        self.db_config = Config.get_db_config()
        self.llm = ChatBedrock(
            model_id="anthropic.claude-3-haiku-20240307-v1:0",
            region_name=Config.AWS_REGION,
            aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
            aws_session_token=Config.AWS_SESSION_TOKEN
        )

    def get_db_connection(self):
        return psycopg2.connect(**self.db_config)

    def _call_llm(self, prompt: str) -> str:
        try:
             response = self.llm.invoke([HumanMessage(content=prompt)])
             return response.content
        except Exception as e:
             logger.error(f"LLM Error: {e}")
             return f"Error: {str(e)}"

    def classify_question(self, question: str) -> str:
        prompt = f"""
        Classify the question. Categories: SQL_ANALYTICS or SEMANTIC_SEARCH. Return ONLY one word.
        Examples:
        How many tickets last month → SQL_ANALYTICS
        Average resolution time → SQL_ANALYTICS
        Most repeated tickets → SEMANTIC_SEARCH
        Summarize ticket problems → SEMANTIC_SEARCH

        Question: {question}
        """
        return self._call_llm(prompt).strip()

    def extract_sql(self, text: str) -> str:
        # Sometimes Claude returns ```sql \n ... \n ```
        match = re.search(r'```(?:sql)?\s*(.*?)\s*```', text, re.DOTALL | re.IGNORECASE)
        if match:
             return match.group(1).strip()
        # Fallback 1: Find the first SELECT ignoring anything before it
        match_select = re.search(r'(SELECT\s+.*)', text, re.DOTALL | re.IGNORECASE)
        if match_select:
             return match_select.group(1).strip()
        # Fallback 2: just stripping the whole text
        return text.strip()

    def generate_sql(self, question: str) -> str:
        prompt = f"""
        You are a PostgreSQL expert.
        Database schema: {self.SCHEMA_PROMPT}

        Rules:
        - Only SELECT queries.
        - PostgreSQL syntax.
        - Always filter LeadInsights tickets.
        - Apply cleaning rules.
        - Return ONLY the SQL code. DO NOT wrap it in backticks, do not include any conversational text like "Here is the SQL". Start immediately with SELECT.

        Question: {question}
        """
        response_text = self._call_llm(prompt)
        return self.extract_sql(response_text)

    def is_safe_sql(self, sql: str) -> bool:
        sql_lower = sql.lower().strip()
        if not sql_lower.startswith("select"): return False
        banned = [r"\bdelete\b", r"\bdrop\b", r"\bupdate\b", r"\binsert\b", r"\btruncate\b", r"\balter\b"]
        for pattern in banned:
            if re.search(pattern, sql_lower):
                return False
        return True

    def run_query(self, sql: str):
        try:
            with self.get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    return cur.fetchall()
        except Exception as e:
            logger.error(f"DB Query Error: {e}")
            raise e

    def vector_search(self, question: str):
        # We perform a simplified mock semantic search identical to the prototype, 
        # ordering by <-> against a single embedding placeholder. In reality, we'd embed the `question` first.
        # But per instruction, we replicate business logic first.
        sql = """
            SELECT subject, structured_description
            FROM freshdesk_tickets
            ORDER BY embedding <-> (
                SELECT embedding FROM freshdesk_tickets WHERE embedding IS NOT NULL LIMIT 1
            )
            LIMIT 10
        """
        return self.run_query(sql)

    def semantic_answer(self, question: str, tickets) -> str:
        prompt = f"""
        User question: {question}
        Relevant tickets: {tickets}
        
        Identify common themes and explain them clearly.
        Format your response in rich Markdown.
        - Use ## headers for main points
        - Use bulleted lists
        - Emphasize important metrics with **bold text** or blockquotes
        - Keep paragraphs short and scannable
        """
        return self._call_llm(prompt)

    def explain_result(self, question: str, sql: str, rows) -> str:
        prompt = f"""
        User question: {question}
        Result data: {rows}
        
        Format the output as a clean bulleted list based on the Result data.
        Each bullet should contain the main item (e.g., ticket subject, group) and its associated count/value.
        
        STRICT RULES:
        - Keep the response extremely concise and data-focused.
        - DO NOT explain the SQL query or mention how the results were obtained.
        - DO NOT include conversational filler like "Here is the explanation".
        - Only display the summarized results derived from the query.
        
        Expected output format example:
        - Your message couldn't be delivered — 11 tickets
        - New Account Added — 11 tickets
        """
        logger.info(f"Executing SQL: {sql}")
        return self._call_llm(prompt)
    
    def fix_sql(self, question: str, bad_sql: str, error: str) -> str:
        prompt = f"The following SQL is invalid.\nQuestion: {question}\nBad SQL: {bad_sql}\nError: {error}\nFix it. Return ONLY the corrected SQL. DO NOT include any conversational text."
        response_text = self._call_llm(prompt)
        return self.extract_sql(response_text)

    def process_query(self, question: str):
        qtype = self.classify_question(question)
        if "SQL_ANALYTICS" in qtype:
            sql = self.generate_sql(question)
            if not self.is_safe_sql(sql):
                return "SQL_ANALYTICS", "Unsafe SQL generated by AI, query blocked for security.", [], sql
            
            try:
                rows = self.run_query(sql)
            except Exception as e:
                logger.warning(f"Initial SQL failed, attempting auto-fix. Error: {e}")
                fixed_sql = self.fix_sql(question, sql, str(e))
                try:
                    rows = self.run_query(fixed_sql)
                    sql = fixed_sql
                except Exception as e2:
                    return "SQL_ANALYTICS", f"Failed to execute SQL after auto-fixing. Error: {e2}", [], fixed_sql

            explanation = self.explain_result(question, sql, rows)
            return "SQL_ANALYTICS", explanation, rows, sql
        else:
            tickets = self.vector_search(question)
            answer = self.semantic_answer(question, tickets)
            return "SEMANTIC_SEARCH", answer, tickets, None
