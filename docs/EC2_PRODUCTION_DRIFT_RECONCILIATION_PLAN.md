# EC2 Production Drift Reconciliation Plan

## 목표

EC2 운영 서버 `/home/ubuntu/travel_data_pipeline`의 dirty working tree를 안전하게 정리하여 Git source-of-truth 기반 배포가 가능한 상태로 되돌린다.

현재 상태:

```text
BLOCKED
```

이 문서는 planning only다. 코드 수정, git reset, git clean, deploy, DB 수정은 수행하지 않는다.

## Drift 분류

### git 반영 필요

운영에 필요한 것으로 판단되는 파일이다. 로컬 repo와 비교 후 정식 commit 대상으로 검토한다.

| 파일 | 분류 | 이유 | 우선순위 |
| --- | --- | --- | --- |
| `Dockerfile` | 운영 backend Dockerfile | 현재 EC2 compose의 `travel-backend` build source | HIGH |
| `docker-compose.yml` | 운영 compose | travel backend/frontend를 saju external network에 연결 | HIGH |
| `frontend/Dockerfile` | 운영 frontend Dockerfile | 현재 `travel-frontend` nginx static image build source | HIGH |
| `frontend/.dockerignore` | frontend build 보조 파일 | build context에서 node_modules/dist/env 제외 | MEDIUM |
| `batch/update_all.sh` | 운영 데이터 업데이트 wrapper 후보 | 운영 batch entry point 가능성 | MEDIUM |

주의:

- `docker-compose.yml`과 `frontend/Dockerfile`에는 현재 VITE env injection이 없으므로, 로컬 최신 수정본과 reconcile 필요.
- `Dockerfile`은 backend 배포용이므로 frontend-only 배포와 직접 관련은 없지만 운영 재현성에는 필요하다.

### archive 필요

git에 넣으면 안 되지만 삭제 전 보관해야 하는 파일이다.

| 파일 | 분류 | 이유 | 우선순위 |
| --- | --- | --- | --- |
| `travel_db.dump` | DB binary dump | 운영 데이터 포함 가능성, git push 금지 | HIGH |
| `travel_db.sql` | DB SQL dump | 운영 데이터 포함 가능성, git push 금지 | HIGH |
| `_anchor_test.txt` 등 `_*.txt` | 진단 산출물 | 재현성 확인 후 archive 가능 | LOW |
| `test_sokcho*.json` | 테스트 산출물 | 운영 로직 파일 아님 | LOW |
| `check_*_out.txt` | 검증 output | 운영 코드 아님 | LOW |

### ignore 필요

repo에 들어가면 안 되는 산출물 패턴이다.

권장 `.gitignore` 패턴:

```gitignore
# DB dumps / backups
*.dump
*.sql
travel_db*.dump
travel_db*.sql
backups/
*.backup

# local QA outputs
*_out.txt
*_test.txt
test_*.json
qa_reports/

# Python/Node generated files
__pycache__/
*.pyc
node_modules/
dist/
.vite/
```

주의:

- migration SQL은 ignore하면 안 된다.
- `sql/` 아래 운영 검증 문서는 무조건 ignore하지 않는다.
- `travel_db.sql` 같은 dump와 migration SQL을 구분해야 한다.

### 삭제 후보

삭제 전 archive 여부를 먼저 확인해야 한다.

| 파일 | 분류 | 삭제 가능 조건 |
| --- | --- | --- |
| `_anchor_test.txt` | 테스트 output | 동일 내용이 docs/report에 반영된 경우 |
| `_course_quality_test.txt` | 테스트 output | QA report에 반영된 경우 |
| `_dq_diagnosis.txt` | 진단 output | 별도 보존 필요 없을 경우 |
| `_enrich_test.txt` | 진단 output | enrichment report에 반영된 경우 |
| `_template_test.txt` | 테스트 output | 별도 보존 필요 없을 경우 |
| `check_*_out.txt` | command output | 재현 가능하면 삭제 가능 |
| `debug.py` | 임시 debug script | 운영 코드가 아니면 archive 후 삭제 |
| `run_fix_103.py` | 임시 fix script | 재실행 필요 없으면 archive 후 삭제 |
| `run_zone_verify.py` | 검증 script | repo에 둘지 판단 필요 |
| `test_course.py` | 임시 test script | 정식 tests로 이동했는지 확인 |
| `test_sokcho*.json` | 테스트 결과 JSON | QA report로 대체 가능하면 archive 후 삭제 |

