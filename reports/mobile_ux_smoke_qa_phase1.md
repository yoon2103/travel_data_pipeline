# mobile_ux_smoke_qa_phase1

## 목표

현재까지 완료된 모바일 UX polish 작업을 기준으로 운영 배포 전 smoke QA를 수행한다.

이번 단계는 검증 전용이다. 신규 기능, 추천 엔진, route assembly, DB, migration은 변경하지 않았다.

## 테스트 환경

- 대상: production `http://travel-planne.duckdns.org`
- Browser: Codex in-app browser viewport simulation
- Viewport:
  - iPhone-style `390x844`
  - Android/Galaxy-style `360x740`
- 테스트 일시: 2026-05-23
- 주요 API: `/api/regions`

## HomeScreen QA 결과

확인 항목:

- district selector open/close
- district 선택 상태
- time-band accordion 기본 collapsed
- time-band 선택 후 collapsed 복귀
- CTA initial viewport 내 노출
- CTA disabled/enabled 상태
- safe-area overlap

결과:

| Viewport | time-band collapsed | 저녁 선택 후 collapsed | CTA top | CTA height | district 선택 후 CTA | 이슈 |
|---|---:|---:|---:|---:|---:|---|
| 390x844 | PASS | PASS | 517px | 62px | enabled | 없음 |
| 360x740 | PASS | PASS | 488px | 62px | enabled | 없음 |

판단:

- CTA는 두 viewport 모두 initial viewport 안에 노출된다.
- time-band accordion은 기본 collapsed이며, `저녁 17:00` 선택 후 `출발 시간대 · 저녁`으로 접힌 상태가 유지된다.
- district selector sheet는 정상 노출된다.
- district 선택 후 CTA가 disabled에서 enabled로 전환된다.

## CourseResultScreen QA 결과

확인 항목:

- 결과 카드 순번 circle
- role/duration meta
- description density
- cafe placeholder
- bottom fixed action overlap

결과:

- timeline number circle 5개 확인
- `대표 관광지 · 1시간 30분`, `분위기 좋은 카페 · 40분` 등 role/duration meta 확인
- description maxHeight `105px` 적용 확인
- cafe placeholder 노출 케이스 확인
- bottom fixed action 정상 노출

## Regenerate 3회 결과

대상 district:

- 성수 감성 카페
- 북촌 한옥 산책
- 한남 감성
- 강남역 주변

연남은 현재 서울 추천 여행지 목록에 노출되지 않아 테스트 제외했다.

| District | Initial result | Regenerate 3회 결과 | NO_COURSE | places_empty | Scroll |
|---|---:|---:|---:|---:|---|
| 성수 감성 카페 | PASS | PASS 3/3 | 0 | 0 | scrollY 약 84px |
| 북촌 한옥 산책 | PASS | PASS 3/3 | 0 | 0 | scrollY 약 84px |
| 한남 감성 | PASS | PASS 3/3 | 0 | 0 | scrollY 약 84px |
| 강남역 주변 | PASS | PASS 3/3 | 0 | 0 | scrollY 약 84px |

Regenerate 확인:

- 조건 화면 복귀 정상
- `이 조건으로 코스 만들기` 재실행 정상
- 결과 화면 복귀 정상
- timeline number 유지
- description density 유지
- placeholder 연속 노출 시 layout 깨짐 없음

관찰 이슈:

- `새 흐름 준비 중` pending label은 일부 cycle에서 확인됐지만, 전환이 빠른 케이스에서는 120ms snapshot에 잡히지 않았다.
- 기능적으로는 조건 화면 이동과 결과 재생성이 정상이며, stuck/중복 화면/empty 화면은 없었다.
- 실기기에서 pending 체감이 약하면 다음 polish에서 delay 또는 local transition 방식을 재검토할 수 있다.

## Viewport별 문제 여부

| 항목 | 390x844 | 360x740 |
|---|---:|---:|
| CTA 겹침 | 없음 | 없음 |
| bottom fixed action 겹침 | 없음 | 없음 |
| sheet overflow | 없음 | 없음 |
| selector 잘림 | 없음 | 없음 |
| result card 잘림 | 없음 | 없음 |

## 운영 안전 확인

- `/api/regions`: 200
- production `places` row count: 26381 유지
- production migration 실행 없음
- production places write 없음
- `docker compose down` 실행 없음
- saju containers running / healthy 상태 유지

## 발견 이슈

Blocker:

- 없음

Non-blocking:

- regenerate pending label은 전환 속도 때문에 항상 관찰되지는 않는다.
- 연남은 현재 추천 여행지 목록에 없어 이번 smoke 대상에서 제외했다.

## 배포 전 판단

현재 모바일 UX polish 범위는 운영 사용 가능한 상태로 판단한다.

단, 다음 단계에서 실제 실기기 Safari/Samsung Internet 기준으로 pending label 체감과 result card scroll 위치를 한 번 더 확인하는 것이 좋다.
