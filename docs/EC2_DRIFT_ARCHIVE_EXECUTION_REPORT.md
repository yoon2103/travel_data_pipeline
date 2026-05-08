# EC2 Drift Archive Execution Report

## 최종 판정

**PASS**

EC2 운영 서버 drift 상태를 copy/archive 방식으로 보존했다.

삭제, git reset, git clean, docker build, docker compose up, DB restore/migration은 수행하지 않았다.

## Archive 경로

```text
/home/ubuntu/backups/travel_data_pipeline/drift_20260508_100021
```

tarball:

```text
/home/ubuntu/backups/travel_data_pipeline/drift_20260508_100021.tar.gz
```

tarball 크기:

```text
20M
```

## 생성된 파일 목록

```text
/home/ubuntu/backups/travel_data_pipeline/drift_20260508_100021/db_dumps/travel_db.dump
/home/ubuntu/backups/travel_data_pipeline/drift_20260508_100021/db_dumps/travel_db.sql
/home/ubuntu/backups/travel_data_pipeline/drift_20260508_100021/metadata/archive_manifest.txt
/home/ubuntu/backups/travel_data_pipeline/drift_20260508_100021/metadata/archive_path.txt
/home/ubuntu/backups/travel_data_pipeline/drift_20260508_100021/metadata/archive_verification.txt
/home/ubuntu/backups/travel_data_pipeline/drift_20260508_100021/metadata/backend_engine_ignore_eol_stat.txt
/home/ubuntu/backups/travel_data_pipeline/drift_20260508_100021/metadata/db_dump_checksums_archive.txt
/home/ubuntu/backups/travel_data_pipeline/drift_20260508_100021/metadata/db_dump_checksums_original.txt
/home/ubuntu/backups/travel_data_pipeline/drift_20260508_100021/metadata/file_sizes.txt
/home/ubuntu/backups/travel_data_pipeline/drift_20260508_100021/metadata/file_types.txt
/home/ubuntu/backups/travel_data_pipeline/drift_20260508_100021/metadata/git_status_short.txt
/home/ubuntu/backups/travel_data_pipeline/drift_20260508_100021/metadata/tracked_diff_files.txt
/home/ubuntu/backups/travel_data_pipeline/drift_20260508_100021/metadata/tracked_diff_stat.txt
/home/ubuntu/backups/travel_data_pipeline/drift_20260508_100021/metadata/untracked_checksums_archive.txt
/home/ubuntu/backups/travel_data_pipeline/drift_20260508_100021/metadata/untracked_files.txt
/home/ubuntu/backups/travel_data_pipeline/drift_20260508_100021/patches/backend_engine_line_ending_drift.patch
/home/ubuntu/backups/travel_data_pipeline/drift_20260508_100021/patches/frontend_drift.patch
/home/ubuntu/backups/travel_data_pipeline/drift_20260508_100021/patches/tracked.diff
/home/ubuntu/backups/travel_data_pipeline/drift_20260508_100021/patches/tracked_ignore_eol.diff
/home/ubuntu/backups/travel_data_pipeline/drift_20260508_100021/untracked/Dockerfile
/home/ubuntu/backups/travel_data_pipeline/drift_20260508_100021/untracked/batch/update_all.ps1
/home/ubuntu/backups/travel_data_pipeline/drift_20260508_100021/untracked/batch/update_all.sh
/home/ubuntu/backups/travel_data_pipeline/drift_20260508_100021/untracked/docker-compose.yml
/home/ubuntu/backups/travel_data_pipeline/drift_20260508_100021/untracked/frontend/.dockerignore
/home/ubuntu/backups/travel_data_pipeline/drift_20260508_100021/untracked/frontend/Dockerfile
```

## Checksum 결과

### 원본 DB dump checksum

```text
f1dc80456e75b4a2ea7e386b84b08e80  travel_db.dump
104fbae0334b829d4f92416e3b077c97  travel_db.sql
53353d140b5403b1d346d196551357ce35245b028098f7bd0d1250f67553448a  travel_db.dump
ed1868d42db8a5474459be6ede6d99a6ace3b0892ff6e68b73596b96c19a596e  travel_db.sql
```

### Archive DB dump checksum

```text
f1dc80456e75b4a2ea7e386b84b08e80  travel_db.dump
104fbae0334b829d4f92416e3b077c97  travel_db.sql
53353d140b5403b1d346d196551357ce35245b028098f7bd0d1250f67553448a  travel_db.dump
ed1868d42db8a5474459be6ede6d99a6ace3b0892ff6e68b73596b96c19a596e  travel_db.sql
```

판정:

```text
PASS
```

원본과 archive copy의 MD5/SHA256 checksum이 일치한다.

## Manifest 결과

manifest에 주요 보존 대상이 포함됐다.

