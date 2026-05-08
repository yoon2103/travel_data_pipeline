# LocalStorage Save MVP Report

## 수정 파일

- `frontend/src/utils/savedCourses.js`
- `frontend/src/screens/day-trip/CourseResultScreen.jsx`
- `frontend/src/screens/day-trip/MyScreen.jsx`

## localStorage 구조

Storage key:

```text
saved_courses_v1
```

저장 데이터:

```json
{
  "course_id": "course-id",
  "region": "서울",
  "created_at": "2026-05-08T00:00:00.000Z",
  "updated_at": "2026-05-08T00:00:00.000Z",
  "summary": "코스 설명 또는 상위 장소 요약",
  "place_count": 5,
  "total_duration_min": 360,
  "total_travel_min": 42,
  "option_notice": null,
  "missing_slot_reason": null,
  "places": [
    {
      "order": 1,
      "place_id": 123,
      "name": "장소명",
      "role": "spot",
      "description": "설명",
      "image": "https://...",
      "time": "10:00",
      "duration": "1시간",
      "lat": 37.0,
      "lon": 127.0
    }
  ]
}
```

정책:

- 같은 `course_id`는 overwrite
- 최신 저장 코스가 목록 상단
- 최대 저장 개수: `30`
- 초과 시 오래된 항목 제거
- JSON parse error 시 빈 목록으로 안전 복구
- localStorage unavailable 시 UI에서 안내

## 저장 흐름

`CourseResultScreen.jsx`:

1. `이 코스 저장하기` 버튼 클릭
2. `saveCourseToLocalStorage()` 호출
3. 성공 시 alert 표시
4. `onSave()` 호출로 마이 화면 이동

중요:

- backend save API 호출하지 않음
- DB 저장 없음
- auth/session 없음

## MyScreen 표시 구조

`MyScreen.jsx`:

- mount 시 `loadSavedCourses()` 호출
- 저장된 코스 리스트 표시
- 표시 항목:
  - 지역
  - summary
  - 저장/업데이트 시간
  - 장소 수
  - 첫 장소 이미지가 있으면 썸네일
- 삭제 버튼 제공
- 삭제 시 `deleteSavedCourse()` 호출 후 목록 갱신

## 테스트 결과

### production build

```bash
npm run build
```

결과:

- PASS

### localStorage utility test

Node mock localStorage로 검증:

- initial empty load: PASS
- 저장: PASS
- 새로고침 후 유지에 해당하는 reload: PASS
- 중복 저장 overwrite: PASS
- 30개 초과 제한: PASS
- 삭제: PASS
- JSON parse error fallback: PASS
- localStorage disabled fallback: PASS

실행 결과:

```text
initial PASS
save PASS
persist PASS
duplicate_overwrite PASS
max_30 PASS
delete PASS
parse_error PASS
storage_unavailable PASS
```

### API 사용 금지 확인

검색 결과:

- 프론트 저장 흐름에서 `/api/course/{course_id}/save` 호출 제거 확인
- `saved_courses_v1` 사용 확인

## backend/DB 영향 없음 확인

변경 없음:

- `api_server.py`
- `database.py`
- `schema.sql`
- `migration_*.sql`
- DB migration 없음
- backend 저장 사용 없음
- auth 구현 없음

## representative governance 영향 없음 확인

변경 없음:

- `course_builder.py`
- `tourism_belt.py`
- `batch/place_enrichment/*`
- representative workflow
- seed overlay workflow
- recommendation engine

## 위험 요소

- localStorage는 같은 브라우저/기기에서만 유지됨
- 브라우저 저장소 삭제 시 저장 목록도 사라짐
- 로그인 기반 동기화는 아직 없음
- private mode 또는 storage disabled 환경에서는 저장 불가
- 서버 저장이 아니므로 다른 기기에서 조회 불가

## 다음 작업 제안

1. production preview에서 실제 모바일 저장/삭제 동작 확인
2. 저장 목록 카드 클릭 시 상세 보기 또는 코스 복원 기능 설계
3. server-side 저장으로 확장할 경우 course snapshot schema 확정
4. 로그인 기반 저장은 별도 단계로 분리
