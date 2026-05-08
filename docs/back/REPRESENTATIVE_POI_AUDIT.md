# Representative POI Audit

작성일: 2026-05-08

이 문서는 대표 랜드마크 누락/대체 POI 문제를 추천 엔진이 아니라 데이터 품질 관점에서 추적하기 위한 대표 POI 기준표 초안이다.

## 현재 Seed 현황

현재 `tourism_belt.py`에 등록된 대표 seed는 총 23개이며, 모두 `places`에 정확한 이름으로 존재한다.

| 권역 | DB region | seed 수 | 상태 |
|---|---:|---:|---|
| 강릉 | 강원 | 5 | DB 존재 |
| 속초 | 강원 | 6 | DB 존재 |
| 경주권 | 경북 | 6 | DB 존재 |
| 충남/태안 | 충남 | 6 | DB 존재 |
| 서울 | 서울 | 0 | seed 없음 |
| 부산 | 부산 | 0 | seed 없음 |
| 제주 | 제주 | 0 | seed 없음 |
| 전주 | 전북 | 0 | seed 없음 |
| 여수 | 전남 | 0 | seed 없음 |

핵심 문제는 기존 seed 23개의 DB 존재 여부가 아니라, 사용자가 기대하는 대표 POI가 DB/seed에 없거나 대표성이 약한 주변 POI로 대체되어 있다는 점이다.

## 원인 분류

| 원인 | 설명 | 예시 |
|---|---|---|
| DB 누락 | 기대 대표 POI가 `places.name` 정확 매칭으로 없음 | 경포대, 오죽헌, 선교장, 불국사, 간월암 |
| seed 누락 | DB에는 있으나 `tourism_belt.py` seed가 아님 | 경복궁, 해운대해수욕장, 협재해수욕장, 영금정 |
| 이름 불일치 | 실제 대표명과 DB명이 다르거나 접두어/부가명이 붙음 | 경주 첨성대 vs 첨성대 |
| 대표성 약함 | 대표 명소 본체 대신 광장/마을/부속시설이 seed 역할 | 경포호수광장, 간월도마을, 국립경주박물관 신라천년서고 |
| 이미지 누락 | seed 또는 대표 후보의 `first_image_url` 없음 | 정동진, 강릉올림픽뮤지엄, 안면암(태안), 영금정 |
| 설명 누락 | `overview` 없음 | 천마총(대릉원), 여수 해상케이블카, 이순신광장 |

## 지역별 대표 POI 기준표 초안

상태값 기준:

- `DB_EXISTS` / `DB_MISSING`
- `SEED_EXISTS` / `SEED_MISSING`
- `REPRESENTATIVE_OK` / `REPRESENTATIVE_WEAK` / `NEEDS_MANUAL_REVIEW`
- `IMAGE_OK` / `IMAGE_MISSING`
- `OVERVIEW_OK` / `OVERVIEW_MISSING`

### 강릉/강원

| expected_poi_name | current_seed_name | db_status | seed_status | representative_status | image_status | overview_status | action_needed | priority |
|---|---|---|---|---|---|---|---|---:|
| 경포대 | 경포호수광장 | DB_MISSING | SEED_MISSING | REPRESENTATIVE_WEAK | UNKNOWN | UNKNOWN | 대표 POI DB 보강 후 seed 교체 검수 | 1 |
| 오죽헌 | 없음 | DB_MISSING | SEED_MISSING | NEEDS_MANUAL_REVIEW | UNKNOWN | UNKNOWN | DB 보강 후보 등록 | 2 |
| 선교장 | 없음 | DB_MISSING | SEED_MISSING | NEEDS_MANUAL_REVIEW | UNKNOWN | UNKNOWN | DB 보강 후보 등록 | 3 |
| 정동진 | 정동진 | DB_EXISTS | SEED_EXISTS | REPRESENTATIVE_OK | IMAGE_MISSING | OVERVIEW_OK | 이미지 보강 | 8 |
| 강릉올림픽뮤지엄 | 강릉올림픽뮤지엄 | DB_EXISTS | SEED_EXISTS | REPRESENTATIVE_OK | IMAGE_MISSING | OVERVIEW_OK | 이미지 보강 | 12 |
| 구룡폭포(소금강) | 구룡폭포(소금강) | DB_EXISTS | SEED_EXISTS | REPRESENTATIVE_OK | IMAGE_OK | OVERVIEW_OK | 유지 | 20 |

