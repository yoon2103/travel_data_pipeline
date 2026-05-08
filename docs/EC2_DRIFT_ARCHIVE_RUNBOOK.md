# EC2 Drift Archive Runbook

## 목적

EC2 운영 서버 `/home/ubuntu/travel_data_pipeline`의 dirty working tree를 정리하기 전에, 현재 drift 상태를 안전하게 보존한다.

이 문서는 실행 절차 초안이다. 현재 단계에서는 실제 archive, 파일 이동, 삭제, git reset, git clean, 배포, DB 수정은 수행하지 않는다.

## 현재 상태

- EC2 `travel_data_pipeline` 작업트리 dirty
- 배포 상태: `BLOCKED`
- 운영 필수 Docker/compose 파일이 untracked
- DB dump가 repo root에 존재
- reset/clean 금지
- deploy 금지

## Archive 대상

### 운영 필수 untracked 파일

보존 대상:

```text
Dockerfile
docker-compose.yml
frontend/Dockerfile
frontend/.dockerignore
```

목적:

- 현재 운영 container build 구조 재현
- 로컬 git source-of-truth에 반영할지 검토
- VITE env injection 적용 전/후 비교

### DB dump 파일

보존 대상:

```text
travel_db.dump
travel_db.sql
```

목적:

- repo 밖 backup으로 보호
- 실수 commit/push 방지
- 삭제 전 checksum 보존

주의:

- git commit 금지
- `psql`, `pg_restore` 실행 금지
- archive 확인 전 삭제 금지

### tracked diff

보존 대상:

```text
tracked.diff
tracked_ignore_eol.diff
tracked_diff_stat.txt
git_status_short.txt
```

목적:

- EC2 운영 서버에서 발생한 tracked file drift 전체 기록
- line ending drift와 실제 코드 변경 분리

### untracked list

보존 대상:

```text
untracked_files.txt
untracked_file_details.txt
```

목적:

- untracked 파일 목록 보존
- 이후 git 반영/ignore/archive 판단 근거

### frontend drift patch

보존 대상:

```text
frontend_drift.patch
```

대상 파일:

```text
frontend/src/App.jsx
frontend/src/components/common/MobileShell.jsx
frontend/src/index.css
frontend/src/screens/day-trip/HomeScreen.jsx
```

목적:

- mock status bar 제거
- mobile viewport/pull-to-refresh 관련 운영 drift 보존
- 로컬 frontend 최신 작업과 비교

### backend/engine line-ending drift patch

보존 대상:

```text
backend_engine_line_ending_drift.patch
backend_engine_ignore_eol_stat.txt
```

대상 파일:

```text
api_server.py
course_builder.py
regional_zone_builder.py
```

목적:

- 추천 엔진/백엔드 파일의 line ending drift 보존
- 실질 로직 변경이 아닌지 재검증

### batch/update wrapper 후보

보존 대상:

```text
batch/update_all.sh
batch/update_all.ps1
```

목적:

- 운영 데이터 업데이트 wrapper 후보 보존
- 추후 git 반영 여부 검토

## Archive 경로

권장 경로:

```text
/home/ubuntu/backups/travel_data_pipeline/drift_YYYYMMDD_HHMMSS
```

예:

```text
/home/ubuntu/backups/travel_data_pipeline/drift_20260508_153000
```

변수:

```bash
ROOT_DIR="/home/ubuntu/travel_data_pipeline"
BACKUP_ROOT="/home/ubuntu/backups/travel_data_pipeline"
ARCHIVE_DIR="${BACKUP_ROOT}/drift_$(date +%Y%m%d_%H%M%S)"
```

설계 원칙:

- repo 밖에 archive
- timestamp 기반으로 반복 실행 가능
- 원본 파일은 archive 1차 단계에서 삭제하지 않음
- DB dump는 우선 copy, 검증 후 별도 단계에서 move

## 실행 명령 초안

### 1. 작업 위치 확인

```bash
cd /home/ubuntu/travel_data_pipeline
pwd
git status --short
```

기대 위치:

```text
/home/ubuntu/travel_data_pipeline
```

### 2. archive directory 생성

