# time_band_accordion_mobile_ux_phase1

## 목표

출발 시간대 선택 영역을 모바일 기준 기본 접힘 accordion UI로 전환해 첫 화면 공간 점유를 줄이고 CTA 노출을 앞당긴다.

## 수정 상태

이미 적용된 상태를 재검증했다.

수정 파일:

- `frontend/src/screens/day-trip/HomeScreen.jsx`
- `travel_service_handoff_master_2026-05-18.md`

## Accordion 기본 collapsed 여부

`HomeScreen.jsx` 기준:

```jsx
const [timeBandExpanded, setTimeBandExpanded] = useState(false);
```

따라서 기본 상태는 collapsed다.

collapsed 상태 표시:

```text
출발 시간대 · 아침
출발 시간대 · 낮
출발 시간대 · 저녁
```

expanded 상태에서만 아침 / 낮 / 저녁 selector가 노출된다.

시간대 선택 시:

```jsx
setTimeBandExpanded(false);
```

선택 후 다시 collapsed 상태로 돌아간다.

## 보장형 문구 제거 유지

production bundle에서 다음 문구가 없는 것을 확인했다.

- `브런치 코스로`
- `가장 다양한 장소`
- `야경·산책 중심`

`추천` badge도 time-band accordion 영역에 없다.

## 모바일 spacing 개선 결과

이전 구조:

- section title
- time-band card header
- 아침/낮/저녁 3개 버튼
- 선택 안내 박스

현재 collapsed 구조:

- single accordion row
- 현재 선택 상태
- chevron toggle

예상 절감 높이:

- 약 100px 이상

효과:

- 첫 화면에서 여행지 선택 영역과 CTA가 더 빨리 보인다.
- 시간대 selector는 필요할 때만 열리므로 스크롤 피로가 줄어든다.
- 선택 상태는 collapsed 상태에서도 유지된다.

## CTA visibility

CTA 자체 로직은 변경하지 않았다.

다만 time-band 영역이 기본 collapsed가 되면서, 모바일 첫 화면에서 CTA까지 도달하는 vertical distance가 줄었다.

## Android/iPhone viewport 확인

자동 브라우저 렌더링 도구는 현재 세션에서 사용할 수 없었다.

대신 다음을 확인했다.

- production bundle에 `출발 시간대 ·` 반영
- production bundle에 `aria-expanded` 반영
- selector는 `repeat(3, minmax(0, 1fr))` grid 유지
- collapsed row는 `minHeight: 56`
- expanded option button은 `height: 54`
- `wordBreak`이 필요한 긴 설명 문구는 제거되어 overflow risk가 낮아졌다.

실기기에서 최종 확인할 항목:

- Android Chrome: open/close tap target 정상
- Samsung Internet: chevron 회전과 selector grid 깨짐 없음
- iPhone Safari: safe-area 하단 CTA와 겹침 없음

## Safety

- 추천 엔진 수정 없음
- departure mapping 수정 없음
- 코스 로직 수정 없음
- backend 수정 없음
- `docker compose down` 미사용
- 사주 영향 없음