### 속초

| expected_poi_name | current_seed_name | db_status | seed_status | representative_status | image_status | overview_status | action_needed | priority |
|---|---|---|---|---|---|---|---|---:|
| 속초해수욕장 | 속초해수욕장 | DB_EXISTS | SEED_EXISTS | REPRESENTATIVE_OK | IMAGE_OK | OVERVIEW_OK | 유지 | 20 |
| 설악산 케이블카 | 설악산 케이블카 | DB_EXISTS | SEED_EXISTS | REPRESENTATIVE_OK | IMAGE_OK | OVERVIEW_OK | 유지 | 20 |
| 아바이마을 | 아바이마을 | DB_EXISTS | SEED_EXISTS | NEEDS_MANUAL_REVIEW | IMAGE_OK | OVERVIEW_OK | 마을 단위 seed 대표성 검수 | 15 |
| 대포항 | 대포항 | DB_EXISTS | SEED_EXISTS | NEEDS_MANUAL_REVIEW | IMAGE_OK | OVERVIEW_OK | 항구 seed 대표성 검수 | 16 |
| 영금정 | 없음 | DB_EXISTS | SEED_MISSING | REPRESENTATIVE_OK | IMAGE_MISSING | OVERVIEW_OK | seed 후보 검토 및 이미지 보강 | 14 |
| 속초관광수산시장 | 없음 | DB_MISSING | SEED_MISSING | NEEDS_MANUAL_REVIEW | UNKNOWN | UNKNOWN | DB 보강 후보 검수 | 22 |

### 경주

| expected_poi_name | current_seed_name | db_status | seed_status | representative_status | image_status | overview_status | action_needed | priority |
|---|---|---|---|---|---|---|---|---:|
| 경주 첨성대 | 경주 첨성대 | DB_EXISTS | SEED_EXISTS | REPRESENTATIVE_OK | IMAGE_OK | OVERVIEW_OK | 유지 | 20 |
| 천마총(대릉원) | 천마총(대릉원) | DB_EXISTS | SEED_EXISTS | REPRESENTATIVE_OK | IMAGE_OK | OVERVIEW_MISSING | 설명 보강 | 13 |
| 경주 동궁과 월지 | 경주 동궁과 월지 | DB_EXISTS | SEED_EXISTS | REPRESENTATIVE_OK | IMAGE_OK | OVERVIEW_OK | 유지 | 20 |
| 불국사 | 없음 | DB_MISSING | SEED_MISSING | NEEDS_MANUAL_REVIEW | UNKNOWN | UNKNOWN | 대표 POI DB 보강 | 4 |
| 국립경주박물관 | 국립경주박물관 신라천년서고 | DB_MISSING | SEED_MISSING | REPRESENTATIVE_WEAK | IMAGE_MISSING | OVERVIEW_OK | 본체 POI 확인 후 부속시설 대체 여부 검수 | 5 |
| 황리단길 | 없음 | DB_MISSING | SEED_MISSING | NEEDS_MANUAL_REVIEW | UNKNOWN | UNKNOWN | DB 보강 후보 검수 | 21 |

### 충남/태안

