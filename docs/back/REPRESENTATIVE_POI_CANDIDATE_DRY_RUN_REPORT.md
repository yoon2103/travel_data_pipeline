# Representative POI Candidate Collection Dry-run Report

작성일: 2026-05-08

## 작업 범위

대표 POI 후보를 외부 source에서 조회하고 dry-run 기준으로 검증했다.

금지 원칙 준수:

- `places` insert 없음
- `places` update 없음
- `tourism_belt.py` 수정 없음
- 추천 엔진 수정 없음
- promote 없음
- DB write 없음

## 추가 파일

- `batch/place_enrichment/collect_representative_poi_candidates.py`

## CLI 사용법

```bash
python -m batch.place_enrichment.collect_representative_poi_candidates --dry-run
python -m batch.place_enrichment.collect_representative_poi_candidates --dry-run --limit 5
python -m batch.place_enrichment.collect_representative_poi_candidates --dry-run --expected-name 경포대
python -m batch.place_enrichment.collect_representative_poi_candidates --dry-run --source kakao
python -m batch.place_enrichment.collect_representative_poi_candidates --dry-run --region 제주
python -m batch.place_enrichment.collect_representative_poi_candidates --dry-run --json
```

## 검증 명령

```bash
python -m py_compile batch/place_enrichment/collect_representative_poi_candidates.py
python -m batch.place_enrichment.collect_representative_poi_candidates --dry-run --expected-name 경포대
python -m batch.place_enrichment.collect_representative_poi_candidates --dry-run --expected-name 불국사
python -m batch.place_enrichment.collect_representative_poi_candidates --dry-run --expected-name 성산일출봉
python -m batch.place_enrichment.collect_representative_poi_candidates --dry-run --expected-name 전주한옥마을
```

## 대표 후보 검색 결과

### 경포대

| source | candidate_count | best_candidate | score | result | risk_flags |
|---|---:|---|---:|---|---|
| TourAPI | 5 | 강릉 경포대 | 85.75 | USABLE_CANDIDATE | OVERVIEW_MISSING |
| Kakao | 5 | 경포대 | 93.0 | USABLE_CANDIDATE | IMAGE_MISSING, OVERVIEW_MISSING |
| Naver | 5 | 경포대 | 93.0 | USABLE_CANDIDATE | IMAGE_MISSING, OVERVIEW_MISSING |

판단:

- usable candidate 있음
- Kakao/Naver는 이름/좌표/주소가 가장 정확함
- TourAPI는 이미지가 있어 staging 후보로 가치 있음
- 호텔/주차장 후보도 함께 섞이므로 review 필수

### 불국사

| source | candidate_count | best_candidate | score | result | risk_flags |
|---|---:|---|---:|---|---|
| TourAPI | 5 | 불국사(서울) | 75.75 | NEEDS_MANUAL_REVIEW | REGION_UNCLEAR, OVERVIEW_MISSING |
| Kakao | 5 | 불국사 | 93.0 | USABLE_CANDIDATE | IMAGE_MISSING, OVERVIEW_MISSING |
| Naver | 5 | 불국사 | 93.0 | USABLE_CANDIDATE | IMAGE_MISSING, OVERVIEW_MISSING |

판단:

- usable candidate 있음
- Kakao/Naver가 안정적
- TourAPI에는 `경주 불국사 [유네스코 세계유산]` 후보가 있으나, 단순 점수상 `불국사(서울)` 같은 동명 후보가 섞여 manual review 필요
- 음식점/숙박/주차장 후보가 섞임

### 성산일출봉

| source | candidate_count | best_candidate | score | result | risk_flags |
|---|---:|---|---:|---|---|
| TourAPI | 2 | 성산일출봉 [유네스코 세계자연유산] | 74.5 | NEEDS_MANUAL_REVIEW | OVERVIEW_MISSING |
| Kakao | 5 | 성산일출봉 | 93.0 | USABLE_CANDIDATE | IMAGE_MISSING, OVERVIEW_MISSING |
| Naver | 5 | 성산일출봉 어멍횟집 | 32.14 | REJECT_OR_LOW_CONFIDENCE | CATEGORY_RISK, IMAGE_MISSING, OVERVIEW_MISSING |

