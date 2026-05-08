# Frontend ↔ Backend Full Function Test Report

## 테스트 환경

- 테스트 일시: 2026-05-08
- Frontend dev: `http://127.0.0.1:5175`
- Frontend production preview: `http://127.0.0.1:4175`
- Backend API: `http://127.0.0.1:5000`
- Vite proxy target: `http://127.0.0.1:5000`
- DB: `localhost:5432/travel_db`, user `postgres`
- 브라우저 확인:
  - Codex in-app browser backend: 사용 불가, backend discovery 실패
  - Chrome headless/CDP: 사용
- 생성된 확인 파일:
  - `qa_reports/frontend_dom_mobile.html`
  - `qa_reports/frontend_home_mobile.png`

주의:

- `/api/course/generate`는 현재 `course_generation_logs`에 운영 로그를 남기는 side effect가 있다.
- 직접 SQL insert/update, migration, places write는 수행하지 않았다.
- 사용자 플로우 검증을 위해 실제 API 호출은 수행했으며, 이로 인한 운영 로그성 write 가능성은 리포트에 명시한다.

## 최종 판정

현재 판정: `QA_REQUIRED`

이유:

- 핵심 코스 생성, 지역/출발지 로드, 후보 조회, 교체, 재계산, localStorage 저장 유틸은 통과했다.
- production preview에서 홈 → 조건 → 결과 화면 실제 클릭 플로우가 통과했다.
- production preview에서 `/api/course/generate` 호출은 1회로 확인됐다.
- 그러나 `npm run lint`가 실패한다.
- Android Chrome/iOS Safari 실기기 검증은 아직 수행하지 못했다.
- CourseEditScreen은 코드상 존재하지만 현재 App 라우팅에서 직접 사용되지 않는다.

## 화면별 기능 결과

| 화면/컴포넌트 | 확인 결과 | 상태 |
| --- | --- | --- |
| `HomeScreen` | `/api/regions`, `/api/region/{region}/departures` 호출 확인. Chrome headless에서 홈 화면 DOM 렌더링 확인 | `PASS` |
| `ConditionScreen` | 조건 선택 화면 진입 및 `이 조건으로 코스 만들기` 버튼 클릭 확인 | `PASS` |
| `CourseResultScreen` | `/api/course/generate` 호출, 결과 카드/총시간/이동시간/저장/편집 CTA 표시 확인 | `PASS` |
| `CourseEditScreen` | 파일은 존재하나 현재 `App.jsx`에서 import/route 연결 없음 | `QA_REQUIRED` |
| `MyScreen` | 저장 목록, 저장 상세, 삭제, regenerate, 사주 버튼 로직 코드/유틸 기준 확인 | `PASS_WITH_LIMITATION` |
| `MobileShell` | 하단 탭 `홈/저장/마이`, production에서 mock status bar 미노출 로직 확인 | `PASS` |
| 하단 탭 | production preview DOM에서 `홈/저장/마이` 표시 확인 | `PASS` |
| 사주 연결 버튼 | env flag/URL 기반 노출. 현재 로컬 env 없음에서는 숨김 | `PASS_WITH_LIMITATION` |
| 저장 목록 | localStorage utility test 통과 | `PASS` |
| 저장 상세 | localStorage snapshot restore utility 통과, UI 코드는 확인 | `PASS_WITH_LIMITATION` |
| 비슷한 코스 다시 만들기 | 저장 snapshot에서 `generation_params` 복원 확인 | `PASS` |

## API별 결과

