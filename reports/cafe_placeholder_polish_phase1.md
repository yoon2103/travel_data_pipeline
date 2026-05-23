# cafe_placeholder_polish_phase1

## 목표

모바일 코스 결과 화면에서 이미지가 없는 카페 카드가 너무 허전하게 보이는 문제를 줄인다.

이번 작업은 실제 장소 이미지 추가가 아니다. production image write, migration, scraping, 외부 이미지 자동 연결 없이 CSS 기반 neutral abstract placeholder만 개선한다.

## 수정 파일

- `frontend/src/screens/day-trip/CourseResultScreen.jsx`
- `travel_service_handoff_master_2026-05-18.md`

## 기존 문제

이미지가 없는 카페 카드는 기존에 warm gradient와 coffee icon만 노출됐다.

문제:

- 카페 district에서 2~3개 카드가 연속 placeholder일 때 화면이 비어 보인다.
- 실제 사진이 없는 상태를 안전하게 처리하고 있지만, 모바일 카드 체감은 약하다.
- 그렇다고 stock photo나 임의 카페 사진을 넣으면 mismatch/fake image 리스크가 크다.

## 개선 방향

카페 role placeholder에만 아래 요소를 추가했다.

- 더 부드러운 neutral cafe tone gradient
- 약한 diagonal pattern
- white translucent icon shell
- 미세한 line accent
- expanded card에서는 `카페 이미지 준비 중`으로 role-specific label 표시

다른 role placeholder는 큰 변경 없이 유지했다.

## 안전 정책

코드 주석에 다음 원칙을 명시했다.

```text
Image-missing cafe cards must stay abstract.
Do not use fake cafe photos or unapproved stock images here.
```

운영 원칙:

- 실제 장소처럼 보이는 fake photo 금지
- generic stock photo 금지
- blog collage/Pinterest/pinimg 금지
- approved image review 전까지 외부 image 자동 연결 금지
- placeholder는 특정 장소가 아니라 image missing 상태를 부드럽게 표시하는 neutral UI로만 사용

## 모바일 확인 항목

코드 기준 확인:

- small card: 기존 `60x60` 유지
- candidate sheet medium card: 기존 `72x72` 유지
- expanded card: 기존 `min-h-[150px]` 유지
- 카드 높이 증가 없음
- title/description 영역 구조 변경 없음
- role별 fallback resolver 변경 없음

## 검증 결과

- frontend Docker build 성공
- production frontend container만 재배포
- production `places` row count 변화 없음
- production migration 실행 없음
- production places write 없음
- raw overwrite 없음
- full reload 없음
- scraping 없음
- 추천 엔진 수정 없음
- 코스 로직 수정 없음
- 사주 영향 없음

## 다음 단계

1. 실제 이미지 보강은 image review persistence migration 이후에만 진행한다.
2. 연남/한남/강남/북촌/성수 순서로 approved image candidate를 늘린다.
3. placeholder polish는 cafe role에만 유지하고, 다른 role은 별도 phase에서 판단한다.
