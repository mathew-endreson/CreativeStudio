# Stage everything the installed app runs from <resources>: an embedded Python with the engine's and the skill's
# packages, a portable Node.js with HyperFrames, FFmpeg, the engine, the skill, the UI and the public configs.
# Downloads are cached in installer/downloads. Output: desktop/src-tauri/resources (bundled by tauri build).
#
#   .\installer\build_runtime.ps1                 full staging
#   .\installer\build_runtime.ps1 -SkipDownloads  only refresh engine, skill, UI and configs
param(
  [string]$PythonVersion = "3.12.10",
  [string]$NodeVersion = "22.14.0",
  [string]$HyperframesVersion = "0.9.38",
  [string]$FfmpegUrl = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
  # the illustration library to ship: the GPT asset tool's folder on the owner's PC, or assets-library/ in the repo (CI)
  [string]$LibraryDir = (Join-Path $env:USERPROFILE "Documents\ChatGPT\asstets tool ebox"),
  [switch]$SkipDownloads
)
$ErrorActionPreference = "Stop"
$studio = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)   # bluxtech-studio
$project = Split-Path -Parent $studio                                             # SH-101126 EBOX YASSINE
$res = Join-Path $studio "desktop\src-tauri\resources"
$dl = Join-Path $studio "installer\downloads"
New-Item -ItemType Directory -Force $res, $dl | Out-Null

function Get-File($url, $name) {
  $out = Join-Path $dl $name
  if (-not (Test-Path -LiteralPath $out)) {
    Write-Host "downloading $name"
    Invoke-WebRequest -UseBasicParsing $url -OutFile $out
  }
  return $out
}

