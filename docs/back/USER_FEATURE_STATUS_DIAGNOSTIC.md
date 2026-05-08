# User Feature Status Diagnostic

## 사주 연결 현황

### 현재 구현 상태

현재 소스 기준으로 사주 연결 기능은 구현되어 있지 않다.

확인 결과:

- 프론트에서 `saju`, `사주`, `mbti`, `duckdns`, `window.open`, 외부 링크 관련 구현 없음
- `frontend/src/App.jsx`는 여행 코스 화면 흐름만 관리
  - `home`
  - `condition`
  - `result`
  - `my`
- `frontend/src/components/common/MobileShell.jsx` 하단 탭은 현재 `홈`, `저장`, `마이` 구조
- `.env.example`, `.env.staging.example`에 사주 서비스 URL 관련 env 없음
- Vite proxy는 `/api -> http://127.0.0.1:5000`만 설정

### 왜 현재 연결 안 되는지

- 사주 연결 버튼/링크가 없음
- 사주 서비스 URL 설정 위치가 없음
- env 기반 URL이 없음
- 모바일/PC 분기 로직 없음
- 현재 앱 라우팅은 여행 서비스 내부 화면 전환만 처리함

### 모바일/PC 동작 방식

현재는 사주 연결 동작이 없으므로 모바일/PC 모두 동일하게 미지원이다.

향후 안전한 방식:

- frontend only 버튼으로 시작
- URL은 env로 분리
- 외부 도메인은 새 탭 또는 현재 탭 이동 중 하나로 명확히 결정
- 운영 도메인과 사주 도메인을 혼동하지 않도록 이름을 명확히 둠

권장 env:

```text
VITE_SAJU_SERVICE_URL=https://saju-mbti-service.duckdns.org/
VITE_SHOW_SAJU_LINK=true
```

권장 위치:

- `frontend/src/screens/day-trip/MyScreen.jsx`
- 또는 `frontend/src/components/common/MobileShell.jsx`의 마이/연결 섹션

주의:

- `travel-planne.duckdns.org`와 `saju-mbti-service.duckdns.org`를 nginx/server 설정에서 혼동하지 않아야 함
- 사주 서비스와 여행 서비스는 API proxy를 공유하지 않는 편이 안전함

## 저장 기능 현황

### 프론트 상태

관련 파일:

- `frontend/src/screens/day-trip/CourseResultScreen.jsx`
- `frontend/src/screens/day-trip/MyScreen.jsx`
- `frontend/src/App.jsx`

현재 상태:

- `CourseResultScreen.jsx`에 `handleSave()` 함수는 존재
- `handleSave()`는 `POST /api/course/{course_id}/save` 호출
- 하지만 실제 화면 버튼은 `disabled` 처리되어 있고 텍스트가 `저장 준비중`
- 따라서 현재 사용자는 저장 API를 호출할 수 없음
- `MyScreen.jsx`는 `savedCourses`와 `recentCourses`를 `useState([])`로 빈 배열 고정
- 저장된 코스 조회 API 호출 없음
- localStorage 저장 없음
- sessionStorage/indexedDB 사용 없음

현재 버튼 상태:

```jsx
<button disabled>
  저장 준비중
</button>
```

### API 상태

관련 파일:

- `api_server.py`

현재 API:

```python
@app.post("/api/course/{course_id}/save")
def save_course(course_id: str):
    if course_id not in _courses:
        raise HTTPException(status_code=404, detail="Course not found")
    return {"saved": True, "course_id": course_id}
```

진단:

- API endpoint는 존재
- 하지만 DB 저장 없음
- user/session 연결 없음
- 저장 결과 조회 API 없음
- 서버 메모리 `_courses`에 course_id가 있어야만 성공
- 서버 재시작 시 `_courses`가 사라지므로 저장 API의 의미가 없음

### DB 상태

실제 DB read-only 확인 결과:

존재하는 course 관련 테이블:

- `course_master`
- `course_day`
- `course_item`
- `course_generation_logs`
- `course_extend_logs`

존재하지 않는 저장/사용자 테이블:

- `users`
- `user_saved_courses`
- `saved_course_place_snapshots`

참고:

- `schema.sql`에는 `travel_courses`, `course_places`, `users`, `user_saved_courses` 설계가 있음
- 하지만 실제 DB에는 해당 user/save 계열 테이블이 적용되어 있지 않음
- `migration_005_add_saved_course_place_snapshots.sql`은 존재하지만 실제 DB의 `saved_course_place_snapshots` 테이블은 없음

### snapshot 구조

파일 기준:

- `migration_005_add_saved_course_place_snapshots.sql` 존재

목적:

- 저장 코스 장소별 외부 API 보강 스냅샷
- places 마스터와 분리
- raw API 응답 저장 금지

실제 DB 상태:

- `saved_course_place_snapshots` 미적용

### 현재 disable 이유

추정:

- 저장 API는 스텁 수준
- 저장 조회/마이 화면 데이터 구조 없음
- 로그인/유저 식별 없음
- DB save schema가 운영 DB에 없음
- 그래서 운영 UI에서 저장 버튼을 비활성화한 상태로 보임

## 로그인 기능 현황

### 프론트 상태

확인 결과:

- 로그인 화면 없음
- auth provider/context 없음
- token 저장 로직 없음
- cookie/session 처리 없음
- 로그인/로그아웃 버튼 없음
- `MyScreen.jsx`는 정적 사용자 영역만 표시

