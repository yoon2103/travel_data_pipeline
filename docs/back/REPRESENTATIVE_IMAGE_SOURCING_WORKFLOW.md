# Production-grade Representative Image Sourcing Workflow

생성일: 2026-05-08

## 목적

대표 POI의 `IMAGE_MISSING` 병목을 해결하기 위해 운영 가능한 대표 이미지 sourcing / QA / review / rollback 정책을 정의한다.

현재 상태:

- representative governance 완료
- seed governance 완료
- overlay QA simulation 완료
- actual overlay 금지 상태
- 주요 blocker: 대표 이미지 승인 후보 없음

이번 문서는 설계 전용이다.

- 자동 이미지 promote 금지
- `places` update 금지
- actual promote 금지
- 이미지 자동 수집/등록 없음

## Representative Image Source 정책

### Source 분류

| source | 사용 가능 여부 | 용도 | 조건 |
|---|---|---|---|
| TourAPI | 가능 | 관광지 baseline 이미지 후보 | source payload, content id, 이미지 URL, 지역/명칭 검수 필수 |
| Manual curator | 가능 | 대표 이미지 수동 등록 | 출처/라이선스/품질 검수 필수 |
| 운영 업로드 | 가능 | 직접 촬영/권리 확보 이미지 | 업로드자, 원본 보관, 라이선스 기록 필수 |
| 외부 검색 기반 | 제한적 가능 | 후보 탐색 참고용 | 이미지 URL 직접 사용 금지, 원 출처와 라이선스 검수 필요 |
| Kakao/Naver Local API | 이미지 source로 부적합 | 장소 매칭/영업상태/리뷰 힌트 | Local 응답에 이미지 필드가 없거나 제한적 |
| AI generated image | 금지 | 대표 랜드마크 이미지로 사용 금지 | 실제 장소 왜곡 위험 |
| 무단 블로그/카페/SNS 이미지 | 금지 | 사용 금지 | 저작권/초상권/출처 불명확 |
| placeholder/example URL | 금지 | 테스트 외 사용 금지 | 실제 이미지 검증 불가 |

### Source별 운영 정책

#### TourAPI

사용 가능:

- 관광지/문화재/자연 명소의 baseline 대표 이미지
- `firstimage`, `firstimage2` 계열 후보

필수 검수:

- expected POI와 source name 일치
- 지역 일치
- 이미지가 본체 landmark인지 확인
- 숙박/상점/주차장/내부시설 오염 여부 확인
- 이미지 URL 유효성 확인

주의:

- TourAPI 후보도 자동 promote 금지
- `전주한옥마을 도서관`처럼 내부시설 이미지가 대표 POI를 오염시킬 수 있음

#### Manual Curator

사용 가능:

- 운영자가 출처와 품질을 확인한 외부 이미지 후보
- 직접 촬영 또는 사용권 확보 이미지

필수 입력:

- `image_url`
- `source_credit`
- `license_note`
- `curator_note`
- `image_source_url`
- `intended_role`
- `quality_note`

#### 운영 업로드

권장 장기 source:

- 운영자가 직접 업로드한 이미지
- 이미지 파일 자체를 통제 가능
- CDN/cache/rollback 관리 가능

필수:

- 원본 저장
- checksum
- 업로드자
- 촬영/권리 정보
- license note
- rollback 가능 버전

#### 외부 검색 기반

사용 원칙:

- 검색 결과는 후보 탐색용으로만 사용
- 원 페이지에서 사용 가능 권한을 확인해야 함
- hotlink 금지
- 크롤링/스크래핑 기반 무단 저장 금지

## QA 기준

대표 이미지 QA checklist:

| 기준 | PASS 조건 |
|---|---|
| Landmark 식별 가능 | 이미지에서 대상 명소를 명확히 알 수 있음 |
| 장소 정확도 | expected POI와 동일 장소 |
| 지역 정확도 | region_1 / region_2 일치 |
| 대표성 | 주변 시설이 아니라 본체/대표 전경 |
| 이미지 유형 | 관광지는 exterior/전경 우선 |
| 해상도 | 최소 800px 이상 권장, thumbnail은 별도 가능 |
| 밝기/선명도 | 심한 blur, 노출 실패 없음 |
| 광고/워터마크 | 광고 배너/워터마크/홍보물 중심 아님 |
| 사람/차량 비중 | 과도한 인물/차량 중심 아님 |
| 상업시설 오염 | 호텔/펜션/식당/상점/주차장 이미지 아님 |
| 출처 | source URL 또는 provider 기록 가능 |
| 라이선스 | 사용권/출처 표기 정책 확인 |
| rollback | 이전 이미지로 복원 가능 |

## Representative Image Approve 기준

`REPRESENTATIVE_IMAGE` 후보 approve 최소 조건:

