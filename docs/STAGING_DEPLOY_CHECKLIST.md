# Staging Deploy Checklist

## 목적

READY_FOR_STAGING 상태의 여행 서비스를 staging 환경에 배포할 때 운영자가 실수 없이 확인해야 할 항목을 정리한다.

이 문서는 checklist 전용이며 코드 수정, DB 수정, migration, 실제 배포 실행을 포함하지 않는다.

## Deploy Checklist

### 1. 사전 확인

| 항목 | 기대 결과 | 확인 |
| --- | --- | --- |
| 현재 브랜치 확인 | staging 배포 대상 브랜치가 맞음 |  |
| 의도치 않은 backend diff 없음 | `api_server.py`, `course_builder.py`, `tourism_belt.py` 변경 없음 |  |
| 의도치 않은 DB diff 없음 | `migration_*.sql`, schema 변경 없음 |  |
| representative actual rollout 없음 | overlay/promote actual 적용 없음 |  |
| frontend 변경 범위 확인 | 저장/복원/regenerate/사주 연결 관련 변경만 포함 |  |
| 최신 문서 확인 | QA/runbook/checklist 문서 최신 |  |

### 2. Frontend build

staging 배포 전 로컬 또는 CI에서 아래 순서로 확인한다.

```bash
cd frontend
npm install
npm run lint
npm run build
```

| 항목 | 기대 결과 | 확인 |
| --- | --- | --- |
| `npm install` | dependency 설치 성공 |  |
| `npm run lint` | PASS |  |
| `npm run build` | PASS |  |
| `dist/` 생성 | `dist/index.html`, `dist/assets/*` 생성 |  |
| build asset 확인 | JS/CSS 파일명이 새 build로 갱신 |  |

## Env Checklist

staging frontend env는 Vite build 시점에 번들된다. 운영 키나 민감정보를 넣지 않는다.

| env | staging 권장값 | 설명 | 확인 |
| --- | --- | --- | --- |
| `VITE_SHOW_SAJU_LINK` | `true` 또는 검증 목적에 따라 `false` | 사주 버튼 노출 여부 |  |
| `VITE_SAJU_SERVICE_URL` | `https://saju-mbti-service.duckdns.org/` | 사주 서비스 외부 링크 |  |
| `VITE_SHOW_SCREEN_REVIEW` | unset 또는 `false` | 5화면 검증 UI production/staging 미노출 |  |

확인 기준:

- `VITE_SHOW_SAJU_LINK=false`이면 MyScreen에서 사주 버튼이 보이면 안 된다.
- `VITE_SHOW_SAJU_LINK=true`이고 URL이 정상일 때만 버튼이 보여야 한다.
- URL이 비어 있거나 잘못된 URL이면 버튼은 숨겨져야 한다.
- 사주 링크는 backend/proxy를 거치지 않는 외부 링크여야 한다.

## Staging Deploy Checklist

| 항목 | 기대 결과 | 확인 |
| --- | --- | --- |
| `dist` 반영 | staging static root에 최신 `dist` 반영 |  |
| nginx 설정 변경 없음 | frontend-only 배포면 nginx 변경 불필요 |  |
| API proxy 유지 | `/api` 요청이 travel API로 연결 |  |
| cache 영향 확인 | 이전 JS/CSS 캐시로 구버전 화면이 뜨지 않음 |  |
| 5화면 검증 UI 미노출 | staging 사용자 화면에서 `5화면 검토` 버튼 없음 |  |
| mock status bar 미노출 | `9:41`, 배터리/신호 mock frame 없음 |  |
| API base 확인 | frontend에서 `/api/regions` 정상 호출 |  |

staging 배포 후 최소 확인 URL:

- frontend staging URL
- `/api/regions`
- `/api/course/generate`

## Smoke Test Checklist

### 핵심 사용자 플로우

| 순서 | 항목 | 기대 결과 | 확인 |
| --- | --- | --- | --- |
| 1 | 홈 진입 | 홈 화면 정상 표시 |  |
| 2 | 지역 선택 | 지역 변경 가능 |  |
| 3 | 출발 시간 선택 | 시간 선택 후 값 표시 |  |
| 4 | 출발 기준점 선택 | departure list 로드 후 선택 가능 |  |
| 5 | 조건 선택 | 분위기/거리/일정 선택 가능 |  |
| 6 | 코스 생성 | 결과 화면 표시, 장소 5개 내외 표시 |  |
| 7 | option_notice/missing_slot_reason | 있는 경우 결과 상단 안내 표시 |  |
| 8 | 저장 | `이 코스 저장하기` 클릭 후 저장 피드백 |  |
| 9 | 저장 목록 | MyScreen에서 저장 카드 표시 |  |
| 10 | 저장 상세 | 저장 카드 클릭 시 상세 표시 |  |
| 11 | regenerate | `비슷한 코스 다시 만들기`로 조건 화면 진입 |  |
| 12 | 삭제 | confirm 후 저장 목록 갱신 |  |
| 13 | 사주 링크 | env ON일 때 새 탭 외부 이동 |  |

### API smoke

| API | 기대 결과 | 확인 |
| --- | --- | --- |
| `GET /api/regions` | 200, region 목록 |  |
| `GET /api/region/서울/departures` | 200, departures 목록 |  |
| `GET /api/region/서울/zones` | 200, zones 목록 |  |
| `POST /api/course/generate` | 200, course result |  |
| `GET /api/course/{course_id}/candidates` | 200, 후보 목록 |  |
| `PATCH /api/course/{course_id}/replace` | 200, places 반환 |  |
| `POST /api/course/{course_id}/recalculate` | 200, 재계산 결과 |  |

저장 버튼은 backend save API를 호출하지 않는 것이 정상이다.