### API 상태

확인 결과:

- `/api/login`
- `/api/logout`
- `/api/me`
- `/api/auth/*`
- session/JWT 관련 route 없음

### DB 상태

실제 DB 기준:

- `users` table 없음
- auth/session/token table 없음
- user_saved_courses 없음

`schema.sql`에는 users 설계가 있으나 실제 DB에는 미적용이다.

### 저장 기능과 연결 가능 여부

현재는 직접 연결 불가.

이유:

- 저장할 user_id가 없음
- 인증된 사용자 식별 방법 없음
- saved course 조회 API 없음
- course 저장 schema가 확정/적용되어 있지 않음

로그인 없이 가능한 최소 대안:

- 익명 device_id 기반 저장
- localStorage 기반 임시 저장
- server-side anonymous session 기반 저장

하지만 장기적으로는 user/auth 도입 후 저장과 연결하는 것이 안전하다.

## 필요 API/DB/프론트 작업

| 기능 | Frontend only | API 필요 | DB migration 필요 | Auth 필요 | 배포 영향 |
| --- | --- | --- | --- | --- | --- |
| 사주 연결 버튼 | 가능 | 불필요 | 불필요 | 불필요 | 낮음 |
| 저장 버튼 UI 복구 | 가능 | 기존 API는 스텁 | 실제 저장에는 필요 | 선택 | 중간 |
| localStorage 임시 저장 | 가능 | 불필요 | 불필요 | 불필요 | 낮음 |
| 서버 저장 | 필요 | 필요 | 필요 | 선택/권장 | 중간~높음 |
| 저장 코스 조회 | 필요 | 필요 | 필요 | 선택/권장 | 중간 |
| 최소 로그인 | 필요 | 필요 | 필요 | 필요 | 높음 |
| 로그인 기반 저장 | 필요 | 필요 | 필요 | 필요 | 높음 |

## production 영향 파일

사주 연결:

- `frontend/src/screens/day-trip/MyScreen.jsx`
- `frontend/src/components/common/MobileShell.jsx`
- `frontend/.env.production` 또는 배포 env
- `frontend/src/App.jsx`는 필요 시만

저장 기능:

- `frontend/src/screens/day-trip/CourseResultScreen.jsx`
- `frontend/src/screens/day-trip/MyScreen.jsx`
- `frontend/src/App.jsx`
- `api_server.py`
- 신규 migration 또는 기존 `course_master/course_day/course_item` 활용 설계
- `migration_005_add_saved_course_place_snapshots.sql` 적용 여부 검토

로그인 기능:

- `api_server.py` 또는 별도 auth router
- 신규 auth service/module
- frontend auth state/context
- users/session 관련 migration
- nginx/CORS/cookie 설정 가능성

## 권장 구현 순서

### 1. 사주 연결

난이도:

- frontend only
- DB/API 불필요
- 가장 안전

권장:

- `VITE_SAJU_SERVICE_URL` env 추가
- `MyScreen` 또는 홈/마이 영역에 연결 버튼 추가
- 외부 링크는 명확히 새 탭 또는 현재 탭 이동으로 결정

### 2. 저장 기능 최소 복구

두 가지 선택지:

1. localStorage 임시 저장
   - 빠름
   - 로그인 불필요
   - 기기 변경 시 유지 안 됨

2. 서버 저장
   - API/DB 필요
   - 운영 품질 좋음
   - auth 또는 anonymous id 정책 필요

권장:

- 먼저 localStorage 기반 “이 기기에 저장” MVP
- 이후 서버 저장으로 확장

### 3. 최소 로그인

권장:

- 저장 기능을 서버화하기 전 auth 정책 결정
- OAuth를 바로 붙이기보다 최소 email/pass 또는 magic link 여부 검토
- session cookie 기반이 모바일 브라우저에 비교적 자연스러움

### 4. 로그인 기반 저장 연결

권장:

- users table
- saved course table
- course item snapshot
- `/api/me`
- `/api/courses/saved`
- `/api/course/{course_id}/save`

## 위험 요소

### 사주 연결

- 잘못된 duckdns 도메인 연결 위험
- nginx/server block 혼동 위험
- 외부 서비스 장애가 여행 서비스 장애처럼 보일 수 있음

완화:

- env 분리
- 링크만 제공
- proxy 연결 금지

### 저장 기능

- 현재 `_courses`는 메모리 기반이라 서버 재시작 시 사라짐
- 현재 save API는 실제 저장이 아님
- 저장 버튼을 단순 활성화하면 사용자가 저장됐다고 오해할 수 있음
- DB schema가 실제 운영 DB에 준비되어 있지 않음

완화:

- localStorage MVP 또는 DB migration 후 활성화
- 저장 성공/실패 메시지 명확화
- MyScreen 조회 기능과 함께 구현

### 로그인 기능

- auth는 보안 영향이 큼
- cookie/CORS/HTTPS 설정 필요
- user data migration 필요
- 저장 기능과 결합하면 롤백이 어려움

완화:

- 로그인은 저장 MVP 이후 별도 단계
- auth router 분리
- 최소 scope로 시작

## 다음 작업 제안

1. 사주 연결 버튼 frontend-only 구현
2. 저장 기능을 localStorage MVP로 할지 server DB 저장으로 할지 결정
3. 저장 기능 server형을 선택한다면 course 저장 schema 확정
4. 로그인은 마지막 단계로 분리
5. 저장/로그인 구현 전 API contract 문서 작성
