# 여행 코스 추천 서비스 인수인계 MASTER 문서

작성일: 2026-05-18  
목적: 새 대화창에서도 현재 프로젝트의 목적, 구현 의도, 완료 내역, 남은 과제, 운영 주의사항, Codex 진행 방식까지 끊김 없이 이어가기 위한 단일 인수인계 문서

---

## 0. 가장 중요한 결론

현재 프로젝트는 단순한 장소 추천 서비스가 아니라, **사용자가 선택한 지역/분위기/시간대에 맞춰 실제 여행자가 만족할 만한 대표 코스 흐름을 만들어주는 서비스**를 목표로 한다.

현재까지의 큰 방향은 다음과 같이 정리된다.

```text
팀장 curated knowledge
>
외부 verified API
>
공공데이터 fallback
```

공공데이터는 데이터 양은 많지만 다음 한계가 있다.

- 실제 인기 장소 판단이 약함
- 야간/데이트/감성/드라이브 흐름이 약함
- 공공시설, 문화센터, 아트홀, 체험관, 도서관류가 여행지처럼 섞임
- 운영시간 신뢰도가 낮음
- 이미지 품질이 약함

따라서 앞으로는 **공공데이터를 기본 재료로 쓰되, 최종 추천 우선순위는 curated representative layer와 외부 verified API를 더 강하게 반영**해야 한다.

---

## 1. 프로젝트 목적과 방향성

### 1.1 서비스 목적

사용자가 지역과 취향을 고르면 다음을 만족하는 여행 코스를 생성한다.

- 실제 사람들이 기대하는 대표 장소 중심
- 지역 정체성이 살아 있는 흐름
- 아침/낮/저녁 시간대에 어울리는 코스
- 관광지, 산책, 카페, 식사, 야경 등 역할이 균형 잡힌 코스
- 모바일에서 바로 사용할 수 있는 간단한 UX
- NO_COURSE, places=[], 이상한 장소 노출 최소화

### 1.2 현재 서비스의 핵심 방향

초기에는 공공데이터 기반 후보에서 코스를 조합하는 구조였지만, 실기기 테스트를 통해 다음 문제가 확인되었다.

- 서울 default가 너무 넓어 정체성 혼합 발생
- 야간/저녁 시간대에서 운영시간 충돌 발생
- 특정 후보가 first-place로 고정됨
- 도서관, 아트홀, 문화센터, 체험관, 공공시설이 여행 코스에 섞임
- 야간인데 실제 닫힌 실내 장소가 노출됨
- 식사 → 식사 → 카페처럼 역할 반복 발생

이에 따라 현재 방향은 다음과 같다.

```text
1. 넓은 지역 default보다 curated district 중심
2. 공공데이터보다 curated knowledge / external verified API 우선
3. 정확한 시간 선택보다 아침/낮/저녁 time-band 사용
4. 대표 장소를 강제 삽입하지 않고, bounded preference / bounded replacement 사용
5. hard route lock 금지
6. fake POI 금지
7. stability 우선: places=[] / NO_COURSE / runtime timeout 방지
```

---

## 2. 개발 진행 방식

사용자는 앞으로도 다음 방식으로 진행하길 원한다.

```text
ChatGPT가 팀장 관점에서 Codex 전달 프롬프트 작성
→ 사용자가 Codex 답변 전달
→ ChatGPT가 결과 검토
→ 다음 Codex 프롬프트 작성
```

중요 원칙:

- 설명은 최소화
- 필요한 경우에만 짧은 판단 추가
- 바로 Codex 프롬프트 중심으로 진행
- 사용자가 잘못된/무관한 결과를 가져오면 작업 지시하지 말고 짧게 잘못된 내용이라고 알림
- 실기기 QA 단계에서는 큰 구조 변경보다 blocker와 체감 문제만 수정
- 문서 생성은 인수인계/규칙 변경/상태 변경에 꼭 필요한 경우만 수행

---

## 3. 현재 구현 완료/반영된 주요 의도

### 3.1 representative family orchestration

기존 문제:

- 선택한 지역과 무관한 장소로 drift
- 부산 기장 선택 시 광안리/해운대로 흐름 이동
- 북촌/성수/강남/광화문 등 서울 내부 family 혼합
- 특정 장소 first-place 고정

구현 의도:

- selected anchor의 family를 보존
- same-family candidate를 우선
- drift는 soft demote
- hard lock 없이 bounded diversity 허용

완료된 방향:

- 부산 east-coast family preservation
- 부산 원도심 family 강화
- 서울 강남/여의도 family 보정
- 전주 한옥마을 representative visibility 강화
- 진주 역사 family 보정
- 을지로/성수/북촌 등 서울 district family 보정

---

### 3.2 public facility contamination 제거

기존 문제:

- 도서관
- 국기원
- 주민센터
- 문화센터
- 아트홀
- 공공강당
- 체육센터
- 공예/체험관
- 박물관/전시관류

등이 대표 관광 slot에 노출됨.

구현 의도:

- 공공시설은 first-place / 대표 slot에서 강하게 약화
- 단, 진짜 대표 문화시설은 완전 제거하지 않고 context 기반 판단
- 야간에는 운영 종료가 명확한 실내 문화/체험 계열을 강하게 demote

현재 남은 문제:

- CTS아트홀, 라운지, 문화공간류 등 semantic edge case가 아직 일부 존재 가능
- 이 영역은 공공데이터보다 curated/API 우선순위 강화로 해결해야 함

---

### 3.3 exact landmark visibility

기존 문제:

- 감천문화마을, BIFF광장, 흰여울문화마을, 자갈치시장, 국제시장 등 부산 원도심 대표 장소가 DB 후보에 없거나 pool에 못 들어옴
- 전주 경기전, 전동성당, 오목대, 남부시장 등이 약함

구현 의도:

- production candidate가 없으면 fake insertion 금지
- verified source 기반 governed enrichment만 허용
- candidate가 있으면 alias/family/pool inclusion 보정
- final route에는 bounded support-slot visibility로 포함 확률 강화

완료된 방향:

- 부산 원도심 missing candidate 일부 governed enrichment
- 감천문화마을, BIFF광장, 흰여울문화마을, 자갈치시장, 국제시장 후보 확보
- 전주향교, 경기전, 오목대, 전주부채문화관 등 visibility 개선
- wrong-city contamination 감소

주의:

- exact landmark를 무조건 삽입하면 hard route lock처럼 보여 다양성 저하
- 반드시 bounded preference 유지

---

### 3.4 candidate pool expansion

기존 문제:

- regenerate해도 장소가 안 바뀜
- first-place 고정
- candidate pool 자체가 좁음

진행한 방향:

- family candidate audit
- coverage audit
- alias normalization
- governed enrichment
- support-slot alignment

개선된 대표 사례:

- 강남: 선릉과 정릉 15/15 고정 해소
- 서면: candidate coverage 0에서 representative 후보 확보
- 부산 원도심: 후보 없음 → 후보 존재 + visibility 일부 개선
- 진주: evaluator false-positive correction 후 coherence 상승

---

### 3.5 야간/저녁 시간 정책 개선 과정

#### 문제의 시작

사용자가 18시 이후/20시 이후를 선택하면 다음 문제가 반복되었다.

- NO_COURSE
- 음식점 1개만 나옴
- 1~2곳짜리 short course
- 실제 닫힌 indoor 장소 노출
- 야간인데 아침/낮 관광지 섞임
- 16~18시 경계 충돌

#### 진행한 정책들

- night-friendly mode
- late-safe relaxed mode
- user selected late time vs auto late time 분리
- known closed indoor demote
- indoor semantic closing refinement
- late soft notice
- nationwide night audit

#### 최종 판단

정확한 hour 기반은 너무 복잡하고 충돌이 많았다.

최종 방향:

```text
화면: 아침 / 낮 / 저녁
내부 매핑:
아침 → 09:00
낮 → 12:00
저녁 → 17:00
```

이 구조로 정확한 16:00, 17:00, 18:00 충돌을 줄이고 UX도 단순화한다.

---

### 3.6 time-band departure UX

현재 적용 방향:

- datetime picker 제거 또는 비노출
- 아침 / 낮 / 저녁 selector 사용
- 내부 departure_time은 고정 매핑

문구는 장소 보장형이 아니라 시간대 선택 상태를 안내하는 수준으로만 유지한다.

현재 UI copy 방향:

```text
아침 출발로 추천해드릴게요.
낮 출발로 추천해드릴게요.
저녁 출발로 추천해드릴게요.
```

time-band 카드와 선택 안내 영역에서는 브런치, 다양한 장소, 야경/산책 중심처럼 실제 결과와 mismatch될 수 있는 하단 설명 문구를 노출하지 않는다.
출발 시간대 아코디언 상단의 “추천” badge도 제거한다.

모바일 공간 절약을 위해 출발 시간대 선택 영역은 기본 collapsed accordion으로 운영한다.

- collapsed 상태에서는 `출발 시간대 · 아침/낮/저녁`처럼 현재 선택 상태만 표시한다.
- 사용자가 영역을 눌렀을 때만 아침/낮/저녁 selector를 펼친다.
- 시간대 선택 후에는 다시 collapsed 상태로 돌아가 첫 화면 CTA 노출을 방해하지 않는다.
- accordion 안에서도 보장형 설명 문구와 추천 badge는 노출하지 않는다.

주의:

- “브런치 추천”처럼 특정 장소/업종을 보장하는 문구 금지
- “야경·감성 코스 보장”처럼 실제 결과와 mismatch 나는 문구 금지
- 시간대 선택은 코스 결과를 보장하지 않고 departure_time mapping을 안내하는 역할로 제한

---

### 3.7 cafe image quality phase1

현재 이미지 품질 정책은 전국 자동 image enrichment보다 대표 카페 district의 체감 품질을 먼저 안정화하는 방향이다.

우선 district:

- 성수
- 한남
- 북촌
- 연남
- 을지로
- 강남
- 부산 전포
- 부산 광안리

카페 카드 이미지 fallback priority:

1. approved HIGH confidence image
2. existing curated image
3. safe neutral cafe fallback
4. icon fallback

운영 원칙:

- 잘못된 이미지를 넣지 않는 것이 이미지 개수를 늘리는 것보다 우선이다.
- generic stock, blog collage, Pinterest/pinimg, 광고 배너, 다른 도시/다른 지점 mismatch 이미지는 금지한다.
- image review gate에서 승인된 image만 production candidate image로 사용할 수 있다.
- safe neutral cafe fallback은 특정 장소의 실제 이미지처럼 보이지 않는 abstract/neutral UI fallback이어야 한다.
- image review persistence migration 전에는 simulation-approved image를 production card에 직접 연결하지 않는다.

2026-05-21 read-only audit 결과:

- 대상 8개 district 카페 후보 247건
- image missing 67건
- mismatch/license-risk URL 자동 탐지 0건
- image가 있는 후보는 대부분 TourAPI `tong.visitkorea.or.kr` 이미지
- icon fallback 비율이 높은 곳은 연남 45.45%, 한남 37.50%, 강남 29.79%, 북촌 29.03%, 성수 25.25%

approved image simulation 후보:

- 낫배드커피 도산
- 젠젠 성수점
- 카페 공명 연남점
- 크림시크

위 4건은 HIGH confidence image 후보가 있었지만, 아직 production write나 실제 reviewer persistence가 아니므로 migration 이후 reviewer approve flow를 통과해야 한다.

---

### 3.8 cafe placeholder polish phase1

이미지 없는 카페 카드의 허전함은 실제 사진 fallback이 아니라 neutral abstract placeholder로 완화한다.

적용 방향:

- `CourseResultScreen.jsx`의 cafe role placeholder만 우선 polish
- 기존 카드 이미지 영역 크기는 유지
- coffee icon은 유지하되 white translucent shell과 약한 pattern을 추가
- expanded card label은 `카페 이미지 준비 중`으로 표시
- meal/history/sea/night/default placeholder는 큰 변경 없이 유지

금지 원칙:

- 실제 장소처럼 보이는 fake cafe photo 사용 금지
- generic stock photo 사용 금지
- blog collage/Pinterest/pinimg 이미지 사용 금지
- approved image review 전 외부 image 자동 연결 금지
- production image write/migration 없이 placeholder만 개선

이 작업은 UI polish이며 추천 엔진, 코스 로직, external image persistence와 무관하다.

---

### 3.9 mobile CTA polish phase1

모바일 첫 화면에서는 선택 UI를 가볍게 유지하고, `코스 만들기` CTA를 선택 흐름의 마지막 행동으로 명확하게 보이게 한다.

적용 방향:

- HomeScreen CTA 영역은 district/time-band selector 다음의 final action으로 보이도록 시각적 weight를 높인다.
- CTA 주변에 subtle blue-tint panel과 safe-area bottom padding을 적용한다.
- CTA button은 mobile tap target을 우선해 `minHeight`를 확보한다.
- 클릭 직후에는 `코스 준비 중` loading label과 `aria-busy`를 사용해 중복 탭을 줄인다.
- loading reset timer는 화면 전환 시 cleanup해 UI 상태 timer가 남지 않게 한다.
- 새 보장형 설명 문구는 추가하지 않는다.

금지 원칙:

- 추천 엔진 변경 금지
- 코스 로직 변경 금지
- departure time-band mapping 변경 금지
- production migration / places write 없이 frontend UI polish만 적용

---

### 3.10 regenerate UX polish phase1

모바일 결과 화면에서 `다른 분위기 추천`과 코스 loading의 체감 품질을 개선한다.

적용 방향:

- regenerate 클릭 직후 `새 흐름 준비 중` pending label과 `aria-busy`를 표시한다.
- pending 상태는 420ms 정도로 짧게 유지하고 기존 조건 화면 이동 흐름은 유지한다.
- loading 화면은 spinner-only 대신 route skeleton card 3개와 약한 shimmer를 사용한다.
- 결과 리스트는 220ms 수준의 짧은 fade/translate transition만 적용한다.
- 이미지 없는 카페 placeholder는 실제 사진 없이 deterministic neutral tone variation만 허용한다.

