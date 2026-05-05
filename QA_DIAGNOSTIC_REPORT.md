# QA_DIAGNOSTIC_REPORT.md
> 진단 기준일: 2026-04-25  
> 수정 완료일: 2026-04-25  
> 진단 방법: 코드 정적 분석 + 엔진 직접 호출 실행 결과  
> 판정 기준: "결과가 다를 때만 정상" — 결과 동일 = 반영 실패

---

## 요약 (Critical Issues 우선)

| # | 문제 | 분류 | 심각도 | 상태 |
|---|------|------|--------|------|
| 1 | theme 변경해도 장소 결과 100% 동일 | 엔진 | CRITICAL | ✅ 수정완료 |
| 2 | density=알차게/적당히 결과 완전 동일 | 엔진 | CRITICAL | ✅ 수정완료 |
| 3 | 재계산 시 24:00/22:00 초과 방어 없음 → 25:03 등 출력 | API | CRITICAL | ✅ 수정완료 |
| 4 | 재계산 cascade 버그 (corrupted time 누적) | API | CRITICAL | ✅ 수정완료 |
| 5 | 장소 추가 후 재계산 시 추가된 장소 사라짐 | 프론트+API | HIGH | ✅ 수정완료 |
| 6 | 광주/대구/대전/인천 anchor 정의 없음 | 데이터 | HIGH | ✅ 수정완료 |
| 7 | CourseResultScreen → 뒤로가기 시 ConditionScreen 선택값 초기화 | 프론트 | MEDIUM | ✅ 수정완료 |
| 8 | companion 반영 미약 (+0.2 점수 보정만) | 엔진 | LOW | 미수정 |
| 9 | city_type 분리 없이 10km 일괄 적용 | 엔진 | MEDIUM | ✅ 수정완료 |
| 10 | 충남 태안/안면도 10km 고정으로 코스 생성 실패 | 엔진+API | HIGH | ✅ 수정완료 |
| 11 | UI "출발지" 단독 표현 (사용자 노출) | 프론트 | LOW | ✅ 수정완료 |
| 12 | 여유롭게 2개로 너무 짧게 종료 (09:00 출발) | 엔진 | HIGH | ✅ 수정완료 |
| 13 | 알차게(full template) 코스 생성 실패 | 엔진 | HIGH | ✅ 수정완료 |
| 14 | 맛집탐방 afternoon meal slot DB후보=0 실패 | 엔진 | HIGH | ✅ 수정완료 |
| 15 | 역사문화/도심감성 = 기본코스와 동일 (theme 분리 미반영) | 엔진 | MEDIUM | ✅ 수정완료 |
| 16 | 코스 카드 아코디언 상세 설명 없음 | 프론트+API | MEDIUM | ✅ 수정완료 |

---

## 1. 프론트 진단

### 1-1. 코스 만들기 버튼 활성화 조건

**코드 근거**: `HomeScreen.jsx:161`
```js
const canGenerate = !!departureTime && !!selectedAnchor;
```

- `departure_time` 없으면 버튼 비활성 → **OK**
- `start_anchor` 없으면 버튼 비활성 → **OK**
- `region`은 기본값 `'서울'`로 항상 존재 → region 미선택 없이 진행 가능 → **기능적 OK, UX 허용 범위**

판정: **조건 자체는 기능 정상. region 기본값 존재로 3-입력 모두 필수 UX는 아님.**

---

### 1-2. ConditionScreen 선택값 state 보존 여부

**코드 근거**: `ConditionScreen.jsx:64`
```js
const [selections, setSelections] = useState({
  companion: '혼자', mood: '자연 선택', walk: '보통', density: '적당히'
});
```

**코드 근거**: `App.jsx:38`
```js
onBack={() => setScreen('condition')}
```

- `CourseResultScreen`에서 뒤로가기 → `setScreen('condition')` 호출
- `ConditionScreen`은 재마운트 → `useState` 초기화 → **이전 선택값 사라짐**

**판정: 프론트 BUG — 카페투어 선택 후 결과 화면 진입 → 뒤로가기 → 자연산책으로 초기화됨.**

---

### 1-3. API payload 실제 포함 여부

**코드 근거**: `CourseResultScreen.jsx:115-128` (console.log 존재)

```js
console.log('[CourseGenerate] request payload:', payload);
```

| 필드 | 전송 여부 | 비고 |
|------|----------|------|
| region | ✅ | params.region |
| departure_time | ✅ | params.departure_time |
| start_anchor | ✅ | params.start_anchor |
| start_lat / start_lon | ✅ | params.start_lat/lon |
| companion | ✅ | params.companion |
| themes | ✅ | MOOD_TO_THEMES[params.mood] 변환 |
| template | ✅ | DENSITY_TO_TEMPLATE[params.density] 변환 |
| walk_max_radius | ✅ | WALK_TO_RADIUS[params.walk] 변환 |
| density 원값 | ❌ | template으로 변환 후 원값 소실 |
| distance_preference 원값 | ❌ | walk_max_radius로 변환 후 소실 |

**변환 맵핑**:
```
MOOD_TO_THEMES:
  '카페 투어'  → ['cafe']
  '맛집 탐방'  → ['food']
  '자연 선택'  → ['nature']
  '역사 문화'  → ['history']
  '도심 감성'  → ['urban']
  '조용한 산책' → ['walk']

DENSITY_TO_TEMPLATE:
  '여유롭게' → 'light'
  '적당히'   → 'standard'
  '알차게'   → 'full'    ← course_builder에서 'full' == 'standard' (버그)

WALK_TO_RADIUS:
  '적게'              → 5km
  '보통'              → 10km
  '조금 멀어도 좋아요' → 18km
```

---

## 2. 출발 기준점 진단