| expected_poi_name | current_seed_name | db_status | seed_status | representative_status | image_status | overview_status | action_needed | priority |
|---|---|---|---|---|---|---|---|---:|
| 꽃지해수욕장 | 꽃지해수욕장 | DB_EXISTS | SEED_EXISTS | REPRESENTATIVE_OK | IMAGE_OK | OVERVIEW_OK | 유지 | 20 |
| 안면암(태안) | 안면암(태안) | DB_EXISTS | SEED_EXISTS | REPRESENTATIVE_OK | IMAGE_MISSING | OVERVIEW_OK | 이미지 보강 | 11 |
| 안면도수목원 | 안면도수목원 | DB_EXISTS | SEED_EXISTS | REPRESENTATIVE_OK | IMAGE_OK | OVERVIEW_OK | 유지 | 20 |
| 백사장항 | 백사장항 | DB_EXISTS | SEED_EXISTS | NEEDS_MANUAL_REVIEW | IMAGE_OK | OVERVIEW_OK | 항구 seed 대표성 검수 | 17 |
| 간월암 | 간월도마을 | DB_MISSING | SEED_MISSING | REPRESENTATIVE_WEAK | UNKNOWN | UNKNOWN | 간월암 DB 보강 후 대체 seed 검토 | 6 |
| 태안 신두리 해안사구 | 없음 | DB_EXISTS | SEED_MISSING | REPRESENTATIVE_OK | IMAGE_OK | OVERVIEW_MISSING | seed 후보 및 설명 보강 검토 | 18 |

### 서울

| expected_poi_name | current_seed_name | db_status | seed_status | representative_status | image_status | overview_status | action_needed | priority |
|---|---|---|---|---|---|---|---|---:|
| 경복궁 | 없음 | DB_EXISTS | SEED_MISSING | REPRESENTATIVE_OK | IMAGE_OK | OVERVIEW_OK | 서울 seed 정책 검토 | 23 |
| 창덕궁 | 없음 | DB_MISSING | SEED_MISSING | NEEDS_MANUAL_REVIEW | UNKNOWN | UNKNOWN | DB 보강 후보 검수 | 24 |
| 남산서울타워 | 없음 | DB_EXISTS | SEED_MISSING | REPRESENTATIVE_OK | IMAGE_OK | OVERVIEW_OK | 서울 seed 정책 검토 | 25 |
| 북촌한옥마을 | 없음 | DB_EXISTS | SEED_MISSING | REPRESENTATIVE_OK | IMAGE_OK | OVERVIEW_OK | 서울 seed 정책 검토 | 26 |
| 청계천 | 없음 | DB_EXISTS | SEED_MISSING | REPRESENTATIVE_OK | IMAGE_OK | OVERVIEW_OK | 서울 seed 정책 검토 | 27 |
| 동대문디자인플라자 | 없음 | DB_MISSING | SEED_MISSING | NEEDS_MANUAL_REVIEW | UNKNOWN | UNKNOWN | DB 보강 후보 검수 | 28 |

### 부산

| expected_poi_name | current_seed_name | db_status | seed_status | representative_status | image_status | overview_status | action_needed | priority |
|---|---|---|---|---|---|---|---|---:|
| 해운대해수욕장 | 없음 | DB_EXISTS | SEED_MISSING | REPRESENTATIVE_OK | IMAGE_OK | OVERVIEW_OK | 부산 seed 정책 검토 | 23 |
| 광안리해수욕장 | 없음 | DB_EXISTS | SEED_MISSING | REPRESENTATIVE_OK | IMAGE_OK | OVERVIEW_OK | 부산 seed 정책 검토 | 24 |
| 감천문화마을 | 없음 | DB_MISSING | SEED_MISSING | NEEDS_MANUAL_REVIEW | UNKNOWN | UNKNOWN | DB 보강 후보 검수 | 19 |
| 태종대 | 없음 | DB_MISSING | SEED_MISSING | NEEDS_MANUAL_REVIEW | UNKNOWN | UNKNOWN | DB 보강 후보 검수 | 20 |
| 자갈치시장 | 없음 | DB_MISSING | SEED_MISSING | NEEDS_MANUAL_REVIEW | UNKNOWN | UNKNOWN | DB 보강 후보 검수 | 21 |
| 해동용궁사 | 없음 | DB_MISSING | SEED_MISSING | NEEDS_MANUAL_REVIEW | UNKNOWN | UNKNOWN | DB 보강 후보 검수 | 22 |