금지 원칙:

- 추천 엔진 rewrite 금지
- route hardcoding 금지
- fake 장소/이미지 추가 금지
- production migration / places write 없이 frontend UI polish만 적용

---

### 3.11 district selector mobile polish phase1

서울 curated district가 늘어난 상태에서 모바일 여행지 선택 바텀시트의 밀도와 선택 상태 가시성을 개선한다.

적용 방향:

- district/family mapping은 변경하지 않고 HomeScreen selector UI만 조정한다.
- 카드 padding/gap을 소폭 줄여 모바일 밀도를 개선한다.
- touch target은 `minHeight: 66px` 수준으로 유지한다.
- 선택 상태는 badge/chip처럼 과하게 강조하지 않고, 은은한 배경, blue border, left accent bar, check icon으로 표시한다.
- 긴 district 이름은 `wordBreak: keep-all`과 `overflowWrap`으로 줄바꿈 안정성을 높인다.
- `기본 분위기 추천:` 문구는 `기본 분위기 ·`로 줄여 selector 카드가 답답해 보이지 않게 한다.

금지 원칙:

- 추천 엔진 rewrite 금지
- district/family mapping 변경 금지
- fake district 추가 금지
- route hardcoding 금지
- production migration / places write 없이 frontend UI polish만 적용

---

### 3.12 result card readability phase1

모바일 코스 결과 화면에서 장소 카드의 스캔성과 정보 hierarchy를 개선한다.

적용 방향:

- 추천 엔진과 route assembly는 변경하지 않고 `CourseResultScreen` 카드 UI만 조정한다.
- 타임라인 dot은 순번 circle로 바꿔 1번/2번/3번 이동 흐름을 더 빨리 인지하게 한다.
- 카드 title은 먼저 읽히게 유지하고, meta line은 `role label · duration` 구조로 정리한다.
- 펼친 카드 설명은 약 5줄 높이 기준으로 제한해 긴 설명이 한 번에 과도하게 노출되지 않게 한다.
- 이동 시간 pill과 timeline connector는 시각 weight를 낮춰 본문 스캔을 방해하지 않게 한다.
- regenerate 반복 시에도 카드가 텍스트 덩어리처럼 보이지 않도록 description density를 낮춘다.

금지 원칙:

- 추천 엔진 rewrite 금지
- route assembly 수정 금지
- fake 장소 추가 금지
- production migration / places write 없이 frontend UI polish만 적용

---

### 3.13 mobile UX smoke QA phase1

현재까지 완료된 mobile-first UX polish를 기준으로 운영 화면 smoke QA를 수행했다.

확인 범위:

- HomeScreen district selector open/close
- time-band accordion collapsed/default/selection flow
- CTA initial viewport visibility
- CourseResultScreen timeline number, role/duration meta, description density
- cafe placeholder layout
- regenerate 3회 반복 흐름
- iPhone-style `390x844`, Galaxy-style `360x740` viewport

결과:

- `390x844`: CTA top 517px, height 62px, initial viewport 내 노출
- `360x740`: CTA top 488px, height 62px, initial viewport 내 노출
- 성수/북촌/한남/강남 각 regenerate 3회 smoke PASS
- `NO_COURSE` 0
- `places_empty` 0
- result card timeline number 5개 및 description maxHeight `105px` 확인
- production `places` row count 26381 유지
- migration / places write / docker compose down 없음
- saju container 영향 없음

남은 non-blocking 관찰:

- `새 흐름 준비 중` pending label은 일부 regenerate cycle에서만 snapshot에 잡혔다. 전환이 빠른 케이스에서는 사용자가 체감하기 전에 조건 화면으로 이동할 수 있다.
- 연남은 현재 서울 추천 여행지 목록에 노출되지 않아 smoke 대상에서 제외했다.

판단:

- 운영 배포 전 blocker 없음
- 실기기 Safari/Samsung Internet에서 pending label 체감만 후속 확인 권장

---

## 4. 현재 서울 정책 변경 방향

### 4.1 서울 broad default 축소

현재 판단:

서울 전체 default는 너무 넓다.

문제:

- 북촌/성수/강남/한남/한강/여의도/명동/인사동 등이 섞임
- identity가 흐려짐
- 식사 → 식사 → 카페 반복
- 공공성 venue 섞임
- 사용자 기대와 결과 mismatch

방향:

```text
서울 default 약화
서울 curated district 중심 운영
```

### 4.2 서울 curated district 최종 후보

사용자 최신 요청 반영:

수식어를 줄이고 district 이름 중심으로 간단히 정리한다.

서울 추천 district:

```text
- 명동
- 인사동
- 북촌
- 성수
- 한남
- 강남
- 한강
- 여의도
- 을지로
```

단, 을지로는 “야간” 표현 금지.

```text
을지로 야간 ❌
을지로 감성 ❌ 또는 수식어 최소화
을지로 ⭕
```

사용자 최종 방향은 “뒤에 붙는 수식어를 빼자”였으므로 가능하면 UI에서는 단순히 다음처럼 표시하는 것이 좋다.

```text
명동
인사동
북촌
성수
한남
강남
한강
여의도
을지로
```

내부적으로만 family identity를 가진다.

### 4.3 명동/인사동 추가 이유

사용자가 제안했고 타당하다.

이유:

- 외국인이 많이 찾는 대표 서울 관광 district
- 서울 대표성이 높음
- broad 서울보다 명확한 identity 제공
- 북촌/성수/강남만 있는 것보다 관광 균형이 좋아짐

---

## 5. 현재 가장 중요한 남은 문제

### 5.1 support-slot role diversity

최근 실기기에서 확인된 문제:

```text
식사 → 식사 → 카페
```

이런 흐름은 코스로서 자연스럽지 않다.

필요한 방향:

```text
role sequence orchestration
```

예:

```text
산책 → 메인 관광 → 식사 → 카페
야경 → 노포 → 산책 → 카페
거리 산책 → 카페 → 전망/수변 → 식사
```

앞으로 해야 할 일:

- 같은 role 연속 노출 감소
- meal candidate 과점 방지
- cafe/meal/support slot 분산
- walk/viewpoint/gallery/market/landmark 역할 강화

### 5.2 공공/문화시설 edge case

아직 남을 수 있는 문제:

- CTS아트홀
- 문화회관
- 아트홀
- 공예/체험관
- 라운지
- 종교계 문화공간
- 공공 전시관

정책:

- curated/API 후보보다 낮은 우선순위
- night/evening에서는 더 강하게 약화
- 단, 실제 대표 문화공간이면 context 기반 유지 가능

### 5.3 야간 품질

현재는 코스가 안 나오는 문제는 많이 해결되었으나, 다음은 아직 polish 대상이다.

- 실제 영업 여부 확인 어려움
- 운영시간 불명 실내 후보
- 야간인데 indoor-heavy route
- 야간 분위기와 맞지 않는 장소

정책:

```text
운영시간 불명 outdoor/walk/coastal/nightlife 후보는 허용
운영 종료 명확 indoor 후보는 강하게 약화
```

### 5.4 이미지 품질

이미지는 체감에 매우 중요하다.

특히:

- 해동용궁사
- 광안리
- 기장
- 북촌
- 전주
- 제주/강원 coastal
- 야경/드라이브/감성카페

방향:

- 전국 모든 장소 수동 관리 금지
- 대표 landmark만 curated image fallback
- Unsplash 등 라이선스 가능한 이미지 활용 가능
- 이미지 불일치가 UX 품질을 크게 낮춤

해동용궁사는 사용자가 특별히 좋아하는 장소이므로 “바다와 어우러지는 절” 느낌의 대표 이미지가 중요하다.

---

## 6. 운영/배포 주의사항

### 6.1 절대 금지

```text
docker compose down 금지
DB schema migration 신중
fake POI 삽입 금지
hardcoded route insertion 금지
hard route lock 금지
saju container 영향 금지
무리한 long-run 금지
```

### 6.2 EC2 과부하 사건

한 번 production EC2에서 600회 long-run QA를 실행하다가 다음 문제가 발생했다.

- public API timeout
- SSH banner timeout
- EC2 instance status check 실패
- 인스턴스 재부팅 필요

원인 판단:

```text
600회 요청
× timeout 90초
× sleep 400ms
× include-raw
× EC2 내부 실행
× 여행/사주 동일 인스턴스
```

이 조합이 사실상 소형 EC2에 부하 테스트처럼 작동했다.

앞으로 QA 기준:

```text
1 batch = 50~80회 이하
100회 초과 금지
timeout 20~30초
sleep 1000ms 이상
raw 저장 금지
연속 실패 3회면 중단
batch 사이 휴식
```

### 6.3 운영 안정성 확인 순서

문제가 생기면:

```text
1. SSH 접속 확인
2. /api/regions 확인
3. docker ps
4. docker stats --no-stream
5. uptime / free -m / df -h
6. runaway python process 확인
7. 필요 시 해당 process만 kill
8. reboot는 마지막 수단
```

하지만 SSH/SSM/Instance Connect 모두 불가하고 인스턴스 상태 검사 실패면 reboot가 현실적일 수 있다.

---

## 7. 현재 기능 상태 요약

### 안정화된 것

- 대표 family orchestration
- drift 대부분 해결
- places=[] 대부분 해결
- NO_COURSE 대부분 해결
- 부산 원도심 후보 보강
- 기장 east-coast drift 감소
- 강남 first-place 고정 해소
- 여의도 공공시설 first-place 감소
- 전주 exact landmark visibility 개선
- 진주 route evaluator false-positive 개선
- 을지로 label 야간 리스크 인지
- time-band UX 적용 방향 확정
- empty state 버튼 미동작 수정
- 늦은 시간 soft notice 분기

### 아직 polish 필요한 것

- 서울 curated district 최종 적용
- 명동/인사동 추가
- 서울 district label 수식어 제거
- 을지로 야간 → 을지로 일반/감성 district로 축소
- support-slot role diversity
- 식사 연속 노출 감소
- 공공/아트홀/문화시설 edge case 감소
- 야간 실내 운영시간 신뢰도
- 이미지 품질
- 로그인/저장/찜/최근 코스

---

## 8. 바로 다음 Codex 작업 추천

현재 사용자 최신 요청 기준 다음 작업은 이것이다.

```text
서울 curated district 최종 정리 + 명동/인사동 추가 + 수식어 제거 + support-slot role diversity 1차 개선
```

### 다음 Codex 프롬프트 초안

```text
[Codex 전달 프롬프트]

목표:
서울 broad default 중심 구조를 축소하고, 서울은 curated district 이름 중심으로 운영되도록 정리한다.
또한 명동/인사동을 추가하고, 기존 district label 뒤의 수식어를 제거한다.

현재 문제:
서울 전체 default는 범위가 너무 넓어 identity가 섞이고,
식사→식사→카페 같은 role repetition이 발생한다.
또한 “을지로 야간”, “북촌 한옥 산책”, “성수 감성”처럼 수식어가 붙으면 실제 코스와 기대가 mismatch될 수 있다.

최종 서울 district label:
- 명동
- 인사동
- 북촌
- 성수
- 한남
- 강남
- 한강
- 여의도
- 을지로

중요:
- 을지로 야간 표현 제거
- label에서는 수식어 제거
- 내부 family identity는 유지 가능
- 서울 broad default는 fallback 정도로 약화

절대 금지:
- representative engine 제거 금지
- broad scoring rewrite 금지
- hard route lock 금지
- fake POI 금지
- DB schema migration 금지
- docker compose down 금지
- 사주 영향 금지

구현:
1. 서울 UI district label 정리
2. 명동/인사동 추가
3. 을지로 야간 label 제거
4. 내부 selected_anchor/family mapping 연결
5. broad 서울 default aggressive mixing 감소
6. district identity alignment 유지
7. support-slot role diversity 1차 개선
   - 식사→식사→카페 연속 감소
   - walk/viewpoint/gallery/market/cafe/meal 역할 분산

검증:
- 명동 아침/낮/저녁
- 인사동 아침/낮/저녁
- 북촌 아침/낮/저녁
- 성수 아침/낮/저녁
- 한남 아침/낮/저녁
- 강남 아침/낮/저녁
- 한강 아침/낮/저녁
- 여의도 아침/낮/저녁
- 을지로 아침/낮/저녁

확인:
- places=[] 없음
- NO_COURSE 없음
- label mismatch 감소
- 식사 연속 감소
- district identity 유지
- 모바일 UI 깨짐 없음
- 사주 영향 없음

보고서:
reports/seoul_curated_district_label_and_role_diversity_phase1.md
```

---

## 9. 로그인 기능 착수 판단

로그인은 아직 바로 들어가기보다 다음 이후가 좋다.

```text
1. 서울 district 정리
2. 실기기 QA
3. 치명 blocker 없음 확인
4. 로그인 기능 착수
```

로그인이 들어가면:

- user table
- session/cookie
- OAuth 가능성
- 저장/찜/최근 코스
- rate limit
- auth middleware

등이 들어가므로 리스크가 커진다.

하지만 현재 코스 생성 핵심은 많이 안정화되었으므로, 서울 district 정리 후에는 로그인 기능으로 넘어가도 된다.

추천 로그인 이후 기능 우선순위:

```text
1. 최근 생성 코스
2. 코스 저장
3. 찜한 장소
4. 공유
5. regenerate feedback
6. 사용자 취향 기반 추천
```

---

## 10. 새 대화창 시작용 요약 프롬프트

새 대화창에서 이어갈 때는 다음 문장을 붙이면 된다.

