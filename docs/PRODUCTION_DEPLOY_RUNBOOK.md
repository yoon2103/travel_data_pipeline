# Production Deploy Runbook

## 목적

여행 서비스 production 배포를 운영자가 실수 없이 수행할 수 있도록 사전 확인, staging 검증, 실기기 QA, production 배포, rollback 절차를 순서대로 정리한다.

이 문서는 실행 절차 문서이며 코드 수정, DB 수정, migration, 실제 배포 실행을 포함하지 않는다.

## 현재 전제

- 상태: `READY_FOR_STAGING`
- `npm run lint`: PASS
- `npm run build`: PASS
- localStorage 저장/복원/regenerate UX 구현 완료
- 사주 연결 MVP 완료
- representative/seed governance fail-closed 유지
- actual overlay rollout 없음
- production 전 Android/iOS 실기기 QA 필요

## 1. 배포 전 확인

### 1.1 Git diff 확인

운영 배포 전 변경 범위를 확인한다.

```bash
git status --short
git diff --name-only
```

확인 기준:

| 항목 | 기대 결과 | 확인 |
| --- | --- | --- |
| frontend 변경 | 의도한 저장/복원/regenerate/사주 연결/UI 관련 변경만 포함 |  |
| backend 변경 | production 배포 대상에 의도치 않은 backend 변경 없음 |  |
| DB/migration 변경 | 이번 배포에 migration 없음 |  |
| representative batch 변경 | actual runtime에 연결되지 않음 |  |
| 민감정보 | `.env`, API key, dump 파일 commit 없음 |  |

절대 포함되면 안 되는 변경:

- `course_builder.py` 의도치 않은 변경
- `tourism_belt.py` seed 직접 변경
- migration 실행이 필요한 DB schema 변경
- places insert/update script 실행
- representative overlay actual enable

### 1.2 Env 확인

Frontend env는 build 시점에 반영된다.

| env | production 권장값 | 확인 |
| --- | --- | --- |
| `VITE_SHOW_SAJU_LINK` | 운영 노출 정책에 따라 `true` 또는 `false` |  |
| `VITE_SAJU_SERVICE_URL` | `https://saju-mbti-service.duckdns.org/` |  |
| `VITE_SHOW_SCREEN_REVIEW` | unset 또는 `false` |  |

확인 기준:

- env OFF이면 사주 버튼 미노출
- env ON이면 사주 버튼 노출
- URL 누락/비정상 URL이면 버튼 미노출
- `5화면 검토` UI는 production에서 미노출

### 1.3 Representative governance safety 확인

| 항목 | 기대 결과 | 확인 |
| --- | --- | --- |
| actual overlay OFF | 추천 요청에서 overlay seed 사용 안 함 |  |
| fail-closed 유지 | eligible overlay 0이면 baseline only |  |
| `build_course` untouched | `course_builder.py` 변경 없음 |  |
| `tourism_belt.py` untouched | seed 직접 수정 없음 |  |
| promote 미실행 | representative/image/seed actual promote 없음 |  |
| places unchanged | places 직접 insert/update 없음 |  |
| batch 분리 | `batch/place_enrichment`는 사용자 요청 중 호출되지 않음 |  |

### 1.4 lint/build 확인

```bash
cd frontend
npm install
npm run lint
npm run build
```

모두 PASS여야 staging 배포로 진행한다.

## 2. Frontend Build 절차

1. frontend 디렉터리로 이동

```bash
cd frontend
```

2. dependency 설치

```bash
npm install
```

3. lint 실행

```bash
npm run lint
```

4. production build 실행

```bash
npm run build
```

5. build 산출물 확인

```bash
ls -la dist
ls -la dist/assets
```

기대 결과:

- `dist/index.html` 존재
- `dist/assets/*.js` 존재
- `dist/assets/*.css` 존재

## 3. Staging 절차

### 3.1 Staging deploy

운영 방식에 맞게 최신 `dist`를 staging static serving 위치에 반영한다.

확인:

| 항목 | 기대 결과 | 확인 |
| --- | --- | --- |
| dist 반영 | staging이 최신 frontend build 사용 |  |
| nginx 변경 없음 | frontend-only 배포라면 nginx 설정 변경 불필요 |  |
| API proxy 유지 | `/api` 요청이 travel API로 연결 |  |
| cache 처리 | 이전 JS/CSS 캐시가 남지 않음 |  |

