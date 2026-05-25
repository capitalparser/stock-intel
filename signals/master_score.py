"""Optional bridge to the local Master Technical Score project."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def format_master_score_for_payload(
    payload: dict,
    *,
    independence_status: str | None = None,
) -> str | None:
    try:
        _ensure_master_score_path()
        from master_score import format_scorecard_ko, from_lazy_alpha_payload, score_candidate
    except ImportError:
        return None

    score_input = from_lazy_alpha_payload(
        payload,
        independence_status=independence_status,
    )
    return format_scorecard_ko(score_candidate(score_input))


def _ensure_master_score_path() -> None:
    configured = os.getenv("MASTER_SCORE_SRC_PATH")
    default = "/Users/kjun/vault/01_Projects/19_master_technical_score/src"
    src_path = Path(configured or default)
    if src_path.exists() and str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

