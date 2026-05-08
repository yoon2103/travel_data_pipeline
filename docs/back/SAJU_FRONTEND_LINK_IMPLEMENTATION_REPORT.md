# Saju Frontend Link Implementation Report

## 수정 파일

- `frontend/src/screens/day-trip/MyScreen.jsx`
- `frontend/.env.example`
- `frontend/.env.staging.example`

## 추가 env

Frontend Vite env:

```text
VITE_SHOW_SAJU_LINK=true
VITE_SAJU_SERVICE_URL=https://saju-mbti-service.duckdns.org/
```

주의:

- `VITE_*` 값은 프론트 번들에 포함되는 public config이다.
- secret 값을 넣으면 안 된다.
- URL이 없거나 `VITE_SHOW_SAJU_LINK`가 `true`가 아니면 버튼은 숨겨진다.

## 버튼 위치

위치:

- `frontend/src/screens/day-trip/MyScreen.jsx`
- 저장/마이 화면 본문 상단
- 저장한 코스 영역보다 위에 표시

노출 조건:

```js
import.meta.env.VITE_SHOW_SAJU_LINK === 'true'
typeof sajuServiceUrl === 'string'
isSafeExternalUrl(sajuServiceUrl)
```

URL 검증:

- `http:`
- `https:`

이외 protocol 또는 잘못된 URL은 숨김 처리된다.

## 동작 방식

버튼:

```text
사주/MBTI 보러가기
여행 성향도 가볍게 확인해 보세요
```

동작:

- `<a>` 링크 사용
- `href=https://saju-mbti-service.duckdns.org/`
- `target="_blank"`
- `rel="noopener noreferrer"`

선택 이유:

- 여행 서비스 현재 화면을 유지한 채 사주 서비스를 새 탭으로 연다.
- 모바일 Chrome에서도 일반 외부 링크 탭 동작을 따른다.
- backend/proxy/nginx를 거치지 않는다.

## 테스트 결과

### env OFF

실행:

```powershell
Remove-Item Env:VITE_SHOW_SAJU_LINK -ErrorAction SilentlyContinue
Remove-Item Env:VITE_SAJU_SERVICE_URL -ErrorAction SilentlyContinue
npm run build
rg -n "saju-mbti-service|사주/MBTI 보러가기" dist
```

결과:

- build PASS
- `OFF_OK_NOT_RENDERED`
- 버튼/도메인 문자열 dist에 없음

### env ON but URL missing

실행:

```powershell
$env:VITE_SHOW_SAJU_LINK='true'
Remove-Item Env:VITE_SAJU_SERVICE_URL -ErrorAction SilentlyContinue
npm run build
rg -n "saju-mbti-service|사주/MBTI 보러가기" dist
```

결과:

- build PASS
- `MISSING_URL_OK_NOT_RENDERED`
- URL 누락 시 버튼 숨김

### env ON

실행:

```powershell
$env:VITE_SHOW_SAJU_LINK='true'
$env:VITE_SAJU_SERVICE_URL='https://saju-mbti-service.duckdns.org/'
npm run build
rg -n "saju-mbti-service|사주/MBTI 보러가기|_blank|noopener noreferrer" dist
```

결과:

- build PASS
- `https://saju-mbti-service.duckdns.org/` 포함 확인
- `사주/MBTI 보러가기` 포함 확인
- `_blank` 포함 확인
- `noopener noreferrer` 포함 확인

### 모바일 브라우저 기준

구현 방식:

- button이 아니라 native anchor 사용
- 모바일 Chrome에서 터치 가능한 일반 링크
- 새 탭 방식
- proxy/API 호출 없음

실기기 브라우저 수동 확인은 별도 배포/preview 단계에서 수행하면 된다.

## 배포 영향

영향 범위:

- frontend build only
- backend 변경 없음
- DB 변경 없음
- migration 없음
- nginx/proxy 변경 없음
- 외부 API 호출 없음

배포 시 주의:

- 실제 운영 build 환경에 `VITE_SHOW_SAJU_LINK=true`와 `VITE_SAJU_SERVICE_URL`을 제공해야 버튼이 노출된다.
- 값을 제공하지 않으면 안전하게 숨김 처리된다.

## 대표 governance 영향 없음 확인

변경하지 않은 파일:

- `api_server.py`
- `course_builder.py`
- `tourism_belt.py`
- `batch/place_enrichment/*`
- representative/seed governance docs

영향 없음:

- representative workflow
- seed overlay workflow
- place enrichment
- recommendation engine
- DB

## 다음 작업 제안

1. 운영 build 환경에 frontend Vite env 주입 방식 확정
2. production preview에서 마이 탭 버튼 노출 확인
3. 모바일 실기기에서 새 탭 이동 확인
4. 다음 사용자-facing 작업으로 저장 기능 MVP 범위 결정
