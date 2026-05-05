-- v04_coordinate_outlier.sql
-- 목적: 좌표 NULL 또는 한국 범위 벗어난 행 (active 기준)
-- 한국 좌표 기준: 위도 33.0~43.0, 경도 124.0~132.0
-- READ-ONLY

SELECT
    place_id,
    name,
    category_id,
    region_1,
    region_2,
    latitude,
    longitude,
    CASE
        WHEN latitude IS NULL OR longitude IS NULL     THEN 'COORD_NULL'
        WHEN latitude  < 33.0 OR latitude  > 43.0     THEN 'LAT_OUT_OF_RANGE'
        WHEN longitude < 124.0 OR longitude > 132.0   THEN 'LNG_OUT_OF_RANGE'
    END                                                AS issue_type
FROM places
WHERE is_active IS TRUE
  AND (
      latitude  IS NULL OR longitude IS NULL
      OR latitude  < 33.0  OR latitude  > 43.0
      OR longitude < 124.0 OR longitude > 132.0
  )
ORDER BY category_id, issue_type, region_1, place_id;
