-- =============================================================
-- Migration 009: Place enrichment staging tables
-- Scope:
--   Store external/AI/manual enrichment candidates for existing places
--   without changing production places immediately.
--   Promotion into places must be handled by a separate guarded batch.
--
-- Important:
--   - No recommendation-engine changes.
--   - No course_builder JOIN requirement.
--   - No direct overwrite of places.first_image_url or other production fields.
-- =============================================================

BEGIN;

CREATE TABLE IF NOT EXISTS place_enrichment_runs (
    run_id              UUID PRIMARY KEY,
    enrichment_type     VARCHAR(40) NOT NULL,
    source_type         VARCHAR(40) NOT NULL,
    status              VARCHAR(30) NOT NULL DEFAULT 'PENDING',
    target_region       VARCHAR(50),
    target_role         VARCHAR(30),
    started_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at         TIMESTAMPTZ,
    candidate_count     INTEGER NOT NULL DEFAULT 0,
    selected_count      INTEGER NOT NULL DEFAULT 0,
    promoted_count      INTEGER NOT NULL DEFAULT 0,
    skipped_count       INTEGER NOT NULL DEFAULT 0,
    failed_count        INTEGER NOT NULL DEFAULT 0,
    error_message       TEXT,
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,
    CHECK (enrichment_type IN ('IMAGE', 'MOOD', 'BUSINESS_STATUS', 'DESCRIPTION', 'PLACE_MATCH')),
    CHECK (source_type IN ('TOURAPI', 'KAKAO', 'NAVER', 'MANUAL', 'AI_GENERATED')),
    CHECK (status IN ('PENDING', 'RUNNING', 'VALID', 'INVALID', 'READY', 'PROMOTED', 'SKIPPED', 'FAILED', 'ROLLED_BACK'))
);

CREATE TABLE IF NOT EXISTS place_enrichment_candidates (
    candidate_id                  BIGSERIAL PRIMARY KEY,
    run_id                        UUID REFERENCES place_enrichment_runs(run_id) ON DELETE SET NULL,
    place_id                      BIGINT NOT NULL REFERENCES places(place_id) ON DELETE CASCADE,

    enrichment_type               VARCHAR(40) NOT NULL,
    source_type                   VARCHAR(40) NOT NULL,
    source_place_id               VARCHAR(180),
    source_category               TEXT,
    source_confidence             NUMERIC(4,3),

    -- IMAGE enrichment fields. Kept nullable so the table can also hold
    -- mood, business status, description, and place-match candidates.
    image_url                     TEXT,
    thumbnail_url                 TEXT,
    image_quality_score           NUMERIC(5,2),
    existing_image_quality_score  NUMERIC(5,2),

    -- Kakao/Naver quality signals for cafe/meal/culture/indoor places.
    external_rating               NUMERIC(3,2),
    review_count                  INTEGER,
    business_status               VARCHAR(40),
    validity_status               VARCHAR(40) NOT NULL DEFAULT 'PENDING',
    mood_keywords                 TEXT[],
    indoor_outdoor                VARCHAR(20),
    place_quality_score           NUMERIC(5,2),

    validation_status             VARCHAR(30) NOT NULL DEFAULT 'PENDING',
    validation_reason             TEXT,
    promote_status                VARCHAR(30) NOT NULL DEFAULT 'PENDING',
    promote_reason                TEXT,
    review_status                 VARCHAR(40) NOT NULL DEFAULT 'PENDING_REVIEW',
    review_payload                JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_selected                   BOOLEAN NOT NULL DEFAULT FALSE,

    is_place_valid                BOOLEAN NOT NULL DEFAULT TRUE,
    place_invalid_reason          TEXT,

    source_payload                JSONB NOT NULL DEFAULT '{}'::jsonb,
    enrichment_payload            JSONB NOT NULL DEFAULT '{}'::jsonb,
    validation_payload            JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at                    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                    TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (enrichment_type IN ('IMAGE', 'MOOD', 'BUSINESS_STATUS', 'DESCRIPTION', 'PLACE_MATCH')),
    CHECK (source_type IN ('TOURAPI', 'KAKAO', 'NAVER', 'MANUAL', 'AI_GENERATED')),
    CHECK (source_confidence IS NULL OR source_confidence BETWEEN 0 AND 1),
    CHECK (image_quality_score IS NULL OR image_quality_score BETWEEN 0 AND 100),
    CHECK (existing_image_quality_score IS NULL OR existing_image_quality_score BETWEEN 0 AND 100),
    CHECK (external_rating IS NULL OR external_rating BETWEEN 0 AND 5),
    CHECK (review_count IS NULL OR review_count >= 0),
    CHECK (business_status IS NULL OR business_status IN ('OPEN', 'CLOSED', 'TEMP_CLOSED', 'UNKNOWN')),
    CHECK (validity_status IN ('PENDING', 'VALID', 'INVALID', 'READY', 'PROMOTED', 'SKIPPED', 'ROLLED_BACK')),
    CHECK (indoor_outdoor IS NULL OR indoor_outdoor IN ('indoor', 'outdoor', 'mixed')),
    CHECK (place_quality_score IS NULL OR place_quality_score BETWEEN 0 AND 100),
    CHECK (validation_status IN ('PENDING', 'VALID', 'INVALID', 'READY', 'PROMOTED', 'SKIPPED', 'ROLLED_BACK')),
    CHECK (promote_status IN ('PENDING', 'VALID', 'INVALID', 'READY', 'PROMOTED', 'SKIPPED', 'ROLLED_BACK')),
    CHECK (review_status IN ('PENDING_REVIEW', 'IN_REVIEW', 'APPROVED', 'REJECTED', 'SKIPPED', 'AUTO_APPROVED', 'ROLLED_BACK')),
    CHECK (enrichment_type <> 'IMAGE' OR image_url IS NOT NULL),
    CHECK (image_url IS NULL OR length(trim(image_url)) > 0)
);

