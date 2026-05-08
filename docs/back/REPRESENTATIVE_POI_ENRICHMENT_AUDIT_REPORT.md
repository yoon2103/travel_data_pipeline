# Representative POI Enrichment Audit Report

생성일: 2026-05-08

## 작업 범위

- `representative_poi_candidates`의 대표 POI 후보에 대해 image / overview / enrichment 품질을 dry-run으로 감사했다.
- 우선 대상은 `APPROVED` 상태인 `경포대`이며, review-only 상태의 `불국사`, `성산일출봉`, `전주한옥마을`도 source availability 기준으로 함께 확인했다.
- `places`, `tourism_belt.py`, `course_builder.py`는 수정하지 않았다.
- 실제 promote, 이미지 insert, seed 변경, places insert/update는 수행하지 않았다.

## 추가 파일

- `batch/place_enrichment/representative_enrichment_audit.py`
- `docs/REPRESENTATIVE_POI_ENRICHMENT_AUDIT_REPORT.md`

## CLI 사용법

```bash
python -m batch.place_enrichment.representative_enrichment_audit
python -m batch.place_enrichment.representative_enrichment_audit --expected-name 경포대
python -m batch.place_enrichment.representative_enrichment_audit --approved-only --json
python -m batch.place_enrichment.representative_enrichment_audit --source-type TOURAPI --json
```

CLI는 읽기 전용 dry-run이다.

## Enrichment Audit 결과

전체 4개 대표 POI 기준:

```text
candidate_row_count: 57
poi_count: 4
readiness_counts:
- NEEDS_MANUAL_CURATION: 4
```

APPROVED 후보 기준:

```text
candidate_row_count: 1
poi_count: 1
readiness_counts:
- NEEDS_MANUAL_CURATION: 1
```

현재 승인 후보는 `경포대` 1건뿐이다.

## 대표 POI별 Image 상태

| expected_poi_name | approved candidate | TourAPI image | Kakao image | Naver image | existing places image | 판단 |
|---|---|---:|---:|---:|---:|---|
| 경포대 | KAKAO / 경포대 / 93.00 | 3 / 5 | 0 / 5 | 0 / 5 | 0 | 승인 후보는 이미지 없음. TourAPI 이미지 후보 별도 review 필요 |
| 불국사 | 없음 | 4 / 5 | 0 / 5 | 0 / 5 | 0 | 승인 후보 없음. TourAPI 이미지 후보는 있으나 review 필요 |
| 성산일출봉 | 없음 | 2 / 2 | 0 / 5 | 0 / 5 | 0 | 승인 후보 없음. TourAPI 이미지 후보는 비교적 유효 |
| 전주한옥마을 | 없음 | 2 / 5 | 0 / 5 | 0 / 5 | 0 | TourAPI 이미지 후보가 내부시설/상업시설 위험 포함 |

### Image 후보 주요 사례

| expected_poi_name | source | candidate_id | source_name | confidence | risk_flags |
|---|---|---:|---|---:|---|
| 경포대 | TOURAPI | 1 | 강릉 경포대 | 85.75 | OVERVIEW_MISSING |
| 경포대 | TOURAPI | 4 | 금릉경포대 | 75.75 | OVERVIEW_MISSING, REGION_UNCLEAR |
| 불국사 | TOURAPI | 16 | 경주 불국사 [유네스코 세계유산] | 68.88 | OVERVIEW_MISSING |
| 성산일출봉 | TOURAPI | 31 | 성산일출봉 [유네스코 세계자연유산] | 74.50 | OVERVIEW_MISSING |
| 전주한옥마을 | TOURAPI | 44 | 전주한옥마을 도서관 | 88.00 | INTERNAL_FACILITY_RISK, OVERVIEW_MISSING, VILLAGE_SCOPE_REVIEW |

## 대표 POI별 Overview 상태

