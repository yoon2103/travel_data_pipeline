# Representative POI Candidate Staging Write Report

작성일: 2026-05-08

## 작업 목표

`representative_poi_candidates` staging 테이블을 dev/local DB에 생성하고, 대표 POI 4개에 대해 외부 source 후보를 staging insert했다.

대상 POI:

- 경포대
- 불국사
- 성산일출봉
- 전주한옥마을

## 준수한 금지 원칙

- `places` insert 없음
- `places` update 없음
- `tourism_belt.py` 수정 없음
- 추천 엔진 수정 없음
- `course_builder.py` 수정 없음
- promote 없음
- seed 변경 없음
- 운영 DB 사용 안 함

## 추가/수정 파일

| 파일 | 작업 |
|---|---|
| `migration_010_representative_poi_candidates.sql` | representative POI candidate staging DDL 작성/보정 |
| `batch/place_enrichment/collect_representative_poi_candidates.py` | `--write` staging insert 지원 |
| `docs/REPRESENTATIVE_POI_CANDIDATE_STAGING_WRITE_REPORT.md` | 작업 결과 보고서 |

## Migration 적용 DB

dev/local DB에만 적용했다.

| 항목 | 값 |
|---|---|
| DB_HOST | localhost |
| DB_PORT | 5432 |
| DB_NAME | travel_db |
| DB_USER | postgres |

## DDL 요약

생성 테이블:

- `representative_poi_candidates`

핵심 컬럼:

- `candidate_id`
- `expected_poi_name`
- `region_1`
- `region_2`
- `matched_place_id`
- `source_type`
- `source_place_id`
- `source_name`
- `category`
- `address`
- `road_address`
- `latitude`
- `longitude`
- `phone`
- `image_url`
- `overview`
- `confidence_score`
- `representative_status`
- `review_status`
- `promote_status`
- `source_payload`
- `validation_payload`
- `review_payload`
- `created_at`
- `updated_at`

중요 설계:

- `matched_place_id`는 nullable FK: `places(place_id)`
- `source_name`은 NOT NULL
- `review_status` 기본값은 `PENDING_REVIEW`
- `promote_status` 기본값은 `PENDING`
- `source_payload`, `validation_payload`, `review_payload`는 JSONB
- source 중복 방지 unique index 포함

## CLI 사용법

Dry-run:

```bash
python -m batch.place_enrichment.collect_representative_poi_candidates --dry-run --limit 4
```

Write:

```bash
python -m batch.place_enrichment.collect_representative_poi_candidates --write --limit 4
```

단일 source:

```bash
python -m batch.place_enrichment.collect_representative_poi_candidates --dry-run --limit 4 --source kakao
```

단일 POI:

```bash
python -m batch.place_enrichment.collect_representative_poi_candidates --dry-run --expected-name 경포대
```

현재 구현에서는 기본 처리 scope를 이번 작업 대상 4개 POI로 제한했다.

## 테스트 결과

| 테스트 | 결과 |
|---|---|
| `py_compile` | PASS |
| `--dry-run --limit 4 --source kakao` | PASS |
| `--write --limit 4` 최초 실행 | PASS |
| `--write --limit 4` 중복 실행 | PASS |

중복 실행 결과:

- 최초 실행: inserted 57, updated 0
- 재실행: inserted 0, updated 57

따라서 source 기준 unique/upsert가 동작한다.

## Inserted Candidate 수

총 staging row:

- `57`

POI별 후보 수:

| expected_poi_name | candidate_count |
|---|---:|
| 경포대 | 15 |
| 불국사 | 15 |
| 성산일출봉 | 12 |
| 전주한옥마을 | 15 |

Source별 후보 수:

| source_type | candidate_count |
|---|---:|
| KAKAO | 20 |
| NAVER | 20 |
| TOURAPI | 17 |

## 상태 분포

Validation result:

| validation_result | count |
|---|---:|
| USABLE_CANDIDATE | 10 |
| NEEDS_MANUAL_REVIEW | 13 |
| REJECT_OR_LOW_CONFIDENCE | 34 |

Staging status:

| representative_status | review_status | promote_status | count |
|---|---|---|---:|
| CANDIDATE | PENDING_REVIEW | PENDING | 10 |
| NEEDS_REVIEW | PENDING_REVIEW | PENDING | 47 |

## 대표 Candidate 샘플

