-- =============================================================
-- Migration 007: Data update batch pipeline tables
-- Purpose:
--   Keep public-data refreshes isolated from the production places table
--   until backup, normalization, AI enrichment, QA, and smoke tests pass.
-- =============================================================

BEGIN;

CREATE TABLE IF NOT EXISTS data_update_runs (
    run_id                  UUID PRIMARY KEY,
    mode                    VARCHAR(30) NOT NULL DEFAULT 'incremental',
    dry_run                 BOOLEAN NOT NULL DEFAULT TRUE,
    promote                 BOOLEAN NOT NULL DEFAULT FALSE,
    status                  VARCHAR(30) NOT NULL DEFAULT 'RUNNING',
    started_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at             TIMESTAMPTZ,
    last_sync_time_at_start TIMESTAMPTZ,
    backup_path             TEXT,
    raw_count               INTEGER NOT NULL DEFAULT 0,
    clean_count             INTEGER NOT NULL DEFAULT 0,
    invalid_count           INTEGER NOT NULL DEFAULT 0,
    staging_count           INTEGER NOT NULL DEFAULT 0,
    qa_status               VARCHAR(30),
    smoke_status            VARCHAR(30),
    error_message           TEXT,
    metadata                JSONB NOT NULL DEFAULT '{}'::jsonb,
    CHECK (status IN ('RUNNING', 'SUCCESS', 'FAILED', 'DRY_RUN_SUCCESS')),
    CHECK (qa_status IS NULL OR qa_status IN ('PASS', 'WEAK', 'FAIL', 'SKIPPED')),
    CHECK (smoke_status IS NULL OR smoke_status IN ('PASS', 'FAIL', 'SKIPPED'))
);

