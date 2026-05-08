# Staging Smoke Test Runbook

## 목적

staging 배포 후 운영자가 실제 사용자 흐름을 기준으로 여행 서비스가 production 배포 가능한 상태인지 확인한다.

이 문서는 smoke test 절차만 정의한다. 코드 수정, DB 수정, migration, 배포 실행은 포함하지 않는다.

## Smoke Test 기준

- 모든 핵심 사용자 흐름이 `PASS`여야 production 배포 가능하다.
- blocker가 1개라도 있으면 production 배포를 중단한다.
- representative/seed overlay는 실제 추천 경로에 적용되지 않은 상태를 유지해야 한다.

## 1. Android Chrome Smoke Test

대상:

- Android 실기기
- Chrome 최신 버전
- staging URL

| 순서 | 테스트 항목 | 실행 방법 | 기대 결과 | 결과 |
| --- | --- | --- | --- | --- |
| 1 | 홈 진입 | staging URL 접속 | 홈 화면이 status bar와 겹치지 않고 정상 표시 | `PASS/FAIL` |
| 2 | safe-area | 상단/하단 영역 확인 | 상단 콘텐츠와 하단 CTA가 브라우저 UI에 가려지지 않음 | `PASS/FAIL` |
| 3 | 지역 선택 | 서울 또는 부산 선택 | 선택 상태가 명확히 표시 | `PASS/FAIL` |
| 4 | 출발지 선택 | 출발지 선택 | 다음 단계로 정상 이동 | `PASS/FAIL` |
| 5 | 옵션 선택 | 기본/카페투어/자연/맛집 중 1개 선택 | 선택 옵션이 유지 | `PASS/FAIL` |
| 6 | 코스 생성 | 코스 생성 CTA 클릭 | 결과 화면 표시, 장소 카드 렌더링 | `PASS/FAIL` |
| 7 | 결과 스크롤 | 마지막 장소까지 스크롤 | 마지막 카드가 하단 CTA에 가려지지 않음 | `PASS/FAIL` |
| 8 | 저장 | `이 코스 저장하기` 클릭 | 저장 완료 피드백 표시 | `PASS/FAIL` |
| 9 | MyScreen 진입 | 마이/저장 화면 이동 | 저장 카드 표시 | `PASS/FAIL` |
| 10 | 복원 | 저장 카드 클릭 | 저장 상세 화면 표시 | `PASS/FAIL` |
| 11 | regenerate | `비슷한 코스 다시 만들기` 클릭 | 저장된 조건 기반으로 새 추천 흐름 진입 | `PASS/FAIL` |
| 12 | 삭제 | 저장 카드 또는 상세에서 삭제 | confirm 후 목록 갱신 | `PASS/FAIL` |
| 13 | 사주 링크 | 사주 버튼 클릭 | 새 탭 또는 외부 브라우저로 사주 서비스 이동 | `PASS/FAIL` |
| 14 | pull-to-refresh | 홈/마이 화면에서 아래로 당김 | 브라우저 기본 새로고침이 막히지 않음 | `PASS/FAIL` |

## 2. iOS Safari Smoke Test

대상:

- iPhone 실기기
- Safari
- staging URL

| 순서 | 테스트 항목 | 실행 방법 | 기대 결과 | 결과 |
| --- | --- | --- | --- | --- |
| 1 | 홈 진입 | staging URL 접속 | notch/status bar 영역 침범 없음 | `PASS/FAIL` |
| 2 | 하단 CTA | 홈/결과/저장 상세에서 하단 버튼 확인 | Safari 하단 바에 가려지지 않음 | `PASS/FAIL` |
| 3 | 코스 생성 | 서울 샘플 코스 생성 | 결과 화면 정상 표시 | `PASS/FAIL` |
| 4 | 결과 스크롤 | 마지막 장소까지 확인 | 카드/설명 잘림 없음 | `PASS/FAIL` |
| 5 | 저장 | 코스 저장 | localStorage 저장 유지 | `PASS/FAIL` |
| 6 | 새로고침 후 복원 | Safari 새로고침 후 MyScreen 진입 | 저장 목록 유지 | `PASS/FAIL` |
| 7 | regenerate | 저장 상세에서 다시 만들기 | 조건 화면으로 정상 이동 | `PASS/FAIL` |
| 8 | 사주 링크 | 사주 버튼 클릭 | Safari 정책 내에서 외부 링크 정상 열림 | `PASS/FAIL` |
| 9 | bounce/scroll | 위아래 스크롤 반복 | 내부 화면이 잠기지 않음 | `PASS/FAIL` |