```bash
ROOT_DIR="/home/ubuntu/travel_data_pipeline"
BACKUP_ROOT="/home/ubuntu/backups/travel_data_pipeline"
ARCHIVE_DIR="${BACKUP_ROOT}/drift_$(date +%Y%m%d_%H%M%S)"

mkdir -p "${ARCHIVE_DIR}"
mkdir -p "${ARCHIVE_DIR}/untracked"
mkdir -p "${ARCHIVE_DIR}/db_dumps"
mkdir -p "${ARCHIVE_DIR}/patches"
mkdir -p "${ARCHIVE_DIR}/metadata"
```

### 3. git status / diff metadata export

```bash
git status --short > "${ARCHIVE_DIR}/metadata/git_status_short.txt"
git diff --stat > "${ARCHIVE_DIR}/metadata/tracked_diff_stat.txt"
git diff --name-only > "${ARCHIVE_DIR}/metadata/tracked_diff_files.txt"
git ls-files --others --exclude-standard > "${ARCHIVE_DIR}/metadata/untracked_files.txt"
```

### 4. 전체 tracked diff export

```bash
git diff > "${ARCHIVE_DIR}/patches/tracked.diff"
git diff --ignore-space-at-eol > "${ARCHIVE_DIR}/patches/tracked_ignore_eol.diff"
```

### 5. frontend drift patch export

```bash
git diff --ignore-space-at-eol -- \
  frontend/src/App.jsx \
  frontend/src/components/common/MobileShell.jsx \
  frontend/src/index.css \
  frontend/src/screens/day-trip/HomeScreen.jsx \
  > "${ARCHIVE_DIR}/patches/frontend_drift.patch"
```

### 6. backend/engine line-ending drift patch export

```bash
git diff -- \
  api_server.py \
  course_builder.py \
  regional_zone_builder.py \
  > "${ARCHIVE_DIR}/patches/backend_engine_line_ending_drift.patch"

git diff --ignore-space-at-eol --stat -- \
  api_server.py \
  course_builder.py \
  regional_zone_builder.py \
  > "${ARCHIVE_DIR}/metadata/backend_engine_ignore_eol_stat.txt"
```

### 7. untracked 운영 파일 copy

우선 `cp`만 사용한다. 이 단계에서 `mv` 금지.

```bash
for f in \
  Dockerfile \
  docker-compose.yml \
  frontend/Dockerfile \
  frontend/.dockerignore \
  batch/update_all.sh \
  batch/update_all.ps1
do
  if [ -e "${ROOT_DIR}/${f}" ]; then
    mkdir -p "${ARCHIVE_DIR}/untracked/$(dirname "${f}")"
    cp -a "${ROOT_DIR}/${f}" "${ARCHIVE_DIR}/untracked/${f}"
  fi
done
```

### 8. DB dump copy

우선 copy만 수행한다.

```bash
for f in travel_db.dump travel_db.sql
do
  if [ -e "${ROOT_DIR}/${f}" ]; then
    cp -a "${ROOT_DIR}/${f}" "${ARCHIVE_DIR}/db_dumps/${f}"
  fi
done
```

### 9. checksum 기록

원본 checksum:

```bash
(
  cd "${ROOT_DIR}"
  md5sum travel_db.dump travel_db.sql 2>/dev/null || true
  sha256sum travel_db.dump travel_db.sql 2>/dev/null || true
) > "${ARCHIVE_DIR}/metadata/db_dump_checksums_original.txt"
```

archive checksum:

```bash
(
  cd "${ARCHIVE_DIR}/db_dumps"
  md5sum travel_db.dump travel_db.sql 2>/dev/null || true
  sha256sum travel_db.dump travel_db.sql 2>/dev/null || true
) > "${ARCHIVE_DIR}/metadata/db_dump_checksums_archive.txt"
```

운영 파일 checksum:

```bash
(
  cd "${ARCHIVE_DIR}/untracked"
  find . -type f -print0 | sort -z | xargs -0 sha256sum
) > "${ARCHIVE_DIR}/metadata/untracked_checksums_archive.txt"
```

### 10. 파일 상세 정보 기록