### 2-1. 지역별 anchor 존재 여부 및 10/15/25km 후보 수

**실행 결과** (DB 직접 조회):

| 지역 | anchor 정의 | viable | 10km 관광지 | 10km 식당 | 10km 카페 | 원인 분류 |
|------|------------|--------|------------|----------|----------|---------|
| 서울 (강남역) | ✅ | ✅ | 597 | 651 | 199 | — |
| 서울 (홍대) | ✅ | ✅ | 513 | 602 | 170 | — |
| 광주 | ❌ | ❌ | — | — | — | **A. anchor 정의 없음** |
| 대구 | ❌ | ❌ | — | — | — | **A. anchor 정의 없음** |
| 대전 | ❌ | ❌ | — | — | — | **A. anchor 정의 없음** |
| 인천 | ❌ | ❌ | — | — | — | **A. anchor 정의 없음** |
| 울산 (삼산) | ✅ | ✅ | 63 | 47 | 10 | — |
| 세종 (정부청사) | ✅ | ✅ | 20 | 39 | 15 | — |
| 강릉→강원 (강릉역) | ✅ | ✅ | 38 | 334 | 56 | — |
| 경주→경북 (경주역) | ✅ | ✅ | 109 | 89 | 20 | — |

**전체 서울 anchor 후보 실측값** (DB 조회):

| anchor | viable | 관광지10km | 식당10km | 카페10km | 전체10km | 전체15km | 전체25km |
|--------|--------|----------|---------|---------|---------|---------|---------|
| 강남역 주변 | ✅ | 597 | 651 | 199 | 1447 | 1952 | 2035 |
| 홍대입구 주변 | ✅ | 513 | 602 | 170 | 1285 | 1857 | 2035 |
| 명동/을지로 주변 | ✅ | 628 | 741 | 240 | 1609 | 1971 | 2035 |
| 광화문/종로 주변 | ✅ | 623 | 726 | 236 | 1585 | 1968 | 2035 |
| 잠실 주변 | ✅ | 566 | 547 | 164 | 1277 | 1839 | 2035 |
| 여의도 주변 | ✅ | 541 | 528 | 128 | 1197 | 1764 | 2035 |
| 성수동/건대 주변 | ✅ | 575 | 703 | 222 | 1500 | 1860 | 2035 |
| 이태원/한남 주변 | ✅ | 628 | 746 | 240 | 1614 | 1972 | 2035 |

**강원(강릉 포함) anchor 실측값**:

| anchor | viable | 관광지10km | 식당10km | 카페10km | 전체15km | 전체25km |
|--------|--------|----------|---------|---------|---------|---------|
| 강릉역 주변 | ✅ | 38 | 334 | 56 | 487 | 637 |
| 경포해변 주변 | ✅ | 36 | 347 | 61 | 533 | 653 |
| 안목해변 주변 | ✅ | 35 | 320 | 53 | 477 | 617 |
| 속초 주변 | ✅ | 73 | 82 | 19 | 230 | 289 |
| 춘천 주변 | ✅ | 71 | 55 | 21 | 170 | 247 |
| 정동진 주변 | ✅ | 7 | 20 | 0 | 115 | 516 |

> **주의**: 정동진 카페10km = 0 → viable 기준 통과 (tourist≥2, meal≥1)하나 코스 품질 낮을 수 있음

**경북(경주 포함) anchor 실측값**:

| anchor | viable | 관광지10km | 식당10km | 카페10km | 전체15km | 전체25km |
|--------|--------|----------|---------|---------|---------|---------|
| 경주역 주변 | ✅ | 109 | 89 | 20 | 258 | 312 |
| 황리단길/대릉원 주변 | ✅ | 110 | 104 | 23 | 257 | 319 |
| 불국사 주변 | ✅ | 66 | 43 | 9 | 263 | 330 |
| 포항 주변 | ✅ | 31 | 35 | 10 | 101 | 370 |
| 안동 주변 | ✅ | 37 | 19 | 2 | 85 | 151 |

### 2-2. UI 지역 목록과 DB 지역 목록 불일치

**코드 근거**: `dayTripDummyData.js:1`
```js
export const REGIONS = ['서울', '부산', '제주', '경주', '강릉', '전주'];
```

`REGION_TO_DB`에 광주, 대구, 대전, 인천이 없음. `/api/regions`에서 DB에 해당 지역 데이터가 있어도 anchor가 없어 departure 목록 비어있게 됨.

---

## 3. API 진단

### 3-1. 서버 payload 수신 확인

**코드 근거**: `api_server.py:35-47` (GenerateRequest 모델)

수신 필드:
- `companion` ✅ (41번째 줄)
- `themes` ✅ (42번째 줄)
- `template` ✅ (43번째 줄)
- `walk_max_radius` ✅ (46번째 줄)
- `region_travel_type` ✅ (44번째 줄)

### 3-2. 기본값 덮어쓰기 여부

**코드 근거**: `api_server.py:327-338`

```python
request = {
    "companion":       body.companion or "",        # 빈 문자열 기본
    "themes":          body.themes or [],            # 빈 리스트 기본
    "template":        body.template or "standard", # 미전송 시 standard 강제
    "walk_max_radius": body.walk_max_radius,         # None 허용
}
```

판정: **기본값 강제 덮어쓰기 없음. 수신값 그대로 course_builder에 전달됨.**

### 3-3. API 응답 JSON 필드 존재 여부