### 3.2 Staging API 확인

staging에서 아래를 확인한다.

```bash
curl -I <staging-url>
curl <staging-url>/api/regions
```

기대 결과:

- frontend 200
- `/api/regions` 200
- region 목록 반환

## 4. Staging Smoke Test 절차

staging URL에서 아래 순서대로 테스트한다.

| 순서 | 테스트 | 기대 결과 | 확인 |
| --- | --- | --- | --- |
| 1 | 홈 진입 | 홈 화면 정상 표시 |  |
| 2 | 지역 선택 | 지역 목록 표시 및 선택 가능 |  |
| 3 | 출발 시간 선택 | 선택값 표시 |  |
| 4 | 출발 기준점 선택 | departures 로드 및 선택 가능 |  |
| 5 | 조건 선택 | 분위기/거리/일정 선택 가능 |  |
| 6 | 코스 생성 | 결과 화면 표시 |  |
| 7 | 결과 화면 | 장소 카드, 총시간, 이동시간 표시 |  |
| 8 | 저장 | 저장 완료 feedback |  |
| 9 | MyScreen | 저장 목록 표시 |  |
| 10 | 저장 상세 | 저장 코스 상세 보기 |  |
| 11 | regenerate | 조건 화면으로 재진입 |  |
| 12 | 삭제 | confirm 후 저장 목록 갱신 |  |
| 13 | 사주 링크 | env ON일 때 외부 링크 정상 이동 |  |

## 5. Android Chrome 실기기 QA 절차

대상:

- Android 실기기
- Chrome 최신 버전
- staging URL

절차:

1. staging URL 접속
2. 홈 화면 상단 safe-area 확인
3. 출발 시간/출발 기준점 선택
4. 코스 생성
5. 결과 화면 마지막 장소까지 스크롤
6. 하단 CTA가 Chrome 하단 UI에 가려지지 않는지 확인
7. 코스 저장
8. MyScreen 저장 목록 진입
9. 저장 상세 마지막 장소까지 스크롤
10. regenerate 진입
11. 사주 링크 클릭
12. pull-to-refresh 동작 확인

PASS 기준:

- 상단/하단 UI 잘림 없음
- CTA 클릭 가능
- 결과/저장 상세 스크롤 정상
- 저장/복원/regenerate 정상
- 사주 링크 정상

## 6. iOS Safari QA 절차

대상:

- iPhone 실기기
- Safari
- staging URL

절차:

1. staging URL 접속
2. notch/status bar 영역 침범 확인
3. Safari 하단 바와 CTA 겹침 확인
4. 코스 생성
5. 결과 화면 스크롤
6. 저장
7. 새로고침 후 저장 목록 유지 확인
8. 저장 상세 스크롤
9. regenerate
10. 사주 링크 새 탭/외부 이동 확인

PASS 기준:

- Safari safe-area 문제 없음
- localStorage 유지
- 저장 상세 잘림 없음
- 사주 링크 정상

## 7. Production Deploy 절차

production 배포는 staging smoke와 실기기 QA가 PASS인 경우에만 진행한다.

### 7.1 Production 사전 확인

| 항목 | 기대 결과 | 확인 |
| --- | --- | --- |
| staging smoke | PASS |  |
| Android QA | PASS |  |
| iOS QA | PASS |  |
| blocker | 0건 |  |
| rollback 준비 | 완료 |  |
| env 최종 확인 | 완료 |  |

### 7.2 Production 반영

운영 배포 방식에 따라 최신 `dist`를 production static serving 위치에 반영한다.

확인:

- nginx 설정 변경 없음
- backend/API 재배포 없음
- DB migration 없음
- cache invalidation 또는 asset hash 갱신 확인

## 8. Production Smoke Test 절차

production 배포 직후 아래만 빠르게 확인한다.

| 순서 | 테스트 | 기대 결과 | 확인 |
| --- | --- | --- | --- |
| 1 | production URL 접속 | 200, 홈 표시 |  |
| 2 | `/api/regions` | 200, region 목록 |  |
| 3 | 서울 코스 생성 | 결과 화면 표시 |  |
| 4 | 저장 | localStorage 저장 성공 |  |
| 5 | 저장 상세 | 저장 코스 표시 |  |
| 6 | regenerate | 조건 화면 이동 |  |
| 7 | 사주 링크 | 정책대로 노출/이동 |  |
| 8 | debug UI | 5화면 검토/Mock frame 미노출 |  |

