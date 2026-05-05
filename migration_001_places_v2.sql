-- =============================================================
-- Migration 001: places 확장 + course 3-tier + ai_validation_log
-- =============================================================
-- 전제: schema.sql 또는 schema_final.sql 이 이미 적용된 상태
-- 원칙: schema.sql / schema_final.sql 은 절대 수정하지 않는다
--       기존 travel_courses / course_places 는 유지 (병존)
--       naver_place_id / kakao_place_id 는 이미 존재 → ADD COLUMN 생략
-- =============================================================

BEGIN;

-- =============================================================
-- 1. places 테이블 신규 컬럼 12개 추가
-- =============================================================

ALTER TABLE places
    ADD COLUMN IF NOT EXISTS data_source          VARCHAR(20)  DEFAULT 'tourapi',
    ADD COLUMN IF NOT EXISTS visit_role           VARCHAR(20),
    ADD COLUMN IF NOT EXISTS estimated_duration   INT,
    ADD COLUMN IF NOT EXISTS visit_time_slot      VARCHAR(20)[],
    ADD COLUMN IF NOT EXISTS visit_theme          JSONB,
    ADD COLUMN IF NOT EXISTS opening_hours        JSONB,
    ADD COLUMN IF NOT EXISTS rating               NUMERIC(3,2),
    ADD COLUMN IF NOT EXISTS review_count         INT,
    ADD COLUMN IF NOT EXISTS source_confidence    NUMERIC(4,3) DEFAULT 0.500,
    ADD COLUMN IF NOT EXISTS last_enriched_at     TIMESTAMP,
    ADD COLUMN IF NOT EXISTS ai_validation_status VARCHAR(20)  DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS ai_validation_errors JSONB;

-- =============================================================
-- 2. CHECK CONSTRAINT 4개
-- 주의: 기존 place_reviews.rating 의 CHECK 와 테이블이 달라 이름 충돌 없음
--       chk_places_rating 으로 명시해 구분
--       DO $$ 블록으로 이미 존재하는 constraint 재적용 방지 (멱등 실행 보장)
-- =============================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_visit_role' AND conrelid = 'places'::regclass
    ) THEN
        ALTER TABLE places
            ADD CONSTRAINT chk_visit_role
            CHECK (visit_role IN ('meal', 'cafe', 'spot', 'rest') OR visit_role IS NULL);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_estimated_duration' AND conrelid = 'places'::regclass
    ) THEN
        ALTER TABLE places
            ADD CONSTRAINT chk_estimated_duration
            CHECK (estimated_duration BETWEEN 10 AND 240 OR estimated_duration IS NULL);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_places_rating' AND conrelid = 'places'::regclass
    ) THEN
        ALTER TABLE places
            ADD CONSTRAINT chk_places_rating
            CHECK (rating BETWEEN 0 AND 5 OR rating IS NULL);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_source_confidence' AND conrelid = 'places'::regclass
    ) THEN
        ALTER TABLE places
            ADD CONSTRAINT chk_source_confidence
            CHECK (source_confidence BETWEEN 0 AND 1 OR source_confidence IS NULL);
    END IF;
END $$;

-- =============================================================
-- 3. 신규 인덱스 3개
-- idx_places_ai_tags 는 schema.sql 에 이미 존재 → 다른 이름 사용
-- =============================================================

CREATE INDEX IF NOT EXISTS idx_places_visit_role
    ON places (visit_role) WHERE visit_role IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_places_validation_status
    ON places (ai_validation_status) WHERE ai_validation_status IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_places_visit_theme
    ON places USING GIN (visit_theme) WHERE visit_theme IS NOT NULL;

-- =============================================================
-- 4. 코스 3-tier 테이블 (기존 travel_courses / course_places 유지)
-- =============================================================

CREATE TABLE IF NOT EXISTS course_master (
    course_id       BIGSERIAL  PRIMARY KEY,
    user_id         BIGINT,
    title           VARCHAR(200),
    region_code     VARCHAR(20),
    trip_start_date DATE,
    trip_end_date   DATE,
    party_size      INT,
    concept_tags    JSONB,
    created_at      TIMESTAMP  DEFAULT NOW()
);

COMMENT ON TABLE course_master IS 'AI 생성/사용자 저장 여행 코스 헤더 (3-tier 구조 최상위)';

CREATE TABLE IF NOT EXISTS course_day (
    course_day_id    BIGSERIAL  PRIMARY KEY,
    course_id        BIGINT     NOT NULL REFERENCES course_master(course_id) ON DELETE CASCADE,
    day_no           INT        NOT NULL,
    start_time       TIME,
    end_time         TIME,
    lodging_place_id BIGINT,
    UNIQUE (course_id, day_no)
);

COMMENT ON TABLE course_day IS '코스 일차별 구조 (course_master → course_day)';

CREATE TABLE IF NOT EXISTS course_item (
    course_item_id         BIGSERIAL    PRIMARY KEY,
    course_day_id          BIGINT       NOT NULL REFERENCES course_day(course_day_id) ON DELETE CASCADE,
    item_order             INT          NOT NULL,
    place_id               BIGINT       NOT NULL,
    visit_role             VARCHAR(20)  NOT NULL,
    planned_start_at       TIMESTAMP,
    planned_end_at         TIMESTAMP,
    stay_minutes           INT,
    move_minutes_from_prev INT,
    distance_km_from_prev  NUMERIC(6,2),
    selection_basis        JSONB        NOT NULL,
    fallback_reason        VARCHAR(100),
    created_at             TIMESTAMP    DEFAULT NOW(),
    UNIQUE (course_day_id, item_order)
);

COMMENT ON TABLE course_item IS '코스 내 장소 배치 단위. selection_basis 는 추천 근거 불변 스냅샷.';

CREATE INDEX IF NOT EXISTS idx_course_item_day
    ON course_item (course_day_id, item_order);

CREATE INDEX IF NOT EXISTS idx_course_item_place
    ON course_item (place_id);

CREATE INDEX IF NOT EXISTS idx_course_item_basis
    ON course_item USING GIN (selection_basis);

-- =============================================================
-- 5. ai_validation_log 테이블
-- =============================================================

CREATE TABLE IF NOT EXISTS ai_validation_log (
    log_id           BIGSERIAL    PRIMARY KEY,
    place_id         BIGINT,
    pipeline_stage   VARCHAR(50)  NOT NULL,
    invalid_field    VARCHAR(50),
    raw_value        TEXT,
    fallback_value   TEXT,
    reason           VARCHAR(100) NOT NULL,
    payload_snapshot JSONB,
    created_at       TIMESTAMP    DEFAULT NOW()
);

COMMENT ON TABLE ai_validation_log IS 'AI 가공 결과 검증 실패 이력 — fallback 발생 시 자동 적재';

CREATE INDEX IF NOT EXISTS idx_ai_val_log_place
    ON ai_validation_log (place_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ai_val_log_stage
    ON ai_validation_log (pipeline_stage, reason);

COMMIT;
