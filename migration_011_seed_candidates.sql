-- =============================================================
-- Migration 011: Seed candidate staging / governance
-- Scope:
--   Stage reviewed representative POIs as seed candidates before any
--   tourism_belt.py or recommendation-engine change.
--
-- Important:
--   - Does not modify tourism_belt.py.
--   - Does not insert/update places.
--   - Does not integrate overlays into the recommendation engine.
-- =============================================================

BEGIN;

CREATE TABLE IF NOT EXISTS seed_candidates (
    seed_candidate_id            BIGSERIAL PRIMARY KEY,

    region_1                     VARCHAR(50) NOT NULL,
    region_2                     VARCHAR(50),

    expected_poi_name            VARCHAR(255) NOT NULL,
    existing_seed_name           VARCHAR(255),
    representative_candidate_id  BIGINT REFERENCES representative_poi_candidates(candidate_id) ON DELETE SET NULL,

    source_type                  VARCHAR(30) NOT NULL DEFAULT 'REPRESENTATIVE_POI',
    candidate_place_name         VARCHAR(255) NOT NULL,

    promote_strategy             VARCHAR(40) NOT NULL DEFAULT 'COEXIST_WITH_EXISTING',
    seed_status                  VARCHAR(40) NOT NULL DEFAULT 'CANDIDATE',
    review_status                VARCHAR(40) NOT NULL DEFAULT 'PENDING_REVIEW',

    risk_flags                   JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_payload               JSONB NOT NULL DEFAULT '{}'::jsonb,
    validation_payload           JSONB NOT NULL DEFAULT '{}'::jsonb,
    review_payload               JSONB NOT NULL DEFAULT '{}'::jsonb,
    dry_run_payload              JSONB NOT NULL DEFAULT '{}'::jsonb,
    rollback_payload             JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at                   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                   TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (source_type IN ('REPRESENTATIVE_POI', 'MANUAL', 'TOURAPI', 'KAKAO', 'NAVER')),
    CHECK (promote_strategy IN (
        'KEEP_EXISTING_ONLY',
        'COEXIST_WITH_EXISTING',
        'REPLACE_EXISTING',
        'REPRESENTATIVE_ALIAS_ONLY'
    )),
    CHECK (seed_status IN (
        'CANDIDATE',
        'NEEDS_REVIEW',
        'APPROVED',
        'REJECTED',
        'COEXIST',
        'READY_FOR_PROMOTE',
        'PROMOTED',
        'ROLLED_BACK'
    )),
    CHECK (review_status IN (
        'PENDING_REVIEW',
        'IN_REVIEW',
        'APPROVED',
        'REJECTED',
        'SKIPPED'
    )),
    CHECK (jsonb_typeof(risk_flags) = 'array'),
    CHECK (length(trim(expected_poi_name)) > 0),
    CHECK (length(trim(candidate_place_name)) > 0)
);

CREATE INDEX IF NOT EXISTS idx_seed_candidates_region_status
    ON seed_candidates(region_1, region_2, seed_status, review_status);

CREATE INDEX IF NOT EXISTS idx_seed_candidates_expected_name
    ON seed_candidates(expected_poi_name);

CREATE INDEX IF NOT EXISTS idx_seed_candidates_representative
    ON seed_candidates(representative_candidate_id)
    WHERE representative_candidate_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_seed_candidates_strategy
    ON seed_candidates(promote_strategy, seed_status, review_status);

CREATE UNIQUE INDEX IF NOT EXISTS uq_seed_candidates_active_candidate
    ON seed_candidates(
        region_1,
        COALESCE(region_2, ''),
        expected_poi_name,
        candidate_place_name,
        promote_strategy
    )
    WHERE seed_status NOT IN ('REJECTED', 'ROLLED_BACK');

COMMENT ON TABLE seed_candidates IS
    'Staging table for seed governance. No direct tourism_belt.py, places, or engine mutation.';

COMMENT ON COLUMN seed_candidates.promote_strategy IS
    'KEEP_EXISTING_ONLY, COEXIST_WITH_EXISTING, REPLACE_EXISTING, or REPRESENTATIVE_ALIAS_ONLY.';

COMMENT ON COLUMN seed_candidates.dry_run_payload IS
    'Dry-run impact analysis payload. Must be reviewed before any future seed overlay promote.';

COMMIT;
