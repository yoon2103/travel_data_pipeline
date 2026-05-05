-- =============================================================
-- 여행 서비스 고도화 DB 스키마
-- PostgreSQL + pgvector
-- OpenAI text-embedding-3-small (dim: 1536)
-- =============================================================

-- -------------------------------------------------------------
-- Extensions
-- -------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS pgvector;
-- PostGIS 확장 준비 (추후 활성화)
-- CREATE EXTENSION IF NOT EXISTS postgis;


-- =============================================================
-- 1. 기준 코드 테이블
-- =============================================================

-- TourAPI 콘텐츠 타입 코드
CREATE TABLE content_types (
    content_type_id   SMALLINT    PRIMARY KEY,
    type_name         VARCHAR(50) NOT NULL,
    type_name_en      VARCHAR(50),
    description       TEXT
);

COMMENT ON TABLE content_types IS 'TourAPI contentTypeId 기준 코드 (12:관광지, 14:문화시설, 15:축제행사, 25:여행코스, 28:레포츠, 32:숙박, 38:쇼핑, 39:음식점)';

INSERT INTO content_types (content_type_id, type_name, type_name_en) VALUES
    (12,  '관광지',   'Tourist Attraction'),
    (14,  '문화시설', 'Cultural Facility'),
    (15,  '축제/행사','Festival & Event'),
    (25,  '여행코스', 'Travel Course'),
    (28,  '레포츠',   'Leisure & Sports'),
    (32,  '숙박',     'Accommodation'),
    (38,  '쇼핑',     'Shopping'),
    (39,  '음식점',   'Restaurant');


-- 시/도 코드 (TourAPI areaCode)
CREATE TABLE areas (
    area_code         SMALLINT    PRIMARY KEY,
    area_name         VARCHAR(30) NOT NULL
);

COMMENT ON TABLE areas IS 'TourAPI 시/도 지역 코드';

INSERT INTO areas (area_code, area_name) VALUES
    (1,  '서울'), (2,  '인천'), (3,  '대전'), (4,  '대구'),
    (5,  '광주'), (6,  '부산'), (7,  '울산'), (8,  '세종'),
    (31, '경기'), (32, '강원'), (33, '충북'), (34, '충남'),
    (35, '경북'), (36, '경남'), (37, '전북'), (38, '전남'),
    (39, '제주');


-- 시/군/구 코드 (TourAPI sigunguCode)
CREATE TABLE sigungu (
    area_code         SMALLINT    NOT NULL REFERENCES areas(area_code),
    sigungu_code      SMALLINT    NOT NULL,
    sigungu_name      VARCHAR(30) NOT NULL,
    PRIMARY KEY (area_code, sigungu_code)
);

COMMENT ON TABLE sigungu IS 'TourAPI 시/군/구 세부 지역 코드';


-- =============================================================
-- 2. 장소 핵심 테이블 (TourAPI 원본 + AI 가공)
-- =============================================================

