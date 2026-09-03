"""One place to make ``logging.getLogger("foodfenbe")`` actually print.

A bare custom logger has no handler, so under uvicorn (which only configures its
own loggers) our records vanish. This attaches a stderr handler once.
"""

from __future__ import annotations

import logging

LOGGER_NAME = "foodfenbe"


def configure_logging() -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s [%(name)s] %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger
