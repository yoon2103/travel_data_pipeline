# Production Readiness QA Checklist

## 목적

운영 배포 전 실제 사용자 흐름 기준으로 여행 서비스의 모바일 UX, 저장 기능, 사주 연결, representative/seed governance 안전성, 배포 환경을 최종 점검한다.

이번 체크리스트는 문서/QA 기준이며 코드, DB, migration, 배포 작업을 포함하지 않는다.

## Release Readiness 상태 모델

| 상태 | 의미 | 운영 판단 |
| --- | --- | --- |
| `BLOCKED` | 사용자 핵심 흐름이 실패하거나 운영 데이터/엔진 안전성이 확인되지 않음 | 배포 금지 |
| `QA_REQUIRED` | 기능 구현은 완료됐지만 실기기/운영 빌드 검증이 부족함 | staging 또는 수동 QA 필요 |
| `READY_FOR_STAGING` | 로컬/빌드 검증은 통과했고 staging 실기기 검증 대기 | staging 배포 가능 |
| `READY_FOR_PRODUCTION` | staging, 실기기, fallback, 배포 환경 QA 통과 | production 배포 가능 |

## 현재 Readiness 판정

현재 상태: `READY_FOR_STAGING`

판정 근거:

- 사주 연결 MVP가 frontend-only로 구현됨.
- localStorage 저장/복원/재생성 UX가 구현되고 production build가 통과됨.
- 저장 유틸의 저장, 복원, 삭제, invalid storage, storage unavailable 기본 검증이 통과됨.
- representative/seed governance는 실제 overlay/promote 없이 fail-closed 구조를 유지함.
- backend/API/DB/recommendation engine 변경은 없음.

production 전 남은 필수 조건:

- Android Chrome 실기기 QA
- iOS Safari 실기기 QA
- production env ON/OFF 조합 확인
- 배포 도메인에서 사주 링크, 저장 상세, 다시 만들기 흐름 확인

## 1. 모바일 UX QA

| 항목 | 기대 결과 | 상태 |
| --- | --- | --- |
| 홈 화면 safe-area | 상단 status bar와 콘텐츠가 겹치지 않음 | `QA_REQUIRED` |
| 하단 CTA | Android Chrome에서 하단 CTA가 브라우저 UI/탭바에 가려지지 않음 | `QA_REQUIRED` |
| 결과 화면 스크롤 | 마지막 장소 카드와 CTA가 겹치지 않음 | `QA_REQUIRED` |
| 저장 상세 스크롤 | 저장 상세의 마지막 장소까지 자연스럽게 스크롤됨 | `QA_REQUIRED` |
| MyScreen 스크롤 | 저장 목록이 길어져도 하단 추천 카드/네비게이션과 겹치지 않음 | `QA_REQUIRED` |
| regenerate flow | 저장 상세에서 `비슷한 코스 다시 만들기` 클릭 시 조건 화면으로 자연스럽게 이동 | `QA_REQUIRED` |
| 사주 링크 | MyScreen에서 버튼 노출 시 외부 사주 서비스로 이동 | `QA_REQUIRED` |
| empty state | 저장 코스가 없을 때 사용자용 안내와 CTA가 보임 | `READY_FOR_STAGING` |
| 삭제 후 UX | 삭제 confirm 후 목록 갱신과 삭제 메시지 표시 | `READY_FOR_STAGING` |

## 2. 저장 기능 QA

| 항목 | 테스트 방법 | 기대 결과 | 상태 |
| --- | --- | --- | --- |
| 저장 | 코스 결과 화면에서 `이 코스 저장하기` 클릭 | localStorage `saved_courses_v1`에 snapshot 저장 | `READY_FOR_STAGING` |
| overwrite | 같은 `course_id`를 다시 저장 | 중복 카드가 생기지 않고 최신 snapshot으로 갱신 | `READY_FOR_STAGING` |
| 최대 30개 | 31개 이상 저장 시도 | 최근 30개만 유지 | `READY_FOR_STAGING` |
| 저장 목록 | MyScreen 진입 | 지역, 요약, 저장 시간, 장소 수, 이동시간 표시 | `READY_FOR_STAGING` |
| restore | 저장 카드 클릭 | 저장 상세 화면 표시 | `READY_FOR_STAGING` |
| regenerate | 저장 상세에서 다시 만들기 클릭 | 저장된 region/조건 기반으로 새 추천 흐름 진입 | `QA_REQUIRED` |
| 삭제 | 카드/상세에서 삭제 | confirm 후 삭제, UI 갱신 | `READY_FOR_STAGING` |
| invalid snapshot | 손상된 저장 데이터 주입 | 앱 crash 없이 안내 또는 필터링 | `READY_FOR_STAGING` |
| storage unavailable | localStorage 비활성/차단 | 앱 crash 없이 안내 표시 | `READY_FOR_STAGING` |
| 새로고침 유지 | 저장 후 브라우저 새로고침 | 저장 목록 유지 | `QA_REQUIRED` |