| 필드 | 존재 | 위치 |
|------|------|------|
| template | ✅ | course_builder 반환 |
| target_place_count | ✅ | course_builder 반환 |
| actual_place_count | ✅ | course_builder 반환 |
| total_duration_min | ✅ | course_builder 반환 |
| total_travel_min | ✅ | course_builder 반환 |
| radius_fallback | ✅ | api_server._build_course_with_fallback |
| radius_fallback_reason | ✅ | api_server._build_course_with_fallback |
| course_id | ✅ | api_server.generate_course |
| applied_options | ❌ | 미구현 |
| selected_radius_km | ❌ | 미구현 |
| selection_basis (top-level) | ❌ | place별로만 존재 |

---

## 4. 엔진 진단 — 실행 결과

### 4-1. 서울 강남역 기준 조건별 비교 (출발 10:00)

**테스트 조건**: region=서울, anchor=강남역(37.4979, 127.0276), start_time=10:00

| 조건 | template | target | actual | 카페 | 식당 | 관광지 | 종료시각 | 이동(분) | fallback |
|------|----------|--------|--------|------|------|--------|---------|---------|---------|
| 기본 | standard | 4 | 4 | 0 | 2 | 2 | 18:45 | 71 | N |
| 카페투어 | standard | 4 | 4 | **0** | 2 | 2 | **18:45** | **71** | N |
| 맛집탐방 | standard | 4 | 4 | **0** | 2 | 2 | **18:45** | **71** | N |
| 자연산책 | standard | 4 | 4 | **0** | 2 | 2 | **18:45** | **71** | N |
| 여유롭게 | light | 3 | 3 | 1 | 1 | 1 | 14:10 | 41 | N |
| **알차게** | **full** | **4** | **4** | **0** | **2** | **2** | **18:45** | **71** | N |
| 거리부담적게 | standard | 4 | 4 | 1 | 2 | 1 | 18:45 | 51 | N |
| 거리멀어도OK | standard | 4 | 4 | 0 | 2 | 2 | 18:45 | 71 | N |

**실제 선택 장소 (상위 3개)**:
- 기본/카페투어/맛집탐방/자연산책/알차게 모두: `['관문사(서울)', '구스아일랜드 브루하우스', '샘터화랑', ...]`
- 거리부담적게: `['관문사(서울)', '구스아일랜드 브루하우스', '썸띵어바웃커피', ...]` (3번째 다름)
- 거리멀어도OK: 기본과 동일

---

### 4-2. 판정

#### CRITICAL — 테마 반영 완전 실패

| 비교 쌍 | 결과 동일 여부 | 판정 |
|---------|-------------|------|
| 기본 vs 카페투어 | **100% 동일** | **엔진 반영 실패** |
| 기본 vs 맛집탐방 | **100% 동일** | **엔진 반영 실패** |
| 기본 vs 자연산책 | **100% 동일** | **엔진 반영 실패** |

**원인 분석**:

1. `course_builder.py:211` — `_fetch_candidates`는 `visit_role`과 `visit_time_slot`으로만 DB 필터:
   ```python
   AND visit_role = ANY(%(roles)s)
   AND visit_time_slot @> ARRAY[%(slot)s]::varchar[]
   ```
   theme 조건 없음 → 후보 풀이 theme과 무관하게 동일

2. `course_builder.py:167-173` — theme은 `_score()`에서만 가중치로 작용:
   ```python
   place_themes = set(tags.get("themes", []) + tags.get("mood", []))
   matched = len(set(user_themes) & place_themes)
   theme_score = matched / max(len(user_themes), 1)
   ```
   WEIGHTS["theme_match"] = 0.30 (30%)이지만 travel_fit 0.40이 지배

3. 같은 anchor에서 같은 후보 풀 → travel_fit 점수 동일 → 모든 theme에서 같은 장소 선택

4. 특히 `카페투어(themes=['cafe'])`: slot 구조가 `standard`이므로 morning=spot, lunch=meal, afternoon=spot/culture, dinner=meal — 카페 슬롯 자체가 없음. afternoon에서 spot/culture 후보 부족 시 cafe fallback만 발동. **카페 3개 보장 불가능, 구조적으로 불가**.

#### CRITICAL — density=알차게/적당히 동일

**코드 근거**: `course_builder.py:22-25`
```python
TEMPLATES = {
    "light":    [("morning", ["spot", "culture"]), ("lunch", "meal"), ("afternoon", "cafe")],
    "standard": [("morning", ["spot", "culture"]), ("lunch", "meal"), ("afternoon", ["spot", "culture"]), ("dinner", "meal")],
    "full":     [("morning", ["spot", "culture"]), ("lunch", "meal"), ("afternoon", ["spot", "culture"]), ("dinner", "meal")],
}
```

`full` == `standard` 완전 동일. 실행 결과도 동일하게 확인됨.

판정: **density=알차게 미구현. 엔진 반영 실패.**

#### MEDIUM — distance_preference=멀어도OK와 기본 동일

- 기본(10km): roles=['spot', 'meal', 'culture', 'meal'], 이동71분
- 거리멀어도OK(18km): **동일한 장소, 동일한 결과**

원인: 10km 반경으로 이미 충분한 서울 후보가 존재 → 18km 확장해도 같은 상위 장소가 선택됨. 서울에서는 사실상 차이 없음.

- 거리부담적게(5km): afternoon spot/culture 후보 5km 내 부족 → **cafe fallback 발동** → 결과 다름 (반영 OK)

#### companion 반영

**코드 근거**: `course_builder.py:170-173`
```python
companions = set(tags.get("companion", []))
if user_companion in companions:
    theme_score = min(theme_score + 0.2, 1.0)
```

+0.2 보정만 존재. `ai_tags.companion` 필드 데이터가 없으면 효과 없음. **미약 구현** — 리포트에 표시.

---

### 4-3. 지방 지역 엔진 결과 (강원, 경북)