```bash
{
  echo "## root files"
  ls -lh "${ROOT_DIR}/Dockerfile" \
         "${ROOT_DIR}/docker-compose.yml" \
         "${ROOT_DIR}/travel_db.dump" \
         "${ROOT_DIR}/travel_db.sql" 2>/dev/null || true

  echo
  echo "## frontend files"
  ls -lh "${ROOT_DIR}/frontend/Dockerfile" \
         "${ROOT_DIR}/frontend/.dockerignore" 2>/dev/null || true

  echo
  echo "## batch files"
  ls -lh "${ROOT_DIR}/batch/update_all.sh" \
         "${ROOT_DIR}/batch/update_all.ps1" 2>/dev/null || true
} > "${ARCHIVE_DIR}/metadata/file_sizes.txt"
```

### 11. file type 기록

```bash
file \
  "${ROOT_DIR}/Dockerfile" \
  "${ROOT_DIR}/docker-compose.yml" \
  "${ROOT_DIR}/frontend/Dockerfile" \
  "${ROOT_DIR}/frontend/.dockerignore" \
  "${ROOT_DIR}/travel_db.dump" \
  "${ROOT_DIR}/travel_db.sql" \
  "${ROOT_DIR}/batch/update_all.sh" \
  "${ROOT_DIR}/batch/update_all.ps1" \
  2>/dev/null \
  > "${ARCHIVE_DIR}/metadata/file_types.txt" || true
```

### 12. archive manifest 생성

```bash
(
  cd "${ARCHIVE_DIR}"
  find . -type f | sort
) > "${ARCHIVE_DIR}/metadata/archive_manifest.txt"
```

### 13. optional tar 생성

원본 archive directory를 유지하면서 tarball도 만들 수 있다.

```bash
tar -czf "${ARCHIVE_DIR}.tar.gz" -C "${BACKUP_ROOT}" "$(basename "${ARCHIVE_DIR}")"
```

주의:

- tar 생성은 선택이다.
- tar 생성 후에도 원본 archive directory는 검증 완료 전 삭제하지 않는다.

## 검증 명령

### archive directory 확인

```bash
ls -lh "${ARCHIVE_DIR}"
find "${ARCHIVE_DIR}" -maxdepth 3 -type f | sort
```

### manifest 확인

```bash
cat "${ARCHIVE_DIR}/metadata/archive_manifest.txt"
```

기대 포함:

```text
./db_dumps/travel_db.dump
./db_dumps/travel_db.sql
./metadata/git_status_short.txt
./metadata/untracked_files.txt
./patches/tracked.diff
./patches/frontend_drift.patch
./patches/backend_engine_line_ending_drift.patch
./untracked/Dockerfile
./untracked/docker-compose.yml
./untracked/frontend/Dockerfile
./untracked/frontend/.dockerignore
```

### checksum 비교

```bash
cat "${ARCHIVE_DIR}/metadata/db_dump_checksums_original.txt"
cat "${ARCHIVE_DIR}/metadata/db_dump_checksums_archive.txt"
```

PASS 기준:

- original과 archive의 `travel_db.dump` checksum 동일
- original과 archive의 `travel_db.sql` checksum 동일

### tar 검증

tarball을 생성한 경우:

```bash
tar -tzf "${ARCHIVE_DIR}.tar.gz" | head -100
```

PASS 기준:

- archive directory 구조가 tar 안에 포함
- DB dump와 patch 파일이 누락되지 않음

### patch 크기 확인

```bash
ls -lh "${ARCHIVE_DIR}/patches"
wc -l "${ARCHIVE_DIR}/patches/"*.patch "${ARCHIVE_DIR}/patches/"*.diff
```

### untracked copy 확인

```bash
diff -q "${ROOT_DIR}/Dockerfile" "${ARCHIVE_DIR}/untracked/Dockerfile" || true
diff -q "${ROOT_DIR}/docker-compose.yml" "${ARCHIVE_DIR}/untracked/docker-compose.yml" || true
diff -q "${ROOT_DIR}/frontend/Dockerfile" "${ARCHIVE_DIR}/untracked/frontend/Dockerfile" || true
diff -q "${ROOT_DIR}/frontend/.dockerignore" "${ARCHIVE_DIR}/untracked/frontend/.dockerignore" || true
```

PASS 기준:

- 차이 없음

## DB dump 보호 전략

### 단계 1. copy archive

먼저 archive directory에 copy한다.

