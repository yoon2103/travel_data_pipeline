# 대표 카페 이미지 품질 안정화 phase1

## 목적

전국 자동 image enrichment보다 성수, 한남, 북촌, 연남, 을지로, 강남, 부산 전포, 부산 광안리처럼 체감에 직접 영향을 주는 대표 카페 district의 이미지 품질 정책을 먼저 안정화한다.

이번 phase는 read-only audit과 정책 정리 단계다. production migration, production `places` write, raw overwrite, full reload, scraping, 추천 엔진 수정은 수행하지 않았다.

## 현재 카페 image 품질 문제 요약

운영 `places`를 read-only로 감사했다.

- 대상 district: 성수, 한남, 북촌, 연남, 을지로, 강남, 부산 전포, 부산 광안리
- 총 카페 후보: 247건
- image missing: 67건
- detected generic fallback URL: 0건
- detected mismatch/license-risk URL: 0건
- image가 있는 후보는 대부분 `tong.visitkorea.or.kr` 기반 TourAPI 이미지였다.

| district | candidates | image missing | icon fallback ratio |
|---|---:|---:|---:|
| 성수 | 99 | 25 | 25.25% |
| 한남 | 8 | 3 | 37.50% |
| 북촌 | 31 | 9 | 29.03% |
| 연남 | 22 | 10 | 45.45% |
| 을지로 | 12 | 3 | 25.00% |
| 강남 | 47 | 14 | 29.79% |
| 부산 전포 | 18 | 3 | 16.67% |
| 부산 광안리 | 10 | 0 | 0.00% |

Audit output:

- `qa_reports/cafe_image_quality_phase1/cafe_image_quality_results_20260521_105455.csv`
- `qa_reports/cafe_image_quality_phase1/cafe_image_quality_samples_20260521_105455.csv`
- `qa_reports/cafe_image_quality_phase1/cafe_image_quality_summary_20260521_105455.json`
- `qa_reports/cafe_image_quality_phase1/cafe_image_quality_summary_20260521_105455.md`

## Fallback 정책

카페 카드 이미지 우선순위는 다음 순서로 둔다.

1. approved HIGH confidence image
2. existing curated image
3. safe neutral cafe fallback
4. icon fallback

중요 원칙:

- 잘못된 이미지 제거가 이미지 개수보다 우선이다.
- generic stock, blog collage, Pinterest/pinimg, 광고 배너, 다른 도시/다른 지점 mismatch 이미지는 사용하지 않는다.
- image review gate에서 승인된 image만 production candidate image로 쓸 수 있다.
- safe neutral cafe fallback은 특정 장소의 실제 이미지처럼 보이면 안 된다.
- image가 없다고 바로 fake image를 넣지 않는다.

## Approved image 우선 사용 가능 후보

이전 image review gate simulation 기준으로 다음 4건은 HIGH confidence image 후보가 있었다.

| candidate | status | note |
|---|---|---|
| 낫배드커피 도산 | IMAGE_APPROVED_SIMULATED | HIGH confidence, no production write |
| 젠젠 성수점 | IMAGE_APPROVED_SIMULATED | HIGH confidence, no production write |
| 카페 공명 연남점 | IMAGE_APPROVED_SIMULATED | HIGH confidence, no production write |
| 크림시크 | IMAGE_APPROVED_SIMULATED | HIGH confidence, no production write |

다만 이 후보들은 아직 production에서 바로 우선 사용하면 안 된다.

이유:

- `staging_external_places` image review persistence migration이 아직 적용되지 않았다.
- 실제 reviewer approval write가 수행되지 않았다.
- current state는 simulation/rehearsal이며 production `places` write는 0건이다.

따라서 현재 정책은 “사용 가능”이 아니라 “migration 이후 approved image 우선 사용 후보”로 둔다.

## Icon fallback 개선 방향

현재 `CourseResultScreen.jsx`는 이미지가 없을 때 `PlaceholderVisual`을 사용한다.

현재 구조:

- cafe: 커피 아이콘 + warm gradient
- meal: 식사 아이콘 + warm gradient
- history/night/sea/default role별 gradient

phase1 판단:

- 지금 즉시 실제 사진 fallback을 넣는 것은 mismatch risk가 크다.
- safe neutral cafe fallback은 CSS 기반 abstract placeholder로 유지하는 것이 안전하다.
- 다음 단계에서 개선한다면 사진이 아니라 neutral background, soft gradient, skeleton/fade 정도가 적절하다.
- 특정 카페 내부처럼 보이는 stock image는 금지한다.

## 모바일 UX 영향

카페 카드에서 image missing이면 현재는 사진 대신 역할별 placeholder가 노출된다.

체감 리스크:

- 연남/한남/강남/북촌은 icon fallback 비율이 높아 감성 카페 district의 첫인상이 약해질 수 있다.
- 광안리는 image missing 0건이라 현재 우선순위가 낮다.
- 부산 전포는 missing 16.67%로 비교적 안정적이다.
- 성수는 candidate pool이 크지만 missing 25.25%라 대표 카페 후보 중심 image review가 효과적이다.

## 다음 단계 권고

1. migration apply 전에는 approved simulation image를 production card에 연결하지 않는다.
2. 먼저 `staging_external_places` image review columns migration을 승인할지 GO/NO-GO 판단한다.
3. migration 이후 HIGH confidence image 4건을 실제 reviewer approve flow로 재검증한다.
4. district별 우선순위는 연남, 한남, 강남, 북촌, 성수 순서가 합리적이다.
5. safe neutral cafe fallback은 frontend CSS placeholder 개선으로만 진행하고, 실제 사진 fallback은 별도 승인 전까지 보류한다.

## Safety

- production migration 실행 없음
- production `places` write 없음
- raw overwrite 없음
- full reload 없음
- scraping 없음
- 추천 엔진 수정 없음
- 사주 영향 없음
