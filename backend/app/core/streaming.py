import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any


def _json_default(value: Any):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


def format_sse_event(event: str, data: dict) -> bytes:
    payload = json.dumps(data, default=_json_default, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n".encode("utf-8")
