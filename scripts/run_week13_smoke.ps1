param(
  [int]$Port = 8010,
  [string]$Origin = "ed_sim_n5",
  [string]$Target = "week13_smoke_test",
  [int]$RunSteps = 5,
  [int]$MaxAttempts = 3
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

python .\scripts\run_week13_smoke.py --port $Port --origin $Origin --target $Target --run-steps $RunSteps --max-attempts $MaxAttempts