### 제주

| expected_poi_name | current_seed_name | db_status | seed_status | representative_status | image_status | overview_status | action_needed | priority |
|---|---|---|---|---|---|---|---|---:|
| 성산일출봉 | 없음 | DB_MISSING | SEED_MISSING | NEEDS_MANUAL_REVIEW | UNKNOWN | UNKNOWN | DB 보강 후보 검수 | 7 |
| 한라산 | 없음 | DB_MISSING | SEED_MISSING | NEEDS_MANUAL_REVIEW | UNKNOWN | UNKNOWN | 범위형 POI 기준 검수 | 9 |
| 협재해수욕장 | 없음 | DB_EXISTS | SEED_MISSING | REPRESENTATIVE_OK | IMAGE_OK | OVERVIEW_OK | 제주 seed 정책 검토 | 25 |
| 천지연폭포 | 없음 | DB_EXISTS | SEED_MISSING | REPRESENTATIVE_OK | IMAGE_OK | OVERVIEW_OK | 제주 seed 정책 검토 | 26 |
| 섭지코지 | 없음 | DB_EXISTS | SEED_MISSING | REPRESENTATIVE_OK | IMAGE_MISSING | OVERVIEW_OK | 이미지 보강 및 seed 후보 검토 | 10 |
| 우도 | 없음 | DB_EXISTS | SEED_MISSING | REPRESENTATIVE_OK | IMAGE_OK | OVERVIEW_OK | 제주 seed 정책 검토 | 27 |

### 전주

| expected_poi_name | current_seed_name | db_status | seed_status | representative_status | image_status | overview_status | action_needed | priority |
|---|---|---|---|---|---|---|---|---:|
| 전주한옥마을 | 없음 | DB_MISSING | SEED_MISSING | NEEDS_MANUAL_REVIEW | UNKNOWN | UNKNOWN | 대표 POI DB 보강 | 8 |
| 전동성당 | 없음 | DB_MISSING | SEED_MISSING | NEEDS_MANUAL_REVIEW | UNKNOWN | UNKNOWN | DB 보강 후보 검수 | 12 |
| 경기전 | 없음 | DB_EXISTS | SEED_MISSING | REPRESENTATIVE_OK | IMAGE_OK | OVERVIEW_OK | 전주 seed 정책 검토 | 23 |
| 오목대 | 없음 | DB_MISSING | SEED_MISSING | NEEDS_MANUAL_REVIEW | UNKNOWN | UNKNOWN | DB 보강 후보 검수 | 15 |
| 전주향교 | 없음 | DB_EXISTS | SEED_MISSING | REPRESENTATIVE_OK | IMAGE_OK | OVERVIEW_MISSING | 설명 보강 및 seed 후보 검토 | 16 |
| 덕진공원 | 없음 | DB_EXISTS | SEED_MISSING | REPRESENTATIVE_OK | IMAGE_OK | OVERVIEW_OK | 전주 seed 정책 검토 | 28 |

### 여수

| expected_poi_name | current_seed_name | db_status | seed_status | representative_status | image_status | overview_status | action_needed | priority |
|---|---|---|---|---|---|---|---|---:|
| 여수 해상케이블카 | 없음 | DB_EXISTS | SEED_MISSING | REPRESENTATIVE_OK | IMAGE_OK | OVERVIEW_MISSING | 설명 보강 및 seed 후보 검토 | 14 |
| 오동도 | 없음 | DB_MISSING | SEED_MISSING | NEEDS_MANUAL_REVIEW | UNKNOWN | UNKNOWN | 대표 POI DB 보강 | 10 |
| 향일암 | 없음 | DB_MISSING | SEED_MISSING | NEEDS_MANUAL_REVIEW | UNKNOWN | UNKNOWN | 대표 POI DB 보강 | 11 |
| 돌산공원 | 없음 | DB_EXISTS | SEED_MISSING | REPRESENTATIVE_OK | IMAGE_OK | OVERVIEW_OK | 여수 seed 정책 검토 | 24 |
| 이순신광장 | 없음 | DB_EXISTS | SEED_MISSING | NEEDS_MANUAL_REVIEW | IMAGE_OK | OVERVIEW_MISSING | 광장 대표성 및 설명 보강 검수 | 18 |
| 아쿠아플라넷 여수 | 없음 | DB_EXISTS | SEED_MISSING | REPRESENTATIVE_OK | IMAGE_OK | OVERVIEW_MISSING | 설명 보강 및 seed 후보 검토 | 19 |

