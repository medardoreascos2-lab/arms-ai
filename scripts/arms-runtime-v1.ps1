param(
    [Parameter(Position=0, Mandatory=$true)]
    [ValidateSet('start', 'status', 'audit', 'stop')]
    [string]$Command,
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$CommandArguments
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $python -PathType Leaf)) {
    throw 'Pinned repository Python is unavailable; offline launcher blocked'
}

Set-Location -LiteralPath $repoRoot
& $python -B -m tools.arms_one_click_runtime_v1 $Command @CommandArguments
exit $LASTEXITCODE
