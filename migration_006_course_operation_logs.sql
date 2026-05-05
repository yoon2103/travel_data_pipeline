CREATE TABLE IF NOT EXISTS course_generation_logs (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    region TEXT,
    option TEXT,
    place_count INTEGER,
    total_travel_minutes INTEGER,
    selected_radius_km NUMERIC(8, 2),
    has_option_notice BOOLEAN NOT NULL DEFAULT FALSE,
    missing_slot_reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_course_generation_logs_created_at
    ON course_generation_logs (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_course_generation_logs_region_option
    ON course_generation_logs (region, option);

CREATE TABLE IF NOT EXISTS course_extend_logs (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    region TEXT,
    option TEXT,
    before_place_count INTEGER,
    after_place_count INTEGER,
    success BOOLEAN NOT NULL DEFAULT FALSE,
    fail_reason TEXT,
    total_travel_minutes INTEGER
);

CREATE INDEX IF NOT EXISTS idx_course_extend_logs_created_at
    ON course_extend_logs (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_course_extend_logs_region_option
    ON course_extend_logs (region, option);