## 대표성 의심 Seed

| seed | 사유 | 권장 조치 |
|---|---|---|
| 경포호수광장 | `광장`, 경포대 대체 가능성 | 경포대 DB 보강 후 대표성 재검수 |
| 간월도마을 | `마을`, 간월암 대체 가능성 | 간월암 DB 보강 후 seed 검토 |
| 국립경주박물관 신라천년서고 | 박물관 본체가 아니라 내부시설/부속시설 가능성 | 국립경주박물관 본체 확인 |
| 아바이마을 | 마을 단위 POI | 대표 관광지로 유지 가능하나 검수 필요 |
| 백사장항 | 항구 POI | 관광 목적지로 유효한지 검수 |
| 대포항 | 항구 POI | 관광 목적지로 유효한지 검수 |

## 이미지/설명 누락 Seed

| seed | 누락 항목 | 조치 |
|---|---|---|
| 정동진 | 이미지 | 대표 이미지 보강 |
| 강릉올림픽뮤지엄 | 이미지 | 대표 이미지 보강 |
| 안면암(태안) | 이미지 | 대표 이미지 보강 |
| 국립경주박물관 신라천년서고 | 이미지 | 본체 검수 후 이미지 보강 |
| 천마총(대릉원) | 설명 | overview/description 보강 |

## 우선 보강 TOP 20

1. 경포대: DB/seed 누락, 경포호수광장 대체 문제
2. 오죽헌: 강릉 대표 POI DB/seed 누락
3. 선교장: 강릉 대표 POI DB/seed 누락
4. 불국사: 경주 대표 POI 본체 DB/seed 누락
5. 국립경주박물관: 본체 누락, 부속시설 seed 대체
6. 간월암: 충남/태안 대표 POI DB/seed 누락
7. 성산일출봉: 제주 대표 POI DB/seed 누락
8. 전주한옥마을: 전주 대표 POI DB/seed 누락
9. 한라산: 제주 대표 POI DB/seed 누락, 범위형 POI 기준 필요
10. 오동도: 여수 대표 POI DB/seed 누락
11. 향일암: 여수 대표 POI DB/seed 누락
12. 전동성당: 전주 대표 POI DB/seed 누락
13. 천마총(대릉원): overview 누락
14. 여수 해상케이블카: overview 누락, seed 후보 검토
15. 오목대: 전주 대표 POI DB/seed 누락
16. 전주향교: overview 누락, seed 후보 검토
17. 안면암(태안): 이미지 누락
18. 이순신광장: 광장 대표성 및 overview 누락 검수
19. 감천문화마을: 부산 대표 POI DB/seed 누락
20. 태종대: 부산 대표 POI DB/seed 누락

## Seed QA 규칙 초안

아래 키워드가 seed 이름에 포함되면 자동 승인하지 않고 수동 검수 대상으로 분류한다.

