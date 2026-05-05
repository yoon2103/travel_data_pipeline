-- =============================================================
-- Migration 008: External Places collection/staging pipeline
-- Scope:
--   External cafe/meal/culture candidates from Kakao/Naver are collected
--   into raw/clean tables and can be merged into staging_places.
--   Production places are not modified by this migration.
-- =============================================================

BEGIN;

CREATE TABLE IF NOT EXISTS raw_external_places (
    id                 BIGSERIAL PRIMARY KEY,
    run_id             UUID NOT NULL REFERENCES data_update_runs(run_id) ON DELETE CASCADE,
    region             VARCHAR(50) NOT NULL,
    anchor_lat         DOUBLE PRECISION NOT NULL,
    anchor_lon         DOUBLE PRECISION NOT NULL,
    radius_km          NUMERIC(6,2) NOT NULL,
    keyword            VARCHAR(120) NOT NULL,
    source             VARCHAR(30) NOT NULL,
    external_id        VARCHAR(120) NOT NULL,
    name               VARCHAR(255) NOT NULL,
    latitude           DOUBLE PRECISION,
    longitude          DOUBLE PRECISION,
    category           TEXT,
    address            TEXT,
    phone              VARCHAR(80),
    place_url          TEXT,
    raw_payload        JSONB NOT NULL DEFAULT '{}'::jsonb,
    collected_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (run_id, source, external_id),
    CHECK (source IN ('kakao', 'naver'))
);

CREATE TABLE IF NOT EXISTS clean_external_places (
    id                    BIGSERIAL PRIMARY KEY,
    run_id                UUID NOT NULL REFERENCES data_update_runs(run_id) ON DELETE CASCADE,
    raw_external_place_id BIGINT REFERENCES raw_external_places(id) ON DELETE SET NULL,
    region                VARCHAR(50) NOT NULL,
    source                VARCHAR(30) NOT NULL,
    external_id           VARCHAR(120) NOT NULL,
    external_content_id   VARCHAR(180) NOT NULL,
    name                  VARCHAR(255) NOT NULL,
    latitude              DOUBLE PRECISION NOT NULL,
    longitude             DOUBLE PRECISION NOT NULL,
    category              TEXT,
    address               TEXT,
    phone                 VARCHAR(80),
    place_url             TEXT,
    visit_role            VARCHAR(30) NOT NULL,
    duplicate_key         TEXT,
    normalized_payload    JSONB NOT NULL DEFAULT '{}'::jsonb,
    cleaned_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (run_id, source, external_id),
    UNIQUE (run_id, external_content_id),
    CHECK (source IN ('kakao', 'naver')),
    CHECK (visit_role IN ('cafe', 'meal', 'culture'))
);

ALTER TABLE staging_places
    ADD COLUMN IF NOT EXISTS source VARCHAR(50) NOT NULL DEFAULT 'tourapi',
    ADD COLUMN IF NOT EXISTS external_source VARCHAR(30),
    ADD COLUMN IF NOT EXISTS external_id VARCHAR(120),
    ADD COLUMN IF NOT EXISTS external_content_id VARCHAR(180),
    ADD COLUMN IF NOT EXISTS address TEXT,
    ADD COLUMN IF NOT EXISTS phone VARCHAR(80),
    ADD COLUMN IF NOT EXISTS place_url TEXT,
    ADD COLUMN IF NOT EXISTS indoor_outdoor VARCHAR(20);

CREATE INDEX IF NOT EXISTS idx_raw_external_places_run_id
    ON raw_external_places(run_id);

CREATE INDEX IF NOT EXISTS idx_raw_external_places_region_source
    ON raw_external_places(region, source);

CREATE INDEX IF NOT EXISTS idx_clean_external_places_run_role
    ON clean_external_places(run_id, region, visit_role);

CREATE INDEX IF NOT EXISTS idx_staging_places_external
    ON staging_places(run_id, source, external_source, external_id)
    WHERE source = 'external';

COMMIT;