## 3. 저장 UX Smoke Test

| 항목 | 실행 방법 | 기대 결과 | 결과 |
| --- | --- | --- | --- |
| empty state | 저장 데이터 없는 브라우저로 MyScreen 진입 | `저장한 코스가 없습니다` 표시 | `PASS/FAIL` |
| 저장 | 결과 화면에서 저장 | 저장 완료 및 MyScreen 카드 표시 | `PASS/FAIL` |
| overwrite | 같은 코스를 다시 저장 | 중복 카드 없이 최신 저장 시간 반영 | `PASS/FAIL` |
| 복원 | 저장 카드 클릭 | 저장 상세 표시 | `PASS/FAIL` |
| 삭제 | 저장 카드 삭제 | confirm 후 삭제 메시지 표시 | `PASS/FAIL` |
| regenerate | 저장 상세에서 다시 만들기 | region/option 등 저장 조건 기반 새 추천 흐름 진입 | `PASS/FAIL` |
| invalid snapshot | 개발자도구로 깨진 JSON 또는 누락 데이터 주입 | 앱 crash 없이 fallback 안내 | `PASS/FAIL` |
| storage unavailable | localStorage 차단 환경에서 진입 | 앱 crash 없이 저장 불가 안내 | `PASS/FAIL` |
| 30개 초과 | 저장 데이터 31개 이상 구성 | 최근 30개만 표시 | `PASS/FAIL` |

## 4. 사주 연결 Env Smoke Test

| env 상태 | 기대 결과 | 결과 |
| --- | --- | --- |
| `VITE_SHOW_SAJU_LINK=false` | 사주 버튼 미노출 | `PASS/FAIL` |
| `VITE_SHOW_SAJU_LINK=true` + 정상 URL | 사주 버튼 노출 | `PASS/FAIL` |
| `VITE_SAJU_SERVICE_URL` missing | 사주 버튼 미노출 | `PASS/FAIL` |
| URL parse 불가 | 사주 버튼 미노출 | `PASS/FAIL` |
| 정상 URL 클릭 | `https://saju-mbti-service.duckdns.org/` 이동 | `PASS/FAIL` |

## 5. Representative Governance Smoke Test

운영자가 확인할 사항:

| 항목 | 확인 방법 | 기대 결과 | 결과 |
| --- | --- | --- | --- |
| overlay actual 미적용 | 추천 결과 생성 경로 확인 | representative overlay가 build_course에 연결되지 않음 | `PASS/FAIL` |
| fail-closed 유지 | overlay eligible count가 0인 상태 확인 | baseline seed만 사용 | `PASS/FAIL` |
| build_course untouched | 배포 diff 확인 | `course_builder.py` 변경 없음 | `PASS/FAIL` |
| places unchanged | 배포 전후 row count 또는 diff 확인 | places 직접 insert/update 없음 | `PASS/FAIL` |
| promote 미실행 | promotions/actual promote 로그 확인 | 실제 promote 없음 | `PASS/FAIL` |
| diagnostics only | overlay/gate CLI가 추천 API와 분리되어 있음 | production request path 영향 없음 | `PASS/FAIL` |

## 6. Staging Deploy Smoke Test

배포 후 확인 순서:

1. staging frontend env 확인
2. `npm run build` 결과물 반영 여부 확인
3. staging URL 접속
4. `/api/regions` 정상 응답 확인
5. `/api/course/generate` 서울 샘플 정상 응답 확인
6. frontend에서 코스 생성 정상 동작 확인
7. 저장/복원/regenerate UX 확인
8. 사주 링크 env 상태 확인
9. production debug UI 미노출 확인
10. nginx/proxy 변경이 없었는지 확인