if (-not $SkipDownloads) {
  # ---- Python (embeddable) + pip + packages
  $py = Join-Path $res "python"
  if (-not (Test-Path -LiteralPath (Join-Path $py "python.exe"))) {
    $zip = Get-File "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip" "python-$PythonVersion-embed-amd64.zip"
    Expand-Archive -LiteralPath $zip -DestinationPath $py -Force
    $pth = Get-ChildItem -LiteralPath $py -Filter "python3*._pth" | Select-Object -First 1
    # the embeddable build ignores site-packages until `import site` is uncommented
    (Get-Content -LiteralPath $pth.FullName) -replace "^#import site", "import site" | Set-Content -LiteralPath $pth.FullName -Encoding ascii
    Add-Content -LiteralPath $pth.FullName -Value "Lib\site-packages" -Encoding ascii
  }
  $python = Join-Path $py "python.exe"
  if (-not (Test-Path -LiteralPath (Join-Path $py "Scripts\pip.exe"))) {
    $getpip = Get-File "https://bootstrap.pypa.io/get-pip.py" "get-pip.py"
    & $python $getpip --no-warn-script-location
  }
  Write-Output "installing the engine's and the skill's packages into the runtime"
  & $python -m pip install --no-warn-script-location --disable-pip-version-check -r (Join-Path $studio "engine\requirements.txt") -r (Join-Path $studio "installer\runtime-requirements.txt")
  if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
  # a normal sys.path (the script's folder, the current folder for -m) despite the ._pth's isolated mode, and the
  # engine folder itself: see installer/runtime/_bluxtech_paths.py
  Copy-Item -LiteralPath (Join-Path $studio "installer\runtime\_bluxtech_paths.py"), (Join-Path $studio "installer\runtime\bluxtech_paths.pth") (Join-Path $py "Lib\site-packages") -Force
  $pthFile = (Get-ChildItem -LiteralPath $py -Filter "python3*._pth" | Select-Object -First 1).FullName
  if (-not (Select-String -LiteralPath $pthFile -SimpleMatch -Pattern "..\engine" -Quiet)) { Add-Content -LiteralPath $pthFile -Value "..\engine" -Encoding ascii }
  # trim what the app never runs: the packages' own test suites
  Get-ChildItem -LiteralPath (Join-Path $py "Lib\site-packages") -Recurse -Directory | Where-Object { $_.Name -in @("tests", "test") } | ForEach-Object { if (Test-Path -LiteralPath $_.FullName) { Remove-Item -Recurse -Force -LiteralPath $_.FullName } }

  # ---- Node.js (portable) + HyperFrames
  $node = Join-Path $res "node"
  if (-not (Test-Path -LiteralPath (Join-Path $node "node.exe"))) {
    $zip = Get-File "https://nodejs.org/dist/v$NodeVersion/node-v$NodeVersion-win-x64.zip" "node-v$NodeVersion-win-x64.zip"
    $tmp = Join-Path $dl "node-tmp"
    if (Test-Path -LiteralPath $tmp) { Remove-Item -Recurse -Force -LiteralPath $tmp }
    Expand-Archive -LiteralPath $zip -DestinationPath $tmp -Force
    Move-Item -LiteralPath (Join-Path $tmp "node-v$NodeVersion-win-x64") $node
    Remove-Item -Recurse -Force -LiteralPath $tmp
  }
  $hf = Join-Path $res "hyperframes"
  New-Item -ItemType Directory -Force $hf | Out-Null
  if (-not (Test-Path -LiteralPath (Join-Path $hf "node_modules\hyperframes\bin\hyperframes.mjs"))) {
    Set-Content -LiteralPath (Join-Path $hf "package.json") -Value '{"name": "_hyperframes", "private": true, "type": "commonjs"}' -Encoding ascii
    $env:PATH = "$node;$env:PATH"
    Push-Location -LiteralPath $hf
    & (Join-Path $node "npm.cmd") install --no-audit --no-fund "hyperframes@$HyperframesVersion"
    $code = $LASTEXITCODE
    Pop-Location
    if ($code -ne 0) { throw "npm install hyperframes failed" }
  }
  Copy-Item -LiteralPath (Join-Path $project "_hyperframes\hyperframes.json") (Join-Path $hf "hyperframes.json") -Force

  # ---- FFmpeg
  $ff = Join-Path $res "ffmpeg\bin"
  if (-not (Test-Path -LiteralPath (Join-Path $ff "ffmpeg.exe"))) {
    $zip = Get-File $FfmpegUrl "ffmpeg-release-essentials.zip"
    $tmp = Join-Path $dl "ffmpeg-tmp"
    if (Test-Path -LiteralPath $tmp) { Remove-Item -Recurse -Force -LiteralPath $tmp }
    Expand-Archive -LiteralPath $zip -DestinationPath $tmp -Force
    New-Item -ItemType Directory -Force $ff | Out-Null
    # only the two tools the engine and the skill call (ffplay and the HTML docs would add 110 MB)
    Get-ChildItem -LiteralPath $tmp -Recurse -File | Where-Object { $_.Name -in @("ffmpeg.exe", "ffprobe.exe") } | ForEach-Object { Copy-Item -LiteralPath $_.FullName (Join-Path $ff $_.Name) -Force }
    Get-ChildItem -LiteralPath $tmp -Recurse -Filter "LICENSE*" | Select-Object -First 1 | ForEach-Object { Copy-Item -LiteralPath $_.FullName (Join-Path $res "ffmpeg\LICENSE.txt") -Force }
    Remove-Item -Recurse -Force -LiteralPath $tmp
  }

  # ---- the speaker matte model, when this machine has it cached (saves the first-run download)
  $matte = Join-Path $env:USERPROFILE ".cache\hyperframes\background-removal\models\u2net_human_seg.onnx"
  if (Test-Path -LiteralPath $matte) {
    New-Item -ItemType Directory -Force (Join-Path $res "models") | Out-Null
    Copy-Item -LiteralPath $matte (Join-Path $res "models\u2net_human_seg.onnx") -Force
  }
}

# ---- the engine, the skill, the UI, the configs (always refreshed)
Write-Output "copying engine, skill, UI"
$eng = Join-Path $res "engine"
if (Test-Path -LiteralPath $eng) { Remove-Item -Recurse -Force -LiteralPath $eng }
New-Item -ItemType Directory -Force $eng | Out-Null
Copy-Item -Recurse -LiteralPath (Join-Path $studio "engine\bluxtech_engine") (Join-Path $eng "bluxtech_engine")
Get-ChildItem -LiteralPath (Join-Path $eng "bluxtech_engine") -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
Copy-Item -Recurse -LiteralPath (Join-Path $studio "engine\prompts") (Join-Path $eng "prompts")

# the two skills the engine lays into the workspace (environment.init_workspace): the edit pipeline and the Darija guide
$renamed = Join-Path $res "skill\camel-gpt"     # the edit skill's name until Nov 26 2026: never ship it twice
if (Test-Path -LiteralPath $renamed) { Remove-Item -Recurse -Force -LiteralPath $renamed }
foreach ($name in @("bluxstudio-skill", "darijadz")) {
  $skill = Join-Path $res "skill\$name"
  if (Test-Path -LiteralPath $skill) { Remove-Item -Recurse -Force -LiteralPath $skill }
  New-Item -ItemType Directory -Force (Split-Path -Parent $skill) | Out-Null
  Copy-Item -Recurse -LiteralPath (Join-Path $project ".claude\skills\$name") $skill
  Get-ChildItem -LiteralPath $skill -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
}