### line ending normalize 후보

실질 로직 변경보다 CRLF/LF drift 가능성이 큰 파일이다.

| 파일 | 근거 | 위험도 |
| --- | --- | --- |
| `api_server.py` | `--ignore-space-at-eol` 기준 실질 diff 없음 | MEDIUM |
| `course_builder.py` | `--ignore-space-at-eol` 기준 실질 diff 없음 | HIGH |
| `regional_zone_builder.py` | `--ignore-space-at-eol` 기준 실질 diff 없음 | MEDIUM |
| `.gitignore` | `--ignore-space-at-eol` 기준 실질 diff 없음 | LOW |
| 테스트/진단 output 파일 다수 | `--ignore-space-at-eol` 기준 실질 diff 없음 | LOW |

## 운영 필수 파일 처리 전략

### Dockerfile

현재 EC2 내용:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"]
```

처리 전략:

1. 로컬 repo의 backend Dockerfile 또는 `Dockerfile.staging`과 비교.
2. EC2 운영 컨테이너가 이 파일로 build되는지 확인.
3. 운영 재현성에 필요하면 git에 추가.
4. frontend-only 배포에서는 이 파일을 수정하지 않는다.

### docker-compose.yml

현재 EC2 역할:

- `travel-backend`
- `travel-frontend`
- external network `saju_mbti_saju-net`

처리 전략:

1. 반드시 git 관리 대상으로 편입한다.
2. `travel-frontend.build.args`에 VITE env injection 구조를 추가한 로컬 최신본과 reconcile한다.
3. `saju-nginx` 설정은 이 파일에서 관리하지 않는다.
4. `travel-backend` build/recreate가 실수로 발생하지 않도록 runbook에 명령 제한 유지.

권장 반영 형태:

```yaml
travel-frontend:
  build:
    context: ./frontend
    args:
      VITE_SHOW_SAJU_LINK: ${VITE_SHOW_SAJU_LINK:-false}
      VITE_SAJU_SERVICE_URL: ${VITE_SAJU_SERVICE_URL:-}
```

### frontend/Dockerfile

현재 EC2 내용에는 VITE env injection이 없다.

처리 전략:

1. 로컬 최신 `frontend/Dockerfile`을 source-of-truth 후보로 사용.
2. build stage에 `ARG/ENV VITE_*` 포함.
3. nginx static serving 구조는 유지.
4. runtime nginx env 방식은 사용하지 않는다.

필수 구조:

```dockerfile
ARG VITE_SHOW_SAJU_LINK=false
ARG VITE_SAJU_SERVICE_URL=