| API | 정상 결과 | 오류/edge 결과 | 상태 |
| --- | --- | --- | --- |
| `GET /api/regions` | 200, 17개 region 반환 | proxy 경유 `5175/api/regions`도 17개 반환 | `PASS` |
| `GET /api/region/{region}/departures` | 서울 8, 부산 6, 강원 6, 제주 7, 전북 4, 전남 4, 경북 5 | `not-a-region`도 200 empty 계열로 동작 | `PASS_WITH_NOTE` |
| `GET /api/region/{region}/zones` | 서울 8, 부산 8, 강원 8, 제주 8, 전북 8, 전남 9, 경북 9 | `not-a-region`도 200 empty 계열로 동작 | `PASS_WITH_NOTE` |
| `POST /api/course/generate` | 서울 기본 5곳 생성, 이동 68분 | 빈 payload 422, departure 누락 400 | `PASS` |
| `GET /api/course/{course_id}/candidates` | 교체 후보 10개, 추가 후보 1개 | 잘못된 course_id 404 | `PASS` |
| `PATCH /api/course/{course_id}/replace` | 후보 `피어커피`로 교체 성공, 5곳 유지 | 잘못된 course_id 404 | `PASS` |
| `POST /api/course/{course_id}/recalculate` | 교체 후 재계산 200, 5곳, 이동 95분 | 잘못된 course_id 404 | `PASS` |
| `POST /api/course/{course_id}/save` | backend stub 200 `{ saved: true }` | 잘못된 course_id 404 | `PASS_WITH_NOTE` |

API 단독 edge note:

- 잘못된 region의 departures/zones는 404가 아니라 200 empty 계열로 응답한다. 서버 crash는 없으나, 엄격한 error status를 기대한다면 QA 기준 조정 또는 API 정책 결정이 필요하다.
- 잘못된 region으로 generate 시 HTTP 200 + body error 형식으로 반환된다.

## Frontend-Backend 연결 매핑

| 사용자 액션 | Frontend 위치 | 호출 API | 확인 결과 |
| --- | --- | --- | --- |
| 지역 로드 | `HomeScreen.jsx` | `GET /api/regions` | dev/proxy/preview 모두 확인 |
| 출발지 로드 | `HomeScreen.jsx` | `GET /api/region/{region}/departures` | production preview 클릭 플로우에서 확인 |
| 권역 로드 | 현재 UI 직접 호출 없음 | `GET /api/region/{region}/zones` | backend 단독 확인 |
| 조건 선택 | `ConditionScreen.jsx` | API 없음 | local state만 변경 |
| 코스 생성 | `CourseResultScreen.jsx` | `POST /api/course/generate` | production preview에서 1회 호출 확인 |
| 장소 교체 후보 조회 | `CourseResultScreen.jsx` | `GET /api/course/{course_id}/candidates?place_id=&role=` | backend 단독 확인 |
| 장소 추가 후보 조회 | `CourseResultScreen.jsx` | `GET /api/course/{course_id}/candidates?role=spot&insert_after_place_id=` | backend 단독 확인 |
| 장소 교체 | `CourseResultScreen.jsx` | `PATCH /api/course/{course_id}/replace` | backend 단독 확인 |
| 재계산 | `CourseResultScreen.jsx` | `POST /api/course/{course_id}/recalculate` | backend 단독 확인 |
| 결과 저장 버튼 | `CourseResultScreen.jsx` | backend save API 호출 없음, `localStorage` 사용 | source + utility test 확인 |
| 저장 목록/복원 | `MyScreen.jsx`, `savedCourses.js` | API 없음 | localStorage utility 확인 |
| 저장 기반 regenerate | `MyScreen.jsx`, `App.jsx` | 저장 단계 API 없음, 새 추천 진입 후 generate 호출 | utility + source 확인 |
| 사주 링크 | `MyScreen.jsx` | API/proxy 없음, 외부 링크 | source 확인 |

## 사용자 플로우 결과

### A. 기본 코스 생성

Chrome headless production preview에서 다음 플로우를 실제 클릭으로 확인했다.

1. 홈 진입
2. 출발 시간 선택: `내일 10:00`
3. 출발 기준점 선택: `이태원/한남 주변`
4. `코스 만들기`
5. 조건 화면 진입
6. `이 조건으로 코스 만들기`
7. 결과 화면 표시

결과:

- `/api/regions`: 1회
- `/api/region/서울/departures`: 1회
- `/api/course/generate`: 1회
- 결과 장소 수: 5곳
- 총 시간/이동시간 표시 확인
- 하단 CTA 표시 확인
- dev server에서는 React StrictMode 때문에 `/api/regions`, `/api/course/generate`가 중복 호출될 수 있음
- production preview에서는 generate 1회 확인

