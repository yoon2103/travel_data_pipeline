-- =============================================================
-- Migration 002: places 대표 이미지 컬럼 추가
-- 대상: first_image_url, first_image_thumb_url
-- 기존 행: NULL 로 초기화 (데이터 손상 없음)
-- =============================================================

ALTER TABLE places
    ADD COLUMN IF NOT EXISTS first_image_url      TEXT,
    ADD COLUMN IF NOT EXISTS first_image_thumb_url TEXT;

COMMENT ON COLUMN places.first_image_url       IS 'TourAPI firstimage  — 대표 이미지 URL';
COMMENT ON COLUMN places.first_image_thumb_url IS 'TourAPI firstimage2 — 썸네일 이미지 URL';