판단:

- usable candidate 있음
- Kakao가 가장 안정적
- TourAPI는 이미지가 있고 후보 품질이 좋지만 이름 확장형이라 review 필요
- Naver는 음식점 후보가 상위에 잡혀 대표 POI source로는 이 케이스에서 위험

### 전주한옥마을

| source | candidate_count | best_candidate | score | result | risk_flags |
|---|---:|---|---:|---|---|
| TourAPI | 5 | 전주한옥마을 도서관 | 88.0 | USABLE_CANDIDATE | INTERNAL_FACILITY_RISK, OVERVIEW_MISSING, VILLAGE_SCOPE_REVIEW |
| Kakao | 5 | 전주한옥마을 | 93.0 | USABLE_CANDIDATE | IMAGE_MISSING, OVERVIEW_MISSING, VILLAGE_SCOPE_REVIEW |
| Naver | 5 | 전주 한옥마을 | 93.0 | USABLE_CANDIDATE | IMAGE_MISSING, OVERVIEW_MISSING, VILLAGE_SCOPE_REVIEW |

판단:

- usable candidate 있음
- Kakao/Naver exact 또는 준 exact 후보가 안정적
- TourAPI는 내부시설인 `전주한옥마을 도서관`이 잡혀 대표성 위험이 있음
- `마을` 단위 POI라 대표성 검수는 필요

## Usable Candidate 존재 여부

| expected_poi_name | usable_candidate |
|---|---|
| 경포대 | 있음 |
| 불국사 | 있음 |
| 성산일출봉 | 있음 |
| 전주한옥마을 | 있음 |

## 대표성 위험 후보

| 후보 | source | 위험 |
|---|---|---|
| 경포대 주차장 | Kakao | 주차장 대체 위험 |
| 경포대오션호텔 | Kakao/TourAPI | 숙박시설 대체 위험 |
| 경포대 산호 펜션 | TourAPI | 숙박시설 대체 위험 |
| 불국사 정문주차장 | Kakao | 주차장 대체 위험 |
| 불국사밀면 | TourAPI/Naver | 음식점 오매칭 |
| 성산일출봉 어멍횟집 | Naver | 음식점 오매칭 |
| 전주한옥마을 도서관 | TourAPI | 내부시설/부속시설 대체 위험 |

## External Source 품질 비교

| source | 장점 | 위험 |
|---|---|---|
| TourAPI | 이미지 제공 가능성이 높음. 관광지 baseline에 강함 | 동명 지역 후보, 내부시설, 숙박/음식점 후보가 섞임 |
| Kakao | 이름/좌표/주소 exact match 품질이 가장 안정적 | Local API 응답에 이미지/overview가 없음 |
| Naver | 경포대/불국사처럼 exact match 가능 | 음식점/상점 후보가 상위에 섞이는 경우가 있음 |

## DB/Seed 변경 없음 확인

dry-run 출력:

- `db_write: false`
- `places_changed: false`
- `seed_changed: false`

실제 수행:

- migration 적용 안 함
- `representative_poi_candidates` insert 안 함
- `places` insert/update 안 함
- `tourism_belt.py` 수정 안 함
- 추천 엔진 수정 안 함

## 구현 메모

CLI 내부 검증 보정 사항:

- `경북` vs `경상북도`, `강원` vs `강원특별자치도` 같은 행정구역 alias를 region match에 반영
- TourAPI content type `32`, `39`는 숙박/음식 위험으로 감점
- 음식점 카테고리 키워드 보강
- `도서관`, `서고`, `주차장`, `호텔`, `펜션`, `마을`, `항` 등 대표성 위험 flag 추가

## 다음 작업 제안

1. `--output` 옵션을 추가해 dry-run JSON 리포트를 파일로 저장한다.
2. `migration_010_representative_poi_candidates.sql`을 dev DB에만 적용한다.
3. `--write`는 별도 작업으로 구현하고, 기본값은 계속 dry-run으로 유지한다.
4. staging insert 후 review CLI에서 `APPROVED/REJECTED`를 관리한다.
5. 승인된 후보만 별도 promote 설계에서 `places`/seed 반영 여부를 검토한다.