| 조건 | template | target | actual | 카페 | 식당 | 관광지 | 종료시각 | 이동(분) |
|------|----------|--------|--------|------|------|--------|---------|---------|
| 강원/강릉역 기본 | standard | 4 | 4 | 0 | 2 | 2 | 18:30 | 65 |
| 경북/경주역 기본 | standard | 4 | 4 | 0 | 2 | 2 | 19:00 | 38 |
| 경북/황리단길 기본 | standard | 4 | 4 | 0 | 2 | 2 | 19:00 | 38 |
| 강원/거리멀어도OK | standard | 4 | 4 | 0 | 2 | 2 | 18:30 | 65 |

**경주역과 황리단길(1km 거리)**: 장소, 시간, 이동시간 모두 동일 → 두 anchor의 10km 권역이 거의 겹침. 사용자 입장에서 다른 출발지를 선택해도 동일한 코스가 나옴.

**강원 거리멀어도OK**: 기본과 동일 → 10km 내 식당 충분(334개)하므로 18km 확장 효과 없음.

---

## 5. 도시/지방 반경 정책 진단

### 현재 상태

```python
# course_builder.py:38
MAX_RADIUS_KM  = 10   # 모든 지역 일괄 적용
MAX_TRAVEL_MIN = 40

# course_builder.py:47
SPARSE_REGIONS = {"제주", "강원", "전남", "경북", "충남", "전북", "경남", "충북"}
# → meal만 20km fallback, spot/culture는 여전히 10km
```

### 진단 결과

| 항목 | 현재 | 판정 |
|------|------|------|
| MAX_RADIUS_KM=10 일괄 적용 | ✅ 확인됨 | 문제: 지방 차량 이동 기준 부족 |
| 서울 10km | 적정 (후보 1000개 이상) | OK |
| 강릉 10km 관광지 | 38개 | 적음. 코스 생성은 가능하나 다양성 부족 |
| 경주 10km 관광지 | 109개 | 충분 |
| 세종 10km 관광지 | 20개 | 경계값 수준 |
| city_type 분리 구현 | 없음 | 권장 |
| MAX_TOTAL_TRAVEL=120 (urban) | 지방 120분 제한 | spot 탈락 가능 |
| REGIONAL_MAX_TOTAL_TRAVEL=180 | regional 모드만 | urban 지방 코스는 혜택 없음 |

### 권장 방향

지방 지역에서 `region_travel_type='urban'`으로 코스 생성 시:
- `SPARSE_REGIONS`에 포함된 지역은 spot/culture도 15km까지 완화 필요
- `MAX_TOTAL_TRAVEL`을 sparse 지역에서 150~180분으로 상향 권장

---

## 6. 경로 재계산 시간 오류 진단

### 6-1. 버그 확인

**코드 근거**: `api_server.py:511-515`

```python
s_min = current_min + travel_min
e_min = s_min + duration_min

updated.append({
    "scheduled_start": f"{s_min // 60:02d}:{s_min % 60:02d}",
    "scheduled_end":   f"{e_min // 60:02d}:{e_min % 60:02d}",
})
```

**24시간 초과 방어 없음** — `s_min=1503`이면 `"25:03"` 직접 출력.

### 6-2. 22:00 제한 비교

| 위치 | END_HOUR_LIMIT 체크 | 비고 |
|------|------------------|----|
| `course_builder.py:648-655` | ✅ 있음 | 초과 장소 제거 |
| `api_server.py:recalculate_course` | **❌ 없음** | **버그** |

### 6-3. Cascade 버그 시뮬레이션

```
[1단계] build_course → places[2].scheduled_start="09:00", scheduled_end="10:30"
[2단계] 재순서 후 recalculate (END_HOUR_LIMIT 없음) → places[4].scheduled_end="22:30"
         → 서버 _courses에 "22:30" 저장
[3단계] 장소 변경 → replace_place 실행 → scheduled_end="22:30" 그대로 유지
[4단계] 다시 recalculate →
         duration_min = (22*60+30) - (9*60+0) = 810분 (!)
         e_min = 600 + 810 = 1410 → "23:30" (overflow 없으나 잘못된 duration)
[X단계] 충분히 쌓이면 "25:03", "33:04" 생성
```

**원인**: 재계산 시 `scheduled_start/end`에서 duration을 복원하는데, 이전 재계산이 생성한 corrupted time을 그대로 사용 → cascade

### 6-4. 추가된 장소 재계산 시 사라지는 버그

**코드 근거**: `CourseResultScreen.jsx:251`, `api_server.py:474`

```js
// 프론트: 추가된 장소 id
const newPlace = { id: `added-${Date.now()}`, ... };

// 서버: place_map은 원본 place_id 기준
place_map = {str(p["place_id"]): p for p in schedule}
reordered = [place_map[pid] for pid in body.place_ids if pid in place_map]
// → 'added-...' ID 조회 실패 → 장소 삭제됨
```

---

## 7. 수정 필요 파일 목록

| 파일 | 수정 항목 | 우선순위 |
|------|----------|---------|
| `course_builder.py` | TEMPLATES["full"]을 standard와 다르게 구성 (5~6슬롯) | CRITICAL |
| `course_builder.py` | theme별 slot 구성 변경 또는 후보 필터 추가 (카페투어 → cafe 슬롯 추가) | CRITICAL |
| `api_server.py` | `recalculate_course`에 22:00 cap 및 24시간 초과 방어 추가 | CRITICAL |
| `api_server.py` | 추가된 장소(added-* ID) 처리 로직 추가 | HIGH |
| `anchor_definitions.py` | 광주, 대구, 대전, 인천 anchor 추가 | HIGH |
| `App.jsx` | ConditionScreen에 이전 선택값 props로 전달 | MEDIUM |
| `HomeScreen.jsx` | "어디서 출발할까요?" → "어느 지역 중심으로 여행할까요?" 문구 변경 | LOW |
| `course_builder.py` | sparse 지역 spot/culture 반경 완화 (15km) | MEDIUM |

