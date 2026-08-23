[CmdletBinding()]
param()

Set-StrictMode -Version Latest

$HadFailure = $false

function Write-Check {
    param(
        [Parameter(Mandatory = $true)][ValidateSet('PASS', 'WARN', 'FAIL')][string]$Status,
        [Parameter(Mandatory = $true)][string]$Message
    )

    Write-Host ('[{0}] {1}' -f $Status, $Message)
}

function Set-Failure {
    param([Parameter(Mandatory = $true)][string]$Message)

    $script:HadFailure = $true
    Write-Check -Status 'FAIL' -Message $Message
}

function Test-CommandVersion {
    param([Parameter(Mandatory = $true)][string]$Name)

    $commandInfo = Get-Command $Name -ErrorAction SilentlyContinue
    if ($null -eq $commandInfo) {
        Set-Failure ("Required command is unavailable: {0}" -f $Name)
        return
    }

    try {
        $versionOutput = & $Name --version 2>&1
        if ($LASTEXITCODE -ne 0) {
            Set-Failure ("{0} --version failed: {1}" -f $Name, ($versionOutput -join ' '))
            return
        }
        Write-Check -Status 'PASS' -Message ("{0}: {1}" -f $Name, ($versionOutput -join ' '))
    }
    catch {
        Set-Failure ("Could not run {0} --version: {1}" -f $Name, $_.Exception.Message)
    }
}

# Derive every repository location from this script; do not hard-code a machine path.
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$DatasetRoot = Join-Path $ProjectRoot 'data\arc-datasets'
$ToolkitRoot = Join-Path $DatasetRoot 'ARC-AGI-3-toolkit'

$RequiredDirectories = @(
    @{ Label = 'data/arc-datasets/ARC-AGI-1/data/training'; Path = (Join-Path $DatasetRoot 'ARC-AGI-1\data\training') },
    @{ Label = 'data/arc-datasets/ARC-AGI-1/data/evaluation'; Path = (Join-Path $DatasetRoot 'ARC-AGI-1\data\evaluation') },
    @{ Label = 'data/arc-datasets/ARC-AGI-2/data/training'; Path = (Join-Path $DatasetRoot 'ARC-AGI-2\data\training') },
    @{ Label = 'data/arc-datasets/ARC-AGI-2/data/evaluation'; Path = (Join-Path $DatasetRoot 'ARC-AGI-2\data\evaluation') },
    @{ Label = 'data/arc-datasets/ARC-AGI-3-toolkit'; Path = $ToolkitRoot }
)

$JsonDirectories = $RequiredDirectories[0..3]

foreach ($directory in $RequiredDirectories) {
    if (Test-Path -LiteralPath $directory.Path -PathType Container) {
        Write-Check -Status 'PASS' -Message ("Directory exists: {0}" -f $directory.Label)
    }
    else {
        Set-Failure ("Required directory is missing: {0}" -f $directory.Label)
    }
}

foreach ($directory in $JsonDirectories) {
    if (-not (Test-Path -LiteralPath $directory.Path -PathType Container)) {
        Set-Failure ("Cannot count JSON files because the directory is missing: {0}" -f $directory.Label)
        continue
    }

    try {
        $jsonCount = @(Get-ChildItem -LiteralPath $directory.Path -File -Filter '*.json' -ErrorAction Stop).Count
        if ($jsonCount -gt 0) {
            Write-Check -Status 'PASS' -Message ("JSON files in {0}: {1}" -f $directory.Label, $jsonCount)
        }
        else {
            Write-Check -Status 'WARN' -Message ("No JSON files found in {0}" -f $directory.Label)
        }
    }
    catch {
        Set-Failure ("Could not count JSON files in {0}: {1}" -f $directory.Label, $_.Exception.Message)
    }
}

foreach ($toolName in @('git', 'python', 'py', 'uv')) {
    Test-CommandVersion -Name $toolName
}

if ($env:ARC_API_KEY) {
    Write-Check -Status 'PASS' -Message 'ARC_API_KEY is configured'
}
else {
    Write-Check -Status 'WARN' -Message 'ARC_API_KEY is not configured'
}

