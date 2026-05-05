# BATCH_RULES_SPEC.md
# 규칙 기반 배치 가공 명세서

작성일: 2026-04-22  
대상 파일: `batch_rules.py`  
대상 테이블: `places`  
처리 완료 기준: `visit_role IS NULL` 행만 처리 (이미 가공된 행 보호)

---

## 1. 처리 대상 카테고리

| category_id | 분류명 | 건수 (1차 배치 기준) |
|-------------|--------|---------------------|
| 12          | 관광지  | 8,240               |
| 14          | 문화시설 | 1,256               |
| 39          | 음식   | 9,350               |
| **합계**    |        | **18,846**          |

---

## 2. visit_role 분류 규칙

### 2-1. 기본값 (category → role)

| category_id | 기본 visit_role |
|-------------|----------------|
| 12          | spot           |
| 14          | culture        |
| 39          | meal           |

### 2-2. cat39 카페 보정 (동적 분류)

`name` 또는 `overview`에 아래 키워드 중 하나라도 포함되면 `meal` 대신 `cafe` 적용.

```
카페, 커피, 디저트, 베이커리, 크레페, 빙수,
아이스크림, 티하우스, 브런치카페, 브런치 카페
```

### 2-3. visit_role 허용값 (DB 제약 기준)

`chk_visit_role` CHECK constraint (migration_003 기준):

```
meal | cafe | spot | rest | culture
```

> **주의**: `rest`는 규칙 배치에서 자동 분류되지 않음. 수동 지정 또는 향후 AI 배치에서 처리.

---

## 3. visit_time_slot 규칙

role별 고정 슬롯값 (배열):

| visit_role | visit_time_slot             |
|------------|-----------------------------|
| spot       | ["morning", "afternoon"]    |
| culture    | ["morning", "afternoon"]    |
| meal       | ["lunch", "dinner"]         |
| cafe       | ["morning", "afternoon"]    |
| rest       | ["afternoon", "night"]      |

허용 슬롯값: `breakfast / morning / lunch / afternoon / dinner / night`

---

## 4. estimated_duration 규칙

### 4-1. 기본값 (category별)

| category_id | 기본값(분) | clamp 범위 |
|-------------|-----------|-----------|
| 12          | 90        | 60–120    |
| 14          | 75        | 45–100    |
| 39          | 60        | 40–90     |

> clamp는 현재 배치에서 직접 적용하지 않음. 이상값 검증(0 이하, 240 초과) 기준으로만 사용.

### 4-2. 키워드 보정 규칙 (우선순위 순, 첫 매치 적용)

**cat12 (관광지)**

| 키워드 | 적용 duration(분) |
|--------|------------------|
| 스파, 찜질, 온천 | 180 |
| 궁, 경복, 창덕, 덕수, 경희궁, 창경궁, 궁궐 | 120 |
| 해수욕장, 해변, 바다, 섬 | 120 |
| 공원, 숲, 등산, 계곡, 트레킹, 생태 | 90 |
| 거리, 골목, 마을, 타운 | 60 |
| 전망대, 타워, 전망 | 60 |

**cat14 (문화시설)**

| 키워드 | 적용 duration(분) |
|--------|------------------|
| 공연장, 극장, 오페라, 콘서트홀, 아트센터 | 120 |
| 박물관, 미술관 | 90 |
| 갤러리 | 45 |
| 도서관, 문화원, 기념관, 전시관, 사당 | 60 |

**cat39 (음식)**

| 키워드 | 적용 duration(분) |
|--------|------------------|
| 뷔페, 코스, 오마카세, 파인다이닝 | 90 |
| 고기, 갈비, 삼겹살, 소고기, 양고기, 돼지갈비 | 90 |
| 카페, 커피, 디저트, 베이커리, 크레페, 빙수, 아이스크림, 티하우스, 브런치 | 40 |
| 분식, 김밥, 떡볶이, 라면, 면, 우동, 국수, 냉면 | 35 |

---

## 5. indoor_outdoor 분류 규칙

### 5-1. 필드 정의

| 항목 | 내용 |
|------|------|
| 필드명 | indoor_outdoor |
| 타입 | VARCHAR(10) |
| 허용값 | indoor / outdoor / mixed |
| NULL 허용 | YES (미분류 허용) |
| 추가 migration | migration_004_add_indoor_outdoor.sql |

### 5-2. category별 기본값

| category_id | 기본 indoor_outdoor |
|-------------|---------------------|
| 12          | outdoor             |
| 14          | indoor              |
| 39          | indoor              |

### 5-3. 키워드 우선순위 규칙

우선순위: **mixed > indoor 키워드 > outdoor 키워드 > category 기본값**

**mixed 키워드** (어느 category든 mixed 적용)
```
복합문화공간, 테마파크, 놀이공원, 리조트, 워터파크
```

**indoor 키워드** (category 기본값 override)
```
박물관, 미술관, 갤러리, 공연장, 극장, 스파, 찜질, 수족관, 실내
```

**outdoor 키워드** (category 기본값 override)
```
공원, 숲, 등산, 계곡, 트레킹, 해수욕장, 해변, 야외
```

### 5-4. fallback 정책

- 키워드 매치 없음 → category 기본값 적용
- category 기본값도 없음 → NULL 유지 (미분류)
- 과도한 분류 금지: 불확실한 경우 기본값 유지

### 5-5. 재처리 안전 조건

```sql
WHERE indoor_outdoor IS NULL
```

이미 분류된 행은 덮어쓰지 않는다.

---

## 6. 마이그레이션 이력

| 파일 | 내용 | 적용일 |
|------|------|--------|
| migration_001_* | 초기 스키마 | — |
| migration_002_add_images.sql | first_image_url, first_image_thumb_url 컬럼 추가 | 2026-04 |
| migration_003_add_culture_role.sql | chk_visit_role에 'culture' 추가 | 2026-04 |
| migration_004_add_indoor_outdoor.sql | indoor_outdoor 컬럼 추가 | — (예정) |

---

## 7. 배치 실행 원칙

1. `batch_rules.py`는 AI 가공 이전 선행 단계 (1차 규칙 배치)
2. `visit_role IS NULL` 행만 처리 — 기존 가공값 보호
3. `indoor_outdoor IS NULL` 행만 처리 — 동일 원칙 적용
4. `--dry-run` 옵션으로 항상 먼저 검증 후 적용
5. 소량(서울 등 단일 지역)부터 적용, 이상 없으면 전국 확대
6. DB CHECK constraint 변경 시 반드시 migration 파일 생성 후 적용

---

## 8. AI 가공 연계 주의사항

- `ai_validator.ALLOWED_ROLES`에 `culture` 포함 완료 (ai_validator.py 반영)
- AI 배치가 실행되면 `visit_role IS NOT NULL` 행은 규칙 배치 결과로 보호됨
- AI 배치는 `visit_role IS NULL` 또는 `ai_summary IS NULL` 대상만 처리해야 함
- `indoor_outdoor` 는 AI 배치 대상이 아님 — 규칙 전용 필드

---

## 9. 1차 배치 결과 요약 (2026-04 기준)

| 항목 | 값 |
|------|---|
| 총 처리 건수 | 18,846 |
| 성공 | 18,846 |
| 실패 | 0 |
| visit_role: spot | 8,240 |
| visit_role: culture | 1,256 |
| visit_role: meal | 7,047 |
| visit_role: cafe | 2,303 |
| cat12 처리 | 8,240 |
| cat14 처리 | 1,256 |
| cat39 처리 | 9,350 |
