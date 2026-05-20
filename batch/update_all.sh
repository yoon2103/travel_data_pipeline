#!/usr/bin/env bash
set -euo pipefail

# EC2/Linux data update entry point.
# Safe by default: dry-run mode does not write raw/clean/staging data and does
# not promote anything into production places.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

MODE="dry-run"
REGION=""
SOURCES="naver"
KEYWORDS="카페,식당,박물관"
ANCHOR_LAT=""
ANCHOR_LON=""
RADIUS_KM="10"
LIMIT_PER_KEYWORD="5"
MAX_TOTAL="30"
QA_REPEAT="1"
BASELINE_JSON=""
API_BASE_URL="http://127.0.0.1:5000"
NO_NETWORK="false"
SKIP_QA="false"
CANDIDATE_ONLY="true"
NO_PROMOTE="true"
REVIEW_REQUIRED="true"
ALLOW_PROMOTE_REQUESTED="false"
APPROVED_ONLY_REHEARSAL="false"
SHADOW_MODE="false"
SHADOW_REPORT="false"
SHADOW_OUTPUT_DIR="qa_reports/shadow_mode"
VISIT_ROLE=""
PROMOTE_UNLOCK_FILE="${EXTERNAL_PROMOTE_UNLOCK_FILE:-${ROOT_DIR}/.external_promote_unlock}"
PROMOTE_UNLOCK_TOKEN="APPROVED_ONLY_EXTERNAL_PROMOTE_UNLOCK"

usage() {
  cat <<'EOF'
Usage:
  bash batch/update_all.sh [--dry-run|--write] --region REGION [options]

Examples:
  bash batch/update_all.sh --dry-run --region 전남 --no-network --skip-qa
  bash batch/update_all.sh --write --region 전남 --sources naver --anchor-lat 34.8161 --anchor-lon 126.4629

Options:
  --dry-run                 Safe default. No DB writes for external collection/clean/enrich/promote.
  --write                   Enable write mode for targeted external data update.
  --region REGION           Target region. Required.
  --sources SOURCES         Comma-separated sources. Default: naver
  --keywords KEYWORDS       Comma-separated keywords. Default: 카페,식당,박물관
  --anchor-lat LAT          Anchor latitude. Required for collection.
  --anchor-lon LON          Anchor longitude. Required for collection.
  --radius-km KM            Anchor radius. Default: 10
  --limit-per-keyword N     Per-keyword API limit. Default: 5
  --max-total N             Total collection cap. Default: 30
  --baseline-json PATH      Existing QA baseline JSON. If omitted, baseline QA is run.
  --qa-repeat N             QA repeat count. Default: 1
  --api-base-url URL        Smoke target base URL. Default: http://127.0.0.1:5000
  --no-network              Do not call external Places APIs. Useful for command validation.
  --skip-qa                 Do not execute QA. Useful for local command validation.
  --candidate-only          Stop after external candidate staging/review visibility. Default.
  --no-promote              Do not promote external candidates into production places. Default.
  --review-required         Require manual review gate before promote. Default.
  --rehearsal               Run approved-only rehearsal preview. No production promote.
  --approved-only-rehearsal Run approved-only rehearsal preview. No production promote.
  --shadow-mode             Compare legacy would-promote vs approved-only candidates. No production promote.
  --shadow-report           Write shadow mode JSON/CSV/Markdown report.
  --shadow-output-dir DIR   Shadow report output directory. Default: qa_reports/shadow_mode
  --visit-role ROLE         Optional review/shadow slice filter: cafe, meal, culture, or spot.
  --allow-promote           Emergency legacy escape hatch. Requires EXTERNAL_PROMOTE_UNLOCK=true and approval file token. Not for normal operations.
  -h, --help                Show this help.
EOF
}

log() {
  printf '[update_all] %s\n' "$*"
}

