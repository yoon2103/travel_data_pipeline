from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .scoring import MatchResult


FinalDecisionType = Literal["AUTO_APPROVE", "MANUAL_REVIEW", "LOW_CONFIDENCE", "REJECT"]


@dataclass
class FinalDecision:
    final_decision: FinalDecisionType
    blocked: bool
    block_reasons: list[str] = field(default_factory=list)
    review_required: bool = False
    review_reasons: list[str] = field(default_factory=list)
    confidence_level: str = "REJECT"
    score: int = 0
    score_decision: str | None = None
    applied_rules: list[str] = field(default_factory=list)


class MatchDecisionEngine:
    def evaluate_match_decision(self, match_result: MatchResult) -> FinalDecision:
        block_reasons = self.evaluate_blocking_rules(match_result)
        if block_reasons:
            return FinalDecision(
                final_decision="REJECT",
                blocked=True,
                block_reasons=block_reasons,
                confidence_level="REJECT",
                score=match_result.score,
                score_decision=match_result.decision,
                applied_rules=block_reasons,
            )

        review_reasons = self.evaluate_review_required_rules(match_result)
        if review_reasons:
            return FinalDecision(
                final_decision="MANUAL_REVIEW",
                blocked=False,
                review_required=True,
                review_reasons=review_reasons,
                confidence_level="MEDIUM",
                score=match_result.score,
                score_decision=match_result.decision,
                applied_rules=review_reasons,
            )

        return self.evaluate_score_based_decision(match_result)

    def evaluate_blocking_rules(self, match_result: MatchResult) -> list[str]:
        flags = set(match_result.risk_flags)
        reasons: list[str] = []
        for flag in (
            "CATEGORY_CONFLICT",
            "DISTANCE_TOO_FAR",
            "CLOSED_BUSINESS",
            "PHONE_CONFLICT",
            "ADDRESS_CONFLICT",
            "BRANCH_MISMATCH",
        ):
            if flag in flags:
                reasons.append(flag)
        if {"CHAIN_BRAND_RISK", "DISTANCE_OVER_100M"} <= flags:
            reasons.append("CHAIN_BRAND_RISK_WITH_DISTANCE_OVER_100M")
        if {"LOW_NAME_SIMILARITY", "NO_ADDRESS", "NO_PHONE"} <= flags:
            reasons.append("LOW_NAME_SIMILARITY_WITH_NO_EVIDENCE")
        return reasons

    def evaluate_review_required_rules(self, match_result: MatchResult) -> list[str]:
        flags = set(match_result.risk_flags)
        reasons: list[str] = []
        if {"CHAIN_BRAND_RISK", "LOW_EVIDENCE"} <= flags:
            reasons.append("CHAIN_BRAND_RISK_WITH_LOW_EVIDENCE")
        if {"CHAIN_BRAND_RISK", "CHAIN_BRANCH_LOW_EVIDENCE"} <= flags:
            reasons.append("CHAIN_BRAND_WITH_WEAK_BRANCH_EVIDENCE")
        if "SAME_BUILDING_AMBIGUITY" in flags:
            reasons.append("SAME_BUILDING_AMBIGUITY")
        if {"NO_ADDRESS", "NO_PHONE"} <= flags:
            reasons.append("NO_ADDRESS_AND_NO_PHONE")
        if match_result.distance_meters is not None and 100 < match_result.distance_meters <= 300:
            reasons.append("MEDIUM_DISTANCE")
        if match_result.score >= 85 and "LOW_EVIDENCE" in flags:
            reasons.append("HIGH_SCORE_BUT_LOW_EVIDENCE")
        return reasons

    def evaluate_score_based_decision(self, match_result: MatchResult) -> FinalDecision:
        if (
            match_result.score >= 85
            and match_result.confidence_level == "HIGH"
            and match_result.distance_meters is not None
            and match_result.distance_meters <= 100
            and match_result.name_similarity >= 0.90
        ):
            decision: FinalDecisionType = "AUTO_APPROVE"
            blocked = False
            review_required = False
        elif match_result.score >= 70:
            decision = "MANUAL_REVIEW"
            blocked = False
            review_required = True
        elif match_result.score >= 50:
            decision = "LOW_CONFIDENCE"
            blocked = False
            review_required = False
        else:
            decision = "REJECT"
            blocked = True
            review_required = False

        return FinalDecision(
            final_decision=decision,
            blocked=blocked,
            review_required=review_required,
            review_reasons=["SCORE_BASED_MANUAL_REVIEW"] if review_required else [],
            confidence_level=match_result.confidence_level,
            score=match_result.score,
            score_decision=match_result.decision,
            applied_rules=["SCORE_BASED"],
        )