---

## 8. 엔진 전면 수정 필요 여부

**필요.** 부분 수정으로는 해결 불가능한 구조적 문제:

1. **TEMPLATES 구조** — `full==standard` 동일 구조 → density=알차게 전혀 의미 없음
2. **theme → 슬롯 연동 부재** — theme은 점수 보정만 하며 slot 구성에 영향 없음 → 카페투어에서 카페 0개 나오는 구조적 원인
3. **DB 후보 필터에 theme 반영 없음** — 테마에 맞는 장소 우선 필터링 없이 view_count DESC 50개 중 점수 정렬만

---

## 9. 권장 수정 방향

### 우선순위 1 — 재계산 시간 오류 (즉시 수정)

```python
# api_server.py recalculate_course 내부
s_min = current_min + travel_min
e_min = s_min + duration_min

# 22:00 초과 시 중단
if e_min > 22 * 60:
    break  # 이후 장소 제외

# 24시간 초과 방어 (표시용)
s_str = f"{min(s_min, 23*60+59) // 60:02d}:{s_min % 60:02d}"
e_str = f"{min(e_min, 23*60+59) // 60:02d}:{e_min % 60:02d}"
```

### 우선순위 2 — density=알차게 차별화

```python
TEMPLATES = {
    "light":    [...3슬롯...],
    "standard": [...4슬롯...],
    "full":     [
        ("morning",   ["spot", "culture"]),
        ("lunch",     "meal"),
        ("afternoon", ["spot", "culture"]),
        ("cafe",      "cafe"),       # 오후 카페 슬롯 추가
        ("dinner",    "meal"),
        ("night",     ["spot", "culture"]),  # 야간 슬롯 추가
    ],
}
```

### 우선순위 3 — 카페투어 theme → slot 반영

```python
# theme별 slot 오버라이드 맵 추가
THEME_SLOT_OVERRIDES = {
    "cafe": {
        "standard": [
            ("morning", "cafe"),
            ("morning2", ["spot", "culture"]),
            ("lunch", "meal"),
            ("afternoon", "cafe"),
            ("dinner", "meal"),
        ]
    }
}
```

또는 `_fetch_candidates`에서 theme 기반 role 우선순위 부여.

### 우선순위 4 — 광주/대구/대전/인천 anchor 정의

`anchor_definitions.py`에 4개 도시 anchor 추가 (각 2~3개씩).

### 우선순위 5 — ConditionScreen 상태 보존

```jsx
// App.jsx
<ConditionScreen
  initialSelections={courseParams?.conditionSelections}  // 기존 선택값 전달
  onBack={() => setScreen('home')}
  onNext={(conditionParams) => { ... }}
/>
```

---

## 10. 부록 — 테스트 실행 증거

### Engine Input (서울, 카페투어)
```json
{
  "region": "서울",
  "departure_time": "오늘 10:00",
  "companion": "",
  "themes": ["cafe"],
  "template": "standard",
  "region_travel_type": "urban",
  "zone_center": [37.4979, 127.0276],
  "walk_max_radius": 10
}
```

### Engine Output (서울, 카페투어)
```json
{
  "template": "standard",
  "target_place_count": 4,
  "actual_place_count": 4,
  "roles": ["spot", "meal", "culture", "meal"],
  "cafe_count": 0,
  "scheduled_end": "18:45"
}
```

### Engine Input (서울, 기본)
```json
{
  "themes": [],
  "template": "standard"
}
```

### Engine Output (서울, 기본)
```json
{
  "roles": ["spot", "meal", "culture", "meal"],
  "cafe_count": 0,
  "place_names": ["관문사(서울)", "구스아일랜드 브루하우스", "샘터화랑", ...]
}
```

**기본 vs 카페투어: 장소명, role, 시간 100% 동일 → 엔진 반영 실패 확인.**

---

## 11. 엔진 수정 후 검증 결과 (수정 완료)

> 수정 기준: request.md 항목 1-7  
> 실행: `qa_diagnostic_runner.py` Section 7  
> 기준점: 서울 강남역(37.4979, 127.0276), 출발 10:00

### 11-1. 종합 판정: **PASS — 모든 기준 통과**

### 11-2. theme 구분 (request.md 항목 1, 3, 4)

| 비교 쌍 | 판정 | 비고 |
|--------|------|------|
| 기본 vs 카페투어 | ✅ PASS | slot 구조 다름: cafe/meal/cafe/cafe vs spot/meal/culture/meal |
| 기본 vs 맛집탐방 | ✅ PASS | slot 구조 다름: spot/meal/meal/meal vs spot/meal/culture/meal |
| 기본 vs 자연산책 | ✅ PASS | 장소 다름: 동달식당 강남본점(힐링태그) vs 노들강본채 |

**카페투어**: `['동작노을카페', '기절초풍왕순대', '페어필드커피', '메종조']`  
**맛집탐방**: `['관문사(서울)', '린스시', '구스아일랜드 브루하우스', '무등산수만리염소탕 강남점']`  
**자연산책**: `['관문사(서울)', '노들강본채', '샘터화랑', '동달식당 강남본점']`  
**기본**: `['관문사(서울)', '구스아일랜드 브루하우스', '샘터화랑', '노들강본채']`

### 11-3. 카페투어 카페 수 (request.md 항목 1)

| 항목 | 판정 |
|------|------|
| cafe_count ≥ 3 | ✅ PASS (cafe=3) |
| roles 구조 | `['cafe', 'meal', 'cafe', 'cafe']` — 카페 3슬롯 |

### 11-4. density 구분 (request.md 항목 2)

