"""
database.py — PostgreSQL 연결 관리 및 핵심 쿼리 함수

지원 모드:
  - pgvector 설치 시: SQL <=> 코사인 거리 연산
  - 미설치 시: embedding을 TEXT(JSON)로 저장, Python 쪽에서 코사인 유사도 계산
"""

import json
import logging
import math
from typing import Optional

import psycopg2
import psycopg2.extras

import config

logger = logging.getLogger(__name__)

# pgvector Python 어댑터 (설치 돼 있으면 사용)
try:
    from pgvector.psycopg2 import register_vector as _reg_vec
    _PGVECTOR = True
except ImportError:
    _PGVECTOR = False

logger.debug("pgvector mode: %s", "SQL" if _PGVECTOR else "Python-fallback")


# ─────────────────────────────────────────────
# 연결
# ─────────────────────────────────────────────

def get_connection() -> psycopg2.extensions.connection:
    conn = psycopg2.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        dbname=config.DB_NAME,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )
    if _PGVECTOR:
        _reg_vec(conn)
    return conn


# ─────────────────────────────────────────────
# Upsert
# ─────────────────────────────────────────────

# ON CONFLICT 키: tourapi_content_id (Partial Unique Index)
#
# AI/후처리 컬럼 보호 정책
# ─────────────────────────────────────────────────────────
# COALESCE 적용 (새 값이 NULL이면 기존 값 유지):
#   ai_summary, ai_tags, embedding
#   visit_role, estimated_duration, visit_time_slot
# COALESCE 제외 (항상 최신값 반영):
#   ai_validation_status, ai_validation_errors  ← 두 값은 항상 쌍으로 최신 상태
# ─────────────────────────────────────────────────────────
_UPSERT_SQL = """
INSERT INTO places (
    name, category_id, region_1, region_2,
    latitude, longitude, overview,
    first_image_url, first_image_thumb_url,
    ai_summary, ai_tags, embedding,
    visit_role, estimated_duration, visit_time_slot,
    ai_validation_status, ai_validation_errors,
    tourapi_content_id, tourapi_modified_time, synced_at
) VALUES (
    %(name)s, %(category_id)s, %(region_1)s, %(region_2)s,
    %(latitude)s, %(longitude)s, %(overview)s,
    %(first_image_url)s, %(first_image_thumb_url)s,
    %(ai_summary)s, %(ai_tags)s, %(embedding)s,
    %(visit_role)s, %(estimated_duration)s, %(visit_time_slot)s,
    %(ai_validation_status)s, %(ai_validation_errors)s,
    %(tourapi_content_id)s, %(tourapi_modified_time)s, NOW()
)
ON CONFLICT (tourapi_content_id)
    WHERE tourapi_content_id IS NOT NULL
DO UPDATE SET
    -- API 원본 필드: 항상 최신값으로 갱신
    name                  = EXCLUDED.name,
    category_id           = EXCLUDED.category_id,
    region_1              = EXCLUDED.region_1,
    region_2              = EXCLUDED.region_2,
    latitude              = EXCLUDED.latitude,
    longitude             = EXCLUDED.longitude,
    -- overview/image: 정상값이면 갱신, NULL 또는 빈 문자열이면 기존값 보존
    overview              = COALESCE(NULLIF(EXCLUDED.overview, ''),              places.overview),
    first_image_url       = COALESCE(NULLIF(EXCLUDED.first_image_url, ''),       places.first_image_url),
    first_image_thumb_url = COALESCE(NULLIF(EXCLUDED.first_image_thumb_url, ''), places.first_image_thumb_url),
    -- AI/후처리 필드: COALESCE — 새 값이 NULL이면 기존 값 보존
    ai_summary            = COALESCE(EXCLUDED.ai_summary,         places.ai_summary),
    ai_tags               = COALESCE(EXCLUDED.ai_tags,            places.ai_tags),
    embedding             = COALESCE(EXCLUDED.embedding,          places.embedding),
    visit_role            = COALESCE(EXCLUDED.visit_role,         places.visit_role),
    estimated_duration    = COALESCE(EXCLUDED.estimated_duration, places.estimated_duration),
    visit_time_slot       = COALESCE(EXCLUDED.visit_time_slot,    places.visit_time_slot),
    -- AI 검증 결과: 항상 최신값 (status·errors 는 항상 쌍으로 갱신)
    ai_validation_status  = EXCLUDED.ai_validation_status,
    ai_validation_errors  = EXCLUDED.ai_validation_errors,
    -- sync 메타: 재활성화 + 시각 갱신
    is_active             = TRUE,
    tourapi_modified_time = EXCLUDED.tourapi_modified_time,
    synced_at             = NOW(),
    updated_at            = NOW()
RETURNING place_id
"""


