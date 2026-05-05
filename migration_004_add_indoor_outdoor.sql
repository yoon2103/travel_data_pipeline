-- =============================================================
-- Migration 004: indoor_outdoor 컬럼 추가
-- 대상: places 테이블
-- 허용값: indoor / outdoor / mixed
-- NULL 허용: 미분류 행 유지
-- =============================================================

ALTER TABLE places
    ADD COLUMN IF NOT EXISTS indoor_outdoor VARCHAR(10)
        CHECK (indoor_outdoor IS NULL OR indoor_outdoor IN ('indoor', 'outdoor', 'mixed'));

COMMENT ON COLUMN places.indoor_outdoor IS '실내외 구분: indoor / outdoor / mixed — 규칙 배치(batch_rules.py) 1차 분류';
