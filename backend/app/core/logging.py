import logging


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
