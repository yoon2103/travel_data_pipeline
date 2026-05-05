-- v10b_misclassify_sample.sql
-- 목적: 오분류 의심 행 샘플 — name / overview / indoor_outdoor / category_id 직접 확인
-- 건수 집계: v10a_misclassify_count.sql 참조
-- READ-ONLY

-- [1] cat12(관광지)인데 indoor — 20건
SELECT
    place_id, category_id, name, region_1, region_2, indoor_outdoor,
    LEFT(COALESCE(overview, ''), 120) AS overview_preview
FROM places
WHERE is_active IS TRUE AND category_id = 12 AND indoor_outdoor = 'indoor'
ORDER BY place_id
LIMIT 20;

-- [2] cat14(문화시설)인데 outdoor — 20건
SELECT
    place_id, category_id, name, region_1, region_2, indoor_outdoor,
    LEFT(COALESCE(overview, ''), 120) AS overview_preview
FROM places
WHERE is_active IS TRUE AND category_id = 14 AND indoor_outdoor = 'outdoor'
ORDER BY place_id
LIMIT 20;

-- [3] cat39(음식점)인데 outdoor — 20건
SELECT
    place_id, category_id, name, region_1, region_2, indoor_outdoor,
    LEFT(COALESCE(overview, ''), 120) AS overview_preview
FROM places
WHERE is_active IS TRUE AND category_id = 39 AND indoor_outdoor = 'outdoor'
ORDER BY place_id
LIMIT 20;