CREATE TABLE places (
    -- ---- 식별자 ----
    place_id          BIGSERIAL   PRIMARY KEY,

    -- ---- 외부 식별자 (NULL 허용) ----
    tourapi_content_id VARCHAR(20) UNIQUE,           -- TourAPI contentid
    naver_place_id     VARCHAR(50) UNIQUE,           -- 네이버 플레이스 ID
    kakao_place_id     VARCHAR(50) UNIQUE,           -- 카카오 장소 ID

    content_type_id   SMALLINT    NOT NULL REFERENCES content_types(content_type_id),

    -- ---- 기본 정보 ----
    title             VARCHAR(200) NOT NULL,
    title_en          VARCHAR(200),                  -- AI 번역 (선택)
    addr1             VARCHAR(255),                  -- 주소
    addr2             VARCHAR(100),                  -- 상세 주소
    zipcode           VARCHAR(10),
    tel               VARCHAR(50),
    homepage          TEXT,
    overview          TEXT,                          -- 장소 소개 원문

    -- ---- 지리 정보 (PostGIS 전환 대비 FLOAT8 사용) ----
    longitude         FLOAT8,                        -- mapx (경도)
    latitude          FLOAT8,                        -- mapy (위도)
    area_code         SMALLINT    REFERENCES areas(area_code),
    sigungu_code      SMALLINT,
    -- PostGIS 전환 시: geom GEOMETRY(Point, 4326) GENERATED ALWAYS AS (ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)) STORED

    -- ---- 이미지 ----
    first_image       TEXT,                          -- 대표 이미지 URL
    first_image_thumb TEXT,                          -- 썸네일 URL

    -- ---- AI 가공 데이터 ----
    ai_summary        TEXT,                          -- AI 생성 요약 (한국어)
    ai_summary_en     TEXT,                          -- AI 생성 요약 (영어)
    ai_tags           JSONB,                         -- AI 분류 태그 (검색 최적화)
    embedding         VECTOR(1536),                  -- OpenAI text-embedding-3-small

    -- ---- TourAPI 메타 ----
    modified_time     TIMESTAMP,                     -- TourAPI modifiedtime
    created_time      TIMESTAMP,                     -- TourAPI createdtime

    -- ---- 시스템 ----
    is_active         BOOLEAN     NOT NULL DEFAULT TRUE,
    synced_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),  -- API 마지막 동기화 시각
    ai_processed_at   TIMESTAMPTZ,                   -- AI 가공 완료 시각
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_sigungu FOREIGN KEY (area_code, sigungu_code)
        REFERENCES sigungu (area_code, sigungu_code)
);

COMMENT ON TABLE places IS '관광지/숙박/음식점 등 멀티소스 원본 데이터 + AI 가공 데이터 통합 테이블';
COMMENT ON COLUMN places.tourapi_content_id IS 'TourAPI contentid — NULL 허용, 네이버/카카오 단독 장소는 없을 수 있음';
COMMENT ON COLUMN places.naver_place_id     IS '네이버 플레이스 고유 ID — NULL 허용';
COMMENT ON COLUMN places.kakao_place_id     IS '카카오 장소 고유 ID — NULL 허용';
COMMENT ON COLUMN places.ai_tags IS 'AI 분류 태그. 예: {"themes":["자연","힐링"],"mood":["조용한"],"season":["봄","가을"],"companion":["가족","커플"]}';
COMMENT ON COLUMN places.embedding IS 'AI 생성 설명 기반 1536차원 임베딩 벡터 (OpenAI text-embedding-3-small)';


-- =============================================================
-- 3. 이미지 테이블 (다중 이미지)
-- =============================================================

