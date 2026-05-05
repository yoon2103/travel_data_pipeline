-- migration_005_add_saved_course_place_snapshots.sql
-- 저장 코스 외부 API 보강 스냅샷 테이블
--
-- 목적:
--   - 사용자가 코스를 저장한 경우에만 외부(Naver/Kakao) 보강 결과를 별도 저장
--   - places 마스터 테이블에는 외부 API 결과 저장 금지
--   - 원본 API 응답 JSON 저장 금지
--   - 재조회/표시/거리계산 보조용 최소 필드만 저장
--   - 엔진 후보 선정 기준으로 사용 금지

CREATE TABLE IF NOT EXISTS saved_course_place_snapshots (

    -- 기본 키
    snapshot_id             BIGSERIAL PRIMARY KEY,

    -- 연결 키
    saved_course_id         BIGINT      NOT NULL,
    saved_course_place_id   BIGINT      NOT NULL,
    place_id                BIGINT      NOT NULL,

    -- 외부 보강 출처
    external_source         VARCHAR(20),                    -- 'naver' | 'kakao' | 'none'
    external_place_name     VARCHAR(255),
    external_address        TEXT,
    external_latitude       DOUBLE PRECISION,
    external_longitude      DOUBLE PRECISION,

    -- 표시용 정보 (화면 렌더링 전용)
    external_image_url      TEXT,
    external_rating         NUMERIC(3,2),
    external_review_count   INTEGER,
    external_phone          VARCHAR(50),
    external_open_status    VARCHAR(50),

    -- 재조회/경로 재계산 보조
    -- 기준 좌표는 여전히 places 우선, 이 컬럼은 표시·경로 보조용
    display_name            VARCHAR(255),
    display_latitude        DOUBLE PRECISION,
    display_longitude       DOUBLE PRECISION,
    snapshot_distance_from_original_km  NUMERIC(6,3),      -- 외부 좌표와 places 좌표 간 거리

    -- 메타
    captured_at             TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    expires_at              TIMESTAMPTZ,                    -- NULL = 만료 없음
    raw_storage_allowed     BOOLEAN         NOT NULL DEFAULT FALSE,

    -- 제약
    CONSTRAINT uq_snapshot_per_place UNIQUE (saved_course_place_id),

    CONSTRAINT chk_external_source
        CHECK (external_source IS NULL OR external_source IN ('naver', 'kakao', 'none')),

    CONSTRAINT chk_external_rating
        CHECK (external_rating IS NULL OR (external_rating >= 0 AND external_rating <= 5))
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_snapshots_saved_course
    ON saved_course_place_snapshots (saved_course_id);

CREATE INDEX IF NOT EXISTS idx_snapshots_place_id
    ON saved_course_place_snapshots (place_id);

CREATE INDEX IF NOT EXISTS idx_snapshots_expires
    ON saved_course_place_snapshots (expires_at)
    WHERE expires_at IS NOT NULL;

COMMENT ON TABLE saved_course_place_snapshots IS
    '저장 코스 장소별 외부 API 보강 스냅샷. places 마스터와 분리. 표시/재조회 보조용 전용.';

COMMENT ON COLUMN saved_course_place_snapshots.external_latitude IS
    '외부 API 반환 좌표. 경로 재계산 보조용. 엔진 기준 좌표는 places 우선.';

COMMENT ON COLUMN saved_course_place_snapshots.raw_storage_allowed IS
    '외부 API 원본 JSON 저장 허용 여부. 기본 FALSE — 별도 승인 없이 변경 금지.';