| 키워드 | 위험 |
|---|---|
| 광장 | 대표 명소 본체가 아니라 주변 집결지일 수 있음 |
| 주차장 | 대표 POI로 부적절 |
| 호텔 | 숙박시설 대체 위험 |
| 펜션 | 숙박시설 대체 위험 |
| 마을 | 권역/생활지명일 수 있어 대표성 검수 필요 |
| 내부시설 | 본체가 아니라 부속시설일 수 있음 |
| 서고 | 박물관/문화시설 본체의 부속시설 가능성 |
| 기념탑 | 대표 명소 대신 하위 시설 가능성 |
| 탐방로 | 전체 명소가 아니라 산책로 일부일 수 있음 |
| 항 | 관광 목적지로 유효할 수 있으나 항구/상권/주차장 대체 위험 |

## 절대 금지 원칙

- DB에 없는 POI를 seed로 등록하지 않는다.
- 주변 상점/숙박/광장을 대표 명소로 대체하지 않는다.
- 대표성 검수 없이 seed를 교체하지 않는다.
- 엔진 로직으로 데이터 문제를 숨기지 않는다.
- fallback 거리 확장으로 대표 POI 누락 문제를 덮지 않는다.
- seed 변경은 `DB_EXISTS`, 추천 가능 `category_id`, `visit_role`, `is_active`, 좌표, 이미지/설명 품질 검수 이후에만 진행한다.

## 다음 개선 방향

1. 대표 POI 후보를 seed에 바로 반영하지 말고 `representative_poi_candidates` 형태의 별도 감사 목록으로 관리한다.
2. 정확명 매칭, 유사명 매칭, 좌표 반경 매칭을 분리한 대표 POI QA 스크립트를 만든다.
3. `REPRESENTATIVE_WEAK` seed는 바로 제거하지 말고 기대 대표 POI가 DB에 확보된 뒤 교체 여부를 검수한다.
4. 서울/부산/제주/전주/여수는 tourism belt seed를 추가할지, 기존 city/anchor 구조를 강화할지 정책을 먼저 정한다.
5. 이미지/overview 누락은 추천 로직 수정이 아니라 데이터 보강 배치 또는 manual candidate workflow로 처리한다.

## 다음 단계: 대표 POI 후보 Staging 설계

대표 POI 누락 문제는 `places` 또는 `tourism_belt.py`를 즉시 수정하지 않고, 후보 수집 -> 검증 -> 수동 검수 -> 별도 promote 판단 순서로 다룬다.

### Staging 테이블 초안

초안 파일: `migration_010_representative_poi_candidates.sql`

테이블: `representative_poi_candidates`

목적:

- DB에 없는 대표 POI 후보를 안전하게 보관한다.
- Kakao/Naver/TourAPI/Manual 후보를 같은 구조로 비교한다.
- 대표성 검수 전에는 `places`와 seed에 반영하지 않는다.
- 외부 후보가 기존 `places`와 안전하게 매칭되는 경우에만 `matched_place_id`를 선택적으로 연결한다.

핵심 컬럼:

| 컬럼 | 목적 |
|---|---|
| `candidate_id` | 후보 식별자 |
| `expected_poi_name` | 기준표의 기대 대표 POI명 |
| `region_1`, `region_2` | 대상 지역 |
| `matched_place_id` | 기존 places와 안전 매칭된 경우만 선택 연결 |
| `source_type` | `TOURAPI`, `KAKAO`, `NAVER`, `MANUAL` |
| `source_place_id` | 외부 source의 장소 ID |
| `source_name` | 외부 source 장소명 |
| `category` | 외부 category |
| `address`, `road_address` | 주소 비교용 |
| `latitude`, `longitude` | 좌표 검증용 |
| `phone` | 동일 장소 검증 보조 |
| `image_url` | 후보 대표 이미지 |
| `overview` | 후보 설명 |
| `confidence_score` | 0~100 검증 점수 |
| `representative_status` | 대표 POI 후보 상태 |
| `review_status` | 운영 검수 상태 |
| `promote_status` | 운영 반영 가능 여부 |
| `source_payload` | 원본 응답 |
| `validation_payload` | 자동 검증 결과 |
| `review_payload` | 운영자 검수 기록 |

### 후보 상태 구조

