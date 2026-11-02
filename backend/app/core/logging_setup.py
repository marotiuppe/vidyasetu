"""Keep personal data out of the logs.

Access-log lines carry the full request path, query string included. Search boxes and filters put
names, phone numbers and e-mail addresses there, so the query string is replaced before the line is
written. Nothing else from a request is logged by the app itself.
"""

import logging

ACCESS_LOGGER = "uvicorn.access"
QUERY_MARK = "?[query removed]"


def _without_query(value: str) -> str:
    path, sep, _ = value.partition("?")
    return path + QUERY_MARK if sep else value


class QueryStringFilter(logging.Filter):
    """Strip query strings from every string argument of an access-log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(
                _without_query(arg) if isinstance(arg, str) else arg for arg in record.args
            )
        return True


def install_log_filters() -> None:
    """Attach the filter to the access logger. Safe to call more than once."""
    logger = logging.getLogger(ACCESS_LOGGER)
    if not any(isinstance(f, QueryStringFilter) for f in logger.filters):
        logger.addFilter(QueryStringFilter())