```bash
cp -a travel_db.dump "${ARCHIVE_DIR}/db_dumps/travel_db.dump"
cp -a travel_db.sql "${ARCHIVE_DIR}/db_dumps/travel_db.sql"
```

### 단계 2. checksum 검증

copy 전후 checksum 일치 확인.

```bash
md5sum travel_db.dump travel_db.sql
md5sum "${ARCHIVE_DIR}/db_dumps/travel_db.dump" "${ARCHIVE_DIR}/db_dumps/travel_db.sql"
```

### 단계 3. 권한 제한

archive copy 권한 제한:

```bash
chmod 600 "${ARCHIVE_DIR}/db_dumps/travel_db.dump" "${ARCHIVE_DIR}/db_dumps/travel_db.sql"
```

### 단계 4. repo 밖 move

copy와 검증이 끝난 뒤, 별도 승인 단계에서만 repo root의 원본을 repo 밖으로 이동한다.

예:

```bash
mkdir -p /home/ubuntu/backups/travel_data_pipeline/db_dumps
mv /home/ubuntu/travel_data_pipeline/travel_db.dump /home/ubuntu/backups/travel_data_pipeline/db_dumps/
mv /home/ubuntu/travel_data_pipeline/travel_db.sql /home/ubuntu/backups/travel_data_pipeline/db_dumps/
chmod 600 /home/ubuntu/backups/travel_data_pipeline/db_dumps/travel_db.dump
chmod 600 /home/ubuntu/backups/travel_data_pipeline/db_dumps/travel_db.sql
```

주의:

- 이 runbook의 archive 1차 단계에서는 `mv`를 실행하지 않는다.
- DB dump를 git에 추가하지 않는다.
- dump를 restore하지 않는다.

## Archive 후에도 아직 하면 안 되는 작업

archive가 끝나도 아래 작업은 바로 실행하면 안 된다.

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

- DB migration
- places update
- representative overlay actual enable
- seed promote
- `course_builder.py` 기능 수정
- nginx route 수정
- 사주 compose/env 수정

## Archive 후 다음 단계

### 1. 운영 Docker/compose를 로컬 repo에 반영

대상:

```text
Dockerfile
docker-compose.yml
frontend/Dockerfile
frontend/.dockerignore
```

반영 기준:

- EC2 운영 구조 유지
- `frontend/Dockerfile`에는 VITE env injection 추가
- `docker-compose.yml`에는 `travel-frontend.build.args` 추가
- 사주 nginx/network 구조 변경 금지

### 2. DB dump repo 밖 이동

archive 검증 후 별도 단계에서:

```text
/home/ubuntu/backups/travel_data_pipeline/db_dumps/
```

로 이동.

### 3. .gitignore 강화

필수 패턴:

```gitignore
*.dump
travel_db*.dump
travel_db*.sql
backups/
*_out.txt
```

주의:

- migration SQL까지 무시하지 않도록 범위를 제한한다.

### 4. line ending normalize

대상:

```text
api_server.py
course_builder.py
regional_zone_builder.py
```

권장:

- `.gitattributes` 기준 확정
- line ending normalize commit을 기능 commit과 분리
- 추천 엔진 로직 변경과 섞지 않음

### 5. frontend drift reconcile

대상:

```text
frontend/src/App.jsx
frontend/src/components/common/MobileShell.jsx
frontend/src/index.css
frontend/src/screens/day-trip/HomeScreen.jsx
```

처리:

- 로컬 최신 UI 수정과 EC2 drift 비교
- 필요한 UX fix는 commit
- 불필요한 drift는 archive 기준으로 폐기 검토

### 6. clean 상태 확인

최종 목표:

```bash
git status --short
```

기대:

```text
<empty>
```

### 7. 배포 재개

clean 상태 이후에만:

```bash
git pull --ff-only
docker compose build travel-frontend
docker compose up -d --no-deps travel-frontend
```

## 요약

이 archive runbook의 핵심 원칙:

1. 삭제보다 보존이 먼저다.
2. DB dump는 git에 절대 넣지 않는다.
3. 운영 Docker/compose는 source-of-truth 후보로 보존한다.
4. line ending drift는 기능 변경과 분리한다.
5. archive 후에도 바로 reset/clean/build 하지 않는다.
