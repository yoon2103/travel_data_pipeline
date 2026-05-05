-- =============================================================
-- 확장형 여행 데이터베이스 최종 스키마 (DDL)
-- PostgreSQL + pgvector | OpenAI text-embedding-3-small (1536d)
-- =============================================================


-- =============================================================
-- 1. 확장 활성화
-- =============================================================
CREATE EXTENSION IF NOT EXISTS vector;


-- =============================================================
-- 2. 장소 마스터 테이블 (places)
-- =============================================================
CREATE TABLE IF NOT EXISTS places (
    -- ---- 내부 식별자 ----
    place_id              BIGSERIAL    PRIMARY KEY,

    -- ---- 기본 정보 ----
    name                  VARCHAR(255) NOT NULL,
    category_id           INT,                          -- 공통 카테고리 코드
    region_1              VARCHAR(50),                  -- 시/도
    region_2              VARCHAR(50),                  -- 시/군/구
    latitude              FLOAT8,                       -- 위도  (PostGIS 전환 대비 FLOAT8)
    longitude             FLOAT8,                       -- 경도

    -- ---- 설명 & AI 가공 ----
    overview              TEXT,                         -- 기본 설명 (원문)
    ai_summary            TEXT,                         -- AI 생성 요약
    ai_tags               JSONB,                        -- AI 추출 태그 (GIN 인덱스)
    embedding             VECTOR(1536),                 -- 장소 벡터 (IVFFlat — 적재 후 생성)

    -- ---- 외부 서비스 식별자 (NULL 허용) ----
    tourapi_content_id    VARCHAR(20),
    naver_place_id        VARCHAR(50),
    kakao_place_id        VARCHAR(50),

    -- ---- 운영 ----
    view_count            INT          NOT NULL DEFAULT 0,
    is_active             BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at            TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at            TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE  places                       IS '멀티소스 장소 마스터 — TourAPI·네이버·카카오 통합';
COMMENT ON COLUMN places.category_id           IS '서비스 공통 카테고리 코드 (별도 categories 테이블 참조 가능)';
COMMENT ON COLUMN places.tourapi_content_id    IS 'TourAPI contentid — NULL 허용';
COMMENT ON COLUMN places.naver_place_id        IS '네이버 플레이스 고유 ID — NULL 허용';
COMMENT ON COLUMN places.kakao_place_id        IS '카카오 장소 고유 ID — NULL 허용';
COMMENT ON COLUMN places.ai_tags               IS '예: {"themes":["자연","힐링"],"season":["봄"],"companion":["가족"]}';
COMMENT ON COLUMN places.embedding             IS 'AI 설명 기반 1536차원 벡터 (OpenAI text-embedding-3-small)';

-- Partial Unique Index — NULL 행 제외로 공간 절약 + 출처별 중복 방지
CREATE UNIQUE INDEX idx_places_tourapi_id
    ON places (tourapi_content_id) WHERE tourapi_content_id IS NOT NULL;

CREATE UNIQUE INDEX idx_places_naver_id
    ON places (naver_place_id)     WHERE naver_place_id IS NOT NULL;

CREATE UNIQUE INDEX idx_places_kakao_id
    ON places (kakao_place_id)     WHERE kakao_place_id IS NOT NULL;

-- 일반 조회 인덱스
CREATE INDEX idx_places_region    ON places (region_1, region_2);
CREATE INDEX idx_places_active    ON places (is_active) WHERE is_active = TRUE;
CREATE INDEX idx_places_geo       ON places (latitude, longitude)
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL;

-- JSONB 태그 검색
CREATE INDEX idx_places_ai_tags   ON places USING GIN (ai_tags);

-- Vector 유사도 (IVFFlat — 데이터 1000건 이상 적재 후 활성화 권장)
-- CREATE INDEX idx_places_embedding
--     ON places USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);