# ---- the Visual C++ 2022 runtime beside python.exe (onnxruntime, ctranslate2 and OpenCV need msvcp140*.dll; a clean
# PC has no VC++ redistributable, and app-local deployment of these DLLs is what Microsoft allows). From the VS Build
# Tools' VC\Redist\MSVC\<ver>\x64\Microsoft.VC143.{CRT,OpenMP}, kept in installer\vcredist.
$vc = Join-Path $studio "installer\vcredist"
if (-not (Test-Path -LiteralPath $vc)) {
  # not kept in the repository: taken from a Visual Studio / Build Tools install (VC\Redist\MSVC\<ver>\x64), which
  # the build PC and the GitHub Actions windows runners both have
  $crt = Get-ChildItem "C:\Program Files*\Microsoft Visual Studio\*\*\VC\Redist\MSVC\*\x64\Microsoft.VC143.CRT" -Directory -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1
  if ($crt) {
    New-Item -ItemType Directory -Force $vc | Out-Null
    Copy-Item -Path (Join-Path $crt.FullName "*.dll") -Destination $vc -Force
    $omp = Join-Path $crt.Parent.FullName "Microsoft.VC143.OpenMP"
    if (Test-Path -LiteralPath $omp) { Copy-Item -Path (Join-Path $omp "*.dll") -Destination $vc -Force }
    Write-Output "vc runtime: taken from $($crt.FullName)"
  }
}
if (Test-Path -LiteralPath $vc) {
  Get-ChildItem -LiteralPath $vc -Filter "*.dll" | ForEach-Object { Copy-Item -LiteralPath $_.FullName (Join-Path $res "python") -Force }
  Write-Output "vc runtime: $((Get-ChildItem -LiteralPath $vc -Filter '*.dll').Count) DLLs beside python.exe"
} else { Write-Warning "installer\vcredist is missing: the embedded runtime will need the VC++ 2022 redistributable on the customer's PC" }

# ---- the illustration library (the GPT asset tool's folder on the build PC): library.json + the pictures + the style
# references. The engine copies it into the workspace when the customer has no ChatGPT asset tool of their own.
$libSrc = $LibraryDir
if (-not (Test-Path -LiteralPath (Join-Path $libSrc "library.json")) -and (Test-Path -LiteralPath (Join-Path $studio "assets-library\library.json"))) {
  $libSrc = Join-Path $studio "assets-library"           # no GPT asset tool on this machine: the copy in the repo
}
$lib = Join-Path $res "assets"
if (Test-Path -LiteralPath (Join-Path $libSrc "library.json")) {
  if (Test-Path -LiteralPath $lib) { Remove-Item -Recurse -Force -LiteralPath $lib }
  New-Item -ItemType Directory -Force $lib | Out-Null
  foreach ($name in @("library.json", "AGENTS.md")) { if (Test-Path -LiteralPath (Join-Path $libSrc $name)) { Copy-Item -LiteralPath (Join-Path $libSrc $name) $lib -Force } }
  foreach ($name in @("generated", "style")) { if (Test-Path -LiteralPath (Join-Path $libSrc $name)) { Copy-Item -Recurse -LiteralPath (Join-Path $libSrc $name) (Join-Path $lib $name) } }
  Get-ChildItem -LiteralPath $lib -Recurse -Directory | Where-Object { $_.Name -in @("_raw", ".gpt-assets", "__pycache__") } | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
  Write-Output "illustration library: $((Get-ChildItem -LiteralPath (Join-Path $lib 'generated') -File -ErrorAction SilentlyContinue).Count) pictures"
} else { Write-Warning "no illustration library at ${libSrc}: ads on the customer's PC get the jar and discs only" }

$ui = Join-Path $res "ui"
if (-not (Test-Path -LiteralPath (Join-Path $studio "desktop\dist\index.html"))) { throw "build the UI first: npm run build in desktop/" }
if (Test-Path -LiteralPath $ui) { Remove-Item -Recurse -Force -LiteralPath $ui }
Copy-Item -Recurse -LiteralPath (Join-Path $studio "desktop\dist") $ui

foreach ($name in @("supabase.config.json", "license_public_key.pem")) {
  $src = Join-Path $studio "desktop\$name"
  if (Test-Path -LiteralPath $src) { Copy-Item -LiteralPath $src (Join-Path $res $name) -Force }
  else { Write-Warning "$name is missing: the app will run with licensing off" }
}
Write-Output "resources staged in $res"
Get-ChildItem -LiteralPath $res | Select-Object Name