### B. 옵션별 생성

서울 / 이태원·한남 기준 API 생성 결과:

| 옵션 | themes | 상태 | 장소 수 | 이동시간 | 안내 |
| --- | --- | --- | ---: | ---: | --- |
| 기본 | `[]` | `PASS` | 5 | 60분 | 없음 |
| 카페투어 | `['cafe']` | `PASS` | 5 | 67분 | 없음 |
| 맛집 | `['food']` | `PASS` | 5 | 74분 | `missing_slot_reason` 있음 |
| 자연 | `['nature']` | `PASS` | 5 | 69분 | 없음 |
| 문화/실내 | `['history']` | `PASS` | 5 | 60분 | 없음 |

### C. 지역별 생성

| 사용자 지역 | DB region | 출발 기준점 | 상태 | place_count | region_status | 안내 |
| --- | --- | --- | --- | ---: | --- | --- |
| 서울 | 서울 | 이태원/한남 주변 | `PASS` | 5 | FULL | 없음 |
| 부산 | 부산 | 서면 주변 | `PASS` | 5 | FULL | 없음 |
| 강릉/강원 | 강원 | 경포해변 주변 | `PASS` | 5 | FULL | 없음 |
| 제주 | 제주 | 제주공항 주변 | `PASS` | 5 | FULL | 없음 |
| 전주 | 전북 | 남부시장 주변 | `PASS` | 5 | FULL | 없음 |
| 여수 | 전남 | 여수 주변 | `PASS` | 5 | LIMITED | `option_notice` 있음 |
| 경주 | 경북 | 황리단길/대릉원 주변 | `PASS` | 5 | FULL | 없음 |

## 결과 화면 기능 결과

| 기능 | 확인 결과 | 상태 |
| --- | --- | --- |
| 장소 카드 표시 | production preview 결과 DOM에 5개 장소 표시 | `PASS` |
| 이미지 fallback | source상 image 없을 때 role별 fallback emoji 표시 | `PASS_WITH_SOURCE_CHECK` |
| 긴 설명 더보기/접기 | accordion 구조, `overflow-visible`, 긴 설명 `break-words` 확인 | `PASS_WITH_SOURCE_CHECK` |
| 마지막 카드 스크롤 | 하단 padding `resultListBottomPadding` 확인. 실기기 검증 필요 | `QA_REQUIRED` |
| 하단 CTA 겹침 | production preview 390x844 렌더링 가능. Android/iOS 실기기 필요 | `QA_REQUIRED` |
| 장소 교체 | 후보 조회 + replace API 단독 성공 | `PASS` |
| 후보 조회 | 교체 후보 10개, 추가 후보 1개 확인 | `PASS` |
| 재계산 | replace 후 recalculate 성공 | `PASS` |
| option_notice 표시 | 전남 LIMITED 생성에서 option_notice 확인 | `PASS` |
| missing_slot_reason 표시 | 서울 맛집 생성에서 missing_slot_reason 확인 | `PASS` |

## 저장 기능 결과

localStorage utility test:

| 항목 | 결과 |
| --- | --- |
| empty state data | `PASS` |
| 저장 | `PASS` |
| 중복 저장 overwrite | `PASS` |
| restore | `PASS` |
| regenerate params | `PASS` |
| 삭제 | `PASS` |
| invalid snapshot filter | `PASS` |
| 30개 제한 | `PASS` |
| storage unavailable | `PASS` |

저장 구현 확인:

- `CourseResultScreen.jsx`의 저장 버튼은 `saveCourseToLocalStorage()`를 호출한다.
- `/api/course/{course_id}/save`는 현재 frontend 저장 버튼에서 호출하지 않는다.
- backend save API는 stub으로 존재하지만 MVP 저장 흐름에는 사용되지 않는다.

제약:

- Chrome CDP에서 저장 버튼 클릭 후 alert 처리까지의 end-to-end 저장 UI 자동화는 timeout으로 완료하지 못했다.
- utility/source 기준으로는 backend save 미사용과 localStorage 저장 구조를 확인했다.

