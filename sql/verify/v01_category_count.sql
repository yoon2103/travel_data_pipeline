-- v01_category_count.sql
-- 목적: category별 전체 / 활성 / 비활성 / is_active NULL 건수 확인
-- 실행 시점: 적재 완료 직후 1순위
-- 검산: total = active + inactive + active_null 이 성립해야 함
-- READ-ONLY

SELECT
    category_id,
    CASE category_id
        WHEN 12 THEN '관광지'
        WHEN 14 THEN '문화시설'
        WHEN 28 THEN '레포츠'
        WHEN 32 THEN '숙박'
        WHEN 39 THEN '음식점'
        ELSE '기타'
    END                                                  AS category_name,
    COUNT(*)                                             AS total,
    COUNT(*) FILTER (WHERE is_active IS TRUE)            AS active,
    COUNT(*) FILTER (WHERE is_active IS FALSE)           AS inactive,
    COUNT(*) FILTER (WHERE is_active IS NULL)            AS active_null
FROM places
GROUP BY category_id
ORDER BY category_id;