## 3. 사주 연결 QA

| 항목 | 테스트 방법 | 기대 결과 | 상태 |
| --- | --- | --- | --- |
| env OFF | `VITE_SHOW_SAJU_LINK=false` | 버튼 미노출 | `READY_FOR_STAGING` |
| env ON | `VITE_SHOW_SAJU_LINK=true`, URL 정상 | 버튼 노출 | `READY_FOR_STAGING` |
| URL 누락 | URL env 없음 | 버튼 미노출 | `READY_FOR_STAGING` |
| 잘못된 URL | URL parse 불가 | 버튼 미노출 | `READY_FOR_STAGING` |
| 외부 이동 | 버튼 클릭 | `https://saju-mbti-service.duckdns.org/` 새 탭 이동 | `QA_REQUIRED` |
| 모바일 브라우저 | Android/iOS에서 클릭 | 브라우저 정책에 맞게 외부 링크 정상 열림 | `QA_REQUIRED` |

## 4. Representative / Seed Governance QA

| 항목 | 기대 결과 | 상태 |
| --- | --- | --- |
| actual overlay 미적용 | 추천 결과 생성 시 overlay seed를 사용하지 않음 | `READY_FOR_STAGING` |
| `build_course` untouched | 추천 엔진 actual path가 변경되지 않음 | `READY_FOR_STAGING` |
| `course_builder.py` 안전 | 추천/slot/fallback 로직 변경 없음 | `READY_FOR_STAGING` |
| `places` unchanged | governance 작업이 운영 places를 직접 수정하지 않음 | `READY_FOR_STAGING` |
| promote 금지 | representative/seed/image promote actual 실행 없음 | `READY_FOR_STAGING` |
| fail-closed | eligible overlay가 0이면 baseline only | `READY_FOR_STAGING` |
| diagnostics only | overlay adapter/checker는 build_course를 호출하지 않음 | `READY_FOR_STAGING` |

## 5. 배포 QA

| 항목 | 기대 결과 | 상태 |
| --- | --- | --- |
| frontend env | production env에 필요한 Vite 변수만 주입 | `QA_REQUIRED` |
| `VITE_SAJU_SERVICE_URL` | `https://saju-mbti-service.duckdns.org/` 설정 | `QA_REQUIRED` |
| `VITE_SHOW_SAJU_LINK` | 운영 노출 정책에 맞게 true/false 결정 | `QA_REQUIRED` |
| Vite build | `npm run build` 성공 | `READY_FOR_STAGING` |
| nginx 영향 | 사주 링크는 외부 이동이므로 nginx/proxy 변경 불필요 | `READY_FOR_STAGING` |
| API proxy | 저장/사주 UX 변경이 API proxy에 영향 없음 | `READY_FOR_STAGING` |
| production preview | production build에서 MyScreen/저장 상세 확인 | `QA_REQUIRED` |
| source map/console | 사용자 화면에 debug UI, 5화면 검증 버튼 미노출 | `QA_REQUIRED` |

## 6. 브라우저 QA

| 브라우저 | 확인 항목 | 상태 |
| --- | --- | --- |
| Android Chrome | safe-area, 하단 CTA, pull-to-refresh, 저장/복원/삭제, 사주 링크 | `QA_REQUIRED` |
| iOS Safari | safe-area, 새 탭 이동, localStorage, 스크롤 bounce | `QA_REQUIRED` |
| Desktop Chrome | 저장 목록, 상세, 다시 만들기, 사주 링크 | `QA_REQUIRED` |
| Desktop Edge | localStorage, 외부 링크, fallback UI | `OPTIONAL` |

## 7. 성능 / UX QA

