# result_card_readability_phase1

## 목표

모바일 코스 결과 화면에서 장소 카드의 스캔성과 정보 hierarchy를 개선한다.

이번 작업은 `CourseResultScreen` 카드 UI polish만 다룬다. 추천 엔진, route assembly, 후보 생성, DB, migration은 변경하지 않는다.

## 수정 파일

- `frontend/src/screens/day-trip/CourseResultScreen.jsx`
- `travel_service_handoff_master_2026-05-18.md`

## Readability 개선 내용

- 타임라인 점을 단순 dot에서 순번이 보이는 circle로 변경했다.
- 시간 텍스트를 약간 줄이고 line-height를 정리해 카드 제목보다 덜 튀게 했다.
- 카드 title은 `font-extrabold`, `leading-snug`로 유지해 장소명이 먼저 읽히게 했다.
- 메타 라인은 `role label · duration` 구조로 정리했다.
- 카드 header padding을 소폭 조정해 이미지/placeholder/title 간 간격을 안정화했다.
- 이동 시간 pill은 조금 더 compact하게 조정했다.

## Description density 조정

- 펼친 카드 설명은 약 5줄 높이 기준으로 제한했다.
- 이미지/placeholder와 description 사이 margin을 소폭 줄였다.
- 긴 설명이 한 번에 크게 쏟아지는 느낌을 줄이고 핵심 정보만 먼저 보이게 했다.

## Route flow readability

- 각 장소 번호를 타임라인 축에 표시해 1번/2번/3번 흐름 인지를 강화했다.
- 타임라인 연결선 색을 `#BFDBFE`로 낮춰 카드 내용을 방해하지 않게 했다.
- card shadow는 유지하되 약간 낮춰 카드가 과하게 무겁지 않게 했다.

## Regenerate scanability 판단

- regenerate 후 같은 구조의 카드가 반복되어도 순번, role/duration, 높이가 제한된 설명이 먼저 읽히도록 정리했다.
- placeholder + 긴 설명 조합에서 텍스트 덩어리 피로가 줄어드는 방향이다.
- regenerate UX pending/loading 변경은 유지하고 추가 로직 변경은 하지 않았다.

## Accessibility 확인 항목

- title contrast 유지
- 작은 meta text는 `12px` 이상 유지
- 이동시간 pill은 `11px`이지만 보조 정보로만 사용
- 카드 tap 영역 및 expand/collapse 버튼 영역 유지
- route order number는 시각 보조이며 기존 시간 텍스트도 유지

## 안전 정책

- 추천 엔진 변경 없음
- route assembly 수정 없음
- fake 장소 추가 없음
- production migration 없음
- production places write 없음
- docker compose down 없음
- 사주 서비스 영향 없음

## 검증 결과

- frontend build: 완료
- mobile viewport `390x844` 확인: 완료
- result card role/duration meta 노출 확인
- timeline number 5개 확인
- description maxHeight `105px` 적용 확인
- regenerate 3회 smoke: pending label 표시, 조건 화면 이동, 결과 재생성 확인
- 3회 모두 `NO_COURSE`/후보 부족 화면 미발생
- `/api/regions`: 200 확인
- production `places` row count: 26381 유지
- migration 실행 없음
- `docker compose down` 실행 없음
- saju container 상태 영향 없음