```text
현재 여행 코스 추천 서비스는 representative family orchestration, drift 방지, NO_COURSE/places=[] 안정화, time-band UX 방향까지 진행된 상태입니다.
공공데이터 기반 한계를 인정하고, 앞으로는 팀장 curated knowledge > 외부 verified API > 공공데이터 fallback 우선순위로 운영합니다.
현재 바로 다음 작업은 서울 broad default를 약화하고, 서울 curated district를 명동/인사동/북촌/성수/한남/강남/한강/여의도/을지로처럼 수식어 없는 label 중심으로 정리하는 것입니다.
또한 식사→식사→카페 같은 support-slot role repetition을 줄이고, district identity를 유지해야 합니다.
작업 방식은 ChatGPT가 Codex 전달 프롬프트 작성 → 사용자가 Codex 결과 전달 → ChatGPT 검토 후 다음 프롬프트 작성 방식입니다.
절대 금지: docker compose down, fake POI, hard route lock, broad scoring rewrite, 사주 영향.
```

---

## 11. 반드시 기억해야 할 사용자 판단

사용자가 중요하게 보는 기준:

- 무조건 동의하지 말 것
- 잘못된 방향이면 강하게 지적할 것
- 단편 해결보다 구조적으로 볼 것
- 설명보다 Codex 프롬프트 중심
- 실기기 체감 중요
- 공공데이터만으로 만족 품질 불가능하다는 점 인정
- 팀장 curated knowledge 적극 활용
- 서비스 완성도를 위해 장기적으로 하나의 md 문서로 상태 유지

사용자가 특히 신경 쓴 장소/흐름:

- 해동용궁사: 특별히 좋아함, 이미지 중요
- 부산 기장: 광안리/해운대 drift 싫어함
- 부산 원도심: 감천/BIFF/흰여울/자갈치/국제시장 중요
- 북촌: 닫힌 실내 문화시설이 야간에 나오면 안 됨
- 을지로: 야간은 위험, label은 을지로로 단순화
- 서울: broad default보다 curated district 중심
- 명동/인사동: 서울 대표 관광 district로 추가 원함

---

## 12. 최종 현재 판단

현재 프로젝트는 실패 상태가 아니다.

오히려 초기 공공데이터 기반 추천에서:

```text
대표 지역 family 기반 코스 생성 엔진
+
curated representative layer
+
time-band UX
+
실기기 QA 기반 polish
```

단계까지 올라왔다.

이제 남은 건 시스템 붕괴 해결이 아니라:

```text
실사용 감성 polish
서울 district 정리
support-slot role diversity
이미지 품질
로그인/저장 기능
```

이다.

다음 대화창에서는 위 문서를 기준으로 바로 이어가면 된다.


# 추가 운영/데이터 품질 인수인계 (2026-05 추가)

## 1. 현재 프로젝트 방향 전환

초기 프로젝트는 공공데이터(TourAPI) 기반 추천 엔진 안정화가 핵심이었다.

하지만 실제 사용자 테스트 결과:

* 사진 부족
* 카페/식당 품질 부족
* 감성 부족
* “가고 싶은 느낌” 부족
* 실내/문화시설 부족

문제가 명확히 드러났다.

현재 판단:

```text
TourAPI 단독 기반 추천
→ 한계 도달

TourAPI + Kakao/Naver 기반
데이터 품질 플랫폼 단계 진입
```

---

## 2. 앞으로의 핵심 방향

중요 우선순위:

```text
팀장 curated knowledge
>
Kakao/Naver verified API
>
TourAPI fallback
```

특히:

* 카페
* 식당
* 실내 장소
* 문화시설
* 감성 장소
* 이미지

는 외부 API 적극 활용이 필요하다.

---

## 3. 외부 API 활용 원칙

절대 실시간 추천 중 직접 호출하지 않는다.

❌ 잘못된 방향:

```text
추천 중 Kakao/Naver 실시간 호출
```

✔ 올바른 방향:

```text
외부 API 수집
→ 정제
→ staging
→ QA
→ places 편입
→ 기존 엔진 사용
```

즉:

```text
외부 API = 데이터 공급망
```

이다.

---

## 4. 현재 운영 배치 구조

배포 후 데이터 업데이트는 반드시 아래 구조를 따른다.

```text
collect
→ clean
→ enrich
→ staging
→ QA
→ promote
```

현재 구현됨:

* batch/update_all.sh
* batch/update_all.ps1
* staging_places
* raw_places
* clean_places
* invalid_places
* data_update_runs
* QA gating
* promote 차단

중요 원칙:

```text
운영 places 직접 수정 금지
QA 실패 시 promote 금지
전체 재적재 금지
```

---

## 5. 장소 데이터 품질이 가장 중요해짐

현재 프로젝트 핵심은:

```text
추천 엔진
```

보다:

```text
좋은 장소 데이터를 운영하는 것
```

이다.

특히 중요한 요소:

* 사진
* 카페 감성
* 실제 인기 장소
* 실내/우천 대응
* 분위기
* 설명 품질

---

## 6. 저장 기능 상태

현재 저장 기능은 운영 수준으로 완성되지 않았다.

현재 상태:

* _courses 인메모리 기반
* DB 저장 없음
* MyPage 조회 없음

즉:

```text
운영 저장 기능 미완성
```

현재는 저장 버튼 비노출/비활성화가 안전하다.

---

## 7. 모바일 실기기 경험

PC 테스트만으로는 실제 문제를 발견할 수 없었다.

실제 문제:

* 100vh
* safe-area
* Android Chrome pull-to-refresh
* mock iPhone frame
* 9:41 / 배터리 상태바 노출

앞으로:

```text
Android Chrome / Samsung Internet 실기기 검증 필수
```

---

## 8. 장소 1개 추가 기능

현재 사용자 추가 기능은 존재한다.

하지만:

* 이동시간
* 거리
* role 균형
* service level

검증을 반드시 통과해야 한다.

현재는 안전 검증 레이어가 추가된 상태다.

---

## 9. 현재 가장 중요한 목표

현재 목표는:

```text
더 똑똑한 추천 엔진
```

이 아니라:

```text
실제로 가고 싶은 장소 데이터 품질 확보
```

이다.

특히:

* 카페
* 식당
* 실내 장소
* 사진
* 분위기

가 사용자 만족도를 크게 좌우한다.

---

## 10. 현재 추천하는 운영 우선순위

1. 모바일 UI polish
2. Kakao/Naver 외부 데이터 보강
3. 이미지 품질 개선
4. 폐업/유효성 검증
5. 운영 로그 기반 데이터 보강
6. 충북/경남 BLOCKED 해제 검토
7. 날씨/실내 기능
8. 저장/로그인/공유

---

## 11. External candidate review gate 운영 방향

2026-05-18 기준으로 여행 서비스의 다음 데이터 방향은 추천 엔진 재튜닝이 아니라, Kakao/Naver 기반 장소 데이터 품질 보강 플랫폼이다.

중요 원칙:

```text
추천 요청 중 Kakao/Naver API 실시간 호출 금지
운영 places 직접 insert/update 금지
fake POI 삽입 금지
QA 실패 시 promote 금지
review/approve 전 promote 금지
```

현재 외부 장소 파이프라인은 다음 기반을 이미 갖고 있다.

* `raw_external_places`
* `clean_external_places`
* `staging_places`
* `data_update_runs`
* `data_update_qa_results`
* `batch/external/collect_external_places.py`
* `batch/external/clean_external_places.py`
* `batch/external/enrich_external_places.py`
* `batch/external/qa_external_places.py`
* `batch/external/promote_external_places.py`

하지만 현재 구조는 다음 위험이 있다.

```text
raw_external_places
→ clean_external_places
→ staging_places
→ QA
→ promote_external_places.py --qa-passed --write
→ production places upsert 가능
```

이 흐름은 운영 플랫폼 방향에서는 너무 빠르다. QA는 코스 생성 실패 증가 여부를 보는 장치이지, 외부 후보가 실제 서비스 장소로 들어가도 되는지 판단하는 human review gate가 아니다.

따라서 다음 구조를 표준으로 삼는다.

```text
collect
→ clean
→ match
→ stage_external_candidates
→ staging_external_places
→ QA
→ review
→ approve/reject
→ approved-only promote
```

### staging_external_places 목적

`staging_external_places`는 외부 후보 전용 검수 게이트다.

보존해야 할 핵심 상태:

* `qa_status`
* `promotion_status`
* `duplicate_review_status`
* `business_safety_status`
* `match_status`
* `match_confidence`
* `duplicate_of_place_id`
* `proposed_action`
* `reviewer`
* `review_note`
* `reviewed_at`
* `promotion_block_reason`

이 테이블은 운영 `places`를 대체하지 않는다.  
운영 반영 전 후보를 검토하고 block reason을 남기는 중간 계층이다.

### promote guard 정책

향후 promote는 아래 조건을 모두 만족해야 한다.

```text
qa_status = 'PASS'
promotion_status = 'approved'
business_safety_status = 'safe'
duplicate_review_status IN ('unique', 'needs_manual_review')
proposed_action IN ('candidate_insert', 'candidate_update')
source IN ('kakao', 'naver')
external_id 존재
name 존재
region 존재
latitude / longitude 존재
visit_role 유효
```

`--qa-passed` 하나만으로 운영 `places` upsert를 허용하면 안 된다.  
기본 실행은 dry-run이어야 하며, approved candidate 목록과 block reason을 먼저 출력해야 한다.

### reviewer workflow

최소 구현은 frontend admin이 아니라 CLI/report 수준으로 시작한다.

1. `stage_external_candidates.py`
   * `clean_external_places` 후보를 `staging_external_places`로 복사
   * duplicate, business status, image, category, coordinate risk를 정리

2. `review_external_candidates.py --run-id ... --report`
   * reviewer용 CSV/Markdown 출력
   * duplicate 의심, 폐업 의심, category mismatch, 좌표 이상, image 없음 표시

3. `review_external_candidates.py --approve <id>` / `--reject <id>`
   * reviewer와 review note 필수
   * bulk approve는 별도 안전 flag 없이는 금지

4. `promote_external_places.py --dry-run`
   * promote 가능 후보와 block reason 출력

5. `promote_external_places.py --write`
   * approved + QA PASS + safety PASS 후보만 운영 반영

### 운영 안전성 정책

다음은 유지해야 한다.

* 추천 엔진/representative orchestration은 이 작업에서 건드리지 않는다.
* external API는 batch ingestion에서만 사용한다.
* 추천 요청 runtime에서는 외부 API를 호출하지 않는다.
* 운영 `places`는 review/QA/promote guard 없이는 수정하지 않는다.
* DB migration은 draft/review 후 별도 승인으로만 적용한다.
* 사주 서비스 container/network에는 영향이 없어야 한다.

관련 산출물:

* `reports/external_places_data_pipeline_phase1.md`
* `reports/external_places_data_pipeline_phase1_migration_draft.sql`

### 2026-05-18 dry-run reviewer tooling 진행 상태

external candidate review gate의 코드 수준 dry-run workflow가 추가되었다.

추가 파일:

* `batch/external/stage_external_candidates.py`
* `batch/external/review_external_candidates.py`

수정 파일:

* `batch/external/promote_external_places.py`
* `batch/update_all.sh`

현재 가능한 것:

* `clean_external_places` 후보를 읽어 duplicate risk 계산
* image missing 여부 표시
* coordinate validity 표시
* category risk 표시
* business safety status 표시
* reviewer decision 산출
* Markdown/CSV/JSON review report 생성
* promote dry-run warning 출력

아직 하지 않은 것:

* `staging_external_places` migration 실행
* 운영 DB write
* production `places` 수정
* approve/reject DB write
* approved-only promote 실제 전환

`batch/update_all.sh` 안전 flag 방향:

```text
--candidate-only
--no-promote
--review-required
--allow-promote
```

기본 정책:

```text
candidate_only=true
no_promote=true
review_required=true
```

즉, write mode에서도 기본은 candidate visibility/report까지만 진행하고 promote는 하지 않는 방향이다.  
legacy promote는 `--allow-promote`를 명시한 operator action으로만 남겨야 한다.

검증 메모:

* EC2 host Python에는 `psycopg2`가 없어 batch 실행은 `travel-backend-v2` 컨테이너 Python 기준으로 검증했다.
* sample review report는 `qa_reports/external_candidate_review_smoke/`에 생성 가능함을 확인했다.
* 사주 서비스 영향 없음.

### 2026-05-18 approved-only promote 전환 준비 상태

external candidate review gate는 다음 방향으로 잠근다.

```text
staging_external_places
→ QA PASS
→ reviewer approve
→ business safety safe
→ duplicate review clear
→ approved-only promote
```

이번 단계에서 정리한 사항:

* `staging_external_places` migration draft를 final draft 수준으로 정리
* `review_external_candidates.py`에 `--approve`, `--reject`, `--reviewer`, `--review-note` dry-run interface 추가
* `promote_external_places.py`에 `--approved-only-dry-run` precondition validator 추가
* `batch/update_all.sh`에서 review report 생성 확인 없이는 promote block
* legacy `staging_places` promote path 제거 계획 명확화

운영자가 관리할 상태는 과도하게 늘리지 않는다.

유지할 최소 상태:

* `promotion_status`
* `duplicate_review_status`
* `business_safety_status`
* `qa_status`

판단:

```text
완벽한 심사 시스템보다 운영 DB 오염 방지가 우선이다.
```

아직 금지/미완료:

* production migration 실행 금지
* production `places` write 금지
* approve/reject 실제 DB update 미구현
* legacy promote path 최종 제거 미완료
* 추천 엔진 수정 없음
* 사주 영향 없음

다음 구현 순서:

1. migration 적용 여부 별도 승인
2. `stage_external_candidates.py --write` 활성화
3. `review_external_candidates.py --approve/--reject --write` 활성화
4. `promote_external_places.py` legacy path 제거
5. approved-only query만 production promote 허용
6. `batch/update_all.sh --allow-promote`도 approved-only promote만 호출

