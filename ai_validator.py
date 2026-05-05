"""
ai_validator.py — AI 가공 결과 검증 레이어

AIValidator.validate_place_payload():
  - visit_role / estimated_duration / visit_time_slot / ai_summary 검증
  - 허용 범위 위반 시 fallback 값으로 보정
  - 검증 결과(ai_validation_status, ai_validation_errors)를 payload에 포함해 반환

log_validation_errors():
  - ai_validation_log 테이블에 오류 이력 INSERT
  - 오류 없으면 아무 작업도 하지 않음 (호출 비용 없음)
"""

import json
import logging

logger = logging.getLogger(__name__)

ALLOWED_ROLES = {"meal", "cafe", "spot", "culture"}
ALLOWED_SLOTS = {"morning", "lunch", "afternoon", "dinner"}

DEFAULT_DURATION = {
    "meal":    60,
    "cafe":    50,
    "spot":    70,
    "culture": 75,
}

# SOT 기준 role별 clamp — DB 제약(10~240)보다 좁은 SOT 범위를 강제
# meal/cafe = cat39(40~90), spot = cat12(60~120), culture = cat14(45~100)
DURATION_CLAMP_BY_ROLE = {
    "meal":    (40, 90),
    "cafe":    (40, 60),
    "spot":    (60, 120),
    "culture": (45, 100),
}

_GARBLED_PATTERNS = [
    "I cannot", "I'm sorry", "As an AI", "I don't have",
    "I am unable", "I apologize",
]


class AIValidator:

    def validate_place_payload(self, payload: dict) -> dict:
        """
        AI 가공 결과 dict를 검증하고 fallback 값으로 보정한다.

        Parameters
        ----------
        payload : AI 결과를 포함한 장소 dict (in-place 수정됨)

        Returns
        -------
        검증/보정된 payload
        포함 키: ai_validation_status ("passed" | "fallback"), ai_validation_errors (list)
        """
        errors = []

        # ── visit_role ────────────────────────────────────────────────
        role = payload.get("visit_role")
        if role not in ALLOWED_ROLES:
            errors.append({
                "field": "visit_role",
                "reason": "invalid_enum",
                "raw_value": str(role),
                "fallback_value": "spot",
            })
            role = "spot"

        # ── estimated_duration ────────────────────────────────────────
        duration = payload.get("estimated_duration")
        lo, hi = DURATION_CLAMP_BY_ROLE.get(role, (10, 240))
        if not isinstance(duration, int) or not (lo <= duration <= hi):
            fallback_dur = DEFAULT_DURATION[role]
            errors.append({
                "field": "estimated_duration",
                "reason": "out_of_range",
                "raw_value": str(duration),
                "fallback_value": str(fallback_dur),
            })
            duration = fallback_dur

        # ── visit_time_slot ───────────────────────────────────────────
        slots = payload.get("visit_time_slot") or []
        if not isinstance(slots, list):
            errors.append({
                "field": "visit_time_slot",
                "reason": "not_list",
                "raw_value": str(slots),
                "fallback_value": "[]",
            })
            slots = []
        cleaned_slots = [s for s in slots if s in ALLOWED_SLOTS]
        if len(cleaned_slots) < len(slots):
            removed = [s for s in slots if s not in ALLOWED_SLOTS]
            errors.append({
                "field": "visit_time_slot",
                "reason": "invalid_slot_values_removed",
                "raw_value": str(removed),
                "fallback_value": str(cleaned_slots),
            })

        # ── ai_summary ────────────────────────────────────────────────
        summary = (payload.get("ai_summary") or "").strip()
        if not summary:
            errors.append({
                "field": "ai_summary",
                "reason": "empty",
                "raw_value": "",
                "fallback_value": "장소 설명 데이터가 부족하여 기본 설명을 사용합니다.",
            })
            summary = "장소 설명 데이터가 부족하여 기본 설명을 사용합니다."
        else:
            for pat in _GARBLED_PATTERNS:
                if pat in summary:
                    errors.append({
                        "field": "ai_summary",
                        "reason": "garbled_pattern",
                        "raw_value": summary[:100],
                        "fallback_value": "장소 설명 데이터가 부족하여 기본 설명을 사용합니다.",
                    })
                    summary = "장소 설명 데이터가 부족하여 기본 설명을 사용합니다."
                    break
            summary = summary[:200]

        # ── 보정값 반영 ───────────────────────────────────────────────
        payload["visit_role"]            = role
        payload["estimated_duration"]    = duration
        payload["visit_time_slot"]       = cleaned_slots
        payload["ai_summary"]            = summary
        payload["ai_validation_status"]  = "fallback" if errors else "passed"
        payload["ai_validation_errors"]  = errors

        if errors:
            logger.warning(
                "[AIValidator] %d개 오류 — role=%s dur=%d slots=%s",
                len(errors), role, duration, cleaned_slots,
            )

        return payload


def log_validation_errors(
    conn, place_id: int, errors: list, payload: dict
) -> None:
    """
    ai_validation_log 테이블에 검증 오류를 INSERT한다.
    오류가 없으면 아무 작업도 하지 않는다.

    Parameters
    ----------
    conn     : psycopg2 connection
    place_id : places.place_id
    errors   : validate_place_payload() 가 반환한 ai_validation_errors 목록
    payload  : 전체 payload (payload_snapshot 으로 저장, 4000자 제한)
    """
    if not errors:
        return

    snapshot = json.dumps(payload, ensure_ascii=False, default=str)[:4000]

    with conn.cursor() as cur:
        for err in errors:
            cur.execute(
                """
                INSERT INTO ai_validation_log
                    (place_id, pipeline_stage, invalid_field,
                     raw_value, fallback_value, reason, payload_snapshot)
                VALUES (%(place_id)s, %(stage)s, %(field)s,
                        %(raw)s, %(fallback)s, %(reason)s,
                        %(snapshot)s::jsonb)
                """,
                {
                    "place_id": place_id,
                    "stage":    "ai_tag_generation",
                    "field":    err.get("field"),
                    "raw":      err.get("raw_value"),
                    "fallback": err.get("fallback_value"),
                    "reason":   err.get("reason", "unknown"),
                    "snapshot": snapshot,
                },
            )
    conn.commit()