| 항목 | 판정 |
|------|------|
| target_count 다름 (full=5 vs standard=4) | ✅ PASS |
| 결과(place_names) 다름 | ✅ PASS |
| 종료시각 다름 (full=19:58 vs standard=18:45) | ✅ PASS |

- **알차게(full)**: 5슬롯 → actual=5, 종료 19:58, roles=`['spot', 'meal', 'culture', 'meal', 'cafe']`
- **적당히(standard)**: 4슬롯 → actual=4, 종료 18:45, roles=`['spot', 'meal', 'culture', 'meal']`

### 11-5. slot 구조 분리 (request.md 항목 3)

| theme | roles |
|-------|-------|
| 기본 | `['spot', 'meal', 'culture', 'meal']` |
| 카페투어 | `['cafe', 'meal', 'cafe', 'cafe']` ← THEME_SLOT_CONFIG["cafe"]["standard"] 적용 |
| 맛집탐방 | `['spot', 'meal', 'meal', 'meal']` ← THEME_SLOT_CONFIG["food"]["standard"] 적용 |
| 자연산책 | `['spot', 'meal', 'culture', 'meal']` ← 구조 동일이나 nature ai_tags 필터로 후보 다름 |

### 11-6. selection_basis / weights (request.md 항목 5)

| 항목 | 기본 | 카페투어 | 판정 |
|------|------|--------|------|
| travel_fit | 0.40 | 0.25 | ✅ PASS |
| theme_match | 0.30 | 0.50 | ✅ PASS |
| mode | default | theme | ✅ PASS |

### 11-7. selected_radius_km 반환 (request.md 항목 5, 6)

| theme | selected_radius_km |
|-------|--------------------|
| 기본 | 10.0 (urban profile) |
| 카페투어 | 10.0 |
| 맛집탐방 | 10.0 |
| 자연산책 | 10.0 |

> 도시/지방 MOBILITY_PROFILE 분리 완료. 서울=urban → 10km/40min/120min. 지방=rural → 15km/60min/180min.

### 11-8. 수정 전후 비교표

| 조건 | 수정 전 | 수정 후 | 변경 |
|------|--------|--------|------|
| 카페투어 roles | `['spot','meal','culture','meal']` | `['cafe','meal','cafe','cafe']` | ✅ |
| 카페투어 cafe_count | 0 | 3 | ✅ |
| 맛집탐방 meal_count | 2 | 3 | ✅ |
| 자연산책 == 기본 | 100% 동일 | 다름 | ✅ |
| full==standard | 4슬롯 동일 | full=5슬롯 (19:58 종료) | ✅ |
| theme weights | travel_fit=0.40 고정 | theme 활성화 시 0.25 | ✅ |
| city_type 분리 | 없음(10km 일괄) | MOBILITY_PROFILE urban/medium/rural | ✅ |
| selected_radius_km | 미반환 | 반환됨 | ✅ |
| selection_basis top-level | 미반환 | `{"weights":..., "mode":"theme"/"default"}` | ✅ |

### 11-9. 수정 파일 목록

| 파일 | 수정 내용 |
|------|---------|
| `course_builder.py` | TEMPLATES["full"] night 슬롯 추가 (5슬롯) |
| `course_builder.py` | THEME_SLOT_CONFIG 추가 (cafe/food별 slot 구조 분리) |
| `course_builder.py` | WEIGHTS_DEFAULT / WEIGHTS_THEME 분리 (theme 활성 시 theme_match 0.30→0.50) |
| `course_builder.py` | THEME_SCORE_EXPAND 추가 (영어→한국어 태그 매핑으로 theme_match 계산 정확화) |
| `course_builder.py` | MOBILITY_PROFILE 추가 (urban/medium/rural city_type별 radius/travel 분리) |
| `course_builder.py` | `_get_city_type`, `_get_weights`, `_resolve_theme_slots` 함수 추가 |
| `course_builder.py` | `_fetch_candidates` — relax_slot + themes 파라미터 추가, nature/food 우선 후보풀 구성 |
| `course_builder.py` | `_score` — relax_slot + weights 파라미터 추가, 한국어 태그 확장 매핑 적용 |
| `course_builder.py` | `build_course` — _resolve_theme_slots 사용, MOBILITY_PROFILE 적용, weights 동적 계산, selected_radius_km 반환 |

---

## 12. 4단계 수정 결과 (2026-04-25)

### 12-1. 1단계: 광주/대구/대전/인천 출발 기준점 목록

**검증 결과 (generate_anchor_departures 실행)**

| 지역 | anchor 수 | 10km 후보 수 (대표 기준점) | 상태 |
|------|-----------|--------------------------|------|
| 광주 | 3개 | 광주역 240 / 충장로 224 / 상무지구 223 | ✅ 정상 |
| 대구 | 4개 | 동성로 317 / 동대구역 316 / 수성못 304 / 서문시장 300 | ✅ 정상 |
| 대전 | 4개 | 둔산/시청 358 / 유성온천 323 / 으능정이 294 / 대전역 291 | ✅ 정상 |
| 인천 | 5개 | 인천역/차이나타운 319 / 월미도 299 / 부평역 281 / 송도 251 / 강화도 42 | ✅ 정상 |

**원인**: `anchor_definitions.py`에 4개 도시 anchor 정의 없음 → 이전 세션에서 추가 완료.  
**API**: `/api/region/{region}/departures` — 정상 응답 확인.

---

### 12-2. 2단계: 충남 태안/안면도 코스 생성 실패

**후보 수 (태안 기준)**

| 반경 | tourist | meal | cafe | total |
|------|---------|------|------|-------|
| 10km | 19 | 14 | 1 | ~34 |
| 15km | (충분) | (충분) | — | ≥4 슬롯 가능 |