### 2026-05-18 approved-only rehearsal 단계

approved-only promote 전환 전 운영 리허설 모드가 추가되었다.

추가 옵션:

```text
promote_external_places.py --approved-only-rehearsal
batch/update_all.sh --rehearsal
batch/update_all.sh --approved-only-rehearsal
```

목적:

```text
실제 promote 없이
candidate review
→ simulated approve/reject
→ promote eligibility validation
→ final approved candidate preview
까지 확인한다.
```

blocked reason taxonomy:

* `BLOCK_DUPLICATE_RISK`
* `BLOCK_BUSINESS_STATUS`
* `BLOCK_QA_FAIL`
* `BLOCK_REVIEW_PENDING`
* `BLOCK_MISSING_COORDINATE`
* `BLOCK_INVALID_ROLE`
* `BLOCK_REQUIRED_FIELD`
* `BLOCK_UNSUPPORTED_SOURCE`
* `BLOCK_CATEGORY_RISK`
* `BLOCK_MISSING_IMAGE`

reviewer simulation:

```text
PENDING_REVIEW → APPROVED → PROMOTE_ELIGIBLE
PENDING_REVIEW → REVIEW_REQUIRED → BLOCKED
PENDING_REVIEW → REJECTED → BLOCKED
```

migration readiness 판단:

* `promotion_status`
* `duplicate_review_status`
* `business_safety_status`
* `qa_status`

위 4개 축이면 현재 목적에는 충분하다.

추가 review state를 더 늘리는 것은 보류한다.  
지금 목표는 완벽한 moderation system이 아니라 운영 DB 오염 방지다.

운영 전환 전 blocker:

1. `staging_external_places` migration 적용 승인
2. `stage_external_candidates.py --write` 활성화
3. `review_external_candidates.py --approve/--reject --write` 활성화
4. legacy `staging_places` promote path 제거
5. `--allow-promote`가 approved-only query만 호출하도록 전환
6. batch 실행 기준을 container Python으로 표준화

현재까지는 production migration 실행 없음, `places` write 없음, 추천 엔진 수정 없음, 사주 영향 없음.

### 2026-05-18 migration rollout / rollback / cutover 기준

approved-only promote 운영 전환은 기능 개발이 아니라 운영 데이터 보호 작업이다.

핵심 원칙:

```text
실수로 production places가 오염되지 않는가
```

#### Rollout checklist

1. promote freeze 선언
   * `--allow-promote` 사용 금지
   * legacy `promote_external_places.py --write` 직접 실행 금지
   * `candidate_only=true`, `no_promote=true`, `review_required=true` 확인

2. pre-check
   * `docker ps`
   * travel/saju container running 확인
   * DB connection 확인
   * 기존 external tables 확인
   * migration SQL 파일 확인

3. checkpoint
   * DB schema-only backup
   * `batch/external/*` checkpoint
   * `batch/update_all.sh` checkpoint
   * current git status/hash 기록

4. migration apply
   * `staging_external_places` 생성
   * required index 생성
   * raw/clean quality columns 추가
   * 적용 후 table/index 확인

5. rehearsal validation
   * `--approved-only-rehearsal`
   * `--approved-only-dry-run`
   * candidate review report 확인
   * QA PASS 조건 확인

6. legacy path disable
   * shadow mode 비교 후 진행
   * legacy `staging_places` promote path 제거
   * approved-only query만 남김

#### Rollback strategy

rollback 목표는 legacy promote 재개가 아니다.

```text
promote freeze 상태로 안전하게 돌아가는 것
```

rollback 조건:

* migration 실패
* index/check constraint 이상
* approved-only validator가 위험 후보를 eligible로 표시
* QA 없이 promote 가능성이 확인됨
* legacy path가 여전히 production write 가능
* 운영자가 report를 해석하기 어려움

rollback 우선순위:

1. promote freeze
2. code rollback
3. migration quarantine
4. 필요 시 schema rollback
5. `places` write가 발생했다면 snapshot 기반 별도 복구

#### Cutover sequence

big bang 전환 금지.

```text
legacy staging path active but frozen
→ migration apply
→ approved-only dry-run
→ candidate review validation
→ approved-only shadow mode
→ legacy promote disabled
→ approved-only promote only
```

#### Shadow mode

shadow mode는 필수에 가깝다.

확인해야 할 비교:

```text
legacy would promote X
approved-only would block X
```

필수 출력:

* legacy_candidate_count
* approved_eligible_count
* blocked_by_duplicate_count
* blocked_by_business_status_count
* blocked_by_review_pending_count
* legacy_only_candidates
* approved_only_candidates

shadow mode에서는 절대 write하지 않는다.

#### Migration readiness final audit

현재 draft 판단:

* nullable: 외부 source별 필드 차이가 있어 적절
* index: review queue/source id/duplicate/business safety 중심으로 충분
* query complexity: 낮음
* status taxonomy: 과하지 않음
* reviewer workflow: 운영 가능 수준

유지할 상태 축:

* `promotion_status`
* `duplicate_review_status`
* `business_safety_status`
* `qa_status`

추가 moderation state는 지금 만들지 않는다.

#### Container execution standard

EC2 host Python에는 `psycopg2` 문제가 있다.

운영 표준:

```text
batch 실행은 travel-backend-v2 container Python 기준
host Python 직접 실행 금지 또는 help/smoke 수준으로 제한
```

권장:

```text
docker exec -i travel-backend-v2 python -m batch.external.stage_external_candidates ...
docker exec -i travel-backend-v2 python -m batch.external.review_external_candidates ...
docker exec -i travel-backend-v2 python -m batch.external.promote_external_places --approved-only-rehearsal ...
```

운영 전환 전 최종 blocker:

1. migration 적용 승인
2. schema backup/checkpoint
3. migration 적용 후 table/index 확인
4. `stage_external_candidates.py --write` 구현
5. `review_external_candidates.py --approve/--reject --write` 구현
6. shadow mode 구현
7. legacy promote path disable
8. `--allow-promote`를 approved-only promote 전용으로 변경
9. container execution standard 확정
10. reviewer report 해석 가이드 확정

### 2026-05-18 migration go / no-go final gate

현재 상태는 migration apply 직전 검토 단계다.  
아직 GO가 아니다.

#### GO 조건

아래 조건을 모두 만족해야 한다.

* approved-only rehearsal 정상
* blocked taxonomy 정상
* review report를 운영자가 이해 가능
* legacy path freeze 가능
* shadow mode 비교 가능
* container execution standard 준비 완료
* reviewer workflow가 단순하게 유지됨

#### NO-GO 조건

아래 조건 중 하나라도 있으면 migration 적용을 미룬다.

* operator confusion 가능
* legacy path가 uncontrolled write 가능
* duplicate/business safety validation 부족
* rollback 불명확
* promote preview 불명확
* shadow mode 미구현

현재 NO-GO 사유:

* `staging_external_places` migration 미적용
* approve/reject persistence 미활성화
* shadow mode 미구현
* legacy promote path 아직 존재

#### Shadow mode final spec

필수 비교:

```text
legacy would promote
vs
approved-only would promote
```

필수 출력:

* `legacy_only_candidates`
* `approved_only_candidates`
* `blocked_reason_counts`
* `false_positive_risk`
* `false_negative_risk`

write는 절대 금지한다.

#### Operator guide 핵심

`REVIEW_REQUIRED`:
사람이 봐야 하는 후보. 자동 승인 금지.

`APPROVED`:
reviewer가 승인한 상태. 단독으로 promote 가능 상태는 아님.

`PROMOTE_ELIGIBLE`:
QA, review, business safety, duplicate 조건을 모두 만족한 최종 후보.

`BLOCK_DUPLICATE_RISK`:
기존 places와 중복 가능성. 같은 장소면 reject 또는 update candidate로 분류.

`BLOCK_MISSING_IMAGE`:
즉시 reject는 아니지만 품질 리스크. 유명 장소면 manual review 가능.

`BLOCK_BUSINESS_STATUS`:
closed면 reject. unknown이면 source payload 확인.

`BLOCK_MISSING_COORDINATE`:
reject. 임의 좌표 생성 금지.

`BLOCK_CATEGORY_RISK`:
숙박/병원/학교/행정시설 등 관광 부적합 가능성. 근거 없으면 reject.

#### Migration apply rehearsal 절차

1. pre-check
2. checkpoint
3. migration dry review
4. apply
5. validator
6. rehearsal
7. shadow mode
8. freeze 유지 확인

#### Legacy promote 제거 조건

legacy path는 아래 조건을 모두 만족한 뒤 제거한다.

* approved-only validator 안정
* reviewer workflow 안정
* rehearsal 결과 안정
* shadow mode discrepancy 허용 가능
* rollback 가능 상태 유지

현재 결론:

```text
migration apply는 아직 보류.
다음 우선순위는 shadow mode 구현과 operator guide 검토.
```

production migration 실행 없음, production `places` write 없음, 추천 엔진 수정 없음, 사주 영향 없음.

### 2026-05-18 small slice validation / raw delta 정책

approved-only promote 운영 전환 전에는 대량 적용이 아니라 작은 운영 slice로 리허설한다.

#### Small slice 후보

1. 서울 카페 10개
   * duplicate risk 높음
   * image missing 판단 훈련에 적합
   * 기존 curated 서울 후보와 충돌 여부 확인 가능

2. 부산 식당 10개
   * generic meal contamination 위험 확인
   * 부산 원도심/광안리/기장 family와 충돌 여부 확인 가능

3. 제주 실내 장소 10개
   * indoor/culture 후보 품질 확인
   * 운영시간/날씨 대응 후보로 쓸 수 있는지 판단 가능

#### Shadow mode 준비 상태

필수 비교:

```text
legacy would promote
vs
approved-only would promote
```

필수 출력:

* `legacy_only_candidates`
* `approved_only_candidates`
* `blocked_reason_counts`
* `false_positive_risk`
* `false_negative_risk`

write는 절대 금지한다.

#### Operator review scenario

duplicate 후보:

* 같은 장소면 reject 또는 update candidate
* 다른 지점이면 manual review
* review note 필수

image missing 후보:

* 유명 장소면 manual review 후 approve 가능
* 일반 카페/식당이면 보류 또는 reject

business status unknown 후보:

* source payload 확인
* 최근성/last_seen 확인
* 불확실하면 promote 보류

정상 후보:

```text
PENDING_REVIEW → APPROVED → PROMOTE_ELIGIBLE
```

#### Raw immutable 정책

raw는 immutable에 가깝게 유지한다.

원칙:

* raw overwrite 금지
* full reload 금지
* source response snapshot 유지
* 같은 source id도 새 run으로 보존
* raw는 수집 시점 증거로 취급

이유:

* 외부 API 응답은 바뀐다.
* 후보 문제가 생기면 원본 payload 추적이 필요하다.
* curated correction / family alignment / visibility tuning을 보호해야 한다.

#### Delta update 정책

full reload가 아니라 delta update 기준으로 운영한다.

기준:

```text
source_id + source + normalized_name + coordinate
```

관리 상태:

* `first_seen_at`
* `last_seen_at`
* `last_verified_at`
* `business_status`
* `source_confidence`

처리:

* 새 후보: staging candidate
* 기존 후보 재확인: candidate update
* source에서 사라진 후보: 즉시 삭제 금지
* 장기간 미확인 후보: inactive_candidate 검토
* 폐업 확인 후보: business safety block

#### 운영 slice rehearsal 성공 기준

* 운영자가 report를 이해함
* block reason이 납득 가능함
* promote eligible 후보가 preview에서 명확함
* legacy vs approved-only 차이가 설명 가능함
* production `places` write 없음

#### 실제 migration 적용 전 위험 요소

1. shadow mode 미구현
2. approve/reject persistence 미활성화
3. legacy promote path 존재
4. `--allow-promote` 오사용 가능성
5. EC2 host Python 실행 혼선
6. `BLOCK_MISSING_IMAGE` 해석 혼선
7. source freshness / last_seen 정책 미구현
8. inactive_candidate 정책 미구현

현재 결론:

```text
small slice rehearsal 준비는 가능하다.
production migration apply는 아직 보류한다.
다음 우선순위는 shadow mode와 operator review guide 확정이다.
```

### 2026-05-18 shadow mode 구현 상태

approved-only promote 전환을 위한 shadow mode가 구현되었다.

추가 옵션:

```text
promote_external_places.py --shadow-mode
batch/update_all.sh --shadow-mode
```

목적:

```text
legacy would promote
vs
approved-only would promote
```

를 write 없이 비교한다.

필수 출력:

* `legacy_candidate_count`
* `approved_eligible_count`
* `legacy_only_candidates`
* `approved_only_candidates`
* `blocked_reason_counts`
* `false_positive_risk`
* `false_negative_risk`
* `operator_report`
* `safety_summary`

현재 `staging_external_places` migration이 적용되지 않았으므로 approved-only 쪽은 `clean_external_places simulation` fallback으로 동작한다.

sample smoke:

```text
run_id = 72e04e7b-62e6-447b-a091-ceefe5560ec8
region = 서울
limit = 5
```

결과:

```text
legacy_candidate_count = 5
approved_eligible_count = 0
legacy_only_count = 5
approved_only_count = 0
blocked_reason_counts:
  BLOCK_DUPLICATE_RISK = 5
  BLOCK_MISSING_IMAGE = 5
```

판단:

* legacy path는 5개 후보를 promote 가능 후보로 볼 수 있음
* approved-only gate는 5개 모두 block
* duplicate/image risk가 운영자에게 노출됨
* write 없음

operator action 예:

* `manual_duplicate_review_required`
* `manual_quality_review_required`
* `reviewer_approval_required`
* `reject_or_fix_source_before_review`
* `preview_only_no_write`

