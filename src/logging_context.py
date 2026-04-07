"""Request-scoped logging context (correlation id for log lines)."""

from __future__ import annotations

import contextvars
import logging
import uuid
from typing import Optional

correlation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default=""
)


def get_or_create_correlation_id(header_value: Optional[str]) -> str:
    """Return a non-empty correlation id from the client header or a new UUID."""
    if header_value:
        stripped = header_value.strip()
        if stripped:
            return stripped[:256]
    return str(uuid.uuid4())


class CorrelationIdFilter(logging.Filter):
    """Populate ``record.correlation_id`` for formatters (``-`` when unset)."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        cid = correlation_id_var.get("")
        record.correlation_id = cid if cid else "-"
        return True
