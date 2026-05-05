-- =============================================================
-- Migration 002: 증분 동기화 지원
-- 전제: schema_final.sql + migration_001_places_v2.sql 적용 완료
-- =============================================================

BEGIN;

ALTER TABLE places
    ADD COLUMN IF NOT EXISTS tourapi_modified_time TIMESTAMP,
    ADD COLUMN IF NOT EXISTS synced_at             TIMESTAMPTZ;  -- DEFAULT 없음: 기존 행은 NULL(미동기화)로 유지

CREATE INDEX IF NOT EXISTS idx_places_mod_time
    ON places (tourapi_modified_time)
    WHERE tourapi_modified_time IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_places_synced_at
    ON places (synced_at);

COMMENT ON COLUMN places.tourapi_modified_time IS 'TourAPI modifiedtime 원본값 → 증분 동기화 기준';
COMMENT ON COLUMN places.synced_at             IS 'TourAPI 마지막 동기화 시각';

COMMIT;