- expected POI와 동일 장소임을 확인
- 대표 landmark가 식별 가능
- source_credit 존재
- license_note 또는 source policy 존재
- image_source_url 존재
- placeholder URL 아님
- 광고/워터마크/상업시설 오염 없음
- image_url이 http(s)이고 접근 가능
- 후보가 `PENDING_REVIEW`
- promote는 아직 실행하지 않음

approve 후 상태:

- `review_status=APPROVED`
- `promote_status=PENDING`
- `places.first_image_url`은 여전히 변경하지 않음

## Reject 사례

반드시 reject:

- `https://example.com/...` placeholder
- AI generated fake landmark
- 다른 지역의 동명 장소
- wrong landmark
- 경포대 대신 경포호수광장/주차장/호텔/식당 사진
- 숙박/상점/주변 비즈니스 사진
- 저해상도 또는 심한 blur
- 워터마크/광고/홍보 배너가 주요 피사체
- 출처/라이선스 불명확
- 무단 블로그/SNS hotlink
- 사람 얼굴이 과도하게 중심
- crop 때문에 landmark 식별 불가
- 지도 캡처/스크린샷
- 폐업/공사중/임시 시설 사진

## Provenance 구조

대표 이미지 후보 payload 권장 구조:

```json
{
  "enrichment_type": "REPRESENTATIVE_IMAGE",
  "expected_poi_name": "경포대",
  "representative_candidate_id": 6,
  "image": {
    "image_url": "https://cdn.example.com/representative/gyeongpodae.jpg",
    "thumbnail_url": "https://cdn.example.com/representative/gyeongpodae_thumb.jpg",
    "image_source_url": "https://source.example.com/page",
    "source_type": "MANUAL",
    "source_credit": "운영 직접 촬영",
    "license_note": "owned_by_operator",
    "copyright_owner": "operator",
    "captured_at": "2026-05-08",
    "uploaded_by": "ops_001",
    "checksum": "sha256:...",
    "width": 1600,
    "height": 1067,
    "mime_type": "image/jpeg"
  },
  "quality": {
    "quality_level": "REPRESENTATIVE_GRADE",
    "landmark_identifiable": true,
    "exterior_or_interior": "exterior",
    "watermark_detected": false,
    "advertisement_detected": false,
    "wrong_place_risk": false,
    "nearby_business_risk": false,
    "quality_note": "경포대 누정 외관과 주변 경관이 명확히 식별됨"
  },
  "review": {
    "review_status": "PENDING_REVIEW",
    "reviewer_id": null,
    "reviewed_at": null,
    "review_note": null
  },
  "safety": {
    "places_write": false,
    "seed_write": false,
    "promote": false,
    "rollback_supported": true
  }
}
```

## Manual Curator Workflow 강화안

### 현재 workflow

```text
add_representative_manual_enrichment.py
  -> representative_poi_candidates insert
  -> review_representative_candidate.py approve/reject/skip
```

### 강화 필요 항목

1. `image_source_url` 필수화
2. `license_note` 필수화
3. `source_credit` 필수화
4. `width`, `height`, `mime_type`, `checksum` 저장
5. placeholder domain reject
6. duplicate image hash check
7. quality checklist payload 저장
8. approve 전 URL 접근성 확인
9. 운영 업로드 source와 외부 URL source 분리
10. image 후보 approve 후에도 promote는 별도 단계로 유지

### 권장 CLI 예시

```bash
python -m batch.place_enrichment.add_representative_manual_enrichment \
  --expected-poi-name 경포대 \
  --image-url "https://cdn.example.com/representative/gyeongpodae.jpg" \
  --thumbnail-url "https://cdn.example.com/representative/gyeongpodae_thumb.jpg" \
  --image-source-url "operator-upload://gyeongpodae/original.jpg" \
  --source-credit "운영 직접 촬영" \
  --license-note "owned_by_operator" \
  --curator-note "경포대 외관과 주변 경관이 명확히 보이는 대표 이미지" \
  --quality-note "landmark exterior, no watermark, no nearby business contamination"
```

## Representative Image Quality Level

| level | 의미 | 처리 |
|---|---|---|
| `BLOCKED` | 사용 금지 | reject |
| `LOW` | 품질 낮음 | reject 또는 재검토 |
| `REVIEW_REQUIRED` | 판단 근거 부족 | manual review |
| `GOOD` | 사용 가능 | gallery 또는 보조 이미지 가능 |
| `REPRESENTATIVE_GRADE` | 대표 이미지로 적합 | primary 후보 가능 |

### 등급 기준

#### BLOCKED

- wrong landmark
- 저작권/출처 불명확
- placeholder
- AI generated fake
- 숙박/상점/주차장 오염

#### LOW

- 해상도 낮음
- 너무 어둡거나 흐림
- landmark 일부만 보임
- crop이 심함

#### REVIEW_REQUIRED