def upsert_place(conn, place: dict) -> int:
    """
    가공 완료된 장소 dict를 places 테이블에 Upsert.

    place dict 예상 키:
        tourapi_content_id, name, category_id, region_1, region_2,
        latitude, longitude, overview,
        ai_summary (str|None), ai_tags (dict|None), embedding (list[float]|None)

    Returns: place_id (int)
    """
    ai_tags_json = (
        psycopg2.extras.Json(place["ai_tags"])
        if place.get("ai_tags") else None
    )

    # ai_validation_errors: list[dict] → JSONB
    ai_val_errors = place.get("ai_validation_errors")
    ai_val_errors_json = (
        psycopg2.extras.Json(ai_val_errors)
        if ai_val_errors is not None else psycopg2.extras.Json([])
    )

    # embedding: pgvector 설치 시 list 그대로, 아니면 JSON 문자열
    raw_emb = place.get("embedding")
    if raw_emb is None:
        emb_value = None
    elif _PGVECTOR:
        emb_value = raw_emb          # register_vector 가 처리
    else:
        emb_value = json.dumps(raw_emb)   # TEXT 컬럼에 JSON 직렬화

    params = {
        "tourapi_content_id":    place.get("tourapi_content_id"),
        "name":                  place.get("name", ""),
        "category_id":           place.get("category_id"),
        "region_1":              place.get("region_1"),
        "region_2":              place.get("region_2"),
        "latitude":              place.get("latitude"),
        "longitude":             place.get("longitude"),
        "overview":              place.get("overview"),
        "first_image_url":       place.get("first_image_url") or None,
        "first_image_thumb_url": place.get("first_image_thumb_url") or None,
        "ai_summary":            place.get("ai_summary"),
        "ai_tags":               ai_tags_json,
        "embedding":             emb_value,
        "visit_role":            place.get("visit_role"),
        "estimated_duration":    place.get("estimated_duration"),
        "visit_time_slot":       place.get("visit_time_slot"),
        "ai_validation_status":  place.get("ai_validation_status", "pending"),
        "ai_validation_errors":  ai_val_errors_json,
        "tourapi_modified_time": place.get("tourapi_modified_time"),
    }

    try:
        with conn.cursor() as cur:
            cur.execute(_UPSERT_SQL, params)
            place_id: int = cur.fetchone()["place_id"]
        conn.commit()
        return place_id
    except psycopg2.Error:
        conn.rollback()  # 중지된 트랜잭션 해제 → 다음 행 처리 가능
        raise


# ─────────────────────────────────────────────
# 벡터 검색 + Haversine 반경 필터링
# ─────────────────────────────────────────────

def _cosine_sim(a: list[float], b: list[float]) -> float:
    """Python 순수 코사인 유사도 (pgvector 없을 때 fallback)."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    return dot / (norm_a * norm_b) if norm_a * norm_b else 0.0


# Haversine 반경 필터 SQL 조각 (PostgreSQL 내에서 계산)
_HAVERSINE_KM = """
    6371.0 * 2 * ASIN(SQRT(
        POWER(SIN(RADIANS(latitude  - %(lat)s) / 2), 2) +
        COS(RADIANS(%(lat)s)) * COS(RADIANS(latitude)) *
        POWER(SIN(RADIANS(longitude - %(lng)s) / 2), 2)
    ))
