import re

import sqlparse

DISALLOWED_PATTERN = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|create|grant|revoke|copy|comment|vacuum|analyze|call)\b",
    re.IGNORECASE,
)


def normalize_sql(query: str) -> str:
    return query.strip().rstrip(";")


def ensure_single_read_only_statement(query: str) -> str:
    normalized = normalize_sql(query)
    statements = [statement for statement in sqlparse.split(normalized) if statement.strip()]
    if len(statements) != 1:
        raise ValueError("Only one SQL statement is allowed.")

    statement = statements[0].strip()
    lowered = statement.lower()
    if not (lowered.startswith("select") or lowered.startswith("with")):
        raise ValueError("Only SELECT or WITH queries are allowed.")
    if DISALLOWED_PATTERN.search(statement):
        raise ValueError("Only read-only SQL is allowed.")
    return statement


def build_limited_query(query: str, limit: int) -> str:
    safe_query = ensure_single_read_only_statement(query)
    return f"SELECT * FROM ({safe_query}) AS mcp_query LIMIT {int(limit)}"


def build_explain_query(query: str) -> str:
    safe_query = ensure_single_read_only_statement(query)
    return f"EXPLAIN (FORMAT JSON, ANALYZE FALSE, VERBOSE FALSE) {safe_query}"
