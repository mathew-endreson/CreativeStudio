# The updater manifest (latest.json) for the installer just built: version, notes, date, and the Windows x64
# artifact's download URL and signature. The Tauri updater reads it from the release channel.
#
#   .\installer\make_update_manifest.ps1 -Tag v0.1.1                      URL on the GitHub release of that tag
#   .\installer\make_update_manifest.ps1 -BaseUrl http://127.0.0.1:8777   URL on a local server (rehearsal)
#
# Notes come from -Notes, else installer\RELEASE_NOTES.md when it exists, else a one-liner. GitHub stores an asset
# "BluxTech Studio_0.1.1_x64-setup.exe" under the name "BluxTech.Studio_0.1.1_x64-setup.exe" (spaces become dots),
# and the manifest must name the file as the server serves it.
param(
  [string]$Tag = "",
  [string]$BaseUrl = "",
  [string]$Repo = "mathew-endreson/CreativeStudio",
  [string]$Notes = "",
  [string]$Out = ""
)
$ErrorActionPreference = "Stop"
$studio = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$bundle = Join-Path $studio "desktop\src-tauri\target\release\bundle\nsis"
$conf = Get-Content -LiteralPath (Join-Path $studio "desktop\src-tauri\tauri.conf.json") -Raw | ConvertFrom-Json
$version = $conf.version

$exe = Get-ChildItem -LiteralPath $bundle -Filter "*_x64-setup.exe" | Where-Object { $_.Name -like "*_$version*" } | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $exe) { throw "no installer for version $version in ${bundle}: build first" }
$sig = "$($exe.FullName).sig"
if (-not (Test-Path -LiteralPath $sig)) { throw "no signature next to $($exe.Name): the build was not signed (TAURI_SIGNING_PRIVATE_KEY)" }

if (-not $Notes) {
  $notesFile = Join-Path $studio "installer\RELEASE_NOTES.md"
  if (Test-Path -LiteralPath $notesFile) { $Notes = (Get-Content -LiteralPath $notesFile -Raw).Trim() }
  else { $Notes = "BluxTech Studio $version" }
}
if ($BaseUrl) { $url = "$($BaseUrl.TrimEnd('/'))/$($exe.Name -replace ' ', '.')" }
elseif ($Tag) { $url = "https://github.com/$Repo/releases/download/$Tag/$($exe.Name -replace ' ', '.')" }
else { throw "give -Tag (a GitHub release) or -BaseUrl (a rehearsal server)" }

$manifest = [ordered]@{
  version   = $version
  notes     = $Notes
  pub_date  = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
  platforms = [ordered]@{ "windows-x86_64" = [ordered]@{ signature = (Get-Content -LiteralPath $sig -Raw).Trim(); url = $url } }
}
if (-not $Out) { $Out = Join-Path $bundle "latest.json" }
[IO.File]::WriteAllText($Out, ($manifest | ConvertTo-Json -Depth 4), (New-Object Text.UTF8Encoding($false)))
Write-Output "manifest: $Out -> $version at $url"