fail() {
  printf '[update_all][ERROR] %s\n' "$*" >&2
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) MODE="dry-run"; shift ;;
    --write) MODE="write"; shift ;;
    --region) REGION="${2:-}"; shift 2 ;;
    --sources) SOURCES="${2:-}"; shift 2 ;;
    --keywords) KEYWORDS="${2:-}"; shift 2 ;;
    --anchor-lat) ANCHOR_LAT="${2:-}"; shift 2 ;;
    --anchor-lon) ANCHOR_LON="${2:-}"; shift 2 ;;
    --radius-km) RADIUS_KM="${2:-}"; shift 2 ;;
    --limit-per-keyword) LIMIT_PER_KEYWORD="${2:-}"; shift 2 ;;
    --max-total) MAX_TOTAL="${2:-}"; shift 2 ;;
    --baseline-json) BASELINE_JSON="${2:-}"; shift 2 ;;
    --qa-repeat) QA_REPEAT="${2:-}"; shift 2 ;;
    --api-base-url) API_BASE_URL="${2:-}"; shift 2 ;;
    --no-network) NO_NETWORK="true"; shift ;;
    --skip-qa) SKIP_QA="true"; shift ;;
    --candidate-only) CANDIDATE_ONLY="true"; shift ;;
    --no-promote) NO_PROMOTE="true"; shift ;;
    --review-required) REVIEW_REQUIRED="true"; shift ;;
    --rehearsal) APPROVED_ONLY_REHEARSAL="true"; CANDIDATE_ONLY="true"; NO_PROMOTE="true"; REVIEW_REQUIRED="true"; shift ;;
    --approved-only-rehearsal) APPROVED_ONLY_REHEARSAL="true"; CANDIDATE_ONLY="true"; NO_PROMOTE="true"; REVIEW_REQUIRED="true"; shift ;;
    --shadow-mode) SHADOW_MODE="true"; CANDIDATE_ONLY="true"; NO_PROMOTE="true"; REVIEW_REQUIRED="true"; shift ;;
    --shadow-report) SHADOW_REPORT="true"; shift ;;
    --shadow-output-dir) SHADOW_OUTPUT_DIR="${2:-}"; shift 2 ;;
    --visit-role) VISIT_ROLE="${2:-}"; shift 2 ;;
    --allow-promote) ALLOW_PROMOTE_REQUESTED="true"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) fail "Unknown option: $1" ;;
  esac
done

cd "$ROOT_DIR"

command -v "$PYTHON_BIN" >/dev/null 2>&1 || fail "Python not found: ${PYTHON_BIN}"
[[ -f ".env" ]] || fail ".env file not found at ${ROOT_DIR}/.env"
[[ -n "$REGION" ]] || fail "--region is required"

if [[ "$NO_NETWORK" != "true" ]]; then
  [[ -n "$ANCHOR_LAT" ]] || fail "--anchor-lat is required unless --no-network is used"
  [[ -n "$ANCHOR_LON" ]] || fail "--anchor-lon is required unless --no-network is used"
fi

log "root=${ROOT_DIR}"
log "mode=${MODE} region=${REGION} sources=${SOURCES} keywords=${KEYWORDS}"
log "safety candidate_only=${CANDIDATE_ONLY} no_promote=${NO_PROMOTE} review_required=${REVIEW_REQUIRED} approved_only_rehearsal=${APPROVED_ONLY_REHEARSAL} shadow_mode=${SHADOW_MODE} shadow_report=${SHADOW_REPORT} allow_promote_requested=${ALLOW_PROMOTE_REQUESTED}"
if [[ -n "$VISIT_ROLE" ]]; then
  log "slice visit_role=${VISIT_ROLE}"
fi

if [[ "$ALLOW_PROMOTE_REQUESTED" == "true" ]]; then
  if [[ "${EXTERNAL_PROMOTE_UNLOCK:-false}" != "true" ]]; then
    fail "--allow-promote blocked: EXTERNAL_PROMOTE_UNLOCK=true is required"
  fi
  if [[ ! -f "$PROMOTE_UNLOCK_FILE" ]]; then
    fail "--allow-promote blocked: approval file not found: ${PROMOTE_UNLOCK_FILE}"
  fi
  if [[ "$(tr -d '\r\n' < "$PROMOTE_UNLOCK_FILE")" != "$PROMOTE_UNLOCK_TOKEN" ]]; then
    fail "--allow-promote blocked: approval file token mismatch"
  fi
  CANDIDATE_ONLY="false"
  NO_PROMOTE="false"
  REVIEW_REQUIRED="false"
  log "legacy promote unlock accepted with env+approval file; this remains emergency-only"
