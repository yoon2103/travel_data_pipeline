# Saved Course Restore MVP Report

## 수정 파일

- `frontend/src/utils/savedCourses.js`
- `frontend/src/screens/day-trip/MyScreen.jsx`

참고:

- `frontend/src/screens/day-trip/CourseResultScreen.jsx`는 이전 localStorage 저장 MVP에서 저장 호출을 이미 연결한 파일이며, 이번 검증 범위에 함께 포함했다.

## 복원 흐름

1. 사용자가 `MyScreen`의 저장 코스 카드를 클릭한다.
2. `getSavedCourse(course_id)`가 `saved_courses_v1`에서 해당 코스를 조회한다.
3. 유효한 코스가 있으면 `SavedCourseDetail` read-only 상세 화면을 표시한다.
4. 상세 화면에서 `목록` 버튼으로 저장 목록으로 돌아간다.
5. 상세 화면 또는 목록 카드에서 `삭제`를 누르면 localStorage에서 제거하고 UI를 갱신한다.

중요:

- backend 호출 없음
- `/api/course/{course_id}/save` 사용 없음
- course regenerate 없음
- saved snapshot 그대로 표시

## 상세 보기 구조

상세 화면 포함 항목:

- region
- 저장/업데이트 시간
- summary
- place_count
- total_travel_min
- total_duration_min
- option_notice 또는 missing_slot_reason
- places 목록
  - 순서
  - 이름
  - role
  - 시간
  - duration
  - image
  - description

구현 위치:

- `frontend/src/screens/day-trip/MyScreen.jsx`
- 내부 컴포넌트: `SavedCourseDetail`

## localStorage 로딩 방식

Storage key:

```text
saved_courses_v1
```

추가/강화 함수:

- `getSavedCourse(courseId)`
- `loadSavedCourses()`
- `deleteSavedCourse(courseId)`

invalid data fallback:

- JSON parse error는 빈 목록으로 복구
- shape이 깨진 항목은 `safeParse()` 단계에서 필터링
- course_id, region, places가 없는 항목은 목록에서 제외
- 삭제 후 선택된 상세 course가 삭제 대상이면 상세 화면을 닫음

## 테스트 결과

### build

```bash
npm run build
```

결과:

- PASS

### localStorage restore utility test

Node mock localStorage로 검증:

```text
save_for_restore PASS
restore PASS
persist_after_reload PASS
deleted_access PASS
invalid_filtered PASS
empty_list PASS
```

검증 항목:

- 저장 후 복원: PASS
- 새로고침 후 복원에 해당하는 reload: PASS
- 삭제 후 접근: PASS
- invalid storage data 필터링: PASS
- 빈 목록: PASS

### API 사용 금지 확인

검색 결과:

- 프론트 저장/복원 흐름에서 `/api/course/{course_id}/save` 호출 없음
- `saved_courses_v1`, `getSavedCourse`, `SavedCourseDetail` 사용 확인

## backend 영향 없음 확인

변경 없음:

- `api_server.py`
- `database.py`
- `schema.sql`
- `migration_*.sql`

수행하지 않음:

- backend 저장
- DB migration
- auth/session
- API 추가
- 배포

## representative governance 영향 없음 확인

변경 없음:

- `course_builder.py`
- `tourism_belt.py`
- `batch/place_enrichment/*`
- representative governance workflow
- seed overlay workflow
- recommendation engine

## 위험 요소

- 저장 상세는 localStorage snapshot 기반이라 서버 최신 데이터와 동기화되지 않는다.
- localStorage가 삭제되면 복원 불가하다.
- 저장 상세에서 코스 재계산/교체/추가는 지원하지 않는다.
- 여러 기기 간 동기화는 로그인/server 저장 전까지 불가하다.

## 다음 작업 제안

1. production preview에서 모바일 저장 카드 클릭/상세/삭제 확인
2. 상세 화면에서 “이 코스로 다시 보기” 또는 “새 코스로 재생성” UX를 별도 설계
3. server-side 저장으로 확장할 경우 snapshot schema와 API contract 확정
