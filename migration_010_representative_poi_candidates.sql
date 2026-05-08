-- =============================================================
-- Migration 010: Representative POI candidate staging
-- Scope:
--   Stage externally discovered or manually curated representative POI
--   candidates before any production place/seed changes.
--
-- Important:
--   - Does not insert into or update places.
--   - Does not modify tourism_belt.py.
--   - Does not create recommendation-engine dependencies.
--   - Candidates must pass review before any later promotion workflow.
-- =============================================================

BEGIN;

CREATE TABLE IF NOT EXISTS representative_poi_candidates (
    candidate_id           BIGSERIAL PRIMARY KEY,

    -- Expected landmark from the representative POI audit list.
    expected_poi_name      VARCHAR(255) NOT NULL,
    region_1               VARCHAR(50) NOT NULL,
    region_2               VARCHAR(50),

    -- Optional match to an existing places row. Many candidates are expected
    -- to be DB-missing at first, so this must stay nullable.
    matched_place_id       BIGINT REFERENCES places(place_id) ON DELETE SET NULL,

    -- Source candidate payload.
    source_type            VARCHAR(30) NOT NULL,
    source_place_id        VARCHAR(180),
    source_name            VARCHAR(255) NOT NULL,
    category               TEXT,
    address                TEXT,
    road_address           TEXT,
    latitude               DOUBLE PRECISION,
    longitude              DOUBLE PRECISION,
    phone                  VARCHAR(80),
    image_url              TEXT,
    overview               TEXT,

    -- Validation/review fields.
    confidence_score       NUMERIC(5,2),
    representative_status  VARCHAR(30) NOT NULL DEFAULT 'CANDIDATE',
    review_status          VARCHAR(30) NOT NULL DEFAULT 'PENDING_REVIEW',
    promote_status         VARCHAR(30) NOT NULL DEFAULT 'PENDING',

    source_payload         JSONB NOT NULL DEFAULT '{}'::jsonb,
    validation_payload     JSONB NOT NULL DEFAULT '{}'::jsonb,
    review_payload         JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (source_type IN ('TOURAPI', 'KAKAO', 'NAVER', 'MANUAL')),
    CHECK (representative_status IN ('CANDIDATE', 'NEEDS_REVIEW', 'APPROVED', 'REJECTED', 'PROMOTED')),
    CHECK (review_status IN ('PENDING_REVIEW', 'IN_REVIEW', 'APPROVED', 'REJECTED', 'SKIPPED', 'PROMOTED')),
    CHECK (promote_status IN ('PENDING', 'NOT_READY', 'READY', 'PROMOTED', 'SKIPPED', 'ROLLED_BACK')),
    CHECK (confidence_score IS NULL OR confidence_score BETWEEN 0 AND 100),
    CHECK ((latitude IS NULL AND longitude IS NULL) OR (latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180)),
    CHECK (length(trim(expected_poi_name)) > 0)
);

CREATE INDEX IF NOT EXISTS idx_representative_poi_candidates_region_status
    ON representative_poi_candidates(region_1, review_status, promote_status, confidence_score DESC);

CREATE INDEX IF NOT EXISTS idx_representative_poi_candidates_expected_name
    ON representative_poi_candidates(expected_poi_name);

CREATE INDEX IF NOT EXISTS idx_representative_poi_candidates_source
    ON representative_poi_candidates(source_type, source_place_id)
    WHERE source_place_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_representative_poi_candidates_matched_place
    ON representative_poi_candidates(matched_place_id)
    WHERE matched_place_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_representative_poi_candidates_source
    ON representative_poi_candidates(region_1, expected_poi_name, source_type, source_place_id)
    WHERE source_place_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_representative_poi_candidates_manual_url
    ON representative_poi_candidates(region_1, expected_poi_name, source_type, md5(COALESCE(image_url, '') || COALESCE(source_name, '') || COALESCE(address, '')))
    WHERE source_type = 'MANUAL';

COMMENT ON TABLE representative_poi_candidates IS
    'Staging table for representative landmark candidates. No direct places or seed mutation.';

COMMENT ON COLUMN representative_poi_candidates.expected_poi_name IS
    'Canonical representative POI name expected by the audit list, e.g. 경포대 or 불국사.';

COMMENT ON COLUMN representative_poi_candidates.matched_place_id IS
    'Optional existing places row if a safe match is found. Nullable for DB-missing representative POIs.';

COMMENT ON COLUMN representative_poi_candidates.representative_status IS
    'Candidate lifecycle: CANDIDATE, NEEDS_REVIEW, APPROVED, REJECTED, PROMOTED.';

COMMENT ON COLUMN representative_poi_candidates.promote_status IS
    'Promotion readiness only. Promotion must be handled by a separate guarded workflow.';

COMMIT;