CREATE TABLE IF NOT EXISTS data_sync_state (
    source              VARCHAR(50) PRIMARY KEY,
    last_sync_time      TIMESTAMPTZ,
    last_success_run_id UUID REFERENCES data_update_runs(run_id),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO data_sync_state (source, last_sync_time)
VALUES ('tourapi', NULL)
ON CONFLICT (source) DO NOTHING;

CREATE TABLE IF NOT EXISTS data_update_step_logs (
    id           BIGSERIAL PRIMARY KEY,
    run_id       UUID NOT NULL REFERENCES data_update_runs(run_id) ON DELETE CASCADE,
    step_name    VARCHAR(80) NOT NULL,
    status       VARCHAR(30) NOT NULL,
    started_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at  TIMESTAMPTZ,
    input_count  INTEGER NOT NULL DEFAULT 0,
    output_count INTEGER NOT NULL DEFAULT 0,
    message      TEXT,
    metadata     JSONB NOT NULL DEFAULT '{}'::jsonb,
    CHECK (status IN ('RUNNING', 'SUCCESS', 'FAILED', 'SKIPPED'))
);

CREATE TABLE IF NOT EXISTS raw_places (
    id                  BIGSERIAL PRIMARY KEY,
    run_id              UUID NOT NULL REFERENCES data_update_runs(run_id) ON DELETE CASCADE,
    source              VARCHAR(50) NOT NULL DEFAULT 'tourapi',
    tourapi_content_id  VARCHAR(40),
    content_type_id     INTEGER,
    area_code           INTEGER,
    sigungu_code        INTEGER,
    modified_time       TIMESTAMPTZ,
    raw_payload         JSONB NOT NULL,
    collected_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (run_id, source, tourapi_content_id)
);

CREATE TABLE IF NOT EXISTS clean_places (
    id                          BIGSERIAL PRIMARY KEY,
    run_id                      UUID NOT NULL REFERENCES data_update_runs(run_id) ON DELETE CASCADE,
    tourapi_content_id          VARCHAR(40) NOT NULL,
    name                        VARCHAR(255) NOT NULL,
    category_id                 INTEGER,
    region_1                    VARCHAR(50),
    region_2                    VARCHAR(50),
    latitude                    DOUBLE PRECISION,
    longitude                   DOUBLE PRECISION,
    overview                    TEXT,
    first_image_url             TEXT,
    first_image_thumb_url       TEXT,
    tourapi_modified_time       TIMESTAMPTZ,
    normalized_payload          JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (run_id, tourapi_content_id)
);

CREATE TABLE IF NOT EXISTS invalid_places (
    id                  BIGSERIAL PRIMARY KEY,
    run_id              UUID NOT NULL REFERENCES data_update_runs(run_id) ON DELETE CASCADE,
    source              VARCHAR(50) NOT NULL DEFAULT 'tourapi',
    tourapi_content_id  VARCHAR(40),
    name                VARCHAR(255),
    reason_code         VARCHAR(80) NOT NULL,
    reason_message      TEXT,
    raw_payload         JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS staging_places (
    id                          BIGSERIAL PRIMARY KEY,
    run_id                      UUID NOT NULL REFERENCES data_update_runs(run_id) ON DELETE CASCADE,
    tourapi_content_id          VARCHAR(40) NOT NULL,
    name                        VARCHAR(255) NOT NULL,
    category_id                 INTEGER,
    region_1                    VARCHAR(50),
    region_2                    VARCHAR(50),
    latitude                    DOUBLE PRECISION,
    longitude                   DOUBLE PRECISION,
    overview                    TEXT,
    first_image_url             TEXT,
    first_image_thumb_url       TEXT,
    ai_summary                  TEXT NOT NULL,
    ai_tags                     JSONB NOT NULL,
    embedding                   JSONB,
    visit_role                  VARCHAR(30) NOT NULL,
    estimated_duration          INTEGER NOT NULL,
    visit_time_slot             TEXT[] NOT NULL,
    ai_validation_status        VARCHAR(30) NOT NULL DEFAULT 'success',
    ai_validation_errors        JSONB NOT NULL DEFAULT '[]'::jsonb,
    tourapi_modified_time       TIMESTAMPTZ,
    staged_at                   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (run_id, tourapi_content_id),
    CHECK (visit_role IN ('spot', 'culture', 'meal', 'cafe')),
    CHECK (jsonb_typeof(ai_tags) = 'object' AND ai_tags <> '{}'::jsonb),
    CHECK (length(trim(ai_summary)) >= 20),
    CHECK (estimated_duration > 0),
    CHECK (array_length(visit_time_slot, 1) > 0)
);

CREATE TABLE IF NOT EXISTS place_update_snapshots (
    id                  BIGSERIAL PRIMARY KEY,
    run_id              UUID NOT NULL REFERENCES data_update_runs(run_id) ON DELETE CASCADE,
    place_id            BIGINT NOT NULL,
    tourapi_content_id  VARCHAR(40),
    before_payload      JSONB NOT NULL,
    snapshot_created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (run_id, place_id)
);

CREATE TABLE IF NOT EXISTS data_update_qa_results (
    id                      BIGSERIAL PRIMARY KEY,
    run_id                  UUID NOT NULL REFERENCES data_update_runs(run_id) ON DELETE CASCADE,
    status                  VARCHAR(30) NOT NULL,
    pass_count              INTEGER NOT NULL DEFAULT 0,
    weak_count              INTEGER NOT NULL DEFAULT 0,
    fail_count              INTEGER NOT NULL DEFAULT 0,
    place_count_distribution JSONB NOT NULL DEFAULT '{}'::jsonb,
    report_path             TEXT,
    result_payload          JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (status IN ('PASS', 'WEAK', 'FAIL', 'SKIPPED'))
);

CREATE INDEX IF NOT EXISTS idx_raw_places_run_id ON raw_places(run_id);
CREATE INDEX IF NOT EXISTS idx_raw_places_modified_time ON raw_places(modified_time);
CREATE INDEX IF NOT EXISTS idx_clean_places_run_id ON clean_places(run_id);
CREATE INDEX IF NOT EXISTS idx_invalid_places_run_id ON invalid_places(run_id);
CREATE INDEX IF NOT EXISTS idx_staging_places_run_id ON staging_places(run_id);
CREATE INDEX IF NOT EXISTS idx_staging_places_region_role ON staging_places(region_1, visit_role);
CREATE INDEX IF NOT EXISTS idx_place_update_snapshots_run_id ON place_update_snapshots(run_id);
CREATE INDEX IF NOT EXISTS idx_data_update_step_logs_run_id ON data_update_step_logs(run_id);

COMMIT;
