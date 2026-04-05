from typing import Any
from app.ticket_intelligence.config.use_cases import UseCaseConfig

class TicketPrompts:
    @staticmethod
    def get_schema_prompt(ticket_schema: str, ticket_support_email: str, config: UseCaseConfig) -> str:
        
        filter_text = ""
        if config.filter_criteria_instruction:
            filter_str = config.filter_criteria_instruction.format(support_email=ticket_support_email)
            filter_text = f"1. Filter Criteria\n        {filter_str}\n"

        cat_list = "\n        ".join(f"* {c}" for c in config.categories)
        categories_text = f"Categories:\n        {cat_list}" if cat_list else "Categories: None"

        return f"""
        Database: PostgreSQL
        Table: {ticket_schema}.{config.table_name}
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

        {filter_text}
        
        2. Closed Ticket Definition
        A ticket is considered closed if its status is either 4 or 5.

        3. Resolution Time Calculation

        * Calculate resolution time only for tickets that are resolved or closed.
        * Ignore all other tickets for resolution time metrics.

        4. Ticket Categorization (Subject-Based)
        Analyze each ticket's subject and assign it to the most relevant category using intelligent understanding (not exact matching). Use intent, keywords, and semantic similarity.

        {categories_text}

        5. Uncategorized Tickets
        If the subject does not clearly match any category, assign:
        "Tickets Not Tagged to Any Type"

        6. Classification Guidelines

        * Normalize text (ignore case, punctuation, spacing).
        * Use fuzzy matching and synonyms (e.g., "can't log in" -> "Login Issue").
        * Prioritize intent over exact words.
        * If multiple categories apply, choose the most specific one.
        * Ensure consistency, accuracy, and no misclassification.

        Cleaning Rules (Exclusions):
        {config.exclusion_rules_text}
        
        SQL Rules:
        - Use ONLY {ticket_schema}.{config.table_name}
        {config.sql_rules}
        {config.exclusion_rules_sql}
        """.strip()

    @staticmethod
    def classify_question_prompt(question: str) -> str:
        return f"""
        Classify the question. Categories: SQL_ANALYTICS or SEMANTIC_SEARCH. Return ONLY one word.
        Examples:
        How many tickets last month -> SQL_ANALYTICS
        Average resolution time -> SQL_ANALYTICS
        Most repeated tickets -> SEMANTIC_SEARCH
        Summarize ticket problems -> SEMANTIC_SEARCH

        Question: {question}
        """

    @staticmethod
    def generate_sql_prompt(question: str, schema_prompt: str, config: UseCaseConfig) -> str:
        return f"""
        You are a PostgreSQL expert.
        Database schema: {schema_prompt}

        Rules:
            - Only produce SELECT statements (no INSERT, UPDATE, DELETE, or DDL operations).
            - Use valid PostgreSQL syntax.
            {config.sql_rules}
            - Apply all required data cleaning rules within the query.
            - Output only the SQL code:
            - Begin directly with SELECT or WITH (if using CTEs).
            - Do not include any explanations, comments, or additional text.

        Cleaning Rules (Exclusions):
        {config.exclusion_rules_text}

        Question: {question}
        """

    @staticmethod
    def validate_sql_prompt(question: str, sql: str, schema_prompt: str) -> str:
        return f"""
        You are a security and SQL validation expert.
        Review the following SQL query to ensure it safely and correctly answers the user's question.
        
        Question: {question}
        Original SQL: {sql}
        Database Schema: {schema_prompt}

        Validation Rules:
        1. NO destructive operations (DROP, DELETE, ALTER, UPDATE, INSERT, TRUNCATE). Only SELECT or WITH (if using CTEs) is allowed. (Note: The word 'delete' is allowed in string literals to search for textual matches).
        2. NO SQL injection patterns (e.g., OR 1=1, UNION SELECT).
        3. Must be perfectly formed PostgreSQL syntax.
        4. Query MUST match the user's intent based on the Question and the Schema.

        If the Original SQL is safe and perfectly answers the question, output ONLY the Original SQL. DO NOT include any conversational text.
        If the Original SQL violates any rules, or doesn't match the intent, rewrite it to be safe and correct. Output ONLY the rewritten SQL. DO NOT include any conversational text like "Here is the fixed query". Start immediately with SELECT or WITH (if using CTEs).
        """

    @staticmethod
    def fix_sql_prompt(question: str, bad_sql: str, error: str, schema_prompt: str) -> str:
        return f"""
        You are a PostgreSQL expert debugging a failed query.
        
        Question: {question}
        Database schema: {schema_prompt}
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

    @staticmethod
    def extract_search_terms_prompt(question: str) -> str:
        return f"""
        Extract up to 6 short search terms or phrases from this ticket-support question.
        Return one term per line with no numbering or extra commentary.

        Question: {question}
        """

    @staticmethod
    def semantic_answer_prompt(question: str, tickets: list[Any], config: UseCaseConfig) -> str:
        return f"""
            You are an assistant that analyzes support tickets and provides clear, structured insights.

            User Question
            {question}

            Input Data
            Relevant tickets:
            {tickets}

            Task
            1. Filter out irrelevant tickets using the rules below.
            2. Analyze the remaining tickets.
            3. Identify key patterns, recurring issues, and notable insights.
            4. Answer the user's question using these insights.

            Filtering Rules (Strict)
            Exclude any ticket where:
            {config.exclusion_rules_text}
        """

    @staticmethod
    def explain_result_prompt(question: str, sql: str, rows: list[Any]) -> str:
        return f"""
        User question: {question}
        Result data: {rows}
        SQL used: {sql}

        Format the output as a concise bulleted list based only on the result data. Do not explain how the query was generated.
        """