| 상태 | 의미 |
|---|---|
| `CANDIDATE` | 수집만 된 초기 후보 |
| `NEEDS_REVIEW` | 자동 검증만으로 승인 불가 |
| `APPROVED` | 운영자가 대표 후보로 승인 |
| `REJECTED` | 오매칭/대표성 부족으로 거절 |
| `PROMOTED` | 별도 promote workflow에서 운영 반영 완료 |

`promote_status`는 별도로 `PENDING`, `NOT_READY`, `READY`, `PROMOTED`, `SKIPPED`, `ROLLED_BACK`를 사용한다. 이 테이블에 insert된 것만으로는 운영 데이터가 변경되지 않는다.

### 대표 POI 검증 기준

| 기준 | 검증 방식 |
|---|---|
| 이름 정확도 | 기대명과 source name의 exact/normalized/fuzzy similarity 비교 |
| 지역 일치 | `region_1`, `region_2`, 주소 내 지역명 비교 |
| 카테고리 적합성 | 관광지/문화시설 중심, 숙박/상점/음식점 오매칭 차단 |
| 좌표 존재 | latitude/longitude 필수 검증 |
| 좌표 합리성 | 기대 지역 중심 또는 유사 후보와의 거리 비교 |
| 대표성 | 본체 POI인지, 광장/주차장/마을/부속시설 대체인지 확인 |
| 이미지/설명 존재 | 대표 이미지와 overview 유무 확인 |
| 오매칭 위험 | 호텔, 펜션, 상점, 음식점, 주차장, 주변 시설명 차단 |

### TOP 20 후보 수집 대상

1. 경포대
2. 오죽헌
3. 선교장
4. 불국사
5. 국립경주박물관
6. 간월암
7. 성산일출봉
8. 전주한옥마을
9. 한라산
10. 오동도
11. 향일암
12. 전동성당
13. 천마총(대릉원)
14. 여수 해상케이블카
15. 오목대
16. 전주향교
17. 안면암(태안)
18. 이순신광장
19. 감천문화마을
20. 태종대

수집 우선순위:

- DB가 없는 대표 POI를 먼저 수집한다.
- 기존 seed가 약한 대체 POI인 경우 원 대표 POI를 먼저 확인한다.
- DB는 있으나 이미지/설명이 부족한 경우 enrichment 후보로 분리한다.

### CLI 설계 초안

실제 구현 전 설계 명령:

```bash
python -m batch.place_enrichment.collect_representative_poi_candidates --dry-run
python -m batch.place_enrichment.collect_representative_poi_candidates --dry-run --region 강원 --limit 5
python -m batch.place_enrichment.collect_representative_poi_candidates --dry-run --source manual
```

예상 옵션:

| 옵션 | 의미 |
|---|---|
| `--dry-run` | insert 없이 대상/검증 결과만 출력 |
| `--write` | staging insert 허용. 기본값은 false |
| `--region` | 특정 region_1만 처리 |
| `--source` | `tourapi`, `kakao`, `naver`, `manual` 중 선택 |
| `--limit` | 처리 후보 수 제한 |
| `--expected-name` | 단일 대표 POI만 수집 |
| `--audit-file` | 기준표 markdown/csv 입력 |

기본 동작:

1. 기준표 TOP 후보 로드
2. 기존 `places` exact match 확인
3. DB 누락이면 외부 후보 검색 대상에 포함
4. 외부 후보를 normalized candidate로 변환
5. 이름/지역/category/좌표/대표성 검증
6. `representative_poi_candidates`에 staging insert 또는 dry-run 리포트 출력

### 금지 사항

- `places`에 바로 insert하지 않는다.
- `places`를 update하지 않는다.
- `tourism_belt.py` seed를 자동 수정하지 않는다.
- `경포호수광장`, `간월도마을` 같은 기존 seed를 자동 제거하지 않는다.
- 대표 POI가 없다고 주변 광장/호텔/펜션/상점으로 대체하지 않는다.
