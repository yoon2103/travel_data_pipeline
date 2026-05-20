-- external_places_data_pipeline_phase1_migration_draft.sql
--
-- DRAFT ONLY. Do not apply to production in this phase.
--
-- Purpose:
--   Extend the existing Kakao/Naver external place pipeline from a simple
--   raw -> clean -> staging_places flow into a governed data-quality platform.
--   Final draft scope is intentionally small: source quality fields,
--   duplicate/business/review status, QA status, and approved-only promote gates.
--
-- Safety:
--   - No production places mutation.
--   - No recommendation engine changes.
--   - No fake POI insertion.
--   - Promotion must remain blocked unless QA and human review pass.

BEGIN;

-- 1. Preserve richer external source signals at raw collection time.
ALTER TABLE raw_external_places
    ADD COLUMN IF NOT EXISTS rating NUMERIC(3,2),
    ADD COLUMN IF NOT EXISTS review_count INTEGER,
    ADD COLUMN IF NOT EXISTS image_url TEXT,
    ADD COLUMN IF NOT EXISTS image_thumb_url TEXT,
    ADD COLUMN IF NOT EXISTS business_status VARCHAR(40),
    ADD COLUMN IF NOT EXISTS opening_hours JSONB,
    ADD COLUMN IF NOT EXISTS last_verified_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS source_confidence NUMERIC(4,3);

-- 2. Preserve normalized quality fields after cleaning/dedup.
ALTER TABLE clean_external_places
    ADD COLUMN IF NOT EXISTS rating NUMERIC(3,2),
    ADD COLUMN IF NOT EXISTS review_count INTEGER,
    ADD COLUMN IF NOT EXISTS image_url TEXT,
    ADD COLUMN IF NOT EXISTS image_thumb_url TEXT,
    ADD COLUMN IF NOT EXISTS business_status VARCHAR(40),
    ADD COLUMN IF NOT EXISTS opening_hours JSONB,
    ADD COLUMN IF NOT EXISTS last_verified_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS source_confidence NUMERIC(4,3),
    ADD COLUMN IF NOT EXISTS duplicate_of_place_id BIGINT,
    ADD COLUMN IF NOT EXISTS match_status VARCHAR(40) NOT NULL DEFAULT 'unmatched',
    ADD COLUMN IF NOT EXISTS match_confidence NUMERIC(4,3);

-- 3. Separate external promotion candidates from generic staging_places.
--    Existing staging_places can continue to be used for QA simulation, but
--    this table holds reviewable candidates and prevents direct places writes.
CREATE TABLE IF NOT EXISTS staging_external_places (
    id                       BIGSERIAL PRIMARY KEY,
    run_id                   UUID NOT NULL REFERENCES data_update_runs(run_id) ON DELETE CASCADE,
    clean_external_place_id  BIGINT REFERENCES clean_external_places(id) ON DELETE SET NULL,
    source                   VARCHAR(30) NOT NULL,
    external_id              VARCHAR(120) NOT NULL,
    external_content_id      VARCHAR(180) NOT NULL,
    name                     VARCHAR(255) NOT NULL,
    region                   VARCHAR(50) NOT NULL,
    region_2                 VARCHAR(50),
    latitude                 DOUBLE PRECISION NOT NULL,
    longitude                DOUBLE PRECISION NOT NULL,
    category                 TEXT,
    visit_role               VARCHAR(30) NOT NULL,
    address                  TEXT,
    phone                    VARCHAR(80),
    place_url                TEXT,
    image_url                TEXT,
    image_thumb_url          TEXT,
    image_source             VARCHAR(40),
    image_confidence         VARCHAR(20),
    image_license_note       TEXT,
    image_reviewer           VARCHAR(120),
    image_review_note        TEXT,
    image_reviewed_at        TIMESTAMPTZ,
    image_block_reason       TEXT,
    image_review_status      VARCHAR(40) NOT NULL DEFAULT 'pending',
    rating                   NUMERIC(3,2),
    review_count             INTEGER,
    business_status          VARCHAR(40),
    opening_hours            JSONB,
    last_verified_at         TIMESTAMPTZ,
    source_confidence        NUMERIC(4,3),
    duplicate_of_place_id    BIGINT,
    match_status             VARCHAR(40) NOT NULL DEFAULT 'unmatched',
    match_confidence         NUMERIC(4,3),
    duplicate_review_status  VARCHAR(30) NOT NULL DEFAULT 'unreviewed',
    business_safety_status   VARCHAR(30) NOT NULL DEFAULT 'unknown',
    proposed_action          VARCHAR(30) NOT NULL DEFAULT 'candidate_insert',
    promotion_status         VARCHAR(30) NOT NULL DEFAULT 'pending_review',
    qa_status                VARCHAR(30),
    qa_report_path           TEXT,
    reviewer                 VARCHAR(120),
    review_note              TEXT,
    promotion_block_reason   TEXT,
    normalized_payload       JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at              TIMESTAMPTZ,
    UNIQUE (run_id, source, external_id),
    UNIQUE (run_id, external_content_id),
    CHECK (source IN ('kakao', 'naver')),
    CHECK (visit_role IN ('cafe', 'meal', 'culture', 'spot')),
    CHECK (rating IS NULL OR rating BETWEEN 0 AND 5),
    CHECK (review_count IS NULL OR review_count >= 0),
    CHECK (source_confidence IS NULL OR source_confidence BETWEEN 0 AND 1),
    CHECK (match_confidence IS NULL OR match_confidence BETWEEN 0 AND 1),
    CHECK (duplicate_review_status IN ('unreviewed', 'unique', 'duplicate', 'needs_manual_review')),
    CHECK (business_safety_status IN ('unknown', 'safe', 'closed', 'suspicious', 'needs_manual_review')),
    CHECK (image_confidence IS NULL OR image_confidence IN ('HIGH', 'MEDIUM', 'LOW', 'NONE')),
    CHECK (image_review_status IN ('pending', 'approved', 'rejected', 'blocked_license', 'low_confidence', 'needs_manual_review')),
    CHECK (proposed_action IN ('candidate_insert', 'candidate_update', 'candidate_skip')),
    CHECK (promotion_status IN ('pending_review', 'approved', 'rejected', 'promoted', 'blocked')),
    CHECK (qa_status IS NULL OR qa_status IN ('PASS', 'WEAK', 'FAIL', 'SKIPPED'))
);

