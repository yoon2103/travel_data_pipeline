import logging
import psycopg2
import psycopg2.extras

import config

logger = logging.getLogger(__name__)

try:
    from pgvector.psycopg2 import register_vector as _register_vector
    _PGVECTOR_AVAILABLE = True
except ImportError:
    _PGVECTOR_AVAILABLE = False

# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def get_connection() -> psycopg2.extensions.connection:
    conn = psycopg2.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        dbname=config.DB_NAME,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        cursor_factory=psycopg2.extras.DictCursor,
    )
    if _PGVECTOR_AVAILABLE:
        _register_vector(conn)
    return conn


# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------

# ON CONFLICT 절에 Partial Index 조건을 명시해야 PostgreSQL이 해당 인덱스를 인식한다.
_UPSERT_PLACE = """
INSERT INTO places (
    name, category_id, region_1, region_2,
    latitude, longitude, overview,
    tourapi_content_id
) VALUES (
    %(name)s, %(category_id)s, %(region_1)s, %(region_2)s,
    %(latitude)s, %(longitude)s, %(overview)s,
    %(tourapi_content_id)s
)
ON CONFLICT (tourapi_content_id)
    WHERE tourapi_content_id IS NOT NULL
DO UPDATE SET
    name        = EXCLUDED.name,
    category_id = EXCLUDED.category_id,
    region_1    = EXCLUDED.region_1,
    region_2    = EXCLUDED.region_2,
    latitude    = EXCLUDED.latitude,
    longitude   = EXCLUDED.longitude,
    overview    = EXCLUDED.overview,
    updated_at  = NOW()
RETURNING place_id
"""

_UPDATE_AI = """
UPDATE places
SET
    ai_tags    = %(ai_tags)s,
    ai_summary = %(ai_summary)s,
    embedding  = %(embedding)s,
    updated_at = NOW()
WHERE place_id = %(place_id)s
"""

_INSERT_LOG = """
INSERT INTO ai_processing_log
    (target_table, target_id, step, status, message)
VALUES
    (%(target_table)s, %(target_id)s, %(step)s, %(status)s, %(message)s)
"""


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def upsert_place(conn, place_data: dict) -> int:
    """Insert or update a place row. Returns the internal place_id."""
    with conn.cursor() as cur:
        cur.execute(_UPSERT_PLACE, place_data)
        place_id: int = cur.fetchone()[0]
    conn.commit()
    return place_id


def update_ai_fields(conn, place_id: int, ai_tags: dict, ai_summary: str, embedding: list) -> None:
    """Persist AI-generated fields. ai_tags는 dict, embedding은 float list."""
    with conn.cursor() as cur:
        cur.execute(_UPDATE_AI, {
            "place_id":   place_id,
            "ai_tags":    psycopg2.extras.Json(ai_tags),   # dict → JSONB
            "ai_summary": ai_summary,
            "embedding":  embedding,                        # list[float] → vector(1536)
        })
    conn.commit()


def log_processing(
    conn,
    target_table: str,
    target_id: int,
    step: str,
    status: str,            # 'success' | 'fail' | 'skip'
    message: str = None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(_INSERT_LOG, {
            "target_table": target_table,
            "target_id":    target_id,
            "step":         step,
            "status":       status,
            "message":      message,
        })
    conn.commit()