아직 수행하지 않은 것:

* 서울 카페 10개 신규 slice
* 부산 식당 10개 신규 slice
* 제주 실내 장소 10개 신규 slice
* shadow mode CSV/Markdown 저장 옵션

다음 권고:

1. operator review guide 검토
2. shadow mode 결과 CSV/Markdown report 저장 옵션 추가
3. small slice 3종 dry-run 수집
4. migration 적용 전후 shadow 결과 비교
5. 이후 migration 적용 여부 판단

production migration 실행 없음, production `places` write 없음, raw overwrite 없음, full reload 없음, 추천 엔진 수정 없음, 사주 영향 없음.

### 2026-05-18 shadow report 저장 / small slice 준비 상태

shadow mode 결과를 운영자가 검토 가능한 report로 저장하는 기능이 추가되었다.

추가 옵션:

```text
promote_external_places.py --shadow-mode --report --output-dir qa_reports/shadow_mode
batch/update_all.sh --shadow-mode --shadow-report --shadow-output-dir qa_reports/shadow_mode
```

출력:

* JSON
* CSV
* Markdown

Markdown report 포함 내용:

* run_id
* region
* approved_only_source
* legacy_candidate_count
* approved_eligible_count
* legacy_only_count
* approved_only_count
* blocked_reason_counts
* false_positive_risk summary
* false_negative_risk summary
* candidate별 decision/action table

operator confusion 방지 문구:

```text
BLOCK_DUPLICATE_RISK: 기존 places와 중복 가능성. 자동 approve 금지.
BLOCK_MISSING_IMAGE: 즉시 reject는 아니지만 품질 review 필요.
REVIEW_REQUIRED: 사람이 판단해야 하며 자동 promote 금지.
PROMOTE_ELIGIBLE: final preview 확인 전 write 금지.
--allow-promote는 일반 운영 옵션이 아니라 legacy escape hatch.
```

sample report 경로:

```text
qa_reports/shadow_mode_smoke/
```

sample 결과:

```text
legacy_candidate_count = 5
approved_eligible_count = 0
legacy_only_count = 5
approved_only_count = 0
BLOCK_DUPLICATE_RISK = 5
BLOCK_MISSING_IMAGE = 5
```

small slice 준비 상태:

1. 서울 카페 10개
   * 부분 가능
   * 현재 sample에 cafe 후보 일부 존재
   * 정확히 10개는 추가 소량 수집 필요

2. 부산 식당 10개
   * 현재 sample만으로 부족 가능성 높음
   * 추가 소량 수집 필요

3. 제주 실내 장소 10개
   * 현재 sample만으로 부족 가능성 높음
   * 추가 소량 수집 필요

주의:

* 신규 수집 시에도 raw overwrite 금지
* full reload 금지
* 새 run 기반 delta 수집만 허용
* production `places` write 금지

다음 권고:

1. operator가 shadow Markdown report를 읽고 혼동 지점 확인
2. small slice 3종을 새 run으로 소량 수집
3. 각 run에 shadow report 생성
4. false positive / false negative 검토
5. 그 후 migration 적용 여부 재판단

production migration 실행 없음, production `places` write 없음, raw overwrite 없음, full reload 없음, 사주 영향 없음.

```
```

## 2026-05-18 서울 카페 small slice shadow validation 결과

approved-only promote 운영 전환 전 첫 번째 실제 small slice rehearsal로 `서울 + cafe` 후보를 검증했다.

### 실행 조건

- run_id: `72e04e7b-62e6-447b-a091-ceefe5560ec8`
- region: `서울`
- visit_role: `cafe`
- limit: `10`
- shadow output: `qa_reports/shadow_mode_seoul_cafe`
- 신규 API 수집: 없음
- raw overwrite: 없음
- full reload: 없음
- production migration: 없음
- production `places` write: 없음

기존 `clean_external_places` / `staging_places` 기준으로 `서울 + cafe` 후보는 2건만 존재했다. 10건을 맞추려면 신규 소량 수집 write가 필요하지만, 이번 단계의 `DB write 없음` 조건과 충돌하므로 2건 기준으로만 검증했다.

### Shadow 결과

```text
legacy_candidate_count = 2
approved_eligible_count = 0
legacy_only_count = 2
approved_only_count = 0
false_positive_risk_count = 2
false_negative_risk_count = 0
BLOCK_DUPLICATE_RISK = 2
BLOCK_MISSING_IMAGE = 2
```

생성 report:

```text
/home/ubuntu/travel_service_prod/qa_reports/shadow_mode_seoul_cafe/shadow_mode_72e04e7b-62e6-447b-a091-ceefe5560ec8_서울_cafe_20260518_043939.json
/home/ubuntu/travel_service_prod/qa_reports/shadow_mode_seoul_cafe/shadow_mode_72e04e7b-62e6-447b-a091-ceefe5560ec8_서울_cafe_20260518_043939.csv
/home/ubuntu/travel_service_prod/qa_reports/shadow_mode_seoul_cafe/shadow_mode_72e04e7b-62e6-447b-a091-ceefe5560ec8_서울_cafe_20260518_043939.md
```

### False Positive 사례

legacy path는 아래 후보를 promote 가능 후보로 보지만 approved-only gate는 block했다.

| 후보 | block reason | 운영 판단 |
|---|---|---|
| 만월다방 시네마 | BLOCK_DUPLICATE_RISK, BLOCK_MISSING_IMAGE | 기존 places 중복 확인 전 approve 금지 |
| 모센트 용산점 | BLOCK_DUPLICATE_RISK, BLOCK_MISSING_IMAGE | 중복 확인 및 이미지 품질 review 필요 |

이 결과는 legacy promote path가 그대로 열려 있으면 중복/이미지 없는 카페 후보가 production places로 들어갈 수 있음을 보여준다.

### Operator Review Simulation

1. `만월다방 시네마`
   - duplicate risk와 missing image가 동시에 있으므로 자동 approve 금지
   - 기존 places와 source id/name/좌표를 비교하고 중복이면 reject

2. `모센트 용산점`
   - missing image만으로 즉시 reject는 아니지만 duplicate risk가 있으므로 manual review 필요
   - 중복이 아니면 이미지 보강 가능성 또는 장소 대표성을 보고 approve/reject 판단

3. 정상 후보
   - 이번 slice에는 `PROMOTE_ELIGIBLE` 후보가 없었다.
   - fake 정상 예시는 만들지 않는다.
   - 정상 후보 판단까지 rehearsal하려면 서울 카페 신규 소량 delta 수집이 필요하다.

### Migration Readiness 판단

- approved-only gate와 shadow report 저장은 정상 작동한다.
- legacy path 위험은 실제 후보 기준으로 확인됐다.
- 다만 slice가 2건뿐이고 정상 후보가 없으므로 migration GO 판단에는 부족하다.
- 현재 상태는 migration apply 계속 NO-GO.

다음 권고:

1. 서울 카페 10건을 채울 수 있는 소량 delta 수집 run 준비
2. 부산 식당 10건, 제주 실내 10건 slice도 동일하게 준비
3. 각 slice에서 정상 후보와 blocked 후보가 모두 관찰된 뒤 migration go/no-go 재판단

## 2026-05-19 서울 카페 delta slice shadow validation 결과

서울 카페 후보 부족을 보강하기 위해 새 `run_id` 기반 소량 delta 수집을 수행했다. raw overwrite/full reload는 하지 않았고, production `places` promote도 수행하지 않았다.

### 실행 정보

- 신규 run_id: `b5ebd247-6601-4e81-9873-db07fd2c6d77`
- region: `서울`
- visit_role: `cafe`
- keywords: `카페,커피,디저트`
- source: `kakao,naver`
- max_total: `15`
- shadow output: `qa_reports/shadow_mode_seoul_cafe_delta`

Kakao는 `HTTP 401 Unauthorized`로 실패했고, 실제 수집 후보는 Naver local search 기반이다.

### 수집 결과

```text
fetched_count = 12
raw inserted_count = 10
clean_count = 7
clean inserted_count = 7
staged_count = 7
role_counts.cafe = 7
```

### Shadow 결과

```text
legacy_candidate_count = 7
approved_eligible_count = 0
legacy_only_count = 7
approved_only_count = 0
false_positive_risk_count = 0
false_negative_risk_count = 7
BLOCK_MISSING_IMAGE = 7
```

생성 report:

```text
/home/ubuntu/travel_service_prod/qa_reports/shadow_mode_seoul_cafe_delta/shadow_mode_b5ebd247-6601-4e81-9873-db07fd2c6d77_서울_cafe_20260518_222536.json
/home/ubuntu/travel_service_prod/qa_reports/shadow_mode_seoul_cafe_delta/shadow_mode_b5ebd247-6601-4e81-9873-db07fd2c6d77_서울_cafe_20260518_222536.csv
/home/ubuntu/travel_service_prod/qa_reports/shadow_mode_seoul_cafe_delta/shadow_mode_b5ebd247-6601-4e81-9873-db07fd2c6d77_서울_cafe_20260518_222536.md
```

후보:

- 낫배드커피 도산
- 젠젠 성수점
- 레자미오네뜨
- 카페 공명 연남점
- 아쿠아산타 성수카페
- 어퍼앤언더
- 크림시크

모두 `BLOCK_MISSING_IMAGE`로 blocked 처리됐다.

### PROMOTE_ELIGIBLE 판단

`PROMOTE_ELIGIBLE` 후보는 0건이다.

핵심 원인:

- 현재 Naver local search 수집 경로는 image URL을 제공하지 않는다.
- approved-only gate는 image missing 후보를 promote eligible에서 제외한다.
- 따라서 후보 수를 7건까지 늘려도 정상 통과 후보가 생기지 않았다.

이 결과는 candidate 수 부족보다 image metadata 공급망 부족이 더 큰 blocker임을 의미한다.

### Operator Review Simulation

1. 정상 approve 후보
   - 이번 delta slice에는 없음
   - fake 정상 후보를 만들지 않음

2. duplicate reject 후보
   - 이번 delta slice에는 없음
   - 직전 서울 카페 slice의 `만월다방 시네마`, `모센트 용산점`을 duplicate review 예시로 유지

3. image review 후보
   - 이번 delta slice 7건 전부 해당
   - 예: `낫배드커피 도산`, `젠젠 성수점`, `카페 공명 연남점`
   - 즉시 reject보다는 이미지 보강 가능성, 중복 여부, 대표성 기준으로 manual review 필요

### Migration Readiness 변화

현재 판단: migration apply 계속 NO-GO.

이유:

- approved-only shadow/report 체계는 작동한다.
- 하지만 image missing 때문에 정상 후보가 전부 막힌다.
- 이 상태로 cutover하면 운영 DB 오염은 막을 수 있지만 정상 external 후보 유입도 막힐 가능성이 높다.

다음 결정 후보:

1. image enrichment source를 추가한 뒤 rehearsal 재실행
2. `BLOCK_MISSING_IMAGE`를 hard block이 아니라 reviewer 승인 가능 상태로 완화
3. image policy 결정 전까지 migration apply 보류

현재 안전한 권고는 3번이다. 플랫폼 전환 속도를 내려면 1번 또는 2번 정책 결정이 필요하다.

검증:

- production `places` row count: `26381`, 변화 없음
- production migration 실행 없음
- production places write 없음
- legacy promote write 없음
- raw overwrite 없음
- full reload 없음
- saju 영향 없음

## 2026-05-19 image review persistence draft

### 목적

Naver Image Search PoC와 image review gate simulation 결과를 바탕으로, image review decision을 실제 운영 전환 가능한 persistence 구조로 확장하기 위한 준비를 완료했다. 이번 단계에서도 production migration, production places write, raw overwrite, full reload, scraping, approved-only 완화는 수행하지 않았다.

### image review status taxonomy

필수 상태:

- `pending`: image candidate 생성 후 reviewer 검토 전
- `approved`: reviewer가 image 사용 승인
- `rejected`: reviewer가 image 부적합 판정
- `blocked_license`: source/license 위험으로 차단
- `low_confidence`: confidence가 낮아 자동 승인 불가
- `needs_manual_review`: 사람이 추가 확인해야 함

필수 필드:

- `image_source`
- `image_url`
- `image_thumb_url`
- `image_confidence`
- `image_license_note`
- `image_reviewer`
- `image_review_note`
- `image_reviewed_at`
- `image_block_reason`

운영 원칙:

- HIGH confidence image도 자동 승인하지 않는다.
- `BLOCK_MISSING_IMAGE`를 직접 완화하지 않는다.
- image approve는 `image_review_status='approved'`, `image_url`, `image_license_note`가 모두 있어야 promote validator에서 인정한다.

### migration draft 변경

`reports/external_places_data_pipeline_phase1_migration_draft.sql`에 아래 draft를 추가했다.

- `staging_external_places` image review columns
- `image_enrichment_candidates` draft table
- image review lookup indexes
- promote guard SQL proposal에 image review 조건 추가

중요: migration proposal만 작성했으며 production DB에는 적용하지 않았다.

### review_image_candidates.py persistence placeholder

`batch/external/review_image_candidates.py`에 아래 옵션을 추가했다.

- `--approve-image`
- `--reject-image`
- `--reviewer`
- `--review-note`
- `--write`

현재 `--write`는 항상 차단된다. migration 적용 전에는 DB write를 수행하지 않고, persistence action payload만 report summary에 출력한다.

### promote validator 연동 정책

`batch/external/promote_external_places.py`의 approved-only TODO에 image gate 조건을 명시했다.

```text
BLOCK_MISSING_IMAGE 해제 조건:
image_review_status = 'approved'
image_url exists
image_license_note exists
```

현재 shadow mode의 `--image-review-report`는 simulation 전용이다. production promote 조건을 완화하지 않는다.

### migration readiness 변화

현재 판단은 계속 NO-GO다.

