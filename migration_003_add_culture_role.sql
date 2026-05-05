-- =============================================================
-- Migration 003: chk_visit_role 제약에 'culture' 추가
-- 대상: places.visit_role CHECK CONSTRAINT
-- =============================================================

ALTER TABLE places DROP CONSTRAINT chk_visit_role;

ALTER TABLE places ADD CONSTRAINT chk_visit_role CHECK (
    visit_role IS NULL
    OR visit_role = ANY(ARRAY['meal', 'cafe', 'spot', 'rest', 'culture'])
);
