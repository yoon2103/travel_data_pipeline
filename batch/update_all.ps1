param(
    [switch]$DryRun = $true,
    [switch]$Write,
    [string]$Region,
    [string]$Sources = "naver",
    [string]$Keywords = "카페,식당,박물관",
    [string]$AnchorLat,
    [string]$AnchorLon,
    [string]$RadiusKm = "10",
    [string]$LimitPerKeyword = "5",
    [string]$MaxTotal = "30",
    [string]$BaselineJson,
    [int]$QaRepeat = 1,
    [string]$ApiBaseUrl = "http://127.0.0.1:5000",
    [switch]$NoNetwork,
    [switch]$SkipQa
)

$ErrorActionPreference = "Stop"
$RootDir = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RootDir
$Python = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { "python" }

function Log($Message) {
    Write-Host "[update_all.ps1] $Message"
}

if (-not (Test-Path ".env")) {
    throw ".env file not found at $RootDir\.env"
}
if (-not $Region) {
    throw "-Region is required"
}
if (-not $NoNetwork -and (-not $AnchorLat -or -not $AnchorLon)) {
    throw "-AnchorLat and -AnchorLon are required unless -NoNetwork is used"
}

$Mode = if ($Write) { "write" } else { "dry-run" }
Log "root=$RootDir"
Log "mode=$Mode region=$Region sources=$Sources keywords=$Keywords"

$DbCheck = @'
import sys
import db_client
required_tables = {
    "data_update_runs", "data_update_step_logs", "data_sync_state",
    "raw_external_places", "clean_external_places", "staging_places",
    "data_update_qa_results",
}
required_staging_columns = {
    "source", "external_source", "external_id", "external_content_id", "indoor_outdoor",
}
conn = db_client.get_connection()
try:
    with conn.cursor() as cur:
        cur.execute("SELECT 1")
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name = ANY(%s)", (list(required_tables),))
        tables = {r[0] for r in cur.fetchall()}
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='staging_places' AND column_name = ANY(%s)", (list(required_staging_columns),))
        columns = {r[0] for r in cur.fetchall()}
        missing_tables = sorted(required_tables - tables)
        missing_columns = sorted(required_staging_columns - columns)
        if missing_tables or missing_columns:
            print({"missing_tables": missing_tables, "missing_staging_columns": missing_columns})
            sys.exit(2)
        print("DB_OK")
finally:
    conn.close()
'@
$DbCheck | & $Python -

if ($SkipQa) {
    Log "baseline QA skipped by -SkipQa"
} elseif ($BaselineJson) {
    Log "using provided baseline QA: $BaselineJson"
} else {
    Log "running baseline QA"
    & $Python run_course_qa_report.py --repeat $QaRepeat
    $BaselineJson = (Get-ChildItem qa_reports -Filter "qa_all_regions_*.json" | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
    Log "baseline QA=$BaselineJson"
}

if ($NoNetwork) {
    Log "external collection skipped by -NoNetwork"
    Log "result: DRY_RUN_OK"
    exit 0
}

if (-not $Write) {
    Log "dry-run: collecting external Places without DB writes"
    & $Python -m batch.external.collect_external_places --region $Region --anchor-lat $AnchorLat --anchor-lon $AnchorLon --keywords $Keywords --radius-km $RadiusKm --sources $Sources --limit-per-keyword $LimitPerKeyword --max-total $MaxTotal
    Log "dry-run mode: clean/enrich/staging/promote are not executed because no raw rows are written"
    Log "result: DRY_RUN_OK"
    exit 0
}

throw "Windows write-mode wrapper is intentionally not implemented. Use EC2/Linux batch/update_all.sh for production writes."
