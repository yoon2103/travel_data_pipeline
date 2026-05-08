from __future__ import annotations


def summarize(candidates: list[dict]) -> dict:
    summary = {
        "promote_candidates": 0,
        "review_required": 0,
        "rejected": 0,
        "no_candidate": 0,
        "by_source": {},
    }
    for item in candidates:
        source = item.get("source_type") or "UNKNOWN"
        summary["by_source"][source] = summary["by_source"].get(source, 0) + 1
        decision = item.get("final_decision")
        if decision == "AUTO_APPROVE":
            summary["promote_candidates"] += 1
        elif decision == "MANUAL_REVIEW":
            summary["review_required"] += 1
        elif decision == "REJECT":
            summary["rejected"] += 1
    return summary
