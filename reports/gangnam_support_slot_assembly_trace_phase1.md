# gangnam_support_slot_assembly_trace_phase1

## 목적

강남 representative support reinforcement 이후에도 weak support 후보가 유지되는 원인을 확인하기 위해 support-slot assembly ordering trace를 추가했다.

이번 phase는 observability 전용이다. score 변경, penalty 확대, replacement, first-place 변경은 적용하지 않았다.

## 변경 범위

- `remote_src/course_builder.py`
  - 강남 family support-slot assembly 단계에서 후보 정렬, weighted 선택 pool, 최종 selected candidate를 trace로 수집.
  - 기존 선택 로직과 score 계산은 변경하지 않음.
- `remote_src/recommendation_observability.py`
  - `summarize_gangnam_support_slot_assembly` helper 추가.
  - `recommendation_trace`에 assembly ordering trace 노출.

## 추가 trace 항목

- `support_slot_assembly_ordering_trace`
- `support_slot_candidate_order`
- `support_slot_candidate_score`
- `support_slot_selected_reason`
- `support_slot_rejected_reason`
- `support_slot_family_alignment`
- `support_slot_editorial_fit`

각 event에는 다음 정보를 포함한다.

- slot
- role_required
- selected_pool
- fallback_reason
- replacement_applied
- initial_selected_place
- selected_place
- top candidate order
- candidate_score
- editorial fit tag
- representative support boost
- editorial soft demote delta
- rejected reason

## 운영 배포

- backend-only deploy 수행.
- 명령:
  - `docker compose -p travel_service_prod build travel-backend`
  - `docker compose -p travel_service_prod up -d --no-deps travel-backend`
- `docker compose down` 미사용.
- production migration 미실행.
- production places write 없음.

## 운영 smoke

| 항목 | 결과 |
|---|---:|
| `/api/regions` | 200 |
| production places row count | 26381 |
| travel-backend-v2 | running |
| travel-frontend-v2 | running |
| saju containers | running |

## 강남 runtime smoke

조건:

- 강남역 주변 12회
- raw 저장 없음
- public API 기준

결과:

| 항목 | 결과 |
|---|---:|
| HTTP 200 | 12/12 |
| NO_COURSE | 0 |
| places_empty | 0 |
| trace events | 48 |
| 평균 trace events/run | 4 |

First-place 분포:

| first-place | count |
|---|---:|
| 코엑스동측광장 | 6 |
| 코엑스 아쿠아리움 | 4 |
| 압구정곱창 | 2 |

## slot ordering 관찰 결과

### morning_2

반복 selected:

- 국가무형유산전수교육관: 12/12

대표 관찰:

- 국가무형유산전수교육관이 `morning_2`에서 거의 항상 candidate order 1위로 남는다.
- score 예시는 `0.1785~0.2145`.
- 경쟁 후보는 예림당아트홀, GB성암아트홀, 논현문화마루도서관 등으로 대부분 weak culture/indoor 계열이며 score가 음수 또는 낮다.

해석:

- 이 slot의 문제는 replacement 부재보다 candidate ordering 자체다.
- weak public/training 후보가 tiny demote 이후에도 top ordering을 유지한다.
- representative support 후보가 같은 slot pool에 충분히 강하게 들어오지 못한다.

### lunch / afternoon_cafe

반복 selected:

- 알라프리마: 12/12
- 진수사: 8/12
- 고깃집열: 3/12
- 레드마블하우스: 1/12

대표 관찰:

- meal slot은 score 상위권이 대부분 generic meal 후보로 채워진다.
- `afternoon_cafe`에서도 실제 cafe/walk texture가 아니라 meal 후보가 반복되는 샘플이 많다.

해석:

- 강남 support 문제는 public/training만이 아니라 meal-heavy support pool issue도 함께 존재한다.
- 단, 이번 phase에서 meal demote 또는 role replacement는 적용하지 않았다.

### afternoon

반복 selected:

- 서울 선릉과 정릉 [유네스코 세계유산]: 다수
- 국기원(세계태권도본부): 일부

대표 관찰:

- 서울 선릉과 정릉이 candidate order 1위로 들어오는 경우에는 representative heritage support로 정상 선택된다.
- 국기원은 candidate order 2위 수준에서도 replacement 이후 선택되는 샘플이 있었다.

해석:

- representative candidate가 pool top에 있으면 선택 가능하다.
- 약한 후보가 유지되는 핵심은 representative 후보의 부재 또는 slot별 ordering 우위 부족이다.

## weak candidate selected reason

주요 weak selected 후보:

| 후보 | count | trace fit |
|---|---:|---|
| 국가무형유산전수교육관 | 12 | weak_public_training |
| 알라프리마 | 12 | weak_generic_meal |
| 진수사 | 8 | weak_generic_meal |
| 국기원(세계태권도본부) | 3 | weak_public_training |
| 고깃집열 | 3 | weak_generic_meal |
| 레드마블하우스 | 1 | weak_generic_meal |

원인:

- `morning_2`: weak public/training 후보가 score order 1위.
- `meal/cafe support`: generic meal 후보가 score 상위권을 과점.
- replacement가 아니라 weighted pool/order 자체에서 weak 후보가 강함.

## representative candidate rejected reason

trace상 `representative_support_not_selected`가 반복된 후보:

| 후보 | count |
|---|---:|
| 가나돈까스의집 | 24 |
| 레드마블하우스 | 23 |
| 플랫폼엘 | 14 |
| 서울 선릉과 정릉 [유네스코 세계유산] | 3 |
| 동달식당 강남본점 | 3 |

해석:

- 현재 trace 기준에서 `representative_support_not_selected`는 `gangnam_representative_support_boost > 0`인 후보를 의미한다.
- 일부 generic meal 후보도 boost 또는 representative signal을 받는 것으로 관찰되어, 다음 구현 전 boost term 범위 검증이 필요하다.
- 서울 선릉과 정릉은 정상 representative 후보이며, selected되지 않은 경우는 weighted choice 또는 slot timing 영향으로 보인다.

## weak support 유지 원인

현재 trace 기준 우선순위는 다음이다.

1. `morning_2` slot에서 representative 대체 후보 depth가 부족하거나 ordering이 약함.
2. 국가무형유산전수교육관이 weak demote 후에도 slot top candidate로 남음.
3. meal/cafe support slot에서 generic meal 후보가 score 상위권을 차지함.
4. representative support boost가 일부 generic meal 후보에도 적용될 가능성이 있어 boost taxonomy 재검토 필요.
5. selected/rejected 차이는 replacement 문제가 아니라 candidate ordering + weighted draw + slot timing 문제에 가깝다.

## future implementation 방향

권장:

- penalty 확대보다 먼저 `support-slot candidate ordering` 기준을 정리.
- 강남 `morning_2`에 COEX/Garosugil/Bongeunsa/Seonjeongneung/urban walk 후보가 실제 pool 상위에 들어오는지 coverage audit.
- `gangnam_representative_support_boost`가 generic meal 후보에 적용되는 조건 재검토.
- support-slot only 범위에서 `weak public/training` tiny demote를 확대하기보다 representative support candidate depth를 먼저 보강.

아직 금지:

- global demote
- penalty expansion
- replacement / bounded replacement
- first-place 변경
- broad scoring rewrite

## 안정성

- NO_COURSE: 0
- places_empty: 0
- production places row count: 26381 유지
- migration 실행 없음
- production places write 없음
- docker compose down 없음
- saju 영향 없음

