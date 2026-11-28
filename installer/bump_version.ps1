# Set the app version everywhere it lives, so the three files always agree (the release workflow refuses a tag
# whose version differs from tauri.conf.json):
#   .\installer\bump_version.ps1 0.1.1
# touches desktop\src-tauri\tauri.conf.json, desktop\src-tauri\Cargo.toml (+ Cargo.lock), desktop\package.json
# (+ package-lock.json). Commit, then tag v<version> to release.
param([Parameter(Mandatory = $true)][string]$Version)
$ErrorActionPreference = "Stop"
if ($Version -notmatch '^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$') { throw "not a version: $Version (expected 0.1.1 or 0.1.1-rc1)" }
$studio = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$desktop = Join-Path $studio "desktop"
$utf8 = New-Object Text.UTF8Encoding($false)

$conf = Join-Path $desktop "src-tauri\tauri.conf.json"
$text = Get-Content -LiteralPath $conf -Raw
$text = ([regex]'"version"\s*:\s*"[^"]+"').Replace($text, "`"version`": `"$Version`"", 1)
[IO.File]::WriteAllText($conf, $text, $utf8)

$cargo = Join-Path $desktop "src-tauri\Cargo.toml"
$text = Get-Content -LiteralPath $cargo -Raw
$text = ([regex]'(?m)^version = "[^"]+"').Replace($text, "version = `"$Version`"", 1)
[IO.File]::WriteAllText($cargo, $text, $utf8)

# the engine reports the version the UI shows (Settings, the title bar)
$engine = Join-Path $studio "engine\bluxtech_engine\config.py"
$text = Get-Content -LiteralPath $engine -Raw
$text = ([regex]'(?m)^VERSION = "[^"]+"').Replace($text, "VERSION = `"$Version`"", 1)
[IO.File]::WriteAllText($engine, $text, $utf8)

Push-Location -LiteralPath $desktop
try {
  npm version $Version --no-git-tag-version --allow-same-version | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "npm version failed" }
  if (Get-Command cargo -ErrorAction SilentlyContinue) {
    cargo update --workspace --manifest-path src-tauri/Cargo.toml --quiet
    if ($LASTEXITCODE -ne 0) { throw "cargo update --workspace failed" }
  }
} finally { Pop-Location }

Write-Output "version $Version in:"
Write-Output "  $conf"
Write-Output "  $cargo (+ Cargo.lock)"
Write-Output "  $engine"
Write-Output "  $(Join-Path $desktop 'package.json') (+ package-lock.json)"
