# OwnGPT V2.2 P2.2 - Observability verification runbook (development only).
#
# Runs the deterministic verification steps that cannot run inside pytest:
#   - promtool check rules  (alert rule syntax)
#   - promtool test rules   (rule firing semantics with fixed input series)
#   - compose profile gating (plain `up` must NOT start monitoring)
#   - dashboard JSON validity (panel count + parse)
#
# promtool is executed from the pinned prom/prometheus container - it is a
# development verification dependency only; the application never depends on
# it. Native stderr is piped to stdout only where it carries the real result
# (promtool); compose stderr is left on the console.

# Usage:  powershell -ExecutionPolicy Bypass -File scripts\verify_p2_2_observability.ps1

$ErrorActionPreference = "Continue"
$promImage = "prom/prometheus:v3.13.2"
$opsPath   = (Resolve-Path (Join-Path $PSScriptRoot "..\ops")).Path

function Invoke-Check($Title, [scriptblock]$Body) {
    Write-Host ""
    Write-Host "== $Title ==" -ForegroundColor Cyan
    & $Body
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAILED: $Title" -ForegroundColor Red
        exit 1
    }
    Write-Host "OK: $Title" -ForegroundColor Green
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "FATAL: docker is not available on PATH." -ForegroundColor Red
    exit 1
}

Invoke-Check "promtool check rules" {
    & docker run --rm --entrypoint promtool -v "${opsPath}/prometheus:/ops/prometheus:ro" $promImage `
        check rules /ops/prometheus/rules/extraction.yml 2>&1 | Out-String | Write-Host
}

Invoke-Check "promtool test rules (deterministic firing semantics)" {
    & docker run --rm --entrypoint promtool -v "${opsPath}/prometheus:/ops/prometheus:ro" $promImage `
        test rules /ops/prometheus/tests/extraction_test.yml 2>&1 | Out-String | Write-Host
}

Invoke-Check "compose profile gating: plain config excludes monitoring" {
    $services = (& docker compose config --services | Out-String)
    if ($services -match "prometheus|grafana") {
        Set-Content -Path (Join-Path $env:TEMP "owngpt_verify_services.txt") -Value $services
        Write-Host "UNEXPECTED: monitoring services present without --profile" -ForegroundColor Red
        exit 1
    }
    ($services -split "`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ }) | Write-Host
    if ($services -notmatch "web" -or $services -notmatch "worker") {
        Write-Host "UNEXPECTED: application services missing" -ForegroundColor Red
        exit 1
    }
}

Invoke-Check "compose profile gating: --profile monitoring includes both" {
    $services = (& docker compose --profile monitoring config --services | Out-String)
    if ($services -notmatch "prometheus" -or $services -notmatch "grafana") {
        Write-Host "UNEXPECTED: monitoring services missing with --profile" -ForegroundColor Red
        exit 1
    }
    ($services -split "`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ }) | Write-Host
}

Invoke-Check "compose config validity (full model, monitoring profile)" {
    & docker compose --profile monitoring config -q 2>&1 | Out-String | Write-Host
}

Invoke-Check "grafana dashboard JSON is valid and complete" {
    $dashPath = Join-Path $opsPath "grafana\dashboards\owngpt-extraction.json"
    $dash = Get-Content $dashPath -Raw | ConvertFrom-Json
    if ($dash.uid -ne "owngpt-extraction") { throw "dashboard uid mismatch" }
    if ($dash.panels.Count -lt 9) { throw "expected >= 9 panels, got $($dash.panels.Count)" }
    Write-Host "dashboard uid=$($dash.uid) panels=$($dash.panels.Count) title=$($dash.title)"
}

Write-Host ""
Write-Host "P2.2 observability verification COMPLETE - all checks passed." -ForegroundColor Green