fi

log "checking DB connection and required migrations"
"$PYTHON_BIN" - <<'PY'
import sys
import db_client

required_tables = {
    "data_update_runs",
    "data_update_step_logs",
    "data_sync_state",
    "raw_external_places",
    "clean_external_places",
    "staging_places",
    "data_update_qa_results",
}
required_staging_columns = {
    "source",
    "external_source",
    "external_id",
    "external_content_id",
    "indoor_outdoor",
}

conn = db_client.get_connection()
try:
    with conn.cursor() as cur:
        cur.execute("SELECT 1")
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = ANY(%s)
        """, (list(required_tables),))
        tables = {row[0] for row in cur.fetchall()}
        missing_tables = sorted(required_tables - tables)
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'staging_places'
              AND column_name = ANY(%s)
        """, (list(required_staging_columns),))
        columns = {row[0] for row in cur.fetchall()}
        missing_columns = sorted(required_staging_columns - columns)
        if missing_tables or missing_columns:
            print({"missing_tables": missing_tables, "missing_staging_columns": missing_columns})
            sys.exit(2)
        print("DB_OK")
finally:
    conn.close()
PY

if [[ "$SKIP_QA" == "true" ]]; then
  log "baseline QA skipped by --skip-qa"
elif [[ -n "$BASELINE_JSON" ]]; then
  log "using provided baseline QA: ${BASELINE_JSON}"
else
  log "running baseline QA"
  "$PYTHON_BIN" run_course_qa_report.py --repeat "$QA_REPEAT"
  BASELINE_JSON="$(ls -t qa_reports/qa_all_regions_*.json | head -n 1)"
  log "baseline QA=${BASELINE_JSON}"
fi

RUN_ID=""
COLLECT_ARGS=(
  -m batch.external.collect_external_places
  --region "$REGION"
  --keywords "$KEYWORDS"
  --radius-km "$RADIUS_KM"
  --sources "$SOURCES"
  --limit-per-keyword "$LIMIT_PER_KEYWORD"
  --max-total "$MAX_TOTAL"
)

if [[ "$NO_NETWORK" == "true" ]]; then
  log "external collection skipped by --no-network"
elif [[ "$MODE" == "write" ]]; then
  log "collecting external Places into raw_external_places"
  COLLECT_OUTPUT="$("$PYTHON_BIN" "${COLLECT_ARGS[@]}" --anchor-lat "$ANCHOR_LAT" --anchor-lon "$ANCHOR_LON" --write)"
  printf '%s\n' "$COLLECT_OUTPUT"
  RUN_ID="$(printf '%s\n' "$COLLECT_OUTPUT" | "$PYTHON_BIN" -c 'import json,sys; print(json.load(sys.stdin).get("run_id") or "")')"
  [[ -n "$RUN_ID" ]] || fail "collect step did not return run_id"
else
  log "dry-run: collecting external Places without DB writes"
  "$PYTHON_BIN" "${COLLECT_ARGS[@]}" --anchor-lat "$ANCHOR_LAT" --anchor-lon "$ANCHOR_LON"
fi

if [[ "$MODE" != "write" ]]; then
  log "dry-run mode: clean/enrich/staging/promote are not executed because no raw rows are written"
  log "result: DRY_RUN_OK"
  exit 0
fi

log "cleaning external Places"
"$PYTHON_BIN" -m batch.external.clean_external_places --run-id "$RUN_ID" --region "$REGION" --write

log "enriching external Places and loading staging_places"
"$PYTHON_BIN" -m batch.external.enrich_external_places --run-id "$RUN_ID" --region "$REGION" --write

log "building external candidate review visibility report"
REVIEW_ARGS=(--run-id "$RUN_ID" --region "$REGION" --limit "$MAX_TOTAL")
if [[ -n "$VISIT_ROLE" ]]; then
  REVIEW_ARGS+=(--visit-role "$VISIT_ROLE")
fi
"$PYTHON_BIN" -m batch.external.stage_external_candidates "${REVIEW_ARGS[@]}"
"$PYTHON_BIN" -m batch.external.review_external_candidates "${REVIEW_ARGS[@]}" --report --output-dir "qa_reports/external_candidate_review"
REVIEW_REPORT_GENERATED="true"

