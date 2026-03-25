import logging
import re
from typing import Any
from langchain_core.messages import HumanMessage
from langchain_core.language_models.chat_models import BaseChatModel

logger = logging.getLogger(__name__)

class LLMHelper:
    def __init__(self, llm: BaseChatModel):
        self._llm = llm

    def call_llm(self, prompt: str) -> str:
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

    @staticmethod
    def extract_sql(text: str) -> str:
        logger.debug("Extracting SQL from LLM response")

        match = re.search(r"```(?:sql)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()

        match_select = re.search(r"((?:with|select)\b.*)", text, re.DOTALL | re.IGNORECASE)
        if match_select:
            return match_select.group(1).strip()

        return text.strip()

    @staticmethod
    def is_safe_sql(sql: str) -> bool:
        logger.debug("Running basic SQL safety check")

        sql_lower = sql.lower().strip()
        # Allow queries that start with SELECT or WITH (for CTEs)
        if not re.match(r"^(select|with)\b", sql_lower):
            logger.warning("SQL must start with SELECT or WITH (CTE)")
            return False

        banned = [r";\s*delete\b", r"\bdrop\b", r"\bupdate\b", r"\binsert\b", r"\btruncate\b", r"\balter\b"]
        is_safe = not any(re.search(pattern, sql_lower) for pattern in banned)

        if not is_safe:
            logger.warning("SQL contains potentially dangerous patterns")

        return is_safe