## 사주 연결 결과

| 항목 | 결과 | 상태 |
| --- | --- | --- |
| env OFF | `.env` 없음 또는 `VITE_SHOW_SAJU_LINK` false이면 버튼 숨김 | `PASS_WITH_SOURCE_CHECK` |
| env ON | `VITE_SHOW_SAJU_LINK=true` + URL 정상일 때 버튼 노출 | `PASS_WITH_SOURCE_CHECK` |
| URL 누락 | `sajuServiceUrl` 없으면 버튼 숨김 | `PASS_WITH_SOURCE_CHECK` |
| 잘못된 URL | `isSafeExternalUrl()` 실패 시 버튼 숨김 | `PASS_WITH_SOURCE_CHECK` |
| 새 탭 | `target="_blank"`, `rel="noopener noreferrer"` 확인 | `PASS_WITH_SOURCE_CHECK` |
| proxy/backend 호출 없음 | `href` 기반 외부 링크, fetch 없음 | `PASS` |

현재 로컬 frontend에는 `.env` 파일이 없어 사주 버튼은 기본 미노출 상태다.

## 모바일 UI 결과

| 항목 | 결과 | 상태 |
| --- | --- | --- |
| Home safe-area | `100dvh`, `env(safe-area-inset-top/bottom)` 사용 확인 | `PASS_WITH_HEADLESS` |
| 하단 CTA | Home/Condition/Result/MyScreen에서 safe-area 보정 확인 | `PASS_WITH_SOURCE_CHECK` |
| 결과 화면 스크롤 | padding bottom 계산 존재 | `QA_REQUIRED` |
| 저장 상세 스크롤 | `overflow-y-auto`, safe-area bottom padding 확인 | `PASS_WITH_SOURCE_CHECK` |
| MyScreen 스크롤 | saved list와 fixed card 구조 확인, 긴 목록 실기기 필요 | `QA_REQUIRED` |
| 하단 탭 겹침 | `MobileShell` sticky bottom + safe-area 확인 | `PASS_WITH_SOURCE_CHECK` |
| mock status bar | production preview에서 `5화면 검토` 미노출, `9:41` frame 미노출 | `PASS` |
| Android Chrome 실기기 | 미수행 | `QA_REQUIRED` |
| iOS Safari 실기기 | 미수행 | `QA_REQUIRED` |

## Backend 단독 테스트 결과

정상 요청:

- `/api/regions`: 200
- `/api/region/서울/departures`: 200
- `/api/region/서울/zones`: 200
- `/api/course/generate`: 200 + 5 places
- `/api/course/{course_id}/candidates`: 200
- `/api/course/{course_id}/replace`: 200
- `/api/course/{course_id}/recalculate`: 200
- `/api/course/{course_id}/save`: 200 stub

오류 요청:

| 케이스 | 결과 |
| --- | --- |
| 빈 generate payload | 422 |
| departure_time 누락 | 400 |
| 잘못된 course_id 후보 조회 | 404 |
| 잘못된 course_id replace | 404 |
| 잘못된 course_id recalculate | 404 |
| 잘못된 course_id save | 404 |
| 잘못된 region departures/zones | 200 empty 계열 |
| 잘못된 region generate | 200 + body error |

서버 crash는 확인되지 않았다.

## 데이터/엔진 안전성 확인

| 항목 | 결과 | 상태 |
| --- | --- | --- |
| `course_builder.py` actual path 변경 없음 | `git diff --name-only` 기준 diff 없음 | `PASS` |
| `tourism_belt.py` 변경 없음 | diff 없음 | `PASS` |
| `api_server.py` 변경 없음 | diff 없음 | `PASS` |
| migration 변경 없음 | diff 없음 | `PASS` |
| representative overlay actual 미적용 | frontend/API request path에서 batch 호출 없음 | `PASS` |
| `batch/place_enrichment` 추천 요청 중 호출 없음 | api_server import path에 없음 | `PASS` |
| 사용자 요청 중 Kakao/Naver 호출 없음 | Kakao/Naver는 batch adapter에만 존재, frontend/API runtime path에 없음 | `PASS` |
| localStorage 저장이 backend save API 호출하지 않음 | source 확인 | `PASS` |
| places row count | 테스트 후 `26371` | `PASS` |

