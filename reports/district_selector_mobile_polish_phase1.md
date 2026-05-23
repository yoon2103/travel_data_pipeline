# district_selector_mobile_polish_phase1

## 목표

서울 curated district가 늘어난 상태에서 모바일 여행지 선택 바텀시트의 밀도와 선택 상태 가시성을 개선한다.

이번 작업은 HomeScreen selector UI polish만 다룬다. 추천 엔진, district/family mapping, route logic, DB, migration은 변경하지 않는다.

## 수정 파일

- `frontend/src/screens/day-trip/HomeScreen.jsx`
- `travel_service_handoff_master_2026-05-18.md`

## 개선 내용

- 추천 여행지 리스트 gap을 `8px`에서 `7px`로 줄여 밀도를 소폭 개선했다.
- 카드 padding을 `14px 16px`에서 `12px 14px`로 조정했다.
- touch target은 `minHeight: 66px`로 유지해 모바일 터치 안정성을 확보했다.
- 선택 상태는 강한 chip/badge 대신 은은한 gradient background, blue border, 왼쪽 3px accent bar, check icon으로 표현했다.
- 카드 shadow를 selected/unselected로 분리해 선택 상태를 더 읽기 쉽게 했다.
- title/subtitle에 `minWidth: 0`, `wordBreak: keep-all`, `overflowWrap: anywhere`를 적용해 긴 district 이름의 줄바꿈 안정성을 높였다.
- `기본 분위기 추천:` 문구는 `기본 분위기 ·`로 줄여 badge처럼 과하게 보이지 않게 했다.
- `aria-pressed`를 추가해 선택 상태 접근성을 보강했다.

## Mobile density 판단

대상 district:

- 명동
- 인사동
- 북촌
- 성수
- 한남
- 강남
- 한강
- 여의도
- 을지로

판단:

- 카드 높이는 과도하게 줄이지 않고 tap target을 유지했다.
- 긴 이름은 줄바꿈을 허용하되 카드 내부에서 깨지지 않도록 조정했다.
- selector 밀도는 개선하되, 읽기 어려운 compact chip grid로 바꾸지는 않았다.

## Selected state 방향

- 선택 상태는 현재보다 명확하지만 과한 badge/chip 느낌은 피했다.
- blue accent는 border/check/icon background/left bar로 제한했다.
- 선택된 district가 목록 안에서 빠르게 식별되도록만 보정했다.

## CTA 영향

- 첫 화면 CTA 구조는 변경하지 않았다.
- 여행지 선택은 바텀시트 내부 변경이라 HomeScreen CTA 위치와 departure time-band mapping에는 영향이 없다.

## 안전 정책

- 추천 엔진 변경 없음
- district/family mapping 변경 없음
- hardcoded route insertion 없음
- fake district 추가 없음
- production migration 없음
- production places write 없음
- docker compose down 없음
- 사주 서비스 영향 없음

## 검증 결과

- frontend build: 완료
- iPhone-style viewport `390x844`: 여행지 선택 sheet 노출, district sample 12개 확인, card height 66~80px
- Galaxy-style viewport `360x740`: 여행지 선택 sheet 노출, district sample 12개 확인, card height 66~80px
- 성수 선택 후 홈 CTA top 517px로 유지되어 CTA 밀림 없음
- selected item `aria-pressed=true` 확인
- `/api/regions`: 200 확인
- production `places` row count: 26381 유지
- migration 실행 없음
- `docker compose down` 실행 없음
- saju container 상태 영향 없음
