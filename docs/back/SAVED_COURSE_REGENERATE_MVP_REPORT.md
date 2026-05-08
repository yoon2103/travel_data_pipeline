# Saved Course Regenerate MVP Report

## 수정 파일

- `frontend/src/App.jsx`
- `frontend/src/utils/savedCourses.js`
- `frontend/src/screens/day-trip/CourseResultScreen.jsx`
- `frontend/src/screens/day-trip/MyScreen.jsx`

## 재생성 UX 흐름

### 다시 보기

저장 목록에서 저장 코스 카드를 탭하면 기존 localStorage snapshot을 read-only 상세 화면으로 다시 연다.

흐름:

```text
MyScreen
→ 저장 카드 탭
→ getSavedCourse(course_id)
→ SavedCourseDetail 표시
```

### 비슷한 코스 다시 만들기

저장 상세 화면에서 `비슷한 코스 다시 만들기`를 누르면 저장 snapshot의 조건을 꺼내 새 generate flow로 진입한다.

흐름:

```text
MyScreen
→ 저장 상세
→ 비슷한 코스 다시 만들기
→ getRegenerateParams(savedCourse)
→ App.handleRegenerateCourse(prefillParams)
→ ConditionScreen prefill
→ 사용자가 조건 확인 후 새 generate
```

중요:

- 저장된 결과를 서버에 다시 저장하지 않음
- 기존 추천 결과를 그대로 재사용해 API를 호출하지 않음
- 새 코스 생성은 기존 generate flow를 그대로 사용
- recommendation engine 수정 없음

## Prefill 구조

저장 시 snapshot에 `generation_params`를 추가했다.

포함 가능 필드:

- `region`
- `displayRegion`
- `departure_time`
- `region_travel_type`
- `start_lat`
- `start_lon`
- `start_anchor`
- `zone_id`
- `_homeAnchor`
- `mood`
- `walk`
- `density`

저장 위치:

```json
{
  "course_id": "...",
  "region": "서울",
  "summary": "...",
  "generation_params": {
    "region": "서울",
    "displayRegion": "서울",
    "departure_time": "10:00",
    "start_anchor": "서울역",
    "mood": "자연 선택",
    "walk": "보통",
    "density": "적당히"
  },
  "places": []
}
```

## Snapshot 확장 여부

확장함:

- `generation_params` 추가

하위 호환:

- 기존 saved snapshot에 `generation_params`가 없어도 `region`으로 fallback
- invalid shape은 load 단계에서 필터링
- region도 없으면 regenerate 불가로 처리

## 테스트 결과

### build

```bash
npm run build
```

결과:

- PASS

### localStorage utility test

Node mock localStorage로 검증:

```text
restore_saved_course PASS
prefill_full PASS
legacy_fallback PASS
invalid_snapshot PASS
deleted_access PASS
old_compat_filter PASS
```

검증 항목:

- 저장 코스 reopen: PASS
- 조건 prefill: PASS
- 새 generate 진입 준비: PASS
- invalid snapshot: PASS
- old snapshot compatibility: PASS
- 삭제 후 접근: PASS

### API 사용 금지 확인

검색 결과:

- `/api/course/{course_id}/save` 호출 없음
- backend 저장 사용 없음
- `generation_params`, `getRegenerateParams`, `비슷한 코스 다시 만들기` 사용 확인

## 추천 엔진 영향 없음 확인

변경 없음:

- `course_builder.py`
- `api_server.py`
- `database.py`
- `schema.sql`
- `migration_*.sql`

영향 없음:

- 추천 엔진 로직
- fallback
- place selection
- API request/response schema

## representative governance 영향 없음 확인

변경 없음:

- `tourism_belt.py`
- `batch/place_enrichment/*`
- representative workflow
- seed overlay workflow
- rollout gate/checker

## 위험 요소

- legacy snapshot은 region만 복원할 수 있어 출발지/옵션은 사용자가 다시 확인해야 한다.
- 저장 당시 option 이름이 바뀌면 prefill 값이 UI 옵션과 맞지 않을 수 있다.
- localStorage 기반이라 다른 기기에서는 재생성 조건을 가져올 수 없다.
- 상세 보기에서 코스 편집/교체/재계산은 아직 지원하지 않는다.

## 다음 작업 제안

1. production preview에서 저장 상세 → 비슷한 코스 다시 만들기 → 조건 화면 prefill 확인
2. legacy snapshot 안내 문구 추가 여부 검토
3. 저장 상세에서 “현재 조건으로 바로 생성” 버튼을 별도 UX로 검토
4. server-side 저장으로 확장 시 `generation_params`를 API contract에 포함
