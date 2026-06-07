"""Centralized logging service for the Scholar backend.

Every module obtains its logger via ``get_logger(__name__)`` and ``configure_logging()``
is called once at startup (see app/main.py). The format embeds the real call site
(filename/func/line) because ``get_logger`` returns the stdlib logger directly rather
than a wrapper.
"""

import contextvars
import logging
import os
import sys
import uuid

# Format string shared by every handler. Embeds the real call site so logs point at
# the module that emitted them, not at this service.
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(filename)s::%(funcName)s::%(lineno)d | %(message)s"

# Guards against adding duplicate handlers if configure_logging() runs more than once.
_configured = False

# Request-ID correlation. Set per-request in the HTTP middleware and read back in the
# exception handlers / anywhere else on the same async task.
request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)


def _resolve_level() -> int:
    """Read LOG_LEVEL from env (case-insensitive); fall back to INFO if missing/invalid."""
    raw = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    level = logging.getLevelName(raw)
    # getLevelName returns an int for known names, otherwise a "Level X" string.
    if isinstance(level, int):
        return level
    return logging.INFO


def configure_logging() -> None:
    """Idempotently configure the root logger to stream to stdout with LOG_FORMAT."""
    global _configured
    level = _resolve_level()

    root = logging.getLogger()
    root.setLevel(level)

    if _configured:
        # Already set up; just keep the level in sync and skip handler creation.
        for handler in root.handlers:
            handler.setLevel(level)
        return

    # Clear any pre-existing handlers (e.g. from a stray basicConfig) so we don't
    # emit duplicate lines.
    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root.addHandler(handler)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return the stdlib logger for ``name``.

    Returning the stdlib logger directly (no wrapper) ensures %(filename)s,
    %(funcName)s and %(lineno)d reflect the real call site.
    """
    return logging.getLogger(name)


def new_request_id() -> str:
    """Return a short, unique request id."""
    return uuid.uuid4().hex[:8]


def set_request_id(rid: str) -> None:
    """Store the current request id in the context."""
    request_id_var.set(rid)


def get_request_id() -> str | None:
    """Return the request id for the current context, or None if unset."""
    return request_id_var.get()
