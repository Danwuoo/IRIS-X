[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Admission', 'TurnA')]
    [string]$Mode,

    [Parameter(Mandatory = $true)]
    [string]$Workspace,

    [Parameter(Mandatory = $true)]
    [string]$PromptPath,

    [Parameter(Mandatory = $true)]
    [string]$StdoutPath,

    [Parameter(Mandatory = $true)]
    [string]$StderrPath,

    [Parameter(Mandatory = $true)]
    [string]$LastMessagePath
)

$ErrorActionPreference = 'Stop'

$codexExecutable = 'C:\Users\wurre\AppData\Local\OpenAI\Codex\bin\bffc5354119c8421\codex.exe'
$expectedExecutableSha256 = '081e4de4be8e38fac6ed4d95e3b1a0b9f6d31c090ddc36e1696b349fe406f575'
$expectedVersion = 'codex-cli 0.154.0-alpha.6.2'

$resolvedWorkspace = (Resolve-Path -LiteralPath $Workspace).Path
$resolvedPrompt = (Resolve-Path -LiteralPath $PromptPath).Path
$resolvedExecutable = (Resolve-Path -LiteralPath $codexExecutable).Path

if (-not (Test-Path -LiteralPath $resolvedWorkspace -PathType Container)) {
    throw "Workspace does not exist: $resolvedWorkspace"
}
if (-not (Test-Path -LiteralPath (Join-Path $resolvedWorkspace 'output') -PathType Container)) {
    throw "Workspace output directory does not exist: $resolvedWorkspace"
}
if (Test-Path -LiteralPath $StdoutPath) {
    throw "Stdout path already exists: $StdoutPath"
}
if (Test-Path -LiteralPath $StderrPath) {
    throw "Stderr path already exists: $StderrPath"
}
if (Test-Path -LiteralPath $LastMessagePath) {
    throw "Last-message path already exists: $LastMessagePath"
}

$actualExecutableSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $resolvedExecutable).Hash.ToLowerInvariant()
$actualVersion = (& $resolvedExecutable --version 2>&1 | Out-String).Trim()
if ($actualExecutableSha256 -ne $expectedExecutableSha256) {
    throw "Codex executable digest drift: $actualExecutableSha256"
}
if ($actualVersion -ne $expectedVersion) {
    throw "Codex executable version drift: $actualVersion"
}

$disabledFeatures = @(
    'multi_agent',
    'multi_agent_v2',
    'apps',
    'browser_use',
    'browser_use_external',
    'browser_use_full_cdp_access',
    'computer_use',
    'in_app_browser',
    'image_generation',
    'plugins',
    'remote_plugin',
    'skill_search',
    'tool_suggest',
    'hooks'
)

$innerArgumentList = @(
    'exec',
    '--dangerously-bypass-approvals-and-sandbox',
    '--strict-config',
    '--ignore-user-config',
    '--ignore-rules',
    '--model', 'gpt-5.6-terra',
    '--config', 'model_provider="openai"',
    '--config', 'model_reasoning_effort="high"',
    '--config', 'service_tier="default"',
    '--cd', $resolvedWorkspace
)
foreach ($feature in $disabledFeatures) {
    $innerArgumentList += @('--disable', $feature)
}
$innerArgumentList += @(
    '--skip-git-repo-check',
    '--ephemeral',
    '--json',
    '--color', 'never',
    '--output-last-message', $LastMessagePath,
    '-'
)

# The inner exec bypasses Codex's model-visible command-policy layer because
# retained B1/C1/B2/C2 evidence and admission A1 show that layer enforcing
# read-only / command denials despite an accepted workspace-write profile. The
# same pinned Codex binary is therefore used a second time as an outer Windows
# restricted-token sandbox. This OS boundary is the authority enforcement:
# inner writes are limited to the isolated workspace even though the inner
# process is configured with the bypass flag.
$argumentList = @(
    'sandbox',
    '-P', ':workspace',
    '-C', $resolvedWorkspace,
    $resolvedExecutable
) + $innerArgumentList

$childEnvironment = @{
    'CODEX_HOME' = 'C:\Users\wurre\.codex'
    'CODEX_APP_TOOLS_PIPE_PATH' = $null
    'CODEX_CI' = $null
    'CODEX_INTERNAL_ORIGINATOR_OVERRIDE' = $null
    'CODEX_MCP_NODE_PATH' = $null
    'CODEX_PERMISSION_PROFILE' = $null
    'CODEX_SAGE_BACKFILL_TRACKER_TAB_REUSE' = $null
    'CODEX_SESSION_ID' = $null
    'CODEX_SHELL' = $null
    'CODEX_THREAD_ID' = $null
    'CODEX_VERSION' = $null
    'OPENAI_API_KEY' = $null
    'OPENAI_MODEL' = $null
    'AZURE_OPENAI_API_KEY' = $null
    'ANTHROPIC_API_KEY' = $null
    'GOOGLE_API_KEY' = $null
}

$launchTimestamp = (Get-Date).ToString('o')
$process = Start-Process `
    -FilePath $resolvedExecutable `
    -ArgumentList $argumentList `
    -WorkingDirectory $resolvedWorkspace `
    -RedirectStandardInput $resolvedPrompt `
    -RedirectStandardOutput $StdoutPath `
    -RedirectStandardError $StderrPath `
    -Environment $childEnvironment `
    -WindowStyle Hidden `
    -PassThru

if ($Mode -eq 'Admission') {
    $process.WaitForExit()
    [pscustomobject]@{
        mode = $Mode
        launch_timestamp = $launchTimestamp
        pid = $process.Id
        exit_code = $process.ExitCode
        completion_timestamp = (Get-Date).ToString('o')
        executable = $resolvedExecutable
        executable_sha256 = $actualExecutableSha256
        executable_version = $actualVersion
        workspace = $resolvedWorkspace
        outer_sandbox = 'windows-restricted-token/:workspace'
        inner_sandbox = 'danger-full-access-via-bypass'
        inner_approval_policy = 'bypassed'
        inner_rules = 'ignored'
    } | ConvertTo-Json -Depth 4
    exit $process.ExitCode
}

$process.Refresh()
$confirmationTimestamp = (Get-Date).ToString('o')
$immediateState = if ($process.HasExited) {
    'process_created_exited_at_immediate_confirmation'
} else {
    'process_created_running_at_immediate_confirmation'
}

[pscustomobject]@{
    mode = $Mode
    launch_timestamp = $launchTimestamp
    pid = $process.Id
    immediate_confirmation_timestamp = $confirmationTimestamp
    immediate_state = $immediateState
    executable = $resolvedExecutable
    executable_sha256 = $actualExecutableSha256
    executable_version = $actualVersion
    workspace = $resolvedWorkspace
    outer_sandbox = 'windows-restricted-token/:workspace'
    inner_sandbox = 'danger-full-access-via-bypass'
    inner_approval_policy = 'bypassed'
    inner_rules = 'ignored'
} | ConvertTo-Json -Depth 4
