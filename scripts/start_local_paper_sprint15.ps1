param(
    [Parameter(Mandatory=$true)][string]$RiskProfile,
    [string]$CertifiedNews,
    [switch]$EnableLocalPaper,
    [switch]$Arm
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot
if ((git branch --show-current) -ne 'refactor/backend-architecture') { throw 'Unexpected branch' }
if (@(git diff --name-only).Count -or @(git diff --cached --name-only).Count) { throw 'Tracked tree or index is not clean' }
if (!(Test-Path -LiteralPath $RiskProfile -PathType Leaf)) { throw 'Reviewed private risk profile required' }
if ($CertifiedNews) {
    if (!(Test-Path -LiteralPath $CertifiedNews -PathType Leaf)) { throw 'Certified news file unavailable' }
    $env:ARMS_CERTIFIED_ECONOMIC_NEWS_PATH = (Resolve-Path -LiteralPath $CertifiedNews).Path
}
$runName = 'run-' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ') + '-' + [guid]::NewGuid().ToString()
$runPath = Join-Path $repoRoot ('.arms-dev/sprint15/' + $runName)
$soakArgs = @('-m','backend.backtesting.operational_paper_soak_v1',
    '--spec',(Join-Path $repoRoot '.arms-dev/sprint13-loaded/native_capture_spec.json'),
    '--directory',(Join-Path $repoRoot '.arms-dev/ninjatrader-current'),
    '--run-directory',$runPath,'--risk-profile',(Resolve-Path -LiteralPath $RiskProfile).Path,
    '--seconds','7500','--activation-seconds','180','--port','8000')
if ($EnableLocalPaper) { $soakArgs += '--enable-local-paper' }
if (!$Arm) { $soakArgs += '--preflight-only' }
Write-Output ('Private run destination: ' + $runPath)
& py @soakArgs
if ($LASTEXITCODE -ne 0) { throw 'LOCAL PAPER stopped fail-closed; review private run status' }