## 9. Rollback 절차

rollback trigger가 발생하면 즉시 이전 정상 frontend build로 되돌린다.

### 9.1 Rollback trigger

- production URL 접속 실패
- 홈/조건/결과/MyScreen 중 하나라도 렌더링 실패
- 코스 생성 실패
- 저장/복원 crash
- 모바일 CTA 클릭 불가
- 사주 링크 오동작
- 예상하지 않은 backend/API 오류 증가
- representative overlay actual 적용 감지

### 9.2 Rollback 실행

1. 이전 정상 `dist` artifact 확인
2. production static root를 이전 artifact로 복구
3. cache 무효화 또는 asset reload 확인
4. production URL 재접속
5. 최소 smoke test 실행

rollback 후 확인:

| 항목 | 기대 결과 | 확인 |
| --- | --- | --- |
| 홈 진입 | 정상 |  |
| 코스 생성 | 정상 |  |
| 저장 목록 | crash 없음 |  |
| 사주 링크 | 기존 상태 복구 |  |
| API 영향 | 없음 |  |

## 10. Production Blockers

아래 중 하나라도 발생하면 production 배포 또는 유지 금지.

| Blocker | 확인 |
| --- | --- |
| `npm run lint` 실패 |  |
| `npm run build` 실패 |  |
| staging smoke 실패 |  |
| Android Chrome 핵심 CTA 클릭 불가 |  |
| iOS Safari 화면 잘림 |  |
| `/api/course/generate` 실패 |  |
| 저장/복원/regenerate crash |  |
| 사주 링크 오도메인 이동 |  |
| env OFF인데 사주 버튼 노출 |  |
| `course_builder.py` 변경 포함 |  |
| `tourism_belt.py` 변경 포함 |  |
| migration/DB 변경 포함 |  |
| representative overlay actual 적용 |  |
| places 직접 변경 |  |

## 11. Release 승인 기준

`READY_FOR_PRODUCTION` 승인 조건:

1. Git diff 확인 완료
2. env 확인 완료
3. representative governance safety PASS
4. `npm run lint` PASS
5. `npm run build` PASS
6. staging deploy 완료
7. staging smoke PASS
8. Android Chrome QA PASS
9. iOS Safari QA PASS
10. production blocker 0건
11. rollback 준비 완료
12. 운영자 승인 완료

## 12. 운영 배포 후 첫 확인 항목

배포 후 10분 이내 확인:

| 항목 | 기대 결과 | 확인 |
| --- | --- | --- |
| production URL | 200 |  |
| frontend 화면 | 홈 정상 표시 |  |
| API proxy | `/api/regions` 정상 |  |
| 코스 생성 | 서울 샘플 생성 성공 |  |
| 저장 | localStorage 저장 성공 |  |
| regenerate | 조건 화면 이동 |  |
| 사주 링크 | 설정값대로 동작 |  |
| console error | 치명적 오류 없음 |  |
| debug UI | 미노출 |  |
| representative overlay | actual OFF |  |

## 13. 위험 요소

- localStorage 저장은 브라우저/기기 단위라 사용자 기기 정책에 따라 삭제될 수 있다.
- 사주 링크는 외부 서비스 의존이므로 외부 서비스 장애는 여행 서비스에서 복구할 수 없다.
- production env가 build 시점에 잘못 들어가면 재build가 필요하다.
- 모바일 safe-area 문제는 desktop/headless 테스트로 완전히 대체할 수 없다.
- representative overlay는 아직 actual rollout 금지 상태이므로 feature flag를 실수로 켜면 안 된다.

## 14. 관련 문서

- `docs/STAGING_DEPLOY_CHECKLIST.md`
- `docs/STAGING_SMOKE_TEST_RUNBOOK.md`
- `docs/PRODUCTION_READINESS_QA_CHECKLIST.md`
- `docs/FRONTEND_BACKEND_FULL_FUNCTION_TEST_REPORT.md`
- `docs/MYSCREEN_LINT_FIX_REPORT.md`