| expected_poi_name | source_type | source_name | score | validation_result | risk_flags |
|---|---|---|---:|---|---|
| 경포대 | KAKAO | 경포대 | 93.00 | USABLE_CANDIDATE | IMAGE_MISSING, OVERVIEW_MISSING |
| 경포대 | NAVER | 경포대 | 93.00 | USABLE_CANDIDATE | IMAGE_MISSING, OVERVIEW_MISSING |
| 경포대 | TOURAPI | 강릉 경포대 | 85.75 | USABLE_CANDIDATE | OVERVIEW_MISSING |
| 불국사 | KAKAO | 불국사 | 93.00 | USABLE_CANDIDATE | IMAGE_MISSING, OVERVIEW_MISSING |
| 불국사 | NAVER | 불국사 | 93.00 | USABLE_CANDIDATE | IMAGE_MISSING, OVERVIEW_MISSING |
| 성산일출봉 | KAKAO | 성산일출봉 | 93.00 | USABLE_CANDIDATE | IMAGE_MISSING, OVERVIEW_MISSING |
| 전주한옥마을 | KAKAO | 전주한옥마을 | 93.00 | USABLE_CANDIDATE | IMAGE_MISSING, OVERVIEW_MISSING, VILLAGE_SCOPE_REVIEW |
| 전주한옥마을 | NAVER | 전주 한옥마을 | 93.00 | USABLE_CANDIDATE | IMAGE_MISSING, OVERVIEW_MISSING, VILLAGE_SCOPE_REVIEW |
| 전주한옥마을 | TOURAPI | 전주한옥마을 도서관 | 88.00 | USABLE_CANDIDATE | INTERNAL_FACILITY_RISK, OVERVIEW_MISSING, VILLAGE_SCOPE_REVIEW |

참고:

- `matched_place_id`는 안전한 exact match인 경우만 연결한다.
- 이번 57건 중 `matched_place_id IS NOT NULL`은 2건이다.
- 대부분의 신규 대표 POI 후보는 기존 `places`에 정확히 없으므로 `matched_place_id`가 NULL이다.

## Risk Flag 분포

| risk_flag | count |
|---|---:|
| OVERVIEW_MISSING | 57 |
| IMAGE_MISSING | 46 |
| CATEGORY_RISK | 30 |
| VILLAGE_SCOPE_REVIEW | 15 |
| LODGING_RISK | 6 |
| PARKING_LOT_RISK | 4 |
| REGION_UNCLEAR | 3 |
| INTERNAL_FACILITY_RISK | 1 |

## Places 변경 없음 확인

`places` row count:

| 시점 | count |
|---|---:|
| migration/write 전 | 26371 |
| staging write 후 | 26371 |

확인 결과:

- `places` row count 변동 없음
- `places` insert 없음
- `places` update 없음
- `경포대`, `불국사`, `성산일출봉`, `전주한옥마을` 직접 insert 없음

## Seed/Engine 변경 없음 확인

Git diff 기준:

- `tourism_belt.py` 변경 없음
- `course_builder.py` 변경 없음

이번 작업에서 추천 엔진, seed, frontend는 수정하지 않았다.

## 중복 방지 확인

`representative_poi_candidates`에는 다음 unique 전략을 적용했다.

- `(region_1, expected_poi_name, source_type, source_place_id)`
- `source_place_id IS NOT NULL`인 외부 후보에 대해 중복 방지

검증:

- 1차 `--write --limit 4`: inserted 57
- 2차 `--write --limit 4`: updated 57
- 중복 row 증가 없음

## 위험 요소

1. TourAPI는 이미지가 강하지만 동명/부속시설/숙박/음식점 후보가 섞인다.
   - 예: `불국사(서울)`, `전주한옥마을 도서관`

2. Kakao/Naver는 exact match 품질이 좋지만 이미지/overview가 거의 없다.
   - 대표 POI match source로는 좋고, 이미지 source로는 한계가 있다.

3. `전주한옥마을`은 마을 단위 POI라 `VILLAGE_SCOPE_REVIEW`가 붙는다.
   - 대표성이 있다고 바로 promote하지 말고 검수 필요.

4. `USABLE_CANDIDATE`도 자동 promote 대상이 아니다.
   - 현재 상태는 staging + `PENDING_REVIEW`까지만이다.

## 다음 작업 제안

1. representative candidate review CLI 구현
   - list
   - approve
   - reject
   - skip

2. `USABLE_CANDIDATE` 중 source agreement가 높은 후보를 우선 검수
   - 경포대: Kakao/Naver/TourAPI 모두 긍정
   - 불국사: Kakao/Naver 긍정, TourAPI는 review 필요
   - 성산일출봉: Kakao 긍정, TourAPI review
   - 전주한옥마을: Kakao/Naver 긍정, TourAPI 내부시설 위험

3. 승인 후보를 바로 `places`에 넣지 말고, `staging_places` 또는 별도 representative promotion 설계를 거친다.

4. TourAPI 상세 API로 overview 보강 가능 여부를 별도 dry-run으로 검증한다.
