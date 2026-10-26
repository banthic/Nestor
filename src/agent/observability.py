"""Structured, privacy-conscious JSONL logs for Nestor runtime events."""

from __future__ import annotations

import contextvars
import json
import logging
import os
import re
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
LOG_PATH = ROOT / "logs" / "nestor.jsonl"
_REQUEST_ID: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "nestor_request_id", default=None
)
_LOGGER = logging.getLogger("nestor")
_SENSITIVE_KEY = re.compile(
    r"token|secret|password|api.?key|authorization", re.IGNORECASE
)
_PRIVATE_KEY = re.compile(
    r"^(action|content|details|member|options|prompt|question|reason|result|response|text|thinking)$",
    re.IGNORECASE,
)
_LOG_CONTENT = os.getenv("NESTOR_LOG_CONTENT", "").casefold() in {"1", "true", "yes"}


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "event": getattr(record, "event", record.getMessage()),
            "request_id": _REQUEST_ID.get(),
        }
        fields = getattr(record, "fields", None)
        if fields:
            payload.update(fields)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging() -> Path:
    """Configure rotating local JSONL logs; safe to call more than once."""
    if not any(isinstance(handler, RotatingFileHandler) for handler in _LOGGER.handlers):
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            LOG_PATH, maxBytes=10_000_000, backupCount=5, encoding="utf-8"
        )
        file_handler.setFormatter(_JsonFormatter())
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(_JsonFormatter())
        _LOGGER.addHandler(file_handler)
        _LOGGER.addHandler(console_handler)
        _LOGGER.setLevel(logging.INFO)
        _LOGGER.propagate = False
    return LOG_PATH


def request_context(request_id: str):
    """Attach a correlation id to logs emitted during one agent request."""
    class _RequestContext:
        def __enter__(self):
            self.token = _REQUEST_ID.set(request_id)
            return request_id

        def __exit__(self, *_exc):
            _REQUEST_ID.reset(self.token)

    return _RequestContext()


def _safe_value(key: str, value: Any) -> Any:
    if _SENSITIVE_KEY.search(key):
        return "[REDACTED]"
    if _PRIVATE_KEY.match(key) and not _LOG_CONTENT:
        size = len(value) if isinstance(value, (str, bytes, list, dict)) else None
        return {"redacted": True, "size": size}
    if isinstance(value, dict):
        return {str(k): _safe_value(str(k), v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe_value(key, item) for item in value]
    if isinstance(value, str) and len(value) > 4000:
        return value[:4000] + "…[truncated]"
    return value


def log_event(event: str, level: int = logging.INFO, **fields: Any) -> None:
    """Write a structured event; likely sensitive text fields are redacted by default."""
    if not _LOGGER.handlers:
        configure_logging()
    safe_fields = {key: _safe_value(key, value) for key, value in fields.items()}
    _LOGGER.log(level, event, extra={"event": event, "fields": safe_fields})


def log_exception(event: str, error: BaseException, **fields: Any) -> None:
    """Write an exception with context without swallowing it."""
    if not _LOGGER.handlers:
        configure_logging()
    safe_fields = {key: _safe_value(key, value) for key, value in fields.items()}
    _LOGGER.exception(
        event,
        exc_info=(type(error), error, error.__traceback__),
        extra={"event": event, "fields": safe_fields},
    )