| 항목 | 기대 결과 | 상태 |
| --- | --- | --- |
| 저장 목록 30개 | 스크롤 버벅임 없이 카드 표시 | `QA_REQUIRED` |
| 이미지 fallback | 이미지 없는 저장 코스에서 깨진 이미지 아이콘 대신 fallback 표시 | `READY_FOR_STAGING` |
| 긴 설명 | 저장 상세에서 긴 설명이 카드 밖으로 넘치지 않음 | `QA_REQUIRED` |
| loading/fallback | storage error, invalid data 상태에서 사용자 안내 표시 | `READY_FOR_STAGING` |
| CTA hierarchy | 주요 액션과 보조 액션이 혼동되지 않음 | `READY_FOR_STAGING` |

## 8. 장애 Fallback QA

| 장애 상황 | 기대 결과 | Production blocker 여부 |
| --- | --- | --- |
| localStorage disabled | 저장 목록 대신 안내 표시, 앱 crash 없음 | blocker 아님 |
| invalid saved data | 손상 데이터 필터링 또는 안내 표시 | blocker 아님 |
| env missing | 사주 버튼 숨김 | blocker 아님 |
| invalid saju URL | 사주 버튼 숨김 | blocker 아님 |
| API 실패 | 저장/마이 화면 자체는 API 없이 동작 | blocker 아님 |
| recommendation generate 실패 | 기존 실패 UI 유지 | 상황별 판단 |

## Production Blocker

아래 중 하나라도 발생하면 production 배포를 중단한다.

- Android Chrome에서 하단 CTA가 계속 가려져 핵심 버튼을 누를 수 없음
- 저장 상세 화면에서 장소 목록 마지막 항목을 볼 수 없음
- 저장/복원/삭제 중 앱 crash 발생
- `비슷한 코스 다시 만들기`가 잘못된 region/option으로 추천 요청을 보냄
- production build에서 사주 링크가 잘못된 도메인으로 이동
- env OFF 상태에서도 사주 버튼이 노출됨
- 저장 UX 변경으로 `/api/course/generate` 호출 payload가 변형됨
- representative overlay/promote가 운영 추천 경로에 실제 반영됨
- `places`, `tourism_belt.py`, `course_builder.py`에 의도치 않은 변경이 포함됨
- production build 실패
- nginx/proxy 설정 변경이 필요해졌으나 검증되지 않음

## 운영 전 필수 확인 항목

1. `npm run build` 성공
2. production preview 또는 staging 도메인에서 MyScreen 진입 확인
3. 저장할 코스 생성 후 저장, 새로고침, 복원, 삭제 확인
4. 저장 상세에서 `비슷한 코스 다시 만들기` 클릭 후 조건 화면 prefill 확인
5. `VITE_SHOW_SAJU_LINK=false`에서 사주 버튼 미노출 확인
6. `VITE_SHOW_SAJU_LINK=true`에서 사주 버튼 노출 및 새 탭 이동 확인
7. Android Chrome 실기기에서 safe-area, CTA, 스크롤 확인
8. iOS Safari 실기기에서 safe-area, 외부 링크, localStorage 확인
9. production 화면에서 5화면 검증/개발자용 UI 미노출 확인
10. `course_builder.py`, `api_server.py`, `tourism_belt.py`, migration 파일 diff 없음 확인

## 위험 요소

- localStorage 기반 저장은 기기/브라우저별 저장소 정책에 따라 삭제될 수 있다.
- 로그인 기반 동기화가 없으므로 다른 기기에서 저장 코스를 볼 수 없다.
- 저장 snapshot은 생성 당시 데이터이므로 최신 장소 정보와 다를 수 있다.
- 사주 연결은 외부 도메인 이동이므로 사주 서비스 장애 시 여행 서비스 안에서 복구할 수 없다.
- iOS Safari의 새 탭/팝업 정책은 실제 터치 이벤트 기준으로만 안정적으로 검증 가능하다.
- representative governance 파일은 안정화되어 있으나 actual overlay는 아직 production enable 상태가 아니다.

## 다음 작업 제안

1. Android Chrome 실기기 QA 결과를 이 문서에 `PASS/FAIL`로 업데이트한다.
2. iOS Safari 실기기 QA 결과를 별도 섹션으로 기록한다.
3. staging 배포 후 production env 조합별 스모크 테스트 로그를 남긴다.
4. production 배포 직전 `git diff --name-only`로 backend/DB/engine 파일 변경 여부를 재확인한다.
5. 로그인 기반 저장을 시작하기 전 현재 localStorage snapshot 구조를 서버 저장 DTO 후보로 문서화한다.
