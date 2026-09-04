"""Small, dependency-free structured logging for the Whisper worker image."""

import datetime as dt
import json
import logging
import os
import socket
import sys
from typing import Any


def _safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    return str(value)


class JsonFormatter(logging.Formatter):
    def __init__(self, service: str):
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        event = getattr(record, "event_name", "log")
        payload: dict[str, Any] = {
            "schema_version": 1,
            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "event": event,
            "service": self.service,
            "container": socket.gethostname(),
            "environment": os.getenv("CLANKR_LOG_ENVIRONMENT", "development"),
            "run_kind": os.getenv("CLANKR_RUN_KIND", "normal"),
            "benchmark_run_id": os.getenv("BENCHMARK_RUN_ID") or None,
            "release_sha": os.getenv("RELEASE_SHA") or None,
        }
        if event == "log":
            payload["message"] = record.getMessage()
        payload.update(_safe(getattr(record, "event_fields", {})))
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def configure_logging(service: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(service))
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper(), handlers=[handler], force=True)


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    logger.info(event, extra={"event_name": event, "event_fields": fields})
