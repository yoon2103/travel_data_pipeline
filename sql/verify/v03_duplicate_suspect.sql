-- v03_duplicate_suspect.sql
-- 목적: 이름 + 지역 기준 1차 중복 의심 탐지 (active 기준)
-- - name은 TRIM 기준으로 묶어 앞뒤 공백 차이를 동일 건으로 처리
-- - region_2 NULL은 '[NULL]'로 치환해 GROUP BY 누락 방지
-- - distinct_category_cnt: 같은 이름이 다른 카테고리로 등록된 경우 식별
-- 2차 판정(좌표 근접 기준)은 별도 SQL로 분리 예정
-- READ-ONLY

SELECT
    TRIM(name)                                                  AS name_trimmed,
    region_1,
    COALESCE(region_2, '[NULL]')                                AS region_2,
    COUNT(*)                                                    AS cnt,
    COUNT(DISTINCT category_id)                                 AS distinct_category_cnt,
    array_agg(place_id           ORDER BY place_id)             AS place_ids,
    array_agg(tourapi_content_id ORDER BY place_id)             AS content_ids,
    array_agg(category_id        ORDER BY place_id)             AS category_ids
FROM places
WHERE is_active IS TRUE
GROUP BY TRIM(name), region_1, COALESCE(region_2, '[NULL]')
HAVING COUNT(*) >= 2
ORDER BY cnt DESC
LIMIT 50;
