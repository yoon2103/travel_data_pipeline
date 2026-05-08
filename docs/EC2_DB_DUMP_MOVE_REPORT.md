# EC2 DB Dump Move Report

## 최종 판정

**PASS**

EC2 repo root에 있던 DB dump 원본을 repo 밖 backup 경로로 이동했다.

삭제, DB restore, migration, git reset, git clean, docker deploy는 수행하지 않았다.

## 대상 파일

```text
/home/ubuntu/travel_data_pipeline/travel_db.dump
/home/ubuntu/travel_data_pipeline/travel_db.sql
```

## 원본 checksum

move 전 repo root 원본 checksum:

```text
f1dc80456e75b4a2ea7e386b84b08e80  travel_db.dump
104fbae0334b829d4f92416e3b077c97  travel_db.sql
53353d140b5403b1d346d196551357ce35245b028098f7bd0d1250f67553448a  travel_db.dump
ed1868d42db8a5474459be6ede6d99a6ace3b0892ff6e68b73596b96c19a596e  travel_db.sql
```

## archive checksum 비교

비교 대상 archive:

```text
/home/ubuntu/backups/travel_data_pipeline/drift_20260508_100021
```

archive checksum:

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

원본과 archive copy의 MD5/SHA256 checksum이 일치했다.

## backup 경로

```text
/home/ubuntu/backups/travel_data_pipeline/db_dumps
```

## move 결과

실행:

```bash
mkdir -p /home/ubuntu/backups/travel_data_pipeline/db_dumps
mv travel_db.dump travel_db.sql /home/ubuntu/backups/travel_data_pipeline/db_dumps/
chmod 600 /home/ubuntu/backups/travel_data_pipeline/db_dumps/travel_db.dump /home/ubuntu/backups/travel_data_pipeline/db_dumps/travel_db.sql
```

move 후 backup 위치 checksum:

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

move 전 원본, archive copy, move 후 backup 파일 checksum이 모두 일치한다.

## 권한 결과

```text
-rw------- 1 ubuntu ubuntu 9.8M May  6 14:09 travel_db.dump
-rw------- 1 ubuntu ubuntu  36M May  6 14:09 travel_db.sql
```

판정:

```text
PASS
```

두 DB dump 파일 모두 `600` 권한으로 제한됐다.

## repo root 제거 확인

확인 결과:

```text
ROOT_DUMPS_REMOVED
```

repo root에서 아래 파일이 제거됐다.

```text
travel_db.dump
travel_db.sql
```

삭제가 아니라 repo 밖 backup 위치로 이동한 것이다.

## git status 변화

이전 untracked 항목:

```text
?? travel_db.dump
?? travel_db.sql
```

현재 `git status --short`에서 위 두 항목은 사라졌다.

남아 있는 dirty/untracked 항목:

```text
 M .gitignore
 M _anchor_test.txt
 M _course_quality_test.txt
 M _dq_diagnosis.txt
 M _enrich_test.txt
 M _template_test.txt
 M api_server.py
 M check_kid_out.txt
 M check_late_out.txt
 M check_schema_out.txt
 M check_selection_basis.py
 M course_builder.py
 M debug.py
 M frontend/src/App.jsx
 M frontend/src/components/common/MobileShell.jsx
 M frontend/src/index.css
 M frontend/src/screens/day-trip/HomeScreen.jsx
 M regional_zone_builder.py
 M run_fix_103.py
 M run_zone_verify.py
 M sql/verify/00_run_order.md
 M test_course.py
 M test_sokcho2.json
 M test_sokcho_a.json
 M test_sokcho_b.json
 M test_sokcho_course.json
?? Dockerfile
?? batch/update_all.ps1
?? batch/update_all.sh
?? docker-compose.yml
?? frontend/.dockerignore
?? frontend/Dockerfile
```

판정:

```text
PARTIAL CLEANUP COMPLETE
```

DB dump blocker는 제거됐지만, 운영 Docker/compose untracked와 tracked drift가 아직 남아 있다.

## 실행 안 한 위험 명령

실행하지 않았다:

```text
pg_restore
psql
docker compose up
docker compose build
docker compose down
docker restart
nginx restart/reload
git clean
git reset
git checkout
DB migration
file delete
```

## 다음 작업 제안

1. 운영 Docker/compose 파일을 로컬 repo source-of-truth에 반영한다.
2. `.gitignore`에 DB dump 패턴을 확실히 추가한다.
3. backend/engine line ending drift를 normalize 계획에 따라 정리한다.
4. frontend UI drift를 로컬 최신 작업과 비교 후 commit 여부를 결정한다.
5. EC2 `git status --short` clean 상태 달성 후 `travel-frontend` only deploy를 재시도한다.
