# regenerate_mobile_ux_phase1

## 목표

모바일 실사용 기준으로 regenerate/다른 분위기 추천 동작의 체감 품질을 개선한다.

이번 작업은 UI/UX polish만 다룬다. 추천 엔진, 코스 생성 로직, route assembly, DB, migration은 변경하지 않는다.

## 수정 파일

- `frontend/src/screens/day-trip/CourseResultScreen.jsx`
- `travel_service_handoff_master_2026-05-18.md`

## 기존 문제

- regenerate 클릭 직후 화면이 바로 전환되어 버튼 feedback이 약했다.
- 코스 생성 loading 화면이 spinner 중심이라 멈춘 느낌이 날 수 있었다.
- 이미지가 없는 카페 카드가 여러 번 반복되면 같은 카드처럼 보일 수 있었다.
- 결과 카드 교체 시 visual transition이 거의 없어 abrupt하게 느껴질 수 있었다.

## 개선 내용

### Regenerate loading polish

- `다른 분위기 추천` 클릭 시 짧은 pending 상태를 추가했다.
- pending 중 label은 `새 흐름 준비 중`으로 바뀐다.
- `aria-busy`와 disabled 상태를 사용해 중복 탭을 줄인다.
- 420ms 후 기존 `onRemakeMood` 흐름으로 이동한다. 사용자가 feedback을 인지할 수 있는 최소 지연으로 제한했다.
- timer cleanup을 추가해 화면 전환 후 pending timer가 남지 않게 했다.

### Loading screen polish

- 기존 spinner-only 화면을 유지하지 않고, route skeleton card 3개를 추가했다.
- skeleton shimmer는 최소 수준으로 적용했다.
- 문구는 과장 없이 `새 코스 흐름을 맞추는 중이에요`, `장소와 이동 순서를 정리하고 있어요.`로 제한했다.

### Transition polish

- 결과 리스트에 `course-soft-in` fade/translate transition을 추가했다.
- motion은 220ms로 짧게 제한했다.

### Placeholder repetition 완화

- 카페 placeholder에 deterministic tone variation 3종을 추가했다.
- variation은 place id/name 기반으로 고정되어 과한 random 느낌을 만들지 않는다.
- 실제 사진, stock image, 외부 이미지 자동 연결은 사용하지 않는다.

## Mobile stability 확인 항목

- regenerate 버튼 높이 유지
- bottom fixed action 영역 유지
- scroll reset/accordion 상태 로직 변경 없음
- safe-area offset 변경 없음
- 추천 엔진 payload 변경 없음

## 안전 정책

- 추천 엔진 rewrite 없음
- hardcoded route insertion 없음
- fake 장소 추가 없음
- production migration 없음
- production places write 없음
- docker compose down 없음
- 사주 서비스 영향 없음

## 검증 결과

- frontend build: 완료
- deployed bundle 반영: 확인
- mobile viewport `390x844` 확인: 완료
- 성수 감성 카페 기준 regenerate 3회 smoke: loading skeleton 표시, pending label 표시, 결과 화면 복귀 확인
- 3회 모두 `NO_COURSE`/후보 부족 화면 미발생
- regenerate 후 result scrollY는 84px 수준으로 유지되어 과도한 top jump는 보이지 않음
- `/api/regions`: 200 확인
- production `places` row count: 26381 유지
- migration 실행 없음
- `docker compose down` 실행 없음
- saju container 상태 영향 없음