"""

_VECTOR_SEARCH_PG = """
    SELECT place_id, name, region_1, region_2, category_id,
           ai_summary, ai_tags,
           embedding::text AS embedding_text,
           latitude, longitude,
           {haversine} AS distance_km,
           1 - (embedding <=> %(query_vec)s::vector) AS similarity
    FROM places
    WHERE is_active = TRUE
      AND embedding IS NOT NULL
      {radius_clause}
    ORDER BY similarity DESC
    LIMIT %(top_k)s
"""

_FALLBACK_SEARCH = """
    SELECT place_id, name, region_1, region_2, category_id,
           ai_summary, ai_tags,
           embedding AS embedding_text,
           latitude, longitude,
           {haversine} AS distance_km
    FROM places
    WHERE is_active = TRUE
      AND embedding IS NOT NULL
      {radius_clause}
    ORDER BY created_at DESC
    LIMIT %(prefetch)s
"""


def search_places_by_vector(
    conn,
    query_embedding: list[float],
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    radius_km: Optional[float] = None,
    top_k: int = 10,
) -> list[dict]:
    """
    벡터 유사도 검색 (+ 선택적 위치 반경 필터).

    Parameters
    ----------
    query_embedding : 검색 질의 임베딩 (1536차원)
    lat, lng        : 기준 좌표 (None 이면 위치 필터 없음)
    radius_km       : 반경(km). lat/lng 없으면 무시
    top_k           : 반환 최대 건수

    Returns
    -------
    list of dict, 유사도 내림차순 정렬.
    각 dict: place_id, name, region_1, region_2, similarity, distance_km
    """
    use_location = (lat is not None and lng is not None)

    haversine_expr = _HAVERSINE_KM if use_location else "NULL"

    radius_clause = ""
    if use_location and radius_km is not None:
        radius_clause = f"AND {_HAVERSINE_KM} <= %(radius_km)s"

    params: dict = {"top_k": top_k}
    if use_location:
        params.update({"lat": lat, "lng": lng})
    if radius_km is not None:
        params["radius_km"] = radius_km

    with conn.cursor() as cur:

        if _PGVECTOR:
            # ── pgvector SQL 경로 ──────────────────────────────────────
            params["query_vec"] = query_embedding
            sql = _VECTOR_SEARCH_PG.format(
                haversine=haversine_expr,
                radius_clause=radius_clause,
            )
            cur.execute(sql, params)
            rows = [dict(r) for r in cur.fetchall()]
            for r in rows:
                r.pop("embedding_text", None)   # 불필요한 raw 벡터 제거
            return rows

        else:
            # ── Python fallback 경로 ──────────────────────────────────
            # 1) Haversine 필터 + 전체 후보를 prefetch
            prefetch = max(top_k * 20, 200)
            params["prefetch"] = prefetch
            sql = _FALLBACK_SEARCH.format(
                haversine=haversine_expr,
                radius_clause=radius_clause,
            )
            cur.execute(sql, params)
            rows = cur.fetchall()

        # 2) Python 코사인 유사도 계산 후 상위 top_k 반환
        scored = []
        for r in rows:
            r = dict(r)
            try:
                emb = json.loads(r.pop("embedding_text") or "null")
                if emb:
                    r["similarity"] = _cosine_sim(query_embedding, emb)
                else:
                    r["similarity"] = 0.0
            except Exception:
                r["similarity"] = 0.0
            scored.append(r)

        scored.sort(key=lambda x: x["similarity"], reverse=True)
        return scored[:top_k]


# ─────────────────────────────────────────────
# 처리 이력 로깅
# ─────────────────────────────────────────────

_LOG_SQL = """
INSERT INTO ai_processing_log (target_table, target_id, step, status, message)
VALUES (%(target_table)s, %(target_id)s, %(step)s, %(status)s, %(message)s)
"""


def log_step(
    conn,
    target_id: int,
    step: str,              # fetch | ai_tag | ai_embed | upsert
    status: str,            # success | fail | skip
    message: str = None,
    target_table: str = "places",
) -> None:
    with conn.cursor() as cur:
        cur.execute(_LOG_SQL, {
            "target_table": target_table,
            "target_id":    target_id,
            "step":         step,
            "status":       status,
            "message":      message,
        })
    conn.commit()


# ─────────────────────────────────────────────
# 증분 동기화 헬퍼
# ─────────────────────────────────────────────

def get_stored_mod_times(
    conn,
    content_type_ids: list[int],
    region_names: list[str],
) -> dict[str, str]:
    """
    증분 sync 기준값 조회.

    비활성(is_active=FALSE) 행을 포함해 조회한다.
    포함하지 않으면 soft-delete 후 API에 재등장한 항목을 '신규'로 오인해
    INSERT를 시도하다 unique 충돌이 발생한다.
    ON CONFLICT 경로로 정상 재활성화하려면 반드시 비활성 행도 대상에 넣어야 한다.

    Returns
    -------
    dict[contentid, modifiedtime_str]
        modifiedtime_str 형식: "YYYYMMDDHHMMSS" — TourAPI 응답과 직접 비교 가능.
        tourapi_modified_time 컬럼이 NULL인 행은 빈 문자열("")로 반환.
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT tourapi_content_id,
                   TO_CHAR(tourapi_modified_time, 'YYYYMMDDHH24MISS') AS mod_str
            FROM   places
            WHERE  tourapi_content_id IS NOT NULL
              AND  category_id = ANY(%(types)s)
              AND  region_1    = ANY(%(regions)s)
        """, {"types": content_type_ids, "regions": region_names})
        return {
            r["tourapi_content_id"]: (r["mod_str"] or "")
            for r in cur.fetchall()
        }


def soft_delete_missing(
    conn,
    seen_ids: set[str],
    content_type_ids: list[int],
    region_names: list[str],
    dry_run: bool = False,
) -> list[dict]:
    """
    이번 API 스캔에서 사라진 장소를 is_active=FALSE 로 soft delete.

    물리 삭제를 하지 않으므로 잘못된 삭제 발생 시 수동 복구 가능.
    seen_ids 가 비어있으면 API 장애로 판단하고 아무것도 하지 않는다.

    Parameters
    ----------
    seen_ids    : 이번 스캔에서 확인된 전체 tourapi_content_id 집합
    dry_run     : True 이면 UPDATE 없이 대상 목록만 반환

    Returns
    -------
    soft delete 대상 행 목록 (place_id, name, tourapi_content_id).
    dry_run=True 이면 실제 변경 없이 목록만 반환.
    """
    if not seen_ids:
        logger.warning("[soft_delete_missing] seen_ids 가 비어있음 — API 장애 가능성, 처리 건너뜀")
        return []

    with conn.cursor() as cur:
        cur.execute("""
            SELECT place_id, name, tourapi_content_id
            FROM   places
            WHERE  is_active = TRUE
              AND  tourapi_content_id IS NOT NULL
              AND  NOT (tourapi_content_id = ANY(%(seen)s))
              AND  category_id = ANY(%(types)s)
              AND  region_1    = ANY(%(regions)s)
        """, {
            "seen":    list(seen_ids),
            "types":   content_type_ids,
            "regions": region_names,
        })
        targets = [dict(r) for r in cur.fetchall()]

        if not dry_run and targets:
            cur.execute("""
                UPDATE places
                SET    is_active  = FALSE,
                       updated_at = NOW()
                WHERE  place_id   = ANY(%(ids)s)
            """, {"ids": [r["place_id"] for r in targets]})

    if not dry_run and targets:
        conn.commit()

    return targets