진전:

- image candidate 생성 가능성 확인
- image review simulation 가능
- image-approved shadow validation에서 eligible 후보 4건 확인
- persistence draft와 validator 연결 정책 정리 완료

남은 blocker:

1. `staging_external_places` / `image_enrichment_candidates` migration 실제 적용 승인
2. reviewer approve/reject persistence 구현
3. approved-only validator가 실제 DB image review status를 읽도록 전환
4. shadow mode로 legacy vs approved-only+image-reviewed 결과 재검증

### 검증 상태

- production migration 실행 없음
- production places write 없음
- raw overwrite 없음
- full reload 없음
- scraping 없음
- approved-only 완화 없음
- 추천 엔진 수정 없음
- saju 영향 없음

## 2026-05-19 image approve/reject write rehearsal

### 목적

image review persistence 구조를 실제 운영 전환 직전 수준으로 검증하기 위해 approve/reject write rehearsal을 추가했다. 이 단계는 production migration 없이 수행되며, 어떤 image review decision이 어떤 DB row update로 저장될 예정인지 payload만 생성한다.

### 구현 파일

- `batch/external/review_image_candidates.py`

추가 옵션:

- `--persistence-rehearsal`
- `--simulate-write`
- `--approve-image`
- `--reject-image`
- `--reviewer`
- `--review-note`
- `--image-license-note`

### rehearsal payload

approve rehearsal은 아래 구조를 생성한다.

```json
{
  "candidate": "낫배드커피 도산",
  "image_review_status": "approved",
  "image_reviewer": "operator_a",
  "image_review_note": "HIGH confidence thumbnail verified",
  "image_license_note": "naver_image_search_preview_only",
  "write_mode": "SIMULATION_ONLY"
}
```

reject rehearsal은 source/license risk 또는 low confidence를 반영한다.

```json
{
  "candidate": "레자미오네뜨",
  "image_review_status": "blocked_license",
  "image_block_reason": "license_source_risk",
  "write_mode": "SIMULATION_ONLY"
}
```

### validator 영향

정책은 유지한다.

- `BLOCK_MISSING_IMAGE` 직접 완화 금지
- image 자동 approve 금지
- image review approve 후에도 `image_url`과 `image_license_note`가 모두 있어야 validator 통과 후보로 인정

### report 경로

```text
qa_reports/image_review_persistence_rehearsal/
/home/ubuntu/travel_service_prod/qa_reports/image_review_persistence_rehearsal/
```

### 운영 판단

image review persistence flow는 rehearsal 가능한 상태가 되었다.

아직 NO-GO인 항목:

1. production migration 미적용
2. 실제 approve/reject persistence 미구현
3. approved-only validator DB 연동 미전환
4. reviewer action audit trail 미확정

### 검증

- `python -m py_compile`: 통과
- production migration 실행 없음
- production places write 없음
- raw overwrite 없음
- full reload 없음
- scraping 없음
- image 자동 approve 없음
- `BLOCK_MISSING_IMAGE` 직접 완화 없음
- saju 영향 없음

## 2026-05-19 approved-only pre-cutover rehearsal

### 목적

approved-only promote cutover 직전 기준으로 운영자가 실제 전환을 안전하게 수행 가능한지 마지막 rehearsal을 수행했다.

실제 migration/write는 수행하지 않았다.

### pre-cutover checklist

| 항목 | 상태 |
|---|---|
| candidate_only=true | OK |
| no_promote=true | OK |
| review_required=true | OK |
| legacy promote freeze default | OK |
| shadow mode 정상 | OK |
| image review rehearsal 정상 | OK |
| container execution standard | OK |
| `--allow-promote` 완전 차단 | NO |

중요:

`--allow-promote`는 기본값으로는 막혀 있지만 코드상 legacy escape hatch로 남아 있다. 따라서 운영 전환 전 완전 차단 상태는 아니다.

### promote cutover simulation

simulation flow:

```text
legacy staging path active but frozen
→ staging_external_places migration assumed
→ approved-only validator
→ image review persistence assumed
→ approved-only promote preview
→ no write
```

결과:

- legacy_candidate_count: 7
- approved_eligible_count: 0
- image_review_adjusted_eligible_count: 4
- image_approved_candidate_count: 4
- remaining BLOCK_MISSING_IMAGE: 3

approved preview candidates:

- 낫배드커피 도산
- 젠젠 성수점
- 카페 공명 연남점
- 크림시크

blocked candidates:

- 레자미오네뜨
- 아쿠아산타 성수카페
- 어퍼앤언더

report:

```text
qa_reports/pre_cutover_staging_image_rehearsal/
```

### reviewer rollback simulation

검증한 흐름:

- `approved → needs_manual_review`
- `approved → blocked_license`
- `approved → quarantine`

판단:

- rollback은 places write 전에 staging row에서 처리해야 한다.
- `approved`를 `needs_manual_review`, `rejected`, `blocked_license`로 되돌리면 promote eligibility에서 제외된다.
- blacklist/source risk 변경 후에는 image review report와 shadow mode를 재실행해야 한다.
- quarantine 상태는 `BLOCK_MISSING_IMAGE` 해제 대상이 아니다.

### operator confusion point

- `BLOCK_MISSING_IMAGE`: reviewer-approved image가 없으므로 promote 금지.
- `IMAGE_APPROVED`: image reviewer 승인 상태. final preview 전 write 금지.
- `IMAGE_LOW_CONFIDENCE_REVIEW`: 낮은 confidence. 자동 승인 금지.
- `blocked_license`: source/license risk. promote 금지.
- `REVIEW_REQUIRED`: 사람 판단 전 자동 promote 금지.
- `PROMOTE_ELIGIBLE`: preview상 가능. write 승인 의미 아님.
- `quarantine`: `needs_manual_review` 또는 `blocked_license`로 격리 후 shadow 재검증.

### migration readiness 최종 판단

현재 판단: NO-GO.

이유:

1. production migration 미적용
2. 실제 staging image review persistence write 미구현
3. legacy `--allow-promote` escape hatch 존재
4. migration 이후 DB-backed shadow mode 미검증

단, staging-only 운영 방향은 충분하다. 별도 `image_enrichment_candidates` 없이도 다음 단계 진행 가능하다.

### 다음 단계 권고

1. `--allow-promote` 제거 또는 승인 파일/환경변수 기반 이중 잠금
2. `staging_external_places` image columns migration 승인 판단
3. migration 적용 후 promote freeze 유지
4. 실제 staging row approve/reject persistence 구현
5. DB-backed shadow mode 재실행
6. 안정 확인 후 approved-only cutover 검토

### 검증

- `python -m py_compile`: 통과
- JSON/CSV/MD pre-cutover report 생성
- production migration 실행 없음
- production places write 없음
- raw overwrite 없음
- full reload 없음
- scraping 없음
- image 자동 approve 없음
- `BLOCK_MISSING_IMAGE` 직접 완화 없음
- docker compose down 없음
- saju 영향 없음

## 2026-05-20 legacy promote escape hatch hardening

### 목적

approved-only cutover 전 마지막 핵심 blocker였던 legacy escape hatch를 이중 잠금했다.

기존 위험 경로:

- `batch/update_all.sh --allow-promote`
- `batch.external.promote_external_places --qa-passed --write`

### hardening 결과

단순 CLI flag만으로는 legacy promote write가 불가능하다.

필수 조건:

```text
EXTERNAL_PROMOTE_UNLOCK=true
AND
approval file exists
AND
approval file content == APPROVED_ONLY_EXTERNAL_PROMOTE_UNLOCK
```

기본 approval file:

```text
.external_promote_unlock
```

override:

```text
EXTERNAL_PROMOTE_UNLOCK_FILE=/path/to/file
```

### promote freeze 강화

기본값 유지:

- `candidate_only=true`
- `no_promote=true`
- `review_required=true`

`--allow-promote`가 들어와도 env+approval file 조건을 모두 통과해야만 freeze가 풀린다.

### legacy bypass audit

| 경로 | 결과 |
|---|---|
| `update_all.sh --allow-promote` | env+approval file 없으면 차단 |
| `promote_external_places.py --qa-passed --write` | env+approval file 없으면 차단 |
| `staging_places` direct promote path | 코드상 남아 있지만 unlock 없으면 진입 불가 |
| shadow/rehearsal | read-only 유지 |

검증한 케이스:

- no env + no file: BLOCKED
- env true + missing file: BLOCKED
- file token exists + env false: BLOCKED

### operator warning

help/warning 문구를 강화했다.

- legacy promote는 emergency path
- approved-only review 미통과 후보 write 금지
- `--allow-promote`는 일반 운영 옵션 아님
- production write 전 final preview 필수

### report

```text
qa_reports/legacy_promote_hardening/
```

### migration readiness 변화

현재 판단: 여전히 NO-GO.

개선:

- uncontrolled legacy write 가능성은 제거됨
- migration apply 직전 운영 안전성은 이전보다 좋아짐

남은 blocker:

1. `staging_external_places` image review columns migration 미적용
2. 실제 staging image review persistence write 미구현
3. migration 이후 DB-backed shadow mode 미검증
4. cutover 후 legacy `staging_places` promote path 제거/비활성화 필요

### 검증

- `python -m py_compile`: 통과
- `update_all.sh --help`: 확인
- `promote_external_places.py --help`: 확인
- uncontrolled write path 없음 확인
- production migration 실행 없음
- production places write 없음
- production places row count 변화 없음
- raw overwrite 없음
- full reload 없음
- docker compose down 없음
- saju 영향 없음

## 2026-05-19 staging image persistence write rehearsal

### 목적

approved-only 전환 직전 마지막 blocker인 `staging_external_places` image review persistence write 흐름을 migration 없이 rehearsal했다.

실제 DB write는 수행하지 않았다.

### persistence payload 최종안

`review_image_candidates.py`의 rehearsal payload는 `staging_external_places` update 기준으로 고정했다.

필드:

- `staging_external_place_id`
- `image_review_status`
- `image_source`
- `image_url`
- `image_thumb_url`
- `image_confidence`
- `image_license_note`
- `image_reviewer`
- `image_review_note`
- `image_reviewed_at`
- `image_block_reason`

`staging_external_place_id`는 migration/table 적용 전에는 `null` 가능하다. migration 적용 후에는 실제 staging row id가 들어가야 한다.

### approve/reject rehearsal 결과

approve rehearsal:

- 낫배드커피 도산: `approved`, validator clear 가능
- 젠젠 성수점: `approved`, validator clear 가능
- 카페 공명 연남점: `approved`, validator clear 가능
- 크림시크: `approved`, validator clear 가능

reject/review rehearsal:

- 레자미오네뜨: `blocked_license`, validator clear 불가
- 아쿠아산타 성수카페: `low_confidence`, validator clear 불가
- 어퍼앤언더: `low_confidence`, validator clear 불가

### validator simulation 결과

조건:

```text
image_review_status = 'approved'
AND image_url IS NOT NULL
AND image_license_note IS NOT NULL
```

결과:

- legacy_candidate_count: 7
- approved_eligible_count: 0
- image_review_adjusted_eligible_count: 4
- image_approved_candidate_count: 4
- remaining BLOCK_MISSING_IMAGE: 3

approved preview candidates:

- 낫배드커피 도산
- 젠젠 성수점
- 카페 공명 연남점
- 크림시크

report 경로:

```text
qa_reports/staging_image_persistence_write_rehearsal/
qa_reports/shadow_mode_staging_image_persistence_rehearsal/
```

### rollback/freeze 판단

1. reviewer mistake rollback
   - `image_review_status='approved'`를 `needs_manual_review` 또는 `rejected`로 되돌리면 promote eligibility에서 제외 가능하다.
   - rollback은 places write 전에 staging row에서 처리해야 한다.

2. image source blacklist update
   - `image_block_reason`과 `blocked_license`를 기준으로 blacklist rule을 추가할 수 있다.
   - blacklist 변경 후 image review report와 shadow mode를 재실행해야 한다.

3. approved image quarantine
   - 승인 후 문제가 생긴 image는 `needs_manual_review` 또는 `blocked_license`로 격리한다.
   - quarantine 상태는 `BLOCK_MISSING_IMAGE` 해제 대상이 아니다.

4. promote freeze
   - migration 적용 직후에도 promote freeze 유지가 필요하다.
   - 실제 staging persistence write와 shadow mode가 안정된 뒤에만 promote cutover를 검토한다.

### migration readiness

현재 판단: 아직 NO-GO.

좋아진 점:

- staging-only persistence payload 확정
- approve/reject rehearsal 완료
- validator simulation에서 4건 adjusted eligible 확인

마지막 blocker:

1. `staging_external_places` image review columns migration 승인
2. 실제 staging row update 구현
3. reviewer mistake rollback command/report 구현
4. staging DB 기반 shadow mode 재검증

### 검증

- `python -m py_compile`: 통과
- JSON/CSV/MD rehearsal report 생성 확인
- production migration 실행 없음
- production places write 없음
- production `places` row count 변화 없음
- raw overwrite 없음
- full reload 없음
- scraping 없음
- image 자동 approve 없음
- `BLOCK_MISSING_IMAGE` 직접 완화 없음
- saju 영향 없음

## 2026-05-19 image persistence scope reduction

### 결정

image persistence 범위를 축소한다.

`image_enrichment_candidates` 별도 테이블 구현은 이번 단계에서 보류하고, `staging_external_places` image review columns 기준으로만 다음 단계를 진행한다.

이유:

1. 현재 목표는 운영 DB 오염 방지이며 별도 image workbench까지는 과함
2. migration 승인 범위를 줄여 실제 전환 가능성을 높여야 함
3. 운영자는 staging candidate 단위로 approve/reject하는 흐름이 더 단순함
4. 별도 image table은 staging 기반 gate가 부족하다는 증거가 생긴 뒤 추가해도 늦지 않음