- 장소는 맞아 보이나 대표성이 애매함
- 내부시설인지 본체인지 불명확
- 출처 정책 확인 필요

#### GOOD

- 장소 정확
- 화질 양호
- 출처 확인
- 대표 이미지로도 가능하지만 더 좋은 후보가 있을 수 있음

#### REPRESENTATIVE_GRADE

- landmark 식별 명확
- 전경/외관 중심
- 품질 좋음
- 출처/라이선스 명확
- primary image 후보로 적합

## Storage 전략

### External URL only

장점:

- 구현 간단
- 저장 비용 없음

단점:

- 링크 깨짐
- hotlink/저작권 리스크
- 이미지 교체/삭제 통제 불가

권장:

- 초기 staging 후보에는 가능
- production primary image에는 비권장

### Local Cache

장점:

- 원본 URL 장애 완화
- checksum/metadata 관리 가능

단점:

- 저장소 관리 필요
- 저작권 준수 필요

권장:

- 검수된 이미지에 한해 cache 가능

### CDN

장점:

- 운영 안정성 높음
- 속도/캐시/버전 관리 가능
- rollback 쉬움

단점:

- 업로드/관리 workflow 필요

권장:

- production 대표 이미지 최종 목표

### Metadata Only

장점:

- 저작권 리스크 낮음
- 후보 검수 관리 용이

단점:

- 실제 서비스 표시에는 별도 image 필요

권장:

- review 단계에서 source tracking용으로 사용

## Image Rollback 전략

대표 이미지 반영 전 snapshot:

- 기존 `places.first_image_url`
- 기존 `places.first_image_thumb_url`
- promoted image candidate id
- source_credit/license payload
- reviewer_id/reviewed_at
- promote reason
- checksum

rollback 조건:

- wrong landmark 확인
- 저작권/출처 문제
- 이미지 깨짐
- 사용자/운영자 신고
- QA에서 이미지 오염 확인
- 더 낮은 품질로 교체된 사실 확인

rollback 방식:

- `places.first_image_url` 이전 값 복원
- image candidate `promote_status=ROLLED_BACK`
- rollback log 저장
- CDN 사용 시 이전 asset version 복원

## 경포대 운영 예시

### 현재 상태

- representative candidate `6`: APPROVED
- overview candidate `116`: APPROVED
- image candidate `115`: REJECTED
- seed candidate `1`: NEEDS_REVIEW
- overlay readiness: NOT_READY
- blocker: `IMAGE_MISSING`

### 운영 가능한 이미지 후보 조건

경포대 이미지는 아래 조건을 만족해야 한다.

- 경포대 누정 또는 본체 landmark가 명확히 보임
- 경포호수광장/주차장/호텔/식당 사진이 아님
- 출처가 명확함
- 사용권 확인 가능
- 워터마크/광고 없음
- 운영 업로드 또는 TourAPI image review 통과

### 권장 흐름

1. TourAPI `강릉 경포대` 이미지 후보를 수동으로 확인한다.
2. 적합하면 manual image candidate로 등록한다.
3. 부적합하면 운영 업로드 이미지를 준비한다.
4. `source_credit`, `license_note`, `image_source_url`을 포함한다.
5. review에서 `REPRESENTATIVE_GRADE` 또는 `GOOD` 이상만 approve한다.
6. approve 후 seed overlay simulation을 다시 실행한다.
7. image gap이 해소된 뒤에도 actual promote는 별도 dry-run과 QA 이후에만 검토한다.

### 경포대 reject 예시

reject:

- `example.com` placeholder
- 경포호수광장만 보이는 사진
- 경포대 주변 호텔/카페 사진
- 주차장 입구 사진
- 다른 지역 경포대/동명 장소
- 워터마크가 크게 있는 블로그 이미지

## 위험 요소

- 이미지 저작권/라이선스 검수 없이 production에 쓰면 운영 리스크가 크다.
- TourAPI 이미지도 장소명/지역 오매칭 가능성이 있다.
- 외부 URL만 쓰면 링크 깨짐과 hotlink 리스크가 있다.
- AI 생성 이미지는 실제 장소 신뢰성을 훼손한다.
- 대표 이미지가 잘못되면 추천 품질보다 더 즉각적으로 사용자 신뢰를 떨어뜨린다.
- image approve와 places promote를 같은 단계로 묶으면 rollback이 어려워진다.

## 다음 작업 제안

1. `add_representative_manual_enrichment.py`에 `image_source_url`, `license_note`, placeholder domain reject를 추가한다.
2. TourAPI `강릉 경포대` image 후보를 review-only로 다시 확인한다.
3. 실제 운영 가능한 경포대 이미지 URL을 manual candidate로 등록한다.
4. image candidate approve 후 seed overlay simulation을 재실행한다.
5. production primary image는 장기적으로 CDN/운영 업로드 기반으로 전환한다.
