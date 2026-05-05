# 검증 SQL 실행 순서

## 파일 목록

- v01_category_count.sql — category별 건수
- v02_null_check.sql — NULL·빈문자 현황
- v03_duplicate_suspect.sql — 중복 의심 탐지
- v04_coordinate_outlier.sql — 좌표 이상치
- v05_image_rate.sql — 이미지 보유율
- v06_visit_role_dist.sql — visit_role 분포
- v07_time_slot_dist.sql — time_slot 분포
- v08_duration_dist.sql — duration 분포
- v09_indoor_outdoor_dist.sql — indoor_outdoor 분포
- v10a_misclassify_count.sql — 오분류 건수
- v10b_misclassify_sample.sql — 오분류 샘플
- v11_ai_status_dist.sql — ai_validation_status 분포
- v12_sync_status.sql — 적재 완료 여부
- v13_engine_candidate_verify.sql — 엔진 후보군(12/14/39) 가공 필드 판정 검증

## 실행 순서

Phase 1: v01 → v12
Phase 2: v02 → v04 → v05
Phase 3: v06 → v07 → v08 → v09 → v10a → v10b
Phase 4: v11 → v03

## 1순위 검증

1. v01 — 5개 카테고리 active > 0
2. v04 — 좌표 NULL·이상치
3. v02 — null_overview 다수면 재수집
4. v10a — 오분류 다수면 batch_rules.py 재실행
5. v11 — pending 대량이면 AI 배치 큐 점검

## 컬럼 참고

- active_null (v01): is_active IS NULL 행
- out_of_range_count (v08): 기대 범위 이탈 건수
- empty_array_count (v07): cardinality=0 빈 배열 행
- overview_preview (v10b): LEFT(COALESCE(overview,''),120)
