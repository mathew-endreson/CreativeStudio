# CreativeStudio, dev mode: the engine on http://127.0.0.1:8766 serving the built UI, opened in the browser.
#   .\dev.ps1              start the engine (boot-token auth) and open the UI
#   .\dev.ps1 -NoAuth      no token on /api (for `npm run dev` in desktop/, which proxies to 8766)
#   .\dev.ps1 -Build       rebuild the UI first
param([switch]$NoAuth, [switch]$Build)
$ErrorActionPreference = "Continue"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = Join-Path $here "engine\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $py)) {
  Write-Output "creating engine\.venv ..."
  python -m venv --system-site-packages (Join-Path $here "engine\.venv")
  & $py -m pip install --quiet --disable-pip-version-check -r (Join-Path $here "engine\requirements.txt")
}
if ($Build -or -not (Test-Path -LiteralPath (Join-Path $here "desktop\dist\index.html"))) {
  Push-Location -LiteralPath (Join-Path $here "desktop")
  if (-not (Test-Path "node_modules")) { npm install --no-audit --no-fund }
  npm run build
  Pop-Location
}
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
$args = @((Join-Path $here "engine\run.py"), "--open")
if ($NoAuth) { $args += "--no-auth" }
& $py @args