-- =============================================================
-- 3. 장소별 외부 수집 리뷰 테이블 (place_reviews)
-- =============================================================
CREATE TABLE IF NOT EXISTS place_reviews (
    review_id             BIGSERIAL    PRIMARY KEY,
    place_id              BIGINT       NOT NULL
                              REFERENCES places (place_id) ON DELETE CASCADE,

    -- ---- 출처 ----
    source                VARCHAR(30)  NOT NULL,        -- naver_blog|naver_map|kakao_map|receipt|google
    source_review_id      VARCHAR(100),                 -- 원본 서비스 내 리뷰 ID (중복 방지)
    source_url            TEXT,                         -- 원문 URL

    -- ---- 리뷰 내용 ----
    content               TEXT         NOT NULL,        -- 리뷰 원문
    rating                NUMERIC(2,1)
                              CHECK (rating BETWEEN 0 AND 5),  -- 출처 평점 (없으면 NULL)
    written_at            DATE,                         -- 작성 일자

    -- ---- AI 가공 ----
    ai_sentiment          VARCHAR(20)
                              CHECK (ai_sentiment IN ('positive', 'negative', 'neutral')),
    ai_summary            TEXT,                         -- AI 요약
    embedding             VECTOR(1536),                 -- 리뷰 텍스트 임베딩 (검색·클러스터링용)

    -- ---- 시스템 ----
    is_visible            BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at            TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE  place_reviews                IS '네이버 블로그/맵·카카오맵·영수증 등 외부 수집 리뷰';
COMMENT ON COLUMN place_reviews.source         IS 'naver_blog | naver_map | kakao_map | receipt | google';
COMMENT ON COLUMN place_reviews.source_review_id IS '(source, source_review_id) UNIQUE — 중복 적재 방지';
COMMENT ON COLUMN place_reviews.embedding      IS '리뷰 원문 기반 1536차원 벡터 — 유사 리뷰 검색·감성 클러스터링';

-- 중복 적재 방지 유니크 인덱스 (source_review_id 가 있는 행만 대상)
CREATE UNIQUE INDEX idx_unique_source_review
    ON place_reviews (source, source_review_id) WHERE source_review_id IS NOT NULL;

-- 조회 인덱스
CREATE INDEX idx_place_reviews_place
    ON place_reviews (place_id, is_visible);

CREATE INDEX idx_place_reviews_source
    ON place_reviews (source, written_at DESC);

-- AI 미처리 리뷰 배치 대상 식별
CREATE INDEX idx_place_reviews_no_embedding
    ON place_reviews (created_at) WHERE embedding IS NULL;

-- Vector 유사도 (데이터 적재 후 활성화)
-- CREATE INDEX idx_place_reviews_embedding
--     ON place_reviews USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);


-- =============================================================
-- 4. AI 처리 이력 테이블 (ai_processing_log)
-- =============================================================
CREATE TABLE IF NOT EXISTS ai_processing_log (
    log_id                BIGSERIAL    PRIMARY KEY,
    target_table          VARCHAR(50)  NOT NULL,        -- 'places' | 'place_reviews'
    target_id             BIGINT       NOT NULL,        -- 해당 테이블의 PK
    step                  VARCHAR(50)  NOT NULL,        -- 'fetch' | 'tag' | 'summarize' | 'embed'
    status                VARCHAR(20)  NOT NULL
                              CHECK (status IN ('success', 'fail', 'skip')),
    message               TEXT,                        -- 오류 메시지 등
    created_at            TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE ai_processing_log IS 'AI 파이프라인 단계별 실행 이력 — 재처리 및 오류 추적용';

CREATE INDEX idx_ai_log_target  ON ai_processing_log (target_table, target_id);
CREATE INDEX idx_ai_log_status  ON ai_processing_log (status, step);


-- =============================================================
-- 5. updated_at 자동 갱신 트리거 (places)
-- =============================================================
CREATE OR REPLACE FUNCTION fn_set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_places_updated_at
    BEFORE UPDATE ON places
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
