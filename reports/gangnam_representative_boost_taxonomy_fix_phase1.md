# gangnam_representative_boost_taxonomy_fix_phase1

## 목적

강남 support-slot assembly trace에서 `representative_support_not_selected`에 generic meal 후보가 포함되는 문제가 확인되어, `gangnam_representative_support_boost` taxonomy를 정밀화했다.

이번 작업은 penalty 확대가 아니라 boost 적용 조건 정리다.

## 수정 범위

- `remote_src/course_builder.py`
  - `_gangnam_representative_support_boost` 조건 정밀화.
  - `visit_role=meal` 또는 meal semantic 후보는 기본적으로 representative support boost 제외.
  - 단, 후보명 자체에 명확한 representative texture가 포함된 경우만 예외적으로 유지.

변경하지 않은 것:

- demote/penalty 확대 없음
- replacement 없음
- first-place 변경 없음
- 추천 엔진 rewrite 없음
- DB/migration/write 없음

## 수정 전 문제

assembly trace에서 다음 generic meal 후보가 `representative_support_not_selected`로 집계됐다.

- 가나돈까스의집
- 레드마블하우스
- 동달식당 강남본점

원인은 representative support boost가 COEX/Garosugil/Apgujeong/Bongeunsa texture뿐 아니라 일부 meal 후보에도 붙을 수 있는 조건이었다.

## 적용한 taxonomy

### boost 제외

아래 조건이면 boost 제외:

- `visit_role == meal`
- 또는 `_is_meal_semantic_candidate(place) == True`
- 후보명 자체에 명확한 representative texture가 없는 경우

### boost 유지

아래 texture는 유지:

- COEX / Starfield / 별마당
- 신사동 / 가로수길
- 압구정 / 로데오 / 청담
- 봉은사 / 선정릉 / 선릉과 정릉
- 플랫폼엘 같은 lifestyle/gallery support
- 에이비카페 같은 curated cafe/walk support

## backend deploy

backend-only deploy 수행:

```bash
docker compose -p travel_service_prod build travel-backend
docker compose -p travel_service_prod up -d --no-deps travel-backend
```

`docker compose down`은 사용하지 않았다.

## runtime smoke

대상:

- 강남역 주변 12회
- 성수 감성 카페 5회
- 북촌 한옥 산책 5회

결과:

| 대상 | HTTP 200 | NO_COURSE | places_empty | trace events |
|---|---:|---:|---:|---:|
| 강남 | 12/12 | 0 | 0 | 48 |
| 성수 | 5/5 | 0 | 0 | 0 |
| 북촌 | 5/5 | 0 | 0 | 0 |

성수/북촌은 강남 family trace 대상이 아니므로 assembly trace events는 0이 정상이다.

## generic meal boost 제거 여부

강남 12회 smoke 기준:

| 항목 | 결과 |
|---|---:|
| boosted generic meal 후보 | 0 |
| generic meal 후보의 `gangnam_representative_support_boost` | 0.0 |

boost가 제거된 후보 예:

- 가나돈까스의집
- 레드마블하우스
- 동달식당 강남본점
- 알라프리마
- 마초쉐프 강남본점
- 강남진해장
- 고깃집열
- 진수사

## boost 유지 후보

강남 12회 smoke 기준 boost가 유지된 후보:

| 후보 | boost trace count |
|---|---:|
| 플랫폼엘 | 15 |
| 서울 선릉과 정릉 [유네스코 세계유산] | 12 |

해석:

- generic meal 후보에 붙던 representative boost는 제거됐다.
- lifestyle/gallery 및 heritage support texture는 유지됐다.

## weak support 변화

강남 weak selected 후보:

| 후보 | count |
|---|---:|
| 알라프리마 | 12 |
| 국가무형유산전수교육관 | 11 |
| 레드마블하우스 | 4 |
| 국기원(세계태권도본부) | 4 |
| 고깃집열 | 4 |
| 진수사 | 4 |

이전 trace와 비교하면:

- 국가무형유산전수교육관은 12/12에서 11/12로 소폭 감소.
- 플랫폼엘이 1회 selected되어 representative/lifestyle support 후보가 실제 선택되는 샘플이 생김.
- 그러나 generic meal support 반복은 여전히 남아 있음.

판단:

- 이번 수정은 boost taxonomy 오류를 해결한 것이며 weak support 전체 해결은 아니다.
- 남은 문제는 `meal/cafe support slot`의 candidate depth/order 문제에 가깝다.
- 다음 단계는 penalty 확대보다 support role/pool ordering 또는 representative support coverage 보강 여부를 확인하는 편이 안전하다.

## first-place 안정성

강남 first-place 분포:

| first-place | count |
|---|---:|
| 코엑스 아쿠아리움 | 4 |
| 코엑스동측광장 | 4 |
| 압구정곱창 | 3 |
| 함흥면옥 압구정점 | 1 |

first-place 로직은 변경하지 않았고, runtime에서 NO_COURSE/places_empty도 재발하지 않았다.

## side effect

성수:

- 5/5 정상 생성
- NO_COURSE 0
- places_empty 0
- 강남 boost trace 0

북촌:

- 5/5 정상 생성
- NO_COURSE 0
- places_empty 0
- 강남 boost trace 0

사주 영향 없음.

## 운영 안전성

- production migration 실행 없음
- production places write 없음
- raw overwrite 없음
- full reload 없음
- docker compose down 없음
- saju 영향 없음

## 다음 단계 권고

1. generic meal boost 제거 상태는 유지.
2. 강남 weak support를 더 줄이려면 penalty 확대보다 `meal/cafe support slot`의 candidate ordering과 representative cafe/walk support depth를 먼저 확인.
3. 국가무형유산전수교육관은 boost 문제가 아니라 `morning_2` slot candidate depth/order 문제로 남아 있으므로 별도 support pool 보강 또는 ordering 분석이 필요.
4. global demote, replacement, first-place 변경은 계속 금지.