-- 4. image_enrichment_candidates is intentionally deferred.
--    The next migration should stay small and use only staging_external_places
--    image review columns. A separate image workbench table can be reconsidered
--    only after the staging-based review gate is proven operationally necessary.

CREATE INDEX IF NOT EXISTS idx_raw_external_places_verified
    ON raw_external_places(region, source, last_verified_at);

CREATE INDEX IF NOT EXISTS idx_clean_external_places_match
    ON clean_external_places(run_id, region, match_status, visit_role);

CREATE INDEX IF NOT EXISTS idx_staging_external_places_review
    ON staging_external_places(run_id, region, promotion_status, qa_status);

CREATE INDEX IF NOT EXISTS idx_staging_external_places_source_id
    ON staging_external_places(source, external_id);

CREATE INDEX IF NOT EXISTS idx_staging_external_places_duplicate_review
    ON staging_external_places(run_id, duplicate_review_status, duplicate_of_place_id);

CREATE INDEX IF NOT EXISTS idx_staging_external_places_business_safety
    ON staging_external_places(run_id, business_safety_status, promotion_status);

CREATE INDEX IF NOT EXISTS idx_staging_external_places_image_review
    ON staging_external_places(run_id, image_review_status, image_confidence);

COMMIT;

-- Promote guard proposal. This is intentionally documented as SQL and should
-- not be wired to production promote until a separate implementation phase.
--
-- A candidate can be promoted only when all of these are true:
--   qa_status = 'PASS'
--   promotion_status = 'approved'
--   duplicate_review_status IN ('unique', 'needs_manual_review') with reviewer note for manual review
--   business_safety_status = 'safe'
--   image is present OR image_review_status = 'approved' with image_url and image_license_note
--   proposed_action IN ('candidate_insert', 'candidate_update')
--   required fields: source, external_id, name, region, latitude, longitude, visit_role
--
-- Suggested dry-run query:
--
-- SELECT id, source, external_id, name, region, visit_role, proposed_action
-- FROM staging_external_places
-- WHERE run_id = :run_id
--   AND qa_status = 'PASS'
--   AND promotion_status = 'approved'
--   AND business_safety_status = 'safe'
--   AND duplicate_review_status IN ('unique', 'needs_manual_review')
--   AND source IN ('kakao', 'naver')
--   AND external_id IS NOT NULL
--   AND name IS NOT NULL
--   AND region IS NOT NULL
--   AND latitude IS NOT NULL
--   AND longitude IS NOT NULL
--   AND visit_role IN ('cafe', 'meal', 'culture', 'spot')
--   AND (
--       image_url IS NOT NULL
--       OR (
--           image_review_status = 'approved'
--           AND image_url IS NOT NULL
--           AND image_license_note IS NOT NULL
--       )
--   );