주의:

- `/api/course/generate` 호출로 `course_generation_logs` 기록은 발생할 수 있다.
- 직접 places insert/update는 수행하지 않았고, places count는 테스트 후 `26371`로 확인했다.

## 빌드/정적 검사

| 검사 | 결과 | 상태 |
| --- | --- | --- |
| `npm run build` | 성공 | `PASS` |
| `npm run lint` | 실패 | `FAIL` |
| Python `py_compile` 주요 파일 | `api_server.py`, `course_builder.py`, `database.py`, `db_client.py`, `tourism_belt.py`, `regional_zone_builder.py`, `run_course_qa_report.py` 모두 PASS | `PASS` |
| Frontend proxy | `5175/api/regions` 17개 반환 | `PASS` |
| Production preview proxy | `4175/api/regions` 17개 반환 | `PASS` |

Lint 실패 상세:

- 파일: `frontend/src/screens/day-trip/MyScreen.jsx`
- 위치: line 40
- rule: `react-hooks/set-state-in-effect`
- 내용: `useEffect` 안에서 `setSavedCourses`, `setStorageError`를 동기 호출
- 이번 작업은 코드 수정 금지이므로 수정하지 않았다.

## 실패/의심 항목

| 항목 | 분류 | 설명 |
| --- | --- | --- |
| `npm run lint` 실패 | 정적 검사 실패 | CI/deploy gate에서 lint를 강제하면 production blocker |
| 실기기 Android/iOS 미검증 | QA_REQUIRED | Chrome headless는 통과했지만 실제 safe-area/browser UI 검증 필요 |
| `CourseEditScreen` 미연결 | 의심/미사용 | 파일은 있으나 현재 `App.jsx` route에 직접 연결되어 있지 않음. 결과 화면 내부 edit mode가 실제 편집 역할 수행 |
| 잘못된 region API status | API 정책 의심 | departures/zones/generate가 일부 invalid region에 200으로 응답 |
| dev 중복 API 호출 | dev only | React StrictMode로 dev server에서 generate 중복 호출 가능. production preview는 1회 |
| 저장 UI alert 자동화 timeout | 테스트 제약 | utility/source 기준 PASS, 브라우저 click 저장 E2E는 추가 수동 QA 필요 |

## Production Blocker

현재 확정 blocker:

- `npm run lint` 실패

조건부 blocker:

- 배포 파이프라인이 lint를 강제하지 않으면 즉시 기능 blocker는 아니지만, production 전 수정 권장
- Android Chrome/iOS Safari에서 하단 CTA 또는 스크롤 문제가 재현되면 blocker
- 저장 버튼 실제 클릭에서 localStorage 저장 실패가 재현되면 blocker
- invalid region 200 응답을 서비스 정책상 실패로 본다면 API 정책 정리 필요

현재 핵심 생성/화면 진입 실패는 없음.

## 수정 필요 우선순위

1. `MyScreen.jsx` lint 실패 해결
2. Android Chrome 실기기에서 결과 화면/저장 상세 하단 CTA 겹침 확인
3. iOS Safari에서 safe-area, localStorage, 외부 링크 확인
4. 저장 버튼 실제 클릭 E2E 수동 QA
5. invalid region API 응답 정책 결정
6. `CourseEditScreen`을 유지할지, 결과 화면 내부 edit mode로 통합됐다고 문서화할지 결정

## 다음 작업 제안

1. 코드 수정 허용 범위에서 `MyScreen.jsx` lint 오류를 최소 수정한다.
2. staging URL에서 Android Chrome/iOS Safari smoke test runbook을 수행한다.
3. 저장 버튼 클릭 → alert → MyScreen 저장 상세 → regenerate까지 실기기에서 수동 확인한다.
4. production deploy gate에 lint가 포함되는지 확인한다.
5. invalid region의 200 body error/empty 응답이 의도인지 API 정책 문서에 반영한다.
