import json
import logging
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    """Render application and Uvicorn records as newline-delimited JSON."""

    def format(self, record: logging.LogRecord) -> str:
        event: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if record.name == "uvicorn.access" and isinstance(record.args, tuple):
            if len(record.args) >= 5:
                event.update(
                    client_addr=record.args[0],
                    method=record.args[1],
                    path=record.args[2],
                    http_version=record.args[3],
                    status_code=record.args[4],
                )

        if record.exc_info:
            event["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            event["stack"] = self.formatStack(record.stack_info)

        return json.dumps(event, default=str, ensure_ascii=False)


class HealthcheckAccessLogFilter(logging.Filter):
    """Keep routine liveness and readiness probes out of the access log."""

    _HEALTHCHECK_PATHS = frozenset({"/health/live", "/health/ready"})

    def filter(self, record: logging.LogRecord) -> bool:
        arguments = record.args
        if isinstance(arguments, tuple) and len(arguments) >= 3:
            path = arguments[2]
            if isinstance(path, str) and path.split("?", 1)[0] in self._HEALTHCHECK_PATHS:
                return False
        return True
