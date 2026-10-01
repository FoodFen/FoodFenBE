"""Token-usage logging for Gemini calls, so prompt/output/thinking cost is visible in the logs."""

from __future__ import annotations

import logging

_log = logging.getLogger("foodfenbe.ai")


def log_usage(call: str, usage) -> None:
    """``usage`` is a response's ``usage_metadata`` (None when the SDK omitted it)."""
    if usage is not None:
        _log.info(
            "gemini %s tokens: prompt=%s output=%s thoughts=%s",
            call,
            getattr(usage, "prompt_token_count", None),
            getattr(usage, "candidates_token_count", None),
            getattr(usage, "thoughts_token_count", None),
        )
