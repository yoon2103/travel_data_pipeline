# Role Sequence Trace Phase1

## 목적

support-slot role diversity phase2로, aggressive role diversity 적용 전에 현재 route assembly가 어떤 support-slot role sequence를 만드는지 관찰 가능한 trace를 추가한다.

이번 단계는 추천 결과를 바꾸는 것이 아니라 observability 확보가 목적이다.

## 변경 파일

- `remote_src/recommendation_observability.py`
- `remote_src/course_builder.py`
- `travel_service_handoff_master_2026-05-18.md`

## Role Sequence Trace 항목

추가된 trace 항목:

```text
support_slot_role_sequence
support_slot_role_repetition
support_slot_indoor_count
support_slot_role_counts
support_slot_missing_preferred_roles
support_slot_role_balance_score
```

각 항목의 의미:

| trace | meaning |
|---|---|
| support_slot_role_sequence | 첫 장소를 제외한 support-slot role 순서 |
| support_slot_role_repetition | 같은 role이 연속된 구간 |
| support_slot_indoor_count | indoor/gallery 계열 support-slot 수 |
| support_slot_role_counts | support-slot role별 count |
| support_slot_missing_preferred_roles | walk/viewpoint/market/gallery/landmark_support 중 누락 role |
| support_slot_role_balance_score | repetition/indoor-heavy/narrow-role 기반 관찰용 balance score |

## Role Classifier Mapping

helper:

```text
summarize_support_slot_roles(selected_places)
```

role group:

| role | mapping source |
|---|---|
| cafe | 카페, coffee, 로스터, 베이커리, 찻집 |
| meal | 맛집, 식당, 음식, 국밥, 갈비, 해장, 분식, restaurant, meal |
| walk | 공원, 산책, 숲, 길, 거리, 골목, 수변, 해변, 호수, 강, 천, 해안 |
| viewpoint | 전망, 야경, 타워, 뷰, 대교, 루프탑, 전망대 |
| market | 시장, 마켓, 야시장 |
| gallery | 갤러리, 전시, 미술, 박물관, 문화, 공예, 체험 |
| landmark_support | 궁, 성, 사찰, 한옥, 역사, 유적, 전통 |
| indoor | 실내, 센터, 회관, 도서관, 아트홀, 라운지 |
| other | 위 mapping에 들어오지 않는 후보 |

주의:

- 이 classifier는 observability 전용이다.
- filtering/scoring에 사용하지 않는다.
- ambiguous category는 `other`로 남길 수 있다.
- `카페거리` 같은 street texture는 cafe stop repetition으로 잡히지 않도록 `walk`로 분리했다.

## Repetition Detection

현재 단계에서 탐지하는 것:

- same-role repetition
- indoor-heavy support slot
- support-role 부족
- role distribution narrowness

현재 단계에서 하지 않는 것:

- score 변경
- candidate 제거
- bounded replacement 실행
- route lock
- hard diversity 적용

## Current Role Sequence Examples

기존 mobile smoke의 성수 결과 샘플:

```text
서울숲 곤충식물원 -> 레이더 -> 뚝도지기 -> 성수동 카페거리 -> 모어딥 성수
```

관찰용 role sequence:

```text
anchor/main -> cafe -> meal -> walk -> cafe
```

판단:

- direct same-role repetition 없음
- cafe가 2회 나오지만 연속은 아님
- `성수동 카페거리`는 실제 카페 stop이 아니라 street/walk texture로 분리하는 것이 맞음

## Repetition Detection Example

예시 입력:

```text
anchor -> cafe -> cafe -> meal -> cafe
```

trace:

```json
{
  "support_slot_role_sequence": ["cafe", "cafe", "meal", "cafe"],
  "support_slot_role_repetition": [
    {
      "role": "cafe",
      "from_support_index": 1,
      "to_support_index": 2
    }
  ],
  "support_slot_indoor_count": 0,
  "support_slot_role_counts": {
    "cafe": 3,
    "meal": 1
  },
  "support_slot_missing_preferred_roles": [
    "gallery",
    "landmark_support",
    "market",
    "viewpoint",
    "walk"
  ]
}
```

## District별 Imbalance 사례