if [[ "$SKIP_QA" == "true" ]]; then
  fail "--write requires QA; remove --skip-qa"
fi

log "running QA after staging"
QA_OUTPUT="$("$PYTHON_BIN" -m batch.external.qa_external_places --run-id "$RUN_ID" --baseline-json "$BASELINE_JSON" --repeat "$QA_REPEAT")"
printf '%s\n' "$QA_OUTPUT"
FAIL_INCREASED="$(printf '%s\n' "$QA_OUTPUT" | "$PYTHON_BIN" -c 'import json,sys; text=sys.stdin.read(); start=text.rfind("{"); print(str(json.loads(text[start:]).get("fail_increased", True)).lower())')"
[[ "$FAIL_INCREASED" == "false" ]] || fail "QA FAIL increased; promote blocked"

if [[ "$APPROVED_ONLY_REHEARSAL" == "true" ]]; then
  log "running approved-only rehearsal preview"
  REHEARSAL_ARGS=(-m batch.external.promote_external_places --run-id "$RUN_ID" --region "$REGION" --approved-only-rehearsal --limit "$MAX_TOTAL")
  if [[ -n "$VISIT_ROLE" ]]; then
    REHEARSAL_ARGS+=(--visit-role "$VISIT_ROLE")
  fi
  "$PYTHON_BIN" "${REHEARSAL_ARGS[@]}"
  log "result: APPROVED_ONLY_REHEARSAL_OK"
  exit 0
fi

if [[ "$SHADOW_MODE" == "true" ]]; then
  log "running approved-only shadow mode preview"
  SHADOW_ARGS=(-m batch.external.promote_external_places --run-id "$RUN_ID" --region "$REGION" --shadow-mode --limit "$MAX_TOTAL")
  if [[ -n "$VISIT_ROLE" ]]; then
    SHADOW_ARGS+=(--visit-role "$VISIT_ROLE")
  fi
  if [[ "$SHADOW_REPORT" == "true" ]]; then
    SHADOW_ARGS+=(--report --output-dir "$SHADOW_OUTPUT_DIR")
  fi
  "$PYTHON_BIN" "${SHADOW_ARGS[@]}"
  log "result: SHADOW_MODE_OK"
  exit 0
fi

if [[ "$CANDIDATE_ONLY" == "true" || "$NO_PROMOTE" == "true" || "$REVIEW_REQUIRED" == "true" ]]; then
  log "promote skipped by safety policy: candidate_only=${CANDIDATE_ONLY} no_promote=${NO_PROMOTE} review_required=${REVIEW_REQUIRED}"
  log "review report generated under qa_reports/external_candidate_review"
  log "result: CANDIDATE_REVIEW_READY"
  exit 0
fi

if [[ "${REVIEW_REPORT_GENERATED:-false}" != "true" ]]; then
  fail "candidate review report was not generated; promote blocked"
fi

log "promoting external staging rows into places"
"$PYTHON_BIN" -m batch.external.promote_external_places --run-id "$RUN_ID" --region "$REGION" --qa-passed --write

log "running API smoke test"
"$PYTHON_BIN" - <<PY
import json
import urllib.request

base_url = "${API_BASE_URL}".rstrip("/")
region = "${REGION}"
payload = {
    "region": region,
    "departure_time": "09:00",
    "themes": ["walk"],
    "template": "standard",
    "region_travel_type": "urban",
    "walk_max_radius": 10,
}

def get(path):
    with urllib.request.urlopen(base_url + path, timeout=10) as resp:
        return resp.status, resp.read()

status, _ = get("/docs")
if status != 200:
    raise SystemExit(f"/docs failed: {status}")
status, body = get("/api/regions")
if status != 200:
    raise SystemExit(f"/api/regions failed: {status}")
req = urllib.request.Request(
    base_url + "/api/course/generate",
    data=json.dumps(payload, ensure_ascii=True).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=30) as resp:
    result = json.loads(resp.read().decode("utf-8"))
print(json.dumps({"docs": 200, "regions": 200, "generate_place_count": len(result.get("places") or []), "error": result.get("error")}, ensure_ascii=False))
PY

log "result: WRITE_OK run_id=${RUN_ID}"
