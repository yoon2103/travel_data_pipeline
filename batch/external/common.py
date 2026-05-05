from __future__ import annotations

import json
import hashlib
import math
import re
import uuid
from datetime import datetime, timezone
from typing import Any

import psycopg2.extras

ALLOWED_ROLES = {"cafe", "meal", "culture"}

CAFE_KEYWORDS = (
    "카페", "커피", "디저트", "베이커리", "브런치", "찻집", "티룸",
)
MEAL_KEYWORDS = (
    "음식점", "한식", "중식", "일식", "양식", "분식", "식당", "맛집",
    "고기", "국수", "라멘", "초밥", "해산물", "레스토랑",
)
CULTURE_KEYWORDS = (
    "박물관", "미술관", "전시", "공연장", "문화", "기념관", "도서관",
    "갤러리", "역사", "예술",
)

ROLE_DEFAULTS = {
    "cafe": {
        "category_id": 39,
        "duration": 40,
        "slots": ["morning", "afternoon"],
        "indoor_outdoor": "indoor",
        "themes": ["cafe", "카페", "휴식"],
    },
    "meal": {
        "category_id": 39,
        "duration": 60,
        "slots": ["lunch", "dinner"],
        "indoor_outdoor": "indoor",
        "themes": ["food", "미식", "식사"],
    },
    "culture": {
        "category_id": 14,
        "duration": 75,
        "slots": ["morning", "afternoon"],
        "indoor_outdoor": "indoor",
        "themes": ["history", "culture", "문화", "전시"],
    },
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_run(conn, run_id: str | None, *, dry_run: bool, promote: bool = False) -> str:
    if run_id:
        return run_id
    new_run_id = str(uuid.uuid4())
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO data_update_runs (run_id, mode, dry_run, promote, status, metadata)
            VALUES (%s, 'external', %s, %s, 'RUNNING', %s)
            """,
            (
                new_run_id,
                dry_run,
                promote,
                psycopg2.extras.Json({"source": "external_places"}),
            ),
        )
    conn.commit()
    return new_run_id


def finish_run(conn, run_id: str, status: str, metadata: dict[str, Any] | None = None) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE data_update_runs
            SET status = %s,
                finished_at = NOW(),
                metadata = metadata || %s::jsonb
            WHERE run_id = %s
            """,
            (status, json.dumps(metadata or {}, ensure_ascii=False), run_id),
        )
    conn.commit()


def log_step(
    conn,
    run_id: str,
    step_name: str,
    status: str,
    *,
    input_count: int = 0,
    output_count: int = 0,
    message: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO data_update_step_logs (
                run_id, step_name, status, started_at, finished_at,
                input_count, output_count, message, metadata
            )
            VALUES (%s, %s, %s, NOW(), NOW(), %s, %s, %s, %s)
            """,
            (
                run_id,
                step_name,
                status,
                input_count,
                output_count,
                message,
                psycopg2.extras.Json(metadata or {}),
            ),
        )
    conn.commit()


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(d_lam / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def valid_korea_coord(lat: Any, lon: Any) -> bool:
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (TypeError, ValueError):
        return False
    return 32.5 <= lat_f <= 39.5 and 124.0 <= lon_f <= 132.5


def normalize_name(value: str) -> str:
    return re.sub(r"[^0-9a-zA-Z가-힣]", "", value or "").lower()


def map_role(name: str, category: str | None) -> str | None:
    text = f"{name or ''} {category or ''}"
    if any(keyword in text for keyword in CAFE_KEYWORDS):
        return "cafe"
    if any(keyword in text for keyword in CULTURE_KEYWORDS):
        return "culture"
    if any(keyword in text for keyword in MEAL_KEYWORDS):
        return "meal"
    return None


def external_content_id(source: str, external_id: str) -> str:
    digest = hashlib.sha1(f"{source}:{external_id}".encode("utf-8")).hexdigest()[:32]
    return f"ex:{source[:1]}:{digest}"


def subject_particle(name: str) -> str:
    if not name:
        return "는"
    code = ord(name[-1])
    if 0xAC00 <= code <= 0xD7A3:
        return "은" if (code - 0xAC00) % 28 else "는"
    return "은"


DESCRIPTION_TEMPLATES = {
    "cafe": [
        "{name}{josa} 이동 중 쉬어가기 좋은 카페로, 여유로운 휴식 시간을 넣기 좋습니다.",
        "{name}{josa} 음료와 디저트를 곁들이며 코스의 템포를 조절하기 좋은 공간입니다.",
        "{name}{josa} 실내에서 잠시 머물며 다음 장소로 이동하기 전 숨을 고르기 좋습니다.",
    ],
    "meal": [
        "{name}{josa} 일정 중 식사 시간을 자연스럽게 채워 줄 수 있는 음식점입니다.",
        "{name}{josa} 주변 코스와 함께 들르기 좋은 식사 장소로 활용하기 적합합니다.",
        "{name}{josa} 점심이나 저녁 슬롯에 배치하기 좋은 지역 기반 식당 후보입니다.",
    ],
    "culture": [
        "{name}{josa} 실내 관람 중심으로 일정을 안정적으로 구성하기 좋은 문화시설입니다.",
        "{name}{josa} 전시와 문화 경험을 더해 코스의 밀도를 높여 줄 수 있는 장소입니다.",
        "{name}{josa} 날씨 영향을 비교적 덜 받으며 머물 수 있는 문화 공간입니다.",
    ],
}


def build_description(name: str, role: str) -> str:
    templates = DESCRIPTION_TEMPLATES.get(role) or DESCRIPTION_TEMPLATES["meal"]
    idx = sum(ord(ch) for ch in name) % len(templates)
    return templates[idx].format(name=name, josa=subject_particle(name))


def role_payload(role: str, name: str) -> dict[str, Any]:
    defaults = ROLE_DEFAULTS[role]
    return {
        "category_id": defaults["category_id"],
        "ai_summary": build_description(name, role),
        "ai_tags": {
            "themes": defaults["themes"],
            "source": ["external"],
        },
        "visit_role": role,
        "estimated_duration": defaults["duration"],
        "visit_time_slot": defaults["slots"],
        "indoor_outdoor": defaults["indoor_outdoor"],
        "ai_validation_status": "success",
        "ai_validation_errors": [],
    }
