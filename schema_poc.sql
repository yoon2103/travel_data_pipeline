-- =============================================================
-- PoC 스키마 — pgvector 없이 동작 (embedding 컬럼 TEXT 임시 대체)
-- pgvector 설치 후 schema_final.sql 로 마이그레이션 예정
-- =============================================================

-- =============================================================
-- 2. 장소 마스터 테이블 (places)
-- =============================================================
CREATE TABLE IF NOT EXISTS places (
    place_id              BIGSERIAL    PRIMARY KEY,

    name                  VARCHAR(255) NOT NULL,
    category_id           INT,
    region_1              VARCHAR(50),
    region_2              VARCHAR(50),
    latitude              FLOAT8,
    longitude             FLOAT8,
    overview              TEXT,
    ai_summary            TEXT,
    ai_tags               JSONB,
    embedding             TEXT,        -- TODO: VECTOR(1536) after pgvector install

    tourapi_content_id    VARCHAR(20),
    naver_place_id        VARCHAR(50),
    kakao_place_id        VARCHAR(50),

    view_count            INT          NOT NULL DEFAULT 0,
    is_active             BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at            TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at            TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Partial Unique Index (외부 식별자 중복 방지)
CREATE UNIQUE INDEX IF NOT EXISTS idx_places_tourapi_id
    ON places (tourapi_content_id) WHERE tourapi_content_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_places_naver_id
    ON places (naver_place_id) WHERE naver_place_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_places_kakao_id
    ON places (kakao_place_id) WHERE kakao_place_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_places_region   ON places (region_1, region_2);
CREATE INDEX IF NOT EXISTS idx_places_active   ON places (is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_places_ai_tags  ON places USING GIN (ai_tags);


-- =============================================================
-- 3. 외부 수집 리뷰 테이블 (place_reviews)
-- =============================================================
CREATE TABLE IF NOT EXISTS place_reviews (
    review_id             BIGSERIAL    PRIMARY KEY,
    place_id              BIGINT       NOT NULL
                              REFERENCES places (place_id) ON DELETE CASCADE,

    source                VARCHAR(30)  NOT NULL,
    source_review_id      VARCHAR(100),
    source_url            TEXT,
    content               TEXT         NOT NULL,
    rating                NUMERIC(2,1) CHECK (rating BETWEEN 0 AND 5),
    written_at            DATE,
    ai_sentiment          VARCHAR(20)  CHECK (ai_sentiment IN ('positive','negative','neutral')),
    ai_summary            TEXT,
    embedding             TEXT,        -- TODO: VECTOR(1536) after pgvector install

    is_visible            BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at            TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_source_review
        UNIQUE (source, source_review_id)
);

CREATE INDEX IF NOT EXISTS idx_place_reviews_place
    ON place_reviews (place_id, is_visible);

CREATE INDEX IF NOT EXISTS idx_place_reviews_source
    ON place_reviews (source, written_at DESC);


-- =============================================================
-- 4. AI 처리 이력 (ai_processing_log)
-- =============================================================
CREATE TABLE IF NOT EXISTS ai_processing_log (
    log_id                BIGSERIAL    PRIMARY KEY,
    target_table          VARCHAR(50)  NOT NULL,
    target_id             BIGINT       NOT NULL,
    step                  VARCHAR(50)  NOT NULL,
    status                VARCHAR(20)  NOT NULL
                              CHECK (status IN ('success','fail','skip')),
    message               TEXT,
    created_at            TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ai_log_target ON ai_processing_log (target_table, target_id);
CREATE INDEX IF NOT EXISTS idx_ai_log_status ON ai_processing_log (status, step);


-- =============================================================
-- 5. updated_at 자동 갱신 트리거
-- =============================================================
CREATE OR REPLACE FUNCTION fn_set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_places_updated_at ON places;
CREATE TRIGGER trg_places_updated_at
    BEFORE UPDATE ON places
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