## Android Chrome 확인 항목

| 항목 | 기대 결과 | 확인 |
| --- | --- | --- |
| 상단 safe-area | status bar 아래로 hero/text가 잘리지 않음 |  |
| 하단 CTA | Chrome 하단 UI에 버튼이 가려지지 않음 |  |
| 홈 스크롤 | pull-to-refresh가 막히지 않음 |  |
| 결과 스크롤 | 마지막 장소 카드까지 확인 가능 |  |
| 저장 상세 스크롤 | 마지막 장소/버튼이 하단 탭에 가려지지 않음 |  |
| 하단 탭 | 홈/저장/마이 정상 전환 |  |
| 사주 링크 | 새 탭 또는 외부 브라우저 이동 정상 |  |

## iOS Safari 확인 항목

| 항목 | 기대 결과 | 확인 |
| --- | --- | --- |
| notch/safe-area | 상단 콘텐츠 침범 없음 |  |
| Safari 하단 바 | CTA와 저장 상세 하단이 가려지지 않음 |  |
| localStorage | 저장 후 새로고침해도 목록 유지 |  |
| 외부 링크 | 사주 링크가 Safari 정책 내에서 정상 열림 |  |
| 스크롤 bounce | 내부 화면이 잠기지 않음 |  |
| 이미지 fallback | 이미지 없는 장소가 깨진 이미지로 보이지 않음 |  |

## Rollback Checklist

production/staging 문제 발생 시 되돌릴 수 있어야 한다.

| 항목 | 기대 결과 | 확인 |
| --- | --- | --- |
| 이전 `dist` 보관 | 직전 정상 build artifact 존재 |  |
| env rollback 가능 | 사주 링크 env ON/OFF 즉시 변경 가능 |  |
| nginx rollback 불필요 | nginx 설정 변경이 없었음 |  |
| backend rollback 불필요 | backend 배포가 없었음 |  |
| DB rollback 불필요 | migration/DB write가 없었음 |  |
| cache clear 방법 | 정적 asset 캐시 무효화 방법 확인 |  |
| rollback 후 smoke | 홈 진입 + 코스 생성 + 저장 최소 확인 |  |

rollback trigger:

- staging/prod 접속 불가
- 홈/조건/결과/MyScreen 중 하나라도 렌더링 실패
- 코스 생성 실패
- 저장/복원 crash
- 모바일 CTA 클릭 불가
- 사주 링크 오동작
- representative overlay가 실제 추천에 반영됨

## Production Blockers

아래 항목이 하나라도 있으면 production 배포를 중단한다.

| Blocker | 확인 |
| --- | --- |
| `npm run lint` 실패 |  |
| `npm run build` 실패 |  |
| `/api/regions` 실패 |  |
| `/api/course/generate` 실패 |  |
| 홈/조건/결과/MyScreen 진입 실패 |  |
| 저장/복원/regenerate crash |  |
| Android Chrome에서 하단 CTA가 눌리지 않음 |  |
| iOS Safari에서 저장 상세가 잘림 |  |
| 사주 링크가 잘못된 도메인으로 이동 |  |
| env OFF인데 사주 버튼 노출 |  |
| `course_builder.py` 변경 포함 |  |
| `tourism_belt.py` 변경 포함 |  |
| migration/DB 변경 포함 |  |
| representative overlay actual 적용 |  |
| places 직접 변경 |  |

## Representative Governance Safety 확인

| 항목 | 기대 결과 | 확인 |
| --- | --- | --- |
| overlay actual 미적용 | build_course 경로에서 overlay 사용 안 함 |  |
| fail-closed 유지 | eligible overlay 0이면 baseline only |  |
| `build_course` untouched | `course_builder.py` diff 없음 |  |
| `tourism_belt.py` untouched | seed 직접 수정 없음 |  |
| promote 미실행 | actual promote 없음 |  |
| places unchanged | places insert/update 없음 |  |
| batch 분리 | `batch/place_enrichment`는 사용자 요청 중 호출되지 않음 |  |

## Release Approval 기준

`READY_FOR_PRODUCTION` 승인 조건:

1. frontend env checklist 완료
2. `npm run lint` PASS
3. `npm run build` PASS
4. staging deploy checklist 완료
5. 핵심 smoke test PASS
6. Android Chrome smoke PASS
7. iOS Safari smoke PASS
8. production blocker 0건
9. rollback 준비 완료
10. representative governance safety PASS

위 조건 중 하나라도 부족하면 `QA_REQUIRED` 유지.

## 위험 요소

- localStorage 저장은 브라우저/기기 단위이며 삭제될 수 있다.
- 로그인 기반 동기화가 없으므로 다른 기기에서 저장 코스를 볼 수 없다.
- 사주 서비스는 외부 도메인이므로 해당 서비스 장애는 여행 서비스 내부에서 복구할 수 없다.
- staging에서 env가 잘못 들어가면 사주 버튼이 의도와 다르게 노출될 수 있다.
- 모바일 safe-area 문제는 headless보다 실기기 확인이 더 중요하다.
- representative overlay는 아직 actual rollout 금지 상태이므로, 배포 중 실수로 feature flag를 켜면 안 된다.

## 다음 작업 제안

1. 이 체크리스트 기준으로 staging 배포를 수행한다.
2. staging smoke test 결과를 `STAGING_SMOKE_TEST_RUNBOOK.md`에 PASS/FAIL로 기록한다.
3. Android/iOS 실기기에서 CTA, 스크롤, 저장 상세을 우선 확인한다.
4. production 배포 전 `FRONTEND_BACKEND_FULL_FUNCTION_TEST_REPORT.md`의 QA_REQUIRED 항목을 해소한다.