### 유지할 image columns

`staging_external_places`에 필요한 필드:

- `image_source`
- `image_url`
- `image_thumb_url`
- `image_confidence`
- `image_license_note`
- `image_review_status`
- `image_reviewer`
- `image_review_note`
- `image_reviewed_at`
- `image_block_reason`

### migration draft 변경

`reports/external_places_data_pipeline_phase1_migration_draft.sql`에서 아래를 제거/보류했다.

- `image_enrichment_candidates` table draft
- `idx_image_enrichment_candidates_review`
- `idx_image_enrichment_candidates_place`

남긴 것은 `staging_external_places` image review columns와 staging image review index다.

### review_image_candidates.py 변경

rehearsal output을 `staging_external_places` update payload 기준으로 단순화했다.

유지:

- `--persistence-rehearsal`
- `--simulate-write`
- `--approve-image`
- `--reject-image`
- `--reviewer`
- `--review-note`
- `--image-license-note`

계속 차단:

- 실제 `--write`
- production DB write

### validator simulation 정책

`promote_external_places.py`의 image review simulation 조건을 staging 기준으로 정리했다.

`BLOCK_MISSING_IMAGE` 해제 simulation 조건:

```text
image_review_status = 'approved'
AND image_url exists
AND image_license_note exists
```

`IMAGE_APPROVED_SIMULATED`만으로는 충분하지 않다.

### migration readiness 변화

현재 판단은 여전히 NO-GO다.

다만 전환 범위가 줄어 다음 승인 단위가 명확해졌다.

### 서울 카페 staging-only 재검증

대상 7건 기준으로 staging-only image review report를 재생성했다.

결과:

- candidate_count: 7
- approved simulation: 4
- blocked_license: 1
- low_confidence: 2
- production write: 없음
- migration 실행: 없음

approved simulation 후보:

- 낫배드커피 도산
- 젠젠 성수점
- 카페 공명 연남점
- 크림시크

block/review 후보:

- 레자미오네뜨: source/license risk
- 아쿠아산타 성수카페: low confidence
- 어퍼앤언더: low confidence

### validator simulation 결과

`promote_external_places.py --shadow-mode --image-review-report` 기준:

- legacy_candidate_count: 7
- approved_eligible_count: 0
- image_review_adjusted_eligible_count: 4
- image_approved_candidate_count: 4
- remaining BLOCK_MISSING_IMAGE: 3

report 경로:

```text
qa_reports/image_review_staging_only_revalidation/
qa_reports/shadow_mode_seoul_cafe_staging_only_image_review/
```

남은 blocker:

1. `staging_external_places` image review columns migration 승인
2. approve/reject persistence write 구현
3. approved-only validator가 staging image columns를 직접 읽도록 전환
4. 서울 카페 slice 기준 staging-only shadow 재검증

### 검증 상태

- production migration 실행 없음
- production places write 없음
- raw overwrite 없음
- full reload 없음
- scraping 없음
- image 자동 approve 없음
- `BLOCK_MISSING_IMAGE` 직접 완화 없음
- saju 영향 없음

## 2026-05-19 image enrichment 공급망 blocker 분석

서울 카페 delta slice에서 후보 수는 7건까지 늘었지만 `PROMOTE_ELIGIBLE`은 0건이었다. 핵심 원인은 approved-only 정책 자체보다 image metadata 공급망 부족이다.

### 현재 구조

운영 DB 기준:

| table | image / quality column 상태 |
|---|---|
| `raw_external_places` | image 관련 컬럼 없음 |
| `clean_external_places` | image 관련 컬럼 없음 |
| `staging_places` | `first_image_url`, `first_image_thumb_url` 존재 |
| `places` | `first_image_url`, `first_image_thumb_url`, `rating`, `review_count`, `opening_hours`, `source_confidence` 존재 |

서울 카페 delta raw payload에는 다음 key만 있었다.

```text
address
category
description
link
mapx
mapy
roadAddress
telephone
title
```

`image`, `thumbnail`, `photo`, `first_image_url` 계열 key는 없었다.

### 유실 지점 판단

현재는 image가 중간에 유실되는 것보다 source에서 애초에 공급되지 않는 상태에 가깝다.

1. Naver local search 응답에 image field가 없다.
2. Kakao local keyword/category 응답도 장소명, 주소, 좌표, 카테고리, 전화번호, 상세 URL 중심이다.
3. raw/clean external table에는 image 컬럼이 아직 없다.
4. `clean_external_places.py`는 image metadata를 보존하지 않는다.
5. `enrich_external_places.py`는 `staging_places.first_image_url`을 채울 경로가 없다.

### Image Source 후보

| source | 판단 |
|---|---|
| Kakao Local | 장소 식별/좌표 source로는 유효하지만 image source로 기대하기 어렵다 |
| Naver Local Search | 현재 사용 중이나 image field 없음 |
| Naver Image Search API | thumbnail/link 제공 가능성이 있어 dry-run PoC 후보 |
| place_url scraping | 약관/운영 리스크가 커서 구현 금지, 검토만 가능 |
| curated fallback image | 대표 landmark/district 한정 가능, 일반 카페 대량 후보에는 부적합 |
| external media enrichment source | 별도 비용/약관 검토 필요 |

공식 문서 참고:

- Kakao Local REST API: https://developers.kakao.com/docs/latest/ko/local/dev-guide
- Naver Image Search API: https://developers.naver.com/docs/serviceapi/search/image/image.md

### Image Enrichment Pipeline 초안

권장 흐름:

```text
raw_external_places
→ clean_external_places
→ image_enrichment_candidates
→ image_validation
→ staging_external_places
→ review
→ approved-only promote preview
```

필요 필드:

- `image_source`
- `image_url`
- `image_thumb_url`
- `image_confidence`
- `image_verified_at`
- `image_hash`
- `is_curated_image`
- `is_fallback_image`
- `image_license_note`
- `image_review_status`

### `BLOCK_MISSING_IMAGE` 정책 비교

| 정책 | 장점 | 단점 | 판단 |
|---|---|---|---|
| hard block 유지 | 운영 DB 품질 보호 강함 | 정상 후보 유입 차단 | migration 전 기본값 유지 |
| reviewer approve 가능 | false negative 감소 | 운영자 판단 부담 증가 | image PoC 후 제한 검토 |
| curated fallback 허용 | 대표 후보 UX 개선 | 일반 카페에는 fake/mismatch 위험 | 대표 landmark/district 한정 |

현재 권고:

- 지금 당장 `BLOCK_MISSING_IMAGE`를 제거하지 않는다.
- 먼저 image enrichment dry-run PoC를 수행한다.
- 그래도 부족하면 reviewer 명시 승인 조건으로만 예외를 검토한다.

### 서울 카페 후보 재평가

delta 후보 7건:

- 낫배드커피 도산
- 젠젠 성수점
- 레자미오네뜨
- 카페 공명 연남점
- 아쿠아산타 성수카페
- 어퍼앤언더
- 크림시크

공통:

- 좌표/카테고리/role은 대체로 정상
- duplicate risk 없음
- business closed risk 없음
- image missing만으로 blocked

따라서 즉시 reject 대상이라기보다 image review 대상이다. 하지만 image 없는 카페를 production places로 promote하면 카드 품질 문제가 발생하므로 현재 gate가 막은 것은 안전 관점에서 타당하다.

### Migration Readiness 영향

현재 판단: migration apply 계속 NO-GO.

이유:

- approved-only shadow/report는 작동한다.
- 하지만 image supply가 없어 정상 후보도 `PROMOTE_ELIGIBLE`이 되지 않는다.
- 이 상태로 cutover하면 운영 DB 오염은 막지만 external data 유입이 사실상 멈춘다.

다음 권고:

1. Naver Image Search API 기반 image enrichment dry-run PoC
2. Kakao Local API 401 문제 해결
3. raw/clean image metadata 컬럼 migration proposal 보강
4. image enrichment 결과를 포함한 서울 카페 shadow validation 재실행
5. 그때 `PROMOTE_ELIGIBLE` 정상 후보가 생기는지 확인 후 migration readiness 재판단

검증:

- production `places` row count: `26381`, 변화 없음
- production migration 실행 없음
- production places write 없음
- raw overwrite 없음
- full reload 없음
- approved-only 완화 없음
- 추천 엔진 수정 없음
- saju 영향 없음

## 2026-05-19 image review gate simulation 결과

Naver Image Search PoC 결과를 바탕으로 image review gate를 report-only simulation 수준으로 구현했다. production migration, production `places` write, raw overwrite, full reload, scraping, image 자동 approve, `BLOCK_MISSING_IMAGE` 정책 완화는 수행하지 않았다.

### 추가 Script

```text
batch/external/review_image_candidates.py
```

역할:

- image enrichment PoC JSON report 읽기
- HIGH/MEDIUM/LOW 후보 분류
- blacklist/license/mismatch 후보 차단
- reviewer action simulation 생성
- JSON/CSV/Markdown report 생성

### Decision Taxonomy

| decision | 의미 |
|---|---|
| `IMAGE_REVIEW_REQUIRED` | reviewer 확인 필요 |
| `IMAGE_APPROVED_SIMULATED` | HIGH confidence를 simulation에서만 승인 |
| `IMAGE_REJECTED_SIMULATED` | usable image candidate 없음 |
| `IMAGE_BLOCKED_MISMATCH` | image/title/source mismatch |
| `IMAGE_BLOCKED_LICENSE_RISK` | Pinterest/pinimg 등 license/source risk |
| `IMAGE_LOW_CONFIDENCE_REVIEW` | low confidence라 reject 또는 manual review |

HIGH confidence도 자동 승인하지 않는다. `--simulate-approve-high` 옵션이 있을 때만 simulation상 approve 처리한다.

### Image Review Simulation 결과

대상:

- run_id: `b5ebd247-6601-4e81-9873-db07fd2c6d77`
- region: `서울`
- visit_role: `cafe`
- candidates: `7`
- simulate_approve_high: `true`

결과:

```text
IMAGE_APPROVED_SIMULATED = 4
IMAGE_BLOCKED_LICENSE_RISK = 1
IMAGE_LOW_CONFIDENCE_REVIEW = 2
```

image review report:

```text
/home/ubuntu/travel_service_prod/qa_reports/image_review_gate/image_review_gate_b5ebd247-6601-4e81-9873-db07fd2c6d77_서울_cafe_20260518_233158.json
/home/ubuntu/travel_service_prod/qa_reports/image_review_gate/image_review_gate_b5ebd247-6601-4e81-9873-db07fd2c6d77_서울_cafe_20260518_233158.csv
/home/ubuntu/travel_service_prod/qa_reports/image_review_gate/image_review_gate_b5ebd247-6601-4e81-9873-db07fd2c6d77_서울_cafe_20260518_233158.md
```

### 후보별 decision

| 후보 | decision |
|---|---|
| 낫배드커피 도산 | IMAGE_APPROVED_SIMULATED |
| 젠젠 성수점 | IMAGE_APPROVED_SIMULATED |
| 레자미오네뜨 | IMAGE_BLOCKED_LICENSE_RISK |
| 카페 공명 연남점 | IMAGE_APPROVED_SIMULATED |
| 아쿠아산타 성수카페 | IMAGE_LOW_CONFIDENCE_REVIEW |
| 어퍼앤언더 | IMAGE_LOW_CONFIDENCE_REVIEW |
| 크림시크 | IMAGE_APPROVED_SIMULATED |

### Image-approved Shadow Validation

`promote_external_places.py`에 shadow-mode 전용 옵션을 추가했다.

```text
--image-review-report
```

동작:

- image review report의 `IMAGE_APPROVED_SIMULATED` 후보를 읽음
- 해당 후보가 `BLOCK_MISSING_IMAGE` 단일 사유로 막힌 경우에만 shadow simulation에서 block 제거
- 실제 approved-only 정책, DB, migration은 변경하지 않음

결과:

```text
original approved_eligible_count = 0
image_review_adjusted_eligible_count = 4
image_approved_candidate_count = 4
remaining BLOCK_MISSING_IMAGE = 3
```

image-approved simulated eligible:

- 낫배드커피 도산
- 젠젠 성수점
- 카페 공명 연남점
- 크림시크

still blocked:

- 레자미오네뜨: license risk
- 아쿠아산타 성수카페: low confidence
- 어퍼앤언더: low confidence

shadow report:

```text
/home/ubuntu/travel_service_prod/qa_reports/shadow_mode_seoul_cafe_image_review/shadow_mode_b5ebd247-6601-4e81-9873-db07fd2c6d77_서울_cafe_20260518_233158.json
/home/ubuntu/travel_service_prod/qa_reports/shadow_mode_seoul_cafe_image_review/shadow_mode_b5ebd247-6601-4e81-9873-db07fd2c6d77_서울_cafe_20260518_233158.csv
/home/ubuntu/travel_service_prod/qa_reports/shadow_mode_seoul_cafe_image_review/shadow_mode_b5ebd247-6601-4e81-9873-db07fd2c6d77_서울_cafe_20260518_233158.md
```

### 정책 판단

이번 simulation으로 확인한 점:

1. image review gate를 붙이면 `BLOCK_MISSING_IMAGE`를 직접 완화하지 않아도 eligible 후보가 생긴다.
2. LOW/blacklist 후보는 계속 막을 수 있다.
3. 서울 카페 7건 기준 reviewer workload는 감당 가능하다.
4. 단, image approval persistence가 없으므로 migration apply는 아직 NO-GO.

### Migration Readiness 변화

현재 blocker는 image 공급망 자체보다 다음으로 이동했다.

- image review decision persistence 부재
- image source/license policy 미확정
- approved image를 promote validator에 반영하는 migration/persistence 구조 부재

approved-only 구조 자체는 viable하다. 다만 운영 전환 전에는 image approval 상태를 저장하고 validator가 이를 읽는 구조가 필요하다.