## 7. Production Blocker Checklist

아래 항목 중 하나라도 `YES`이면 production 배포를 중단한다.

| Blocker | YES/NO | 메모 |
| --- | --- | --- |
| production build 실패 |  |  |
| 홈/결과/마이 화면 중 하나라도 진입 불가 |  |  |
| 모바일 하단 CTA가 눌리지 않음 |  |  |
| 결과 화면 마지막 장소가 CTA에 가려짐 |  |  |
| 저장/복원/삭제 중 앱 crash |  |  |
| regenerate가 잘못된 지역/옵션으로 이동 |  |  |
| 사주 링크가 잘못된 도메인으로 이동 |  |  |
| env OFF인데 사주 버튼 노출 |  |  |
| localStorage 장애 시 앱 crash |  |  |
| API generate payload가 의도치 않게 변경 |  |  |
| `course_builder.py` 변경 포함 |  |  |
| `api_server.py` 변경 포함 |  |  |
| migration/DB 변경 포함 |  |  |
| representative overlay actual 적용 |  |  |
| places 직접 변경 |  |  |

## 8. PASS/FAIL 기록 템플릿

테스트 일시:

테스트 환경:

- staging URL:
- API URL:
- device:
- browser:
- app/build version:
- tester:

결과 요약:

| 영역 | PASS | FAIL | BLOCKED | 메모 |
| --- | ---: | ---: | ---: | --- |
| Android Chrome |  |  |  |  |
| iOS Safari |  |  |  |  |
| 저장 UX |  |  |  |  |
| 사주 연결 |  |  |  |  |
| representative governance |  |  |  |  |
| 배포/env |  |  |  |  |

FAIL 상세:

| ID | 영역 | 재현 경로 | 기대 결과 | 실제 결과 | blocker 여부 | 담당 | 상태 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| QA-001 |  |  |  |  |  |  |  |

최종 판정:

- `BLOCKED`
- `QA_REQUIRED`
- `READY_FOR_PRODUCTION`

## 9. Rollback 확인 항목

production 배포 전 반드시 확인:

| 항목 | 기대 결과 | 확인 |
| --- | --- | --- |
| 이전 frontend build 보관 | 즉시 되돌릴 수 있는 이전 artifact 존재 |  |
| nginx 설정 변경 없음 | frontend-only 배포면 nginx rollback 불필요 |  |
| API/backend 변경 없음 | backend rollback 불필요 |  |
| DB migration 없음 | DB rollback 불필요 |  |
| env 변경 이력 | 사주 env ON/OFF 되돌릴 수 있음 |  |
| static cache 무효화 방식 | 이전 JS/CSS 캐시 문제 대응 가능 |  |
| production smoke 실패 시 절차 | 이전 build로 복구 후 smoke 재실행 |  |

rollback trigger:

- production 진입 불가
- 주요 CTA 클릭 불가
- 저장/복원 crash
- 사주 링크 오동작
- 예상하지 않은 API 요청 실패 증가
- representative/seed actual overlay가 잘못 활성화됨

## 10. 운영 전 최종 확인 순서

1. `git diff --name-only`로 backend/DB/engine 변경 없음 확인
2. frontend env 값 확인
3. production build 성공 확인
4. staging 배포
5. Android Chrome smoke test
6. iOS Safari smoke test
7. desktop Chrome smoke test
8. 저장 UX smoke test
9. 사주 연결 env ON/OFF smoke test
10. representative governance fail-closed 확인
11. production blocker checklist 모두 `NO` 확인
12. rollback 준비 상태 확인
13. `READY_FOR_PRODUCTION` 판정 후 production 배포 승인

## 11. 최종 판정 기준

`READY_FOR_PRODUCTION` 조건:

- Android Chrome 핵심 흐름 PASS
- iOS Safari 핵심 흐름 PASS
- 저장/복원/regenerate PASS
- 사주 링크 env ON/OFF PASS
- production blocker 0건
- backend/API/DB/engine 변경 없음
- representative overlay actual 미적용 확인
- rollback 준비 완료

하나라도 부족하면 `QA_REQUIRED` 또는 `BLOCKED`로 유지한다.