| expected_poi_name | TourAPI overview | Kakao overview | Naver overview | existing places overview | 판단 |
|---|---:|---:|---:|---:|---|
| 경포대 | 0 / 5 | 0 / 5 | 0 / 5 | 0 | overview 수동 보강 필요 |
| 불국사 | 0 / 5 | 0 / 5 | 0 / 5 | 0 | overview 수동 보강 필요 |
| 성산일출봉 | 0 / 2 | 0 / 5 | 0 / 5 | 0 | overview 수동 보강 필요 |
| 전주한옥마을 | 0 / 5 | 0 / 5 | 0 / 5 | 0 | overview 수동 보강 필요 |

현재 대표 후보 staging에는 usable overview가 없다.

## 경포대 상세

- approved candidate: `candidate_id=6`, `KAKAO`, `경포대`, `confidence_score=93.00`
- image_url: 없음
- overview: 없음
- validation risk: `IMAGE_MISSING`, `OVERVIEW_MISSING`
- existing places exact match: 없음
- enrichment_readiness: `NEEDS_MANUAL_CURATION`
- manual_curation_required: `true`

판단:

- `경포대` 자체의 대표 후보 매칭은 좋다.
- 그러나 Kakao/Naver Local 응답에는 이미지와 overview가 없다.
- TourAPI의 `강릉 경포대` 후보는 이미지가 있으므로, 바로 promote하지 말고 이미지 후보 review 대상으로 분리하는 것이 안전하다.

## Manual Curation 필요 여부

| expected_poi_name | manual curation 필요 | 이유 |
|---|---|---|
| 경포대 | 필요 | approved candidate에 image/overview 없음. TourAPI 이미지는 별도 review 필요 |
| 불국사 | 필요 | approved candidate 없음. TourAPI 이미지는 있으나 후보 승인 필요 |
| 성산일출봉 | 필요 | approved candidate 없음. TourAPI 이미지는 있으나 후보 승인 필요 |
| 전주한옥마을 | 필요 | approved candidate 없음. TourAPI 후보가 내부시설/마을 scope 위험 포함 |

## 대표 이미지 위험

- Kakao/Naver Local 후보는 이미지가 없어 대표 이미지 평가 자체가 불가능하다.
- TourAPI 이미지는 관광지 baseline에는 유효하지만, 후보 이름과 지역이 정확하지 않으면 오염 위험이 있다.
- `전주한옥마을 도서관`처럼 대표 POI가 아니라 내부시설 이미지가 선택될 위험이 있다.
- `경포대`는 TourAPI `강릉 경포대` 이미지 후보가 가장 현실적이지만 아직 승인 후보가 아니다.
- overview는 4개 대표 POI 모두 source staging 기준으로 비어 있으므로 수동 요약 또는 TourAPI detail 확장이 필요하다.

## 검증 결과

```text
python -m py_compile .\batch\place_enrichment\representative_enrichment_audit.py
PASS

python -m batch.place_enrichment.representative_enrichment_audit --expected-name 경포대
PASS

python -m batch.place_enrichment.representative_enrichment_audit --json
PASS

python -m batch.place_enrichment.representative_enrichment_audit --approved-only --json
PASS
```

## places/seed 변경 없음 확인

- `places` row count: `26371`
- CLI 결과: `places_changed=false`
- CLI 결과: `seed_changed=false`
- CLI 결과: `engine_changed=false`
- `tourism_belt.py` diff: 없음
- `course_builder.py` diff: 없음

## 다음 작업 제안

1. `경포대`의 TourAPI `강릉 경포대` 이미지 후보를 manual image candidate workflow로 별도 등록하거나 review 대상으로 승격한다.
2. `불국사`, `성산일출봉`, `전주한옥마을`은 먼저 정확한 대표 후보를 approve한 뒤 enrichment audit을 다시 실행한다.
3. overview는 현재 source 후보에 없으므로 manual curator 또는 TourAPI detail overview 수집 dry-run을 별도 단계로 설계한다.
4. 대표 이미지 promote 전에 `IMAGE` enrichment candidate와 `PLACE_MATCH` candidate를 분리해 승인 상태를 따로 관리한다.
