# mobile_cta_polish_phase1

## 목표

모바일 첫 화면에서 코스 생성 CTA가 선택 흐름의 마지막 행동으로 더 명확하게 보이도록 개선한다.

이번 작업은 HomeScreen CTA UI polish만 다룬다. 추천 엔진, 코스 생성 로직, departure time-band mapping, DB, migration은 변경하지 않는다.

## 수정 파일

- `frontend/src/screens/day-trip/HomeScreen.jsx`
- `travel_service_handoff_master_2026-05-18.md`

## 기존 문제

- 출발지와 시간대 선택 이후 CTA가 시각적으로 약해 선택 흐름의 마지막 단계처럼 보이지 않았다.
- 모바일 첫 화면에서 CTA가 일반 버튼처럼 평평하게 보여 행동 유도가 약했다.
- 클릭 직후 상태 feedback이 없어 느린 네트워크에서 중복 탭 가능성이 있었다.

## 개선 내용

- CTA 주변에 아주 약한 blue-tint panel을 추가해 selector 흐름의 마지막 단계로 묶었다.
- CTA 버튼 높이를 `minHeight: 62`로 조정해 모바일 tap target을 강화했다.
- button gradient, subtle shadow, inset highlight를 추가해 존재감을 높였다.
- `aria-busy`와 `코스 준비 중` 상태를 추가해 클릭 직후 feedback을 제공했다.
- loading 중 버튼을 비활성화해 중복 탭을 줄였다.
- 화면 전환 후 loading reset timer가 남지 않도록 cleanup을 추가했다.
- safe-area bottom padding을 CTA wrapper에 반영했다.

## 모바일 spacing 판단

- time-band accordion은 기본 collapsed 상태를 유지한다.
- CTA wrapper padding은 작게 유지해 첫 화면 높이를 과도하게 늘리지 않는다.
- 새 설명 문구는 추가하지 않았다.
- CTA는 district/time-band 선택 이후 자연스럽게 이어지는 마지막 action으로 보이도록만 조정했다.

## Accessibility 확인 항목

- disabled 상태는 `not-allowed` cursor와 muted color로 구분된다.
- loading 상태는 `aria-busy=true`와 `코스 준비 중` label로 표시된다.
- tap target은 기존 58px에서 62px 이상으로 커졌다.
- 텍스트 contrast는 흰색/blue gradient 조합으로 유지된다.

## 안전 정책

- 추천 엔진 변경 없음
- 코스 로직 변경 없음
- departure mapping 변경 없음
- production migration 없음
- production places write 없음
- 사주 서비스 영향 없음

## 검증 결과

- frontend build: 완료
- deployed bundle 반영: 확인
- iPhone-style viewport `390x844`: CTA top 517px, height 62px, initial viewport 내 노출 확인
- Galaxy-style viewport `360x740`: CTA top 488px, height 62px, initial viewport 내 노출 확인
- `/api/regions`: 200 확인
- production `places` row count: 26381 유지
- migration 실행 없음
- `docker compose down` 실행 없음
- saju container 상태 영향 없음