CREATE TABLE IF NOT EXISTS place_enrichment_promotions (
    promotion_id              BIGSERIAL PRIMARY KEY,
    candidate_id              BIGINT NOT NULL REFERENCES place_enrichment_candidates(candidate_id),
    run_id                    UUID REFERENCES place_enrichment_runs(run_id) ON DELETE SET NULL,
    place_id                  BIGINT NOT NULL REFERENCES places(place_id) ON DELETE CASCADE,
    enrichment_type           VARCHAR(40) NOT NULL,

    before_payload            JSONB NOT NULL DEFAULT '{}'::jsonb,
    after_payload             JSONB NOT NULL DEFAULT '{}'::jsonb,

    promoted_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    promoted_by               VARCHAR(80),
    rollback_status           VARCHAR(30) NOT NULL DEFAULT 'PENDING',
    rolled_back_at            TIMESTAMPTZ,
    rollback_reason           TEXT,

    CHECK (enrichment_type IN ('IMAGE', 'MOOD', 'BUSINESS_STATUS', 'DESCRIPTION', 'PLACE_MATCH')),
    CHECK (rollback_status IN ('PENDING', 'PROMOTED', 'ROLLED_BACK', 'FAILED'))
);

CREATE INDEX IF NOT EXISTS idx_place_enrichment_runs_started_at
    ON place_enrichment_runs(started_at DESC);

CREATE INDEX IF NOT EXISTS idx_place_enrichment_candidates_place_status
    ON place_enrichment_candidates(place_id, enrichment_type, validation_status, promote_status);

CREATE INDEX IF NOT EXISTS idx_place_enrichment_candidates_ready
    ON place_enrichment_candidates(place_id, enrichment_type, place_quality_score DESC, image_quality_score DESC, created_at DESC)
    WHERE validation_status = 'VALID'
      AND promote_status = 'READY'
      AND is_selected = TRUE
      AND is_place_valid = TRUE;

CREATE INDEX IF NOT EXISTS idx_place_enrichment_candidates_source
    ON place_enrichment_candidates(source_type, source_place_id)
    WHERE source_place_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_place_enrichment_candidates_run_id
    ON place_enrichment_candidates(run_id);

CREATE INDEX IF NOT EXISTS idx_place_enrichment_promotions_place_id
    ON place_enrichment_promotions(place_id, enrichment_type, promoted_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS uq_place_enrichment_candidate_source_payload
    ON place_enrichment_candidates(place_id, enrichment_type, source_type, source_place_id, md5(enrichment_payload::text))
    WHERE source_place_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_place_enrichment_selected_ready
    ON place_enrichment_candidates(place_id, enrichment_type)
    WHERE is_selected = TRUE
      AND validation_status = 'VALID'
      AND promote_status IN ('READY', 'PROMOTED');

COMMENT ON TABLE place_enrichment_runs IS
    'Place enrichment batch run metadata. Does not modify places directly.';

COMMENT ON TABLE place_enrichment_candidates IS
    'Generic staging table for place quality enrichment candidates: images, mood, business status, descriptions, and place matching.';

COMMENT ON TABLE place_enrichment_promotions IS
    'Promotion audit table storing before/after payloads for rollback.';

COMMIT;
