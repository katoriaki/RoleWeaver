$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$stage = Join-Path $root ".codex_tmp\RoleWeaver_A800_Server_$timestamp"
$zipDir = Join-Path $root "dist"
$zipPath = Join-Path $zipDir "RoleWeaver_A800_Server_$timestamp.zip"

New-Item -ItemType Directory -Force -Path $stage | Out-Null
New-Item -ItemType Directory -Force -Path $zipDir | Out-Null

function Copy-File($relativePath) {
    $src = Join-Path $root $relativePath
    if (Test-Path $src) {
        $dst = Join-Path $stage $relativePath
        New-Item -ItemType Directory -Force -Path (Split-Path $dst -Parent) | Out-Null
        Copy-Item -LiteralPath $src -Destination $dst -Force
    }
}

function Copy-Dir($relativePath) {
    $src = Join-Path $root $relativePath
    if (Test-Path $src) {
        $dst = Join-Path $stage $relativePath
        New-Item -ItemType Directory -Force -Path $dst | Out-Null
        Get-ChildItem -LiteralPath $src -Force | ForEach-Object {
            Copy-Item -LiteralPath $_.FullName -Destination $dst -Recurse -Force
        }
    }
}

$files = @(
    "API.py",
    "role_chat_service.py",
    "role_config.py",
    "memory_runtime.py",
    "memory_store_faiss.py",
    "persona_kernel_scorer.py",
    "planning_runtime.py",
    "anchor_runtime.py",
    "background_scheduler.py",
    "learning_runtime.py",
    "session_paths.py",
    "tool_runtime.py",
    "README.md",
    "README.zh-CN.md",
    "LICENSE"
)

foreach ($file in $files) {
    Copy-File $file
}

$dirs = @(
    "server",
    "web",
    "docs",
    "resources\qwen3_omni_training"
)

foreach ($dir in $dirs) {
    Copy-Dir $dir
}

Get-ChildItem -Path $stage -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
Get-ChildItem -Path $stage -Recurse -Include "*.pyc","*.pyo" -File | Remove-Item -Force

Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $zipPath -Force
Write-Host "[RoleWeaver A800] Package created: $zipPath"