ENV VITE_SHOW_SAJU_LINK=$VITE_SHOW_SAJU_LINK
ENV VITE_SAJU_SERVICE_URL=$VITE_SAJU_SERVICE_URL
```

### frontend/.dockerignore

현재 EC2 내용:

```text
node_modules
dist
.vite
.env
```

처리 전략:

1. git 관리 대상으로 편입 권장.
2. `.env`를 build context에서 제외하는 것은 적절.
3. public env는 Docker build args로 전달한다.

## DB dump 처리 전략

대상:

- `travel_db.dump`
- `travel_db.sql`

현재 위험:

- repo root에 존재
- git status에 untracked로 노출
- 실수 commit/push 위험
- 운영 데이터/민감정보 포함 가능성

권장 처리:

1. 삭제 전 checksum 기록.

```bash
md5sum travel_db.dump travel_db.sql
```

현재 확인값:

```text
f1dc80456e75b4a2ea7e386b84b08e80  travel_db.dump
104fbae0334b829d4f92416e3b077c97  travel_db.sql
```

2. repo 밖 backup 경로로 이동.

예:

```bash
mkdir -p /home/ubuntu/backups/travel_data_pipeline
mv travel_db.dump /home/ubuntu/backups/travel_data_pipeline/
mv travel_db.sql /home/ubuntu/backups/travel_data_pipeline/
```

3. 권한 제한.

```bash
chmod 600 /home/ubuntu/backups/travel_data_pipeline/travel_db.*
```

4. `.gitignore` 강화.

```gitignore
*.dump
travel_db*.sql
travel_db*.dump
backups/
```

주의:

- 이 계획 문서에서는 실제 이동/권한 변경을 수행하지 않았다.
- 운영자가 백업 필요성을 확인한 뒤 별도 작업으로 수행해야 한다.

## Line ending normalize 전략

문제:

- `api_server.py`, `course_builder.py`, `regional_zone_builder.py`가 CRLF/LF drift로 dirty 상태.
- `course_builder.py`는 추천 엔진 핵심 파일이라 배포 blocker.

권장 정책:

1. `.gitattributes`에서 text normalization 기준 확정.

권장:

```gitattributes
*.py text eol=lf
*.jsx text eol=lf
*.js text eol=lf
*.css text eol=lf
*.md text eol=lf
*.yml text eol=lf
*.yaml text eol=lf
*.sh text eol=lf
*.ps1 text eol=crlf
```

2. 로컬 개발환경에서 normalize commit 생성.

예:

```bash
git add --renormalize .
git diff --cached --check
```

3. 운영 서버에서는 `reset --hard`로 처리하지 않는다.

4. 운영 서버는 정리 전 파일 백업 후 source-of-truth commit을 pull하는 방식으로 복구한다.

주의:

- line ending normalize commit은 기능 변경 commit과 분리하는 것이 좋다.
- `course_builder.py` normalize는 추천 로직 변경과 섞으면 안 된다.

## Frontend drift 처리 전략

대상:

- `frontend/src/App.jsx`
- `frontend/src/components/common/MobileShell.jsx`
- `frontend/src/index.css`
- `frontend/src/screens/day-trip/HomeScreen.jsx`

변경 성격:

- mock status bar 제거
- preview frame DEV/flag 전용화
- production viewport full screen 적용
- body scroll/pull-to-refresh 복구
- HomeScreen internal scroll 완화

처리 전략:

1. 로컬 최신 frontend 작업과 EC2 drift 비교.
2. 동일한 UX fix라면 git commit 대상으로 포함.
3. 다르면 EC2 drift를 patch로 백업 후 로컬에서 검토.
4. staging build/lint 재검증.
5. 모바일 smoke test 항목에 포함.

권장 commit 분리:

1. frontend mobile shell/scroll UX fix
2. frontend VITE env injection Docker/compose fix
3. line ending normalize

이유:

- 배포 문제가 생겼을 때 rollback 범위를 명확하게 하기 위해서다.

## Clean 상태 목표

최종 목표:

```bash
cd /home/ubuntu/travel_data_pipeline
git status --short
```

기대:

```text
<empty>
```

또는 `.env`처럼 gitignore 대상인 운영 파일만 존재하고 git status에는 표시되지 않아야 한다.

clean 상태 조건:

- 운영 Dockerfile/compose가 git source-of-truth에 포함
- DB dump가 repo root 밖으로 이동
- 테스트 산출물 archive 또는 ignore 처리
- line ending drift 해소
- frontend UI drift가 commit 또는 폐기 기준으로 정리
- `.env`에는 frontend public env 존재
- `git pull --ff-only` 가능

## 안전한 정리 순서

### Phase 0. 작업 중단 유지

현재는 배포 금지.

금지:

- git pull
- docker build
- docker compose up
- reset/clean

### Phase 1. drift backup 준비

운영자 승인 후 repo 외부 백업 생성.

백업 대상:

- 운영 필수 untracked 파일
- DB dump
- frontend drift patch
- backend/engine drift patch

예상 명령:

```bash
mkdir -p /home/ubuntu/backups/travel_data_pipeline/drift_$(date +%Y%m%d_%H%M%S)
```

### Phase 2. patch export

삭제/정리 전 patch로 보존.

예:

```bash
git diff > /home/ubuntu/backups/travel_data_pipeline/drift_YYYYMMDD_HHMMSS/tracked.diff
git ls-files --others --exclude-standard > /home/ubuntu/backups/travel_data_pipeline/drift_YYYYMMDD_HHMMSS/untracked.txt
```

### Phase 3. DB dump archive

`travel_db.dump`, `travel_db.sql`을 repo 밖으로 이동.

주의:

- DB restore 명령 실행 금지.
- DB 파일 삭제 전 archive 확인.

### Phase 4. 운영 필수 파일을 로컬 repo에 반영

로컬에서 처리:

- `Dockerfile`
- `docker-compose.yml`
- `frontend/Dockerfile`
- `frontend/.dockerignore`

VITE env injection 포함.

### Phase 5. frontend drift reconcile

로컬에서 처리:

- EC2 drift와 로컬 latest 비교
- 필요한 UX fix는 commit
- 불필요하면 archive 후 제외

### Phase 6. line ending normalize

로컬에서 별도 commit으로 처리.

대상:

- `.gitattributes`
- Python/JS/CSS/MD/YAML line ending

### Phase 7. EC2 clean 재확인

source-of-truth commit push 후 EC2에서:

```bash
git status --short
```

clean 상태가 아니면 배포 재개 금지.

### Phase 8. env 확인

EC2 `.env`에 public frontend env 추가 여부 확인.

```bash
grep -E '^VITE_SHOW_SAJU_LINK=|^VITE_SAJU_SERVICE_URL=' .env
```

### Phase 9. frontend-only deploy 재개

clean 상태 이후에만:

```bash
git pull --ff-only
docker compose build travel-frontend
docker compose up -d --no-deps travel-frontend
```

## Rollback 관점 고려

정리 전 보존해야 할 것:

- 현재 `travel-frontend` image id
- 현재 `travel-backend` image id
- 현재 `saju-nginx` image id
- current untracked Docker/compose files
- DB dump checksum
- tracked diff patch

rollback 기준:

- frontend deploy 후 travel domain blank
- `/api/regions` 실패
- 사주 domain 영향 발생
- built JS env 미반영
- 저장/regenerate UX 장애

rollback 우선순위:

1. `travel-frontend`만 이전 image로 복구
2. 그래도 안 되면 frontend source commit revert 후 frontend-only rebuild
3. backend/nginx/saju는 rollback 대상이 아님

## 금지 작업

현재 drift reconciliation 전까지 금지:

```bash
git reset --hard
git clean -fd
git checkout -- .
git pull --rebase
git merge
docker compose up -d --build
docker compose up -d
docker compose down
docker compose build
docker compose build travel-backend
docker restart saju-nginx
docker restart saju-frontend
docker restart saju-backend
sudo nginx -s reload
sudo systemctl restart nginx
psql -f travel_db.sql
pg_restore travel_db.dump
```

추가 금지:

- 운영 DB migration
- representative overlay actual enable
- seed promote
- `course_builder.py` 기능 수정
- nginx route 수정
- 사주 compose/env 수정

## 배포 재개 절차

배포 재개 조건:

- EC2 `git status --short` clean
- `VITE_SHOW_SAJU_LINK=true`
- `VITE_SAJU_SERVICE_URL=https://saju-mbti-service.duckdns.org/`
- 운영 Docker/compose 파일 git 반영 완료
- DB dump repo 밖 이동
- frontend UI drift commit 여부 확정
- line ending drift 해소
- local/staging `npm run build` PASS
- Docker build PASS