CREATE TABLE place_images (
    image_id          BIGSERIAL   PRIMARY KEY,
    place_id          BIGINT      NOT NULL REFERENCES places(place_id) ON DELETE CASCADE,
    tourapi_content_id VARCHAR(20),
    image_url         TEXT        NOT NULL,
    image_url_small   TEXT,
    serial_num        SMALLINT,                      -- TourAPI serialnum
    img_name          VARCHAR(200),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE place_images IS '장소 다중 이미지 (TourAPI detailImage API)';


-- =============================================================
-- 4. 타입별 상세 정보 테이블
-- =============================================================

-- 숙박 상세 (contentTypeId=32)
CREATE TABLE accommodation_details (
    place_id          BIGINT      PRIMARY KEY REFERENCES places(place_id) ON DELETE CASCADE,
    benikia           VARCHAR(5),       -- 베니키아 여부
    goodstay          VARCHAR(5),       -- 굿스테이 여부
    hanok             VARCHAR(5),       -- 한옥 여부
    room_count        SMALLINT,
    checkin_time      VARCHAR(20),
    checkout_time     VARCHAR(20),
    parking           TEXT,
    reservation_url   TEXT,
    sub_facility      TEXT,
    barbecue          BOOLEAN,
    beauty            BOOLEAN,
    beverage          BOOLEAN,
    bicycle           BOOLEAN,
    campfire          BOOLEAN,
    fitness           BOOLEAN,
    karaoke           BOOLEAN,
    pickup            BOOLEAN,
    public_bath       BOOLEAN,
    sauna             BOOLEAN,
    seminar           BOOLEAN,
    sports            BOOLEAN
);

-- 음식점 상세 (contentTypeId=39)
CREATE TABLE restaurant_details (
    place_id          BIGINT      PRIMARY KEY REFERENCES places(place_id) ON DELETE CASCADE,
    open_time         TEXT,
    rest_date         TEXT,
    menu             TEXT,
    pack_lunch        VARCHAR(10),      -- 도시락 판매
    reservation       TEXT,
    smoking           VARCHAR(10),
    kid_facility      VARCHAR(10),      -- 어린이 놀이방
    seat             SMALLINT,
    credit_card_yn    VARCHAR(5),
    takeout_yn        VARCHAR(5),
    main_menu         VARCHAR(200)
);

-- 관광지 상세 (contentTypeId=12)
CREATE TABLE tourist_spot_details (
    place_id          BIGINT      PRIMARY KEY REFERENCES places(place_id) ON DELETE CASCADE,
    heritage1         SMALLINT,         -- 세계문화유산 유무
    heritage2         SMALLINT,         -- 세계자연유산 유무
    heritage3         SMALLINT,         -- 세계기록유산 유무
    infocenter        TEXT,             -- 문의 및 안내
    open_date         VARCHAR(30),
    restdate          TEXT,
    usetime           TEXT,
    expguide          TEXT,
    parking           TEXT,
    chkpet            VARCHAR(10),
    chkbabycarriage   VARCHAR(10),
    chkcreditcard     VARCHAR(10),
    accom_count       INT,              -- 수용 인원
    useseason         TEXT
);


-- =============================================================
-- 5. 여행 코스 (AI 생성 + 사용자 저장)
-- =============================================================

CREATE TABLE travel_courses (
    course_id         BIGSERIAL   PRIMARY KEY,
    title             VARCHAR(200) NOT NULL,
    description       TEXT,
    region_name       VARCHAR(100),
    area_code         SMALLINT    REFERENCES areas(area_code),
    duration_days     SMALLINT    NOT NULL DEFAULT 1,
    themes            JSONB,                         -- 예: ["자연","힐링","가족여행"]
    companion_type    VARCHAR(50),                   -- 혼자/커플/가족/친구
    total_distance_km FLOAT8,
    estimated_budget  INT,                           -- 예상 경비 (원)
    source            VARCHAR(20) NOT NULL DEFAULT 'ai',  -- 'ai' | 'user' | 'tourapi'
    is_public         BOOLEAN     NOT NULL DEFAULT TRUE,
    view_count        INT         NOT NULL DEFAULT 0,
    like_count        INT         NOT NULL DEFAULT 0,
    embedding         VECTOR(1536),                  -- 코스 전체 임베딩
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE travel_courses IS 'AI 생성 또는 사용자 저장 여행 코스';


-- 코스 구성 장소 (순서 포함)
CREATE TABLE course_places (
    course_place_id   BIGSERIAL   PRIMARY KEY,
    course_id         BIGINT      NOT NULL REFERENCES travel_courses(course_id) ON DELETE CASCADE,
    place_id          BIGINT      NOT NULL REFERENCES places(place_id),
    day_number        SMALLINT    NOT NULL DEFAULT 1,  -- 몇 일차
    order_in_day      SMALLINT    NOT NULL DEFAULT 1,  -- 당일 순서
    visit_duration_min SMALLINT,                       -- 예상 체류 시간 (분)
    travel_time_min   SMALLINT,                        -- 다음 장소까지 이동 시간 (분)
    memo              TEXT,
    UNIQUE (course_id, day_number, order_in_day)
);

COMMENT ON TABLE course_places IS '여행 코스 내 장소 순서 매핑';


-- =============================================================
-- 6. 사용자 (간략화 — 실제 서비스는 별도 auth 모듈 연동)
-- =============================================================

CREATE TABLE users (
    user_id           BIGSERIAL   PRIMARY KEY,
    external_id       VARCHAR(100) UNIQUE,           -- OAuth sub / 외부 식별자
    nickname          VARCHAR(50),
    email             VARCHAR(150),
    preferences       JSONB,                         -- 여행 취향 설정
    embedding         VECTOR(1536),                  -- 사용자 취향 임베딩
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON COLUMN users.preferences IS '사용자 취향. 예: {"themes":["액티비티"],"regions":[1,6],"companion":"family"}';


-- 사용자 저장 코스
CREATE TABLE user_saved_courses (
    user_id           BIGINT      NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    course_id         BIGINT      NOT NULL REFERENCES travel_courses(course_id) ON DELETE CASCADE,
    saved_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, course_id)
);

-- 사용자 찜 장소
CREATE TABLE user_liked_places (
    user_id           BIGINT      NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    place_id          BIGINT      NOT NULL REFERENCES places(place_id) ON DELETE CASCADE,
    liked_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, place_id)
);


-- =============================================================
-- 7. 외부 수집 리뷰 (네이버 블로그, 카카오맵, 영수증 등)
-- =============================================================

CREATE TABLE place_reviews (
    review_id         BIGSERIAL   PRIMARY KEY,
    place_id          BIGINT      NOT NULL REFERENCES places(place_id) ON DELETE CASCADE,

    -- ---- 출처 ----
    source            VARCHAR(30) NOT NULL,           -- 'naver_blog' | 'naver_map' | 'kakao_map' | 'receipt' | 'google'
    source_review_id  VARCHAR(100),                   -- 원본 시스템의 리뷰 ID (중복 적재 방지)
    source_url        TEXT,                           -- 원문 URL (블로그 포스팅 등)

    -- ---- 리뷰 내용 ----
    content           TEXT        NOT NULL,           -- 리뷰 원문
    rating            NUMERIC(2,1) CHECK (rating BETWEEN 0 AND 5),  -- 출처별 평점 (없으면 NULL)
    written_at        DATE,                           -- 작성일자 (크롤링 기준)
    author_name       VARCHAR(100),                   -- 작성자 닉네임 (익명화 가능)

    -- ---- AI 가공 ----
    ai_sentiment      VARCHAR(20) CHECK (ai_sentiment IN ('positive', 'negative', 'neutral')),
    ai_summary        TEXT,                           -- AI 요약
    embedding         VECTOR(1536),                   -- 리뷰 임베딩 (유사 리뷰 클러스터링용)

    -- ---- 시스템 ----
    is_visible        BOOLEAN     NOT NULL DEFAULT TRUE,
    collected_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_place_reviews_source UNIQUE (source, source_review_id)
);

COMMENT ON TABLE place_reviews IS '네이버 블로그/맵, 카카오맵, 영수증 등 외부 수집 리뷰 원문 및 AI 가공 결과';
COMMENT ON COLUMN place_reviews.source IS '수집 출처: naver_blog | naver_map | kakao_map | receipt | google';
COMMENT ON COLUMN place_reviews.source_review_id IS '원본 시스템 식별자 — source와 함께 UNIQUE 제약으로 중복 적재 방지';
COMMENT ON COLUMN place_reviews.embedding IS '리뷰 원문 기반 1536차원 임베딩 — 유사 리뷰 클러스터링 및 감성 분석에 활용';


-- =============================================================
-- 8. 사용자 작성 리뷰
-- =============================================================

CREATE TABLE reviews (
    review_id         BIGSERIAL   PRIMARY KEY,
    place_id          BIGINT      NOT NULL REFERENCES places(place_id) ON DELETE CASCADE,
    user_id           BIGINT      REFERENCES users(user_id) ON DELETE SET NULL,
    rating            SMALLINT    NOT NULL CHECK (rating BETWEEN 1 AND 5),
    content           TEXT,
    visit_date        DATE,
    companion_type    VARCHAR(30),
    ai_sentiment      VARCHAR(20),                   -- 'positive' | 'negative' | 'neutral'
    ai_summary        TEXT,                          -- AI 요약 리뷰
    is_visible        BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- =============================================================
-- 9. AI 처리 이력 (파이프라인 모니터링)
-- =============================================================

CREATE TABLE ai_processing_log (
    log_id            BIGSERIAL   PRIMARY KEY,
    place_id          BIGINT      REFERENCES places(place_id) ON DELETE SET NULL,
    task_type         VARCHAR(50) NOT NULL,          -- 'embedding' | 'tagging' | 'summary' | 'translation'
    model_name        VARCHAR(100),                  -- 'text-embedding-3-small' 등
    status            VARCHAR(20) NOT NULL DEFAULT 'pending',  -- 'pending'|'success'|'failed'
    input_tokens      INT,
    error_message     TEXT,
    processed_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE ai_processing_log IS 'AI 가공 파이프라인 실행 이력 및 오류 추적';


-- =============================================================
-- 10. 인덱스
-- =============================================================

-- 외부 식별자 조회
CREATE INDEX idx_places_tourapi_id   ON places (tourapi_content_id) WHERE tourapi_content_id IS NOT NULL;
CREATE INDEX idx_places_naver_id     ON places (naver_place_id)     WHERE naver_place_id IS NOT NULL;
CREATE INDEX idx_places_kakao_id     ON places (kakao_place_id)     WHERE kakao_place_id IS NOT NULL;

-- 기본 조회
CREATE INDEX idx_places_content_type ON places (content_type_id);
CREATE INDEX idx_places_area         ON places (area_code, sigungu_code);
CREATE INDEX idx_places_active       ON places (is_active) WHERE is_active = TRUE;
CREATE INDEX idx_places_synced_at    ON places (synced_at);
CREATE INDEX idx_places_ai_proc      ON places (ai_processed_at) WHERE ai_processed_at IS NULL;

-- 위치 기반 (PostGIS 전환 전 임시)
CREATE INDEX idx_places_geo          ON places (latitude, longitude)
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL;

-- JSONB 태그 검색
CREATE INDEX idx_places_ai_tags      ON places USING GIN (ai_tags);

-- Vector 유사도 검색 (IVFFlat — 데이터 적재 후 생성 권장)
-- 주석 처리: 데이터 삽입 후 아래 명령으로 생성
-- CREATE INDEX idx_places_embedding ON places USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
-- CREATE INDEX idx_courses_embedding ON travel_courses USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);

-- 여행 코스
CREATE INDEX idx_course_places_course ON course_places (course_id, day_number, order_in_day);
CREATE INDEX idx_courses_themes        ON travel_courses USING GIN (themes);

-- 외부 수집 리뷰
CREATE INDEX idx_place_reviews_place    ON place_reviews (place_id, is_visible);
CREATE INDEX idx_place_reviews_source   ON place_reviews (source, written_at DESC);
CREATE INDEX idx_place_reviews_ai_proc  ON place_reviews (collected_at) WHERE embedding IS NULL;
-- CREATE INDEX idx_place_reviews_emb   ON place_reviews USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- 사용자 리뷰
CREATE INDEX idx_reviews_place        ON reviews (place_id, is_visible);
CREATE INDEX idx_reviews_user         ON reviews (user_id);

-- AI 처리 이력
CREATE INDEX idx_ai_log_status        ON ai_processing_log (status, task_type);
CREATE INDEX idx_ai_log_place         ON ai_processing_log (place_id, task_type);


-- =============================================================
-- 11. updated_at 자동 갱신 트리거
-- =============================================================

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_places_updated_at
    BEFORE UPDATE ON places
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_courses_updated_at
    BEFORE UPDATE ON travel_courses
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
