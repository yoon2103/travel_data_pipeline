from __future__ import annotations


def score_image_candidate(candidate: dict, *, category: str | None = None) -> tuple[int | None, dict]:
    image_url = candidate.get("image_url")
    if not image_url:
        return None, {
            "image_quality_score": None,
            "hard_reject": True,
            "reject_reasons": ["NO_IMAGE_URL"],
            "score_breakdown": {},
        }

    source_type = (candidate.get("source_type") or "").upper()
    source_quality = 18 if source_type in {"KAKAO", "NAVER"} else 12
    technical_quality = 15
    category_fit = 15 if (category or "").lower() in {"cafe", "카페"} else 10
    place_identity = 10
    mood_appeal = 8 if source_type in {"KAKAO", "NAVER"} else 5
    score = min(100, source_quality + technical_quality + category_fit + place_identity + mood_appeal)
    payload = {
        "image_quality_score": score,
        "image_quality_grade": grade_image_score(score),
        "hard_reject": False,
        "reject_reasons": [],
        "score_breakdown": {
            "technical_quality": technical_quality,
            "source_quality": source_quality,
            "category_fit": category_fit,
            "place_identity": place_identity,
            "mood_appeal": mood_appeal,
            "safety_penalty": 0,
        },
    }
    return score, payload


def grade_image_score(score: int) -> str:
    if score >= 90:
        return "EXCELLENT"
    if score >= 75:
        return "GOOD"
    if score >= 60:
        return "USABLE"
    if score >= 40:
        return "REVIEW_REQUIRED"
    return "REJECT"