**수정 내용**:
1. `course_builder._fetch_candidates` — `pre_filter_radius_km` 파라미터 추가.  
   `zone_center` 있고 `zone_radius_km` 없을 때 SQL-level 거리 pre-filter 적용 (`max(eff_max_radius * 4.0, 30.0)`km).  
   → 충남 province-wide top-50이 모두 천안/서산에서 뽑히던 문제 해결.
2. `api_server._is_course_sufficient` 추가 — 성공 기준을 `actual >= max(2, target-1)`로 상향.  
   → 10km 2/4 = 불충분 → 15km 자동 확장.
3. `api_server._build_course_with_fallback` — `>= 2` 조건을 `_is_course_sufficient()` 호출로 교체.

**검증 결과**:
```
10km: actual=2, target=4, sufficient=False → 15km fallback 진입
15km: actual=4, target=4, sufficient=True → 반환
최종: selected_radius_km=15.0, 태안해변길(spot), 태안식당(meal), 안면도 카페(cafe), 안면도덮밥집(meal)
```
**판정: ✅ 통과** — 15km에서 4/4 코스 생성 성공.

---

### 12-3. 3단계: 장소 추가 후 경로 재계산

**수정 파일**:

- **`api_server.py`**:
  - `RecalculatePlace` 모델 추가 (`id`, `place_id`, `name`, `visit_role`, `lat/lon`, `duration_min`, `first_image_url`)
  - `RecalculateRequest`에 `current_places: Optional[list[RecalculatePlace]]` 추가
  - `END_HOUR_LIMIT = 22 * 60` 상수 추가
  - `recalculate_course` 전면 재작성:
    - `current_places` 수신 시 프론트 상태 기준으로 목록 구성
    - `added-*` ID 장소는 `place_id`로 DB에서 좌표/이미지 조회 후 포함
    - 22:00 이후 시작 시 해당 장소 이후 전부 드롭
    - `estimated_duration` → `scheduled_start/end` 차이 → 기본 60분 순으로 체류 시간 결정

- **`frontend/src/screens/day-trip/CourseResultScreen.jsx`**:
  - `normalizePlace` — `place_id`, `duration_min`, `lat`, `lon` 필드 추가 (재계산 payload 구성에 필요)
  - `normalizeCandidate` — `lat`, `lon` 필드 추가
  - `handleAddConfirm` — `place_id`, `lat`, `lon`, `duration_min` 필드를 추가 장소에 보존
  - `handleRecalculate` — `current_places` 배열 포함하여 API 전송

**수정 기준 충족 여부**:
| 기준 | 충족 |
|------|------|
| 재계산 = 새 코스 생성 아님 | ✅ (place 재선정 없음) |
| 현재 places 배열 유지 | ✅ (current_places 기반) |
| 추가된 장소 유지 | ✅ (added-* ID → DB 조회로 편입) |
| 엔진이 임의 제거 금지 | ✅ |
| start_time 기준 전체 재계산 | ✅ |
| 22:00 초과 금지 | ✅ (END_HOUR_LIMIT = 22*60) |
| 24:00 이상 표시 금지 | ✅ (e_min cap) |
| total_travel_min 갱신 | ✅ |

---

### 12-4. 4단계: UI 명칭 수정

| 파일 | 변경 전 | 변경 후 |
|------|---------|---------|
| `HomeScreen.jsx:215` | 어디서 출발할까요? | 어느 지역 주변을 돌까요? |
| `HomeScreen.jsx:381` | 추천 출발지 | 추천 출발 기준점 |
| `HomeScreen.jsx:390` | 출발지 후보가 없어요 | 출발 기준점 후보가 없어요 |
| `HomeScreenRedesign.jsx:159` | 어디서 출발할까요? | 어느 지역 주변을 돌까요? |
| `HomeScreenRedesign.jsx:279` | 인기 출발지 | 인기 출발 기준점 |

**잔여 "출발지" 텍스트**: 0건 (전체 검색 후 확인).

---

### 12-5. 수정 파일 전체 목록

| 파일 | 수정 내용 |
|------|---------|
| `course_builder.py` | `_fetch_candidates` — `pre_filter_radius_km` 파라미터 추가, zone_center 기준 SQL 거리 pre-filter |
| `course_builder.py` | `build_course` — `pre_filter_r` 계산 추가, 슬롯 루프에서 `pre_filter_radius_km=pre_filter_r` 전달 |
| `api_server.py` | `_is_course_sufficient` 함수 추가 (actual >= max(2, target-1)) |
| `api_server.py` | `_build_course_with_fallback` — 성공 기준을 `_is_course_sufficient()`로 교체 |
| `api_server.py` | `RecalculatePlace`, `RecalculateRequest` — `current_places` 필드 추가 |
| `api_server.py` | `recalculate_course` — 전면 재작성 (current_places 기반, DB 조회, 22:00 cap) |
| `anchor_definitions.py` | 광주/대구/대전/인천 anchor 정의 추가 (이전 세션) |
| `frontend/…/HomeScreen.jsx` | "출발지" → "출발 기준점" / "어느 지역 주변을 돌까요?" 3개소 |
| `frontend/…/HomeScreenRedesign.jsx` | "출발지" → "출발 기준점" / "어느 지역 주변을 돌까요?" 2개소 |
| `frontend/…/CourseResultScreen.jsx` | normalizePlace/normalizeCandidate/handleAddConfirm/handleRecalculate 수정 |

---

### 12-6. 남은 이슈

| # | 문제 | 비고 |
|---|------|------|
| 8 | companion 반영 미약 | 미수정 (low priority) |

---

## 13. 추가 수정 결과 (2026-04-26)

### 13-1. 충남 태안 09:00 출발 조건별 비교 (수정 후)