if (-not (Test-Path -LiteralPath $ToolkitRoot -PathType Container)) {
    Set-Failure 'Cannot test the ARC-AGI-3 Toolkit because its directory is missing.'
}
elseif ($null -eq (Get-Command uv -ErrorAction SilentlyContinue)) {
    Set-Failure 'Cannot test the ARC-AGI-3 Toolkit because uv is unavailable.'
}
else {
    Push-Location -LiteralPath $ToolkitRoot
    try {
        $syncOutput = & uv sync 2>&1
        $syncSucceeded = $LASTEXITCODE -eq 0
        if ($LASTEXITCODE -eq 0) {
            Write-Check -Status 'PASS' -Message 'ARC-AGI-3 Toolkit: uv sync completed'
        }
        else {
            Set-Failure ("ARC-AGI-3 Toolkit: uv sync failed: {0}" -f ($syncOutput -join ' '))
        }

        $importsSucceeded = $false
        if ($syncSucceeded) {
            $importOutput = & uv run python -c "import arc_agi; print('arc_agi import OK')" 2>&1
            $arcAgiImportSucceeded = $LASTEXITCODE -eq 0
            if ($LASTEXITCODE -eq 0) {
                Write-Check -Status 'PASS' -Message ('ARC-AGI-3 Toolkit: ' + ($importOutput -join ' '))
            }
            else {
                Set-Failure ("ARC-AGI-3 Toolkit: arc_agi import failed: {0}" -f ($importOutput -join ' '))
            }

            $engineOutput = & uv run python -c "import arcengine; print('arcengine import OK')" 2>&1
            $arcEngineImportSucceeded = $LASTEXITCODE -eq 0
            if ($LASTEXITCODE -eq 0) {
                Write-Check -Status 'PASS' -Message ('ARC-AGI-3 Toolkit: ' + ($engineOutput -join ' '))
            }
            else {
                Set-Failure ("ARC-AGI-3 Toolkit: arcengine import failed: {0}" -f ($engineOutput -join ' '))
            }

            $importsSucceeded = $arcAgiImportSucceeded -and $arcEngineImportSucceeded
        }

        $LocalEnvironmentDir = Join-Path $ToolkitRoot 'test_environment_files'
        if (-not (Test-Path -LiteralPath $LocalEnvironmentDir -PathType Container)) {
            Set-Failure 'ARC-AGI-3 Toolkit: test_environment_files is missing; no offline smoke test can run.'
        }
        elseif ($importsSucceeded) {
            $smokeTestCode = @'
import logging

from arc_agi import Arcade, OperationMode

logging.disable(logging.CRITICAL)
arc = Arcade(
    operation_mode=OperationMode.OFFLINE,
    environments_dir="test_environment_files",
)
environments = arc.get_environments()
if not environments:
    raise SystemExit("No local environments found")

print("LOCAL_ENVIRONMENTS=" + ",".join(item.game_id for item in environments))
env = None
try:
    env = arc.make(environments[0].game_id, seed=0, save_recording=False)
    if env is None:
        raise RuntimeError("Arcade.make returned None")

    initial = env.reset()
    if initial is None:
        raise RuntimeError("reset returned None")
    actions = env.action_space
    print("RESET_OK game_id={0} state={1} actions={2}".format(
        initial.game_id, initial.state.name, len(actions)
    ))

    if actions:
        action = actions[0]
        action_data = {"x": 0, "y": 0} if action.is_complex() else {}
        result = env.step(action, data=action_data)
        if result is None:
            raise RuntimeError("step returned None")
        print("STEP_OK action={0} state={1}".format(action.name, result.state.name))
    else:
        print("STEP_SKIPPED no legal actions")
finally:
    close = getattr(env, "close", None) if env is not None else None
    if callable(close):
        close()
        print("ENVIRONMENT_CLOSE_OK")
    else:
        closed = arc.close_scorecard()
        print("ENVIRONMENT_CLOSE_NOT_EXPOSED_SCORECARD_CLOSED={0}".format(closed is not None))
'@
            $smokeOutput = $smokeTestCode | & uv run python - 2>&1
            if ($LASTEXITCODE -eq 0) {
                $smokeSummary = ($smokeOutput | Where-Object {
                    $_ -match '^(LOCAL_ENVIRONMENTS|RESET_OK|STEP_OK|STEP_SKIPPED|ENVIRONMENT_CLOSE_)'
                }) -join ' | '
                Write-Check -Status 'PASS' -Message ('ARC-AGI-3 offline smoke test: ' + $smokeSummary)
            }
            else {
                Set-Failure ("ARC-AGI-3 offline smoke test failed: {0}" -f ($smokeOutput -join ' '))
            }
        }
        else {
            Write-Check -Status 'WARN' -Message 'ARC-AGI-3 offline smoke test skipped because installation checks failed.'
        }
    }
    catch {
        Set-Failure ("ARC-AGI-3 Toolkit test could not complete: {0}" -f $_.Exception.Message)
    }
    finally {
        Pop-Location
    }
}

if ($HadFailure) {
    exit 1
}

exit 0