```text
./db_dumps/travel_db.dump
./db_dumps/travel_db.sql
./metadata/archive_manifest.txt
./metadata/archive_path.txt
./metadata/backend_engine_ignore_eol_stat.txt
./metadata/db_dump_checksums_archive.txt
./metadata/db_dump_checksums_original.txt
./metadata/file_sizes.txt
./metadata/file_types.txt
./metadata/git_status_short.txt
./metadata/tracked_diff_files.txt
./metadata/tracked_diff_stat.txt
./metadata/untracked_checksums_archive.txt
./metadata/untracked_files.txt
./patches/backend_engine_line_ending_drift.patch
./patches/frontend_drift.patch
./patches/tracked.diff
./patches/tracked_ignore_eol.diff
./untracked/Dockerfile
./untracked/batch/update_all.ps1
./untracked/batch/update_all.sh
./untracked/docker-compose.yml
./untracked/frontend/.dockerignore
./untracked/frontend/Dockerfile
```

판정:

```text
PASS
```

## Patch export 결과

patch directory:

```text
/home/ubuntu/backups/travel_data_pipeline/drift_20260508_100021/patches
```

파일 크기:

```text
backend_engine_line_ending_drift.patch  258K
frontend_drift.patch                    8.7K
tracked.diff                            434K
tracked_ignore_eol.diff                 8.7K
```

판정:

```text
PASS
```

tracked diff, ignore-eol diff, frontend drift patch, backend/engine drift patch가 모두 생성됐다.

## DB dump archive 결과

archive 대상:

```text
travel_db.dump
travel_db.sql
```

archive 위치:

```text
/home/ubuntu/backups/travel_data_pipeline/drift_20260508_100021/db_dumps/
```

권한:

```text
chmod 600 applied to archive copies
```

판정:

```text
PASS
```

주의:

- repo root 원본은 삭제/이동하지 않았다.
- archive copy만 수행했다.

## Tar 생성 결과

tarball:

```text
/home/ubuntu/backups/travel_data_pipeline/drift_20260508_100021.tar.gz
```

tar list 확인 결과 주요 파일 포함:

```text
drift_20260508_100021/patches/tracked_ignore_eol.diff
drift_20260508_100021/patches/frontend_drift.patch
drift_20260508_100021/patches/tracked.diff
drift_20260508_100021/patches/backend_engine_line_ending_drift.patch
drift_20260508_100021/db_dumps/travel_db.sql
drift_20260508_100021/db_dumps/travel_db.dump
drift_20260508_100021/metadata/git_status_short.txt
drift_20260508_100021/metadata/db_dump_checksums_original.txt
drift_20260508_100021/metadata/backend_engine_ignore_eol_stat.txt
drift_20260508_100021/metadata/archive_manifest.txt
drift_20260508_100021/metadata/untracked_files.txt
drift_20260508_100021/untracked/docker-compose.yml
drift_20260508_100021/untracked/Dockerfile
drift_20260508_100021/untracked/frontend/.dockerignore
drift_20260508_100021/untracked/frontend/Dockerfile
drift_20260508_100021/untracked/batch/update_all.ps1
drift_20260508_100021/untracked/batch/update_all.sh
```

판정:

```text
PASS
```

## 검증 결과

| 항목 | 결과 |
| --- | --- |
| archive directory 생성 | PASS |
| git status export | PASS |
| tracked diff export | PASS |
| untracked list export | PASS |
| frontend drift patch export | PASS |
| backend/engine drift patch export | PASS |
| 운영 필수 untracked 파일 copy | PASS |
| DB dump copy | PASS |
| DB dump checksum 비교 | PASS |
| file size/type 기록 | PASS |
| manifest 생성 | PASS |
| tarball 생성 | PASS |
| tarball list 확인 | PASS |

## 실행 안 한 위험 명령 확인

실행하지 않았다:

```text
git clean
git reset
docker compose build
docker compose up
docker compose down
docker restart
nginx restart/reload
file delete
DB restore
DB migration
psql
pg_restore
```

## 특이사항

초기 archive script 마지막 출력 단계에서 PowerShell CRLF가 원격 `cat` 경로 끝에 섞여 출력만 실패했다.

영향:

- archive directory 생성 완료
- 파일 copy 완료
- checksum 기록 완료
- manifest/tar 생성 완료
- 이후 원격 변수 escape를 보정해 검증 완료

판정:

```text
archive 자체 영향 없음
```

## 다음 작업 제안

1. DB dump 원본을 repo 밖으로 이동하는 별도 작업 수행.
2. 운영 Docker/compose 파일을 로컬 git source-of-truth에 반영.
3. `.gitignore`에 DB dump와 운영 산출물 패턴 강화.
4. line ending drift normalize 작업을 별도 commit으로 분리.
5. frontend UI drift를 로컬 최신 작업과 비교 후 commit 여부 결정.
6. EC2 `git status --short` clean 상태 달성 후 `travel-frontend` only deploy 재시도.