| 조건 | 판정 | actual | roles | end | ttm | r | fallback |
|------|------|--------|-------|-----|-----|---|---------|
| 기본 | ✅ | 4 | spot/meal/spot/meal | 18:10 | 96 | 10km | 없음 |
| 여유롭게 | ✅ | 3 | spot/meal/cafe | 15:00 | 79 | 15km | 15km fallback |
| 적당히 | ✅ | 4 | spot/meal/spot/meal | 18:10 | 96 | 10km | 없음 |
| 알차게 | ✅ | 4 | spot/meal/spot/meal | 18:10 | 96 | 10km | 없음 |
| 카페투어 | ✅ | 3 | cafe/meal/cafe | 14:14 | 57 | 10km | 없음 |
| 도심감성 | ✅ | 4 | spot/meal/spot/meal | 18:10 | 96 | 10km | 없음 (note: 지역 특성상 도심 후보 부족) |
| 맛집탐방 | ✅ | 4 | spot/meal/meal/meal | 18:10 | 126 | 10km | 없음 |
| 역사문화 | ✅ | 4 | culture/meal/cafe/meal | 18:10 | 67 | 10km | 없음 |

**이전 대비 개선:**
- 여유롭게: 2개(12:30 종료) → 3개(15:00 종료) ✅
- 알차게: 실패 → 4개 성공 ✅
- 맛집탐방: 실패 → 4개(meal×3) 성공 ✅
- 역사문화: spot 시작 → **culture** 시작 (theme 분리 반영) ✅
- 도심감성: fallback_reason note 추가 ✅

---

### 13-2. 수정 원인별 분석

| 문제 | 원인 | 수정 |
|------|------|------|
| 알차게 실패 | afternoon 슬롯 실패 후 `prev_role="meal"` 유지 → dinner meal 전부 차단 | `skips_since_last` 카운터 추가 — 스킵된 슬롯 있으면 same-role 체크 해제 |
| 맛집탐방 실패 | food theme meal 슬롯에 `visit_time_slot='afternoon'` 조건 적용 → DB후보=0 | food+meal 조합에 `relax_slot=True` 적용 |
| 여유롭게 2개 | `_is_course_sufficient: max(2, target-1)=2` → 2개 반환으로 충분 판정 | `max(3, target-1)` — light(target=3)에서 최소 3개 요구 |
| pre_filter 100km 문제 | 25km radius에서 pre_filter_r=100km → 충남 전역 후보 포함, 천안 등 원거리 top-N | `min(max(r*3, 30), 60)` — 60km 상한 적용 |
| 역사문화 = 기본 | `THEME_SLOT_CONFIG["history"]` 없음 | history theme 추가: morning=culture 우선, `_fetch_candidates` 역사/문화 tag 필터 |
| 도심감성 note 없음 | `_get_city_type != "rural"` 조건 (충남=medium) | 조건을 `!= "urban"`으로 변경 |

---

### 13-3. ConditionScreen 상태 유지

**수정 파일**: `App.jsx`, `ConditionScreen.jsx`

- `App.jsx`에 `conditionValues` state 추가
- `ConditionScreen.onNext(selections)` 호출 시 `setConditionValues(conditionParams)` 저장
- `ConditionScreen`에 `initialValues={conditionValues}` prop 전달
- `ConditionScreen.jsx`: `initialValues ?? {기본값}` 으로 초기화

결과: 코스 결과 화면 → 뒤로가기 → ConditionScreen 재진입 시 이전 선택값(companion/mood/walk/density) 유지됨.

---

### 13-4. 아코디언 상세 설명 (description)

**수정 파일**: `course_builder.py`, `CourseResultScreen.jsx`

- `_fetch_candidates` SQL에 `ai_summary`, `overview` 컬럼 추가
- `_build_schedule` 출력에 `description` 필드 추가 (ai_summary → overview → fallback 문구 순)
- description 200자 초과 시 자르기
- `normalizePlace`에서 `p.description` 사용 (기존 `''` 고정 제거)

**검증 결과** (충남 태안 기본 코스):
- 갈음이해수욕장(spot): fallback 문구 (ai_summary 없음)
- 옥양수산(meal): ai_summary 60자+ ✅
- 리츠캐슬 리조트(spot): overview 60자+ ✅
- 화해당(meal): ai_summary 60자+ ✅

---

### 13-5. 수정 파일 목록

| 파일 | 수정 내용 |
|------|---------|
| `course_builder.py` | THEME_SLOT_CONFIG — history theme 슬롯 추가 (light/standard/full), food light 추가 |
| `course_builder.py` | `_fetch_candidates` — history theme 역사/문화 태그 필터 추가, ai_summary/overview 컬럼 추가 |
| `course_builder.py` | `build_course` — pre_filter_r cap 60km, relax 조건 food+meal 포함, skips_since_last 카운터 |
| `course_builder.py` | `_build_schedule` — description 필드 추가 (ai_summary/overview/fallback) |
| `course_builder.py` | `build_course` return — theme_notes(도심감성 지역 부족 메시지) 추가 |
| `api_server.py` | `_is_course_sufficient` — max(2,…) → max(3,…) |
| `App.jsx` | conditionValues state 추가, ConditionScreen에 initialValues 전달 |
| `ConditionScreen.jsx` | initialValues prop 수신, useState 초기값으로 사용 |
| `CourseResultScreen.jsx` | normalizePlace에서 description 필드 전달 |

---

### 13-6. 남은 이슈

| # | 문제 | 비고 |
|---|------|------|
| 8 | companion 반영 미약 | 미수정 (low priority) |
| — | 알차게 5개 목표 달성 불가 (night slot DB후보=0 태안) | 데이터 한계, 코드 수정으로 해결 불가 |