재개 명령:

```bash
cd /home/ubuntu/travel_data_pipeline

git status --short
git pull --ff-only

docker inspect travel-frontend --format '{{.Image}}' > /tmp/travel-frontend-prev-image.txt

docker compose build travel-frontend
docker compose up -d --no-deps travel-frontend

docker exec travel-frontend sh -c "grep -R 'saju-mbti-service.duckdns.org' -n /usr/share/nginx/html/assets | head"
curl -I http://travel-planne.duckdns.org/
curl -s http://travel-planne.duckdns.org/api/regions | head
curl -I http://saju-mbti-service.duckdns.org/result
```

PASS 기준:

- `travel-frontend`만 recreate
- `travel-backend` restart 없음
- `saju-nginx` restart 없음
- 사주 컨테이너 restart 없음
- 여행 도메인 200
- `/api/regions` 정상
- built JS에 사주 도메인 포함
- MyScreen 사주 링크 정상
- 저장/복원/regenerate 정상

## 다음 작업 제안

1. EC2 drift archive 실행 계획을 별도 runbook으로 작성한다.
2. 운영 Docker/compose 파일을 로컬 git에 반영한다.
3. DB dump를 repo 밖으로 이동하고 `.gitignore`를 강화한다.
4. line ending normalize commit을 기능 commit과 분리한다.
5. clean 상태 달성 후 frontend-only deploy를 재시도한다.