검증:

- `python -m py_compile` 통과
- image review report JSON/CSV/MD 생성
- image-approved shadow validation JSON/CSV/MD 생성
- production `places` row count: `26381`, 변화 없음
- production migration 실행 없음
- production places write 없음
- raw overwrite 없음
- full reload 없음
- scraping 없음
- approved-only 완화 없음
- saju 영향 없음

## 2026-05-19 Naver Image Search dry-run PoC 결과

서울 카페 delta 후보 7건에 대해 Naver Image Search API 기반 image enrichment 가능성을 dry-run으로 검증했다. production migration, production `places` write, raw overwrite, full reload, scraping, approved-only 완화는 수행하지 않았다.

### 추가 Script

```text
batch/external/image_enrichment_poc.py
```

역할:

- `clean_external_places` 후보 조회
- 후보별 query 생성
- Naver Image Search API 호출
- image candidate confidence 계산
- JSON/CSV/Markdown report 생성

자동 approve는 하지 않는다.

### 실행 결과

대상:

- run_id: `b5ebd247-6601-4e81-9873-db07fd2c6d77`
- region: `서울`
- visit_role: `cafe`
- candidate_count: `7`

summary:

```text
places_with_image_candidates = 7
high_confidence_count = 4
medium_confidence_count = 0
low_confidence_count = 3
none_count = 0
errors_count = 0
```

생성 report:

```text
/home/ubuntu/travel_service_prod/qa_reports/image_enrichment_poc/image_enrichment_poc_b5ebd247-6601-4e81-9873-db07fd2c6d77_서울_cafe_20260518_232445.json
/home/ubuntu/travel_service_prod/qa_reports/image_enrichment_poc/image_enrichment_poc_b5ebd247-6601-4e81-9873-db07fd2c6d77_서울_cafe_20260518_232445.csv
/home/ubuntu/travel_service_prod/qa_reports/image_enrichment_poc/image_enrichment_poc_b5ebd247-6601-4e81-9873-db07fd2c6d77_서울_cafe_20260518_232445.md
```

### Confidence Heuristic

현재 heuristic:

- place name/title similarity
- region token match
- cafe/category token match
- blacklist term 감점

blacklist 예:

- `pinterest`
- `pinimg`
- `banner`
- `logo`
- `menu`
- `coupon`

confidence:

- `HIGH`: reviewer image candidate
- `MEDIUM`: manual review
- `LOW`: reject 또는 manual review

중요: `HIGH`도 자동 approve가 아니다.

### 후보별 판단

| 후보 | confidence | mismatch | action |
|---|---|---|---|
| 낫배드커피 도산 | HIGH | none | REVIEW_IMAGE_CANDIDATE |
| 젠젠 성수점 | HIGH | none | REVIEW_IMAGE_CANDIDATE |
| 레자미오네뜨 | LOW | blacklist:pinimg | REJECT_OR_MANUAL_REVIEW |
| 카페 공명 연남점 | HIGH | none | REVIEW_IMAGE_CANDIDATE |
| 아쿠아산타 성수카페 | LOW | low score | REJECT_OR_MANUAL_REVIEW |
| 어퍼앤언더 | LOW | low score | REJECT_OR_MANUAL_REVIEW |
| 크림시크 | HIGH | none | REVIEW_IMAGE_CANDIDATE |

### Mismatch Risk

`레자미오네뜨`는 title score는 높지만 `pinimg` 계열 thumbnail이라 blacklist 처리했다. 이 케이스는 “텍스트 매칭이 좋아도 source/license risk가 있으면 자동 연결하면 안 된다”는 대표 사례다.

`아쿠아산타 성수카페`, `어퍼앤언더`는 image candidate는 있으나 title/source alignment가 낮다. broader article/cafe image로 흐를 가능성이 있어 reviewer 확인 전 사용 금지.

### 현실성 판단

Naver Image Search는 image metadata blocker를 풀 가능성이 있다.

다만 바로 production image로 연결하기에는 부족하다.

필요한 보완:

1. image candidate review gate
2. source/license note
3. source reliability scoring
4. blacklist 강화
5. reviewer thumbnail preview

### `BLOCK_MISSING_IMAGE` 영향

이번 결과로도 `BLOCK_MISSING_IMAGE`를 제거하면 안 된다.

대신 권장 흐름:

```text
BLOCK_MISSING_IMAGE
→ image enrichment candidate 생성
→ HIGH/MEDIUM 후보 reviewer preview
→ reviewer image approve
→ image missing block 해제
```

LOW 또는 mismatch candidate는 계속 block한다.

### Migration Readiness 영향

현재 판단: migration apply는 아직 NO-GO.

변화:

- image candidate 생성 가능성은 확인됨
- 하지만 image validation/review/persistence 구조가 아직 없음
- `PROMOTE_ELIGIBLE` 정상 후보를 만들려면 image review gate가 먼저 필요

다음 단계:

1. `image_enrichment_candidates` report-only workflow를 먼저 정리
2. image review status 정책 추가
3. HIGH image candidate만 포함한 shadow validation 재실행
4. reviewer approve simulation 후 `PROMOTE_ELIGIBLE` 발생 여부 확인

검증:

- production `places` row count: `26381`, 변화 없음
- production migration 실행 없음
- production places write 없음
- raw overwrite 없음
- full reload 없음
- scraping 없음
- approved-only 완화 없음
- 추천 엔진 수정 없음
- saju 영향 없음


---

## 2026-05-23 Mobile UX Deployment Sync

### 목적

현재 운영 서버의 mobile UX polish 결과를 canonical source로 확정하고 GitHub remote와 동기화한다.

### 반영 범위

- HomeScreen mobile UX polish
  - district selector mobile density 개선
  - 출발 시간대 accordion 기본 접힘 유지
  - CTA visibility / loading state 개선
- CourseResultScreen mobile UX polish
  - cafe placeholder neutral abstract polish
  - regenerate loading / transition polish
  - result card readability 개선
- 관련 phase report 반영
  - time-band accordion
  - cafe placeholder
  - CTA polish
  - regenerate UX
  - district selector polish
  - result card readability
  - mobile UX smoke QA

### Mobile UX Smoke QA 결과

- HomeScreen: district selector, time-band accordion, CTA 흐름 정상
- CourseResultScreen: 카드 순번, description density, cafe placeholder 정상
- regenerate: 성수/북촌/한남/강남 기준 3회 반복 smoke 통과
- NO_COURSE: 재발 없음
- places_empty: 재발 없음
- production migration: 실행 없음
- production places write: 없음
- saju 영향: 없음

### Deployment Readiness

현재 mobile UX polish 범위는 frontend-only redeploy 대상으로 판단한다.
Backend/recommendation engine/DB schema 변경은 이번 deployment sync 범위에 포함하지 않는다.

### Canonical Source 상태

운영 서버 /home/ubuntu/travel_service_prod의 선별 변경분을 commit/push 대상으로 삼는다.
qa_reports, .env, key, tmp, log, dist, node_modules, cache, 무관 backend 변경은 commit 대상에서 제외한다.

## 2026-05-23 Role Sequence Trace Runtime Smoke Phase1

- support-slot role sequence trace를 backend-only 방식으로 운영 배포했다.
- 배포 범위는 `recommendation_observability.py`, `course_builder.py`의 observability-only 변경이다.
- 추천 scoring, candidate filtering, bounded replacement, route assembly 동작 변경은 적용하지 않았다.
- 운영 smoke 결과 `/api/regions=200`, `places` row count `26381`, `NO_COURSE=0`, `places_empty=0`을 확인했다.
- 실제 `/api/course/generate` 응답에서 아래 trace 필드가 관찰됐다.
  - `support_slot_role_sequence`
  - `support_slot_role_repetition`
  - `support_slot_indoor_count`
  - `support_slot_missing_preferred_roles`
  - `support_slot_role_balance_score`
- 소량 runtime smoke 대상은 성수, 북촌, 한남, 강남 각 2회다.
- 한남에서 `meal -> meal` support-slot repetition이 반복 관찰되어, 다음 role diversity soft-demote 후보로 기록한다.
- soft demote, score 변경, candidate 제거는 아직 보류한다.
- 상세 보고서는 `reports/role_sequence_trace_runtime_smoke_phase1.md`에 기록했다.
## 2026-05-24 Meal Repetition Soft Demote Phase1

- support-slot role diversity phase3로 한남 `meal -> meal` repetition에만 very small soft demote를 적용했다.
- 적용 범위는 `selected_anchor_family_id == seoul_hannam`, support-slot, previous/current semantic role이 모두 meal인 경우로 제한했다.
- penalty는 `same_role_soft_demote_delta = 0.018`이며 candidate 제거, hard replacement, first-place 변경은 없다.
- trace 필드는 `same_role_soft_demote_applied`, `same_role_soft_demote_role`, `same_role_soft_demote_delta`, `same_role_soft_demote_applied_count`를 사용한다.
- 한남 runtime smoke 5회 결과 `NO_COURSE=0`, `places_empty=0`, meal repetition `0/5`를 확인했다.
- 성수 side effect smoke 3회 결과 soft demote 미적용, cafe identity 유지, `NO_COURSE=0`, `places_empty=0`을 확인했다.
- 성수 같은 cafe-led district에는 cafe repetition demote를 적용하지 않는 원칙을 유지한다.
- 상세 보고서는 `reports/meal_repetition_soft_demote_phase1.md`에 기록했다.
## 2026-05-24 Meal Repetition Accumulation Window Phase1

- 한남 meal repetition tiny penalty `0.018`의 짧은 accumulation 관찰을 수행했다.
- 대상은 한남, 성수, 북촌, 강남 각 6회, 총 24회다.
- 전체 결과 `NO_COURSE=0`, `places_empty=0`, production places write 없음, migration 없음.
- 한남은 meal repetition `0/6`, soft demote trace count sum `24`, avg role balance `0.9700`, avg coherence `0.7847`로 관찰됐다.
- 성수는 soft demote trace `0`, cafe identity 유지, cafe repetition 억지 suppression 없음.
- 북촌/강남은 이번 penalty 영향은 없었으나 기존 weak support 후보는 별도 editorial cleanup 후보로 남긴다.
- 현재 penalty는 유지 가능하지만, cafe repetition demote, indoor-heavy penalty, bounded replacement는 계속 금지한다.
- 상세 보고서는 `reports/meal_repetition_accumulation_window_phase1.md`에 기록했다.
## 2026-05-24 Gangnam Editorial Support Cleanup Proposal Phase1

- 강남 support 후보 문제를 role repetition이 아니라 editorial support quality 문제로 분리했다.
- 대표 support taxonomy는 COEX-family, Garosugil walk, Apgujeong/Cheongdam lifestyle, Bongeunsa/Seonjeongneung heritage support, Starfield/urban landmark, curated cafe/walk support로 정리했다.
- weak risk group은 public/training venue, generic indoor education/culture, weak lifestyle slot, repeated generic meal support로 분류했다.
- 국기원, 국가무형유산전수교육관, 한생연 실험누리과학관, 슈피겐홀, 반려문화는 hard-invalid가 아니라 context-dependent weak support로 기록한다.
- 진수사/콴안다오는 global meal demote 대상이 아니라 강남 support-slot repeated generic meal risk로만 추적한다.
- 실제 demote, scoring 변경, bounded replacement는 아직 적용하지 않는다.
- 향후 필요 시 강남-only editorial support-fit trace counter부터 추가하는 것이 안전하다.
- 상세 보고서는 `reports/gangnam_editorial_support_cleanup_phase1.md`에 기록했다.
## 2026-05-24 Gangnam Editorial Fit Trace Phase1

- 강남 editorial support quality를 scoring이 아니라 trace-only observability로 노출했다.
- 추가 trace는 `gangnam_editorial_support_fit`, `gangnam_weak_public_support_risk`, `gangnam_repeated_generic_meal_support`, `gangnam_support_candidate_tags`다.
- helper는 final selected route만 읽으며 ranking/filtering/route assembly에는 연결하지 않는다.
- 강남 runtime smoke 6회 결과 `NO_COURSE=0`, `places_empty=0`, avg editorial support fit ratio `0.2917`이다.
- weak public/training support risk는 6건, generic meal support risk는 11건으로 관찰됐다.
- 아직 demote, score 변경, replacement는 적용하지 않는다.
- 향후에도 global public-facility demote와 global meal demote는 금지하고, 필요 시 강남 support-slot only tiny policy로 별도 phase를 분리한다.
- 상세 보고서는 `reports/gangnam_editorial_fit_trace_phase1.md`에 기록했다.

## 2026-05-24 Gangnam Weak Support Candidate Action Plan Phase1

- 강남 editorial fit trace 결과를 기준으로 weak support 후보를 원인별로 분류했다.
- 원인 그룹은 public/training, generic meal, weak indoor/culture, weak lifestyle로 나눴다.
- `국가무형유산전수교육관`, `국기원(세계태권도본부)`, `슈피겐홀`은 hard-invalid가 아니라 context-dependent weak support로 유지한다.
- `콴안다오`, `진수사`, `토말 본점`, `송화유수`, `알라프리마`는 global meal demote 대상이 아니라 강남 support-slot repeated generic meal risk로만 추적한다.
- 보강 우선 후보군은 COEX-family, 봉은사/선정릉 heritage, 가로수길 walk, 압구정/청담 lifestyle, curated cafe/walk support다.
- 이번 phase에서도 demote, scoring 변경, bounded replacement, DB write는 적용하지 않는다.
- 다음 단계는 candidate 보강 및 trace accumulation이며, cleanup이 필요하더라도 강남 support-slot only tiny policy로 별도 승인 후 진행한다.
- 상세 보고서는 `reports/gangnam_weak_support_candidate_action_plan_phase1.md`에 기록했다.