| district | likely imbalance | trace로 볼 항목 |
|---|---|---|
| 성수 | cafe/cafe, cafe/meal 반복 | cafe count, cafe repetition, missing walk/gallery |
| 북촌 | indoor/gallery 과다, cafe 부족 또는 indoor 연속 | indoor_count, gallery repetition, missing walk |
| 한남 | cafe/meal/lifestyle 편중 | cafe/meal count, missing gallery/walk |
| 강남 | meal/luxury/generic support 반복 | meal repetition, missing landmark_support |
| 부산 원도심 | market/meal 과점 또는 oldtown substitute 반복 | market/meal count, missing viewpoint/walk |
| 기장 | coastal role 대신 indoor/family slot 혼입 | indoor_count, missing viewpoint/walk |

## Indoor-heavy 사례 탐지

현재 trace에서는 `indoor`와 `gallery`를 indoor-heavy 관찰 대상으로 본다.

예:

```text
anchor -> gallery -> indoor -> gallery -> cafe
```

탐지:

```text
support_slot_indoor_count = 3
support_slot_role_balance_score 감소
```

주의:

- gallery/culture가 항상 나쁜 것은 아니다.
- 북촌/한남/성수에서는 gallery가 district identity와 맞을 수 있다.
- 따라서 이 값은 demote 근거가 아니라 관찰 지표다.

## Support-role 부족 사례

preferred support role:

```text
walk
viewpoint
market
gallery
landmark_support
```

누락 role은 아래 trace에 표시된다.

```text
support_slot_missing_preferred_roles
```

용도:

- `meal -> meal -> cafe`가 발생할 때 어떤 대체 role이 부족한지 확인
- district별 후보풀 보강 방향 판단
- future bounded replacement 후보 탐색 기준 준비

## Regenerate 관찰 결과

이번 단계에서는 production deploy를 하지 않았기 때문에 신규 trace를 production 응답에서 직접 관찰하지 않았다.

대신 기존 mobile smoke 기준으로 다음을 정리했다.

| district | observed risk | note |
|---|---|---|
| 성수 | cafe 반복 체감 가능 | 실제 샘플은 cafe가 2회이나 연속은 아님 |
| 북촌 | heritage/walk/cafe balance 필요 | indoor culture 연속 여부 추적 필요 |
| 한남 | cafe/meal/lifestyle 편중 가능 | gallery/walk support 추적 필요 |
| 강남 | meal/generic lifestyle 반복 가능 | landmark_support/walk 부족 추적 필요 |

## Future Soft-demote Proposal

이번 phase에서는 적용하지 않는다.

향후 안전한 범위:

1. same-role soft demote only
   - `meal -> meal`
   - `cafe -> cafe`
   - `indoor -> indoor`

2. support-slot only
   - first-place는 건드리지 않는다.

3. same-family better candidate가 있을 때만 bounded replacement
   - family 밖 drift 금지
   - replacement 최대 1회

4. district-specific exception 유지
   - 성수/연남 같은 cafe district는 cafe count 자체를 과도하게 줄이면 안 된다.
   - 북촌/한남의 gallery는 identity에 맞을 수 있으므로 일괄 demote 금지.

권장 penalty는 phase3에서 safe batch 후 결정한다.

## Current Risk

현재 남은 위험:

1. production에 trace를 배포하지 않아 runtime 응답 확인은 아직 없음
2. role classifier가 coarse helper라 ambiguous category는 `other`로 남을 수 있음
3. `visit_role`/`category` 품질이 후보별로 균일하지 않음
4. soft demote를 바로 적용하면 NO_COURSE/places_empty 재발 위험 있음

## 검증

수행한 검증:

```bash
python -m py_compile remote_src/recommendation_observability.py remote_src/course_builder.py
```

결과:

```text
PASS
```

helper smoke:

```text
anchor -> meal -> walk -> cafe
support_slot_role_repetition = []
support_slot_role_balance_score = 1.0
```

## Safety

이번 phase에서 수행하지 않은 작업:

- 추천 엔진 rewrite 없음
- hard route lock 없음
- fake diversity 없음
- production migration 실행 없음
- production places write 없음
- broad scoring rewrite 없음
- aggressive role replacement 없음
- docker compose down 없음
- saju 영향 없음

## 결론

role sequence trace는 observability-first 방향으로 최소 범위 추가됐다.

다음 단계는 이 trace를 production-safe deploy 후 소량 regenerate smoke에서 확인하고, 실제 repetition 빈도가 확인된 뒤에만 same-role soft demote를 검토하는 것이다.
