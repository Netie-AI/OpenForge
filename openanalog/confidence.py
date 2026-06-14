from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ConfidenceAction(str, Enum):
    AUTO_ACCEPT = "auto_accept"
    AUTO_ACCEPT_REVIEW = "needs_review"
    HOLD = "hold"
    REJECT = "reject"


@dataclass
class ConfidenceDecision:
    score: float
    action: ConfidenceAction
    needs_claude: bool
    reason: str


def decide(score: float) -> ConfidenceDecision:
    if score >= 0.9:
        return ConfidenceDecision(score, ConfidenceAction.AUTO_ACCEPT, False, "high confidence")
    if score >= 0.7:
        return ConfidenceDecision(
            score, ConfidenceAction.AUTO_ACCEPT_REVIEW, False, "accepted with review flag"
        )
    if score >= 0.5:
        return ConfidenceDecision(score, ConfidenceAction.HOLD, True, "ambiguous — Claude re-examine")
    return ConfidenceDecision(score, ConfidenceAction.REJECT, False, "below threshold")


def kg_tier(score: float) -> str | None:
    if score >= 0.95:
        return "gold"
    if score >= 0.85:
        return "silver"
    if score >= 0.70:
        return "bronze"
    return None


def should_write_kg_seed(score: float, sim_validated: bool) -> bool:
    d = decide(score)
    return sim_validated and d.action in (
        ConfidenceAction.AUTO_ACCEPT,
        ConfidenceAction.AUTO_ACCEPT_REVIEW,
    )


def record_flags(score: float) -> dict[str, Any]:
    d = decide(score)
    return {
        "confidence": score,
        "confidence_action": d.action.value,
        "needs_review": d.action == ConfidenceAction.AUTO_ACCEPT_REVIEW,
        "kg_tier": kg_tier(score),
    }
