# Deploy the licensing backend to a Supabase project, without the database password:
#   .\installer\deploy_supabase.ps1 -ProjectRef <ref>          (the <ref> in https://<ref>.supabase.co)
# Needs one `npx supabase login` beforehand: its saved access token (or $env:SUPABASE_ACCESS_TOKEN) is what the CLI
# and the Management API calls below use. Safe to run again: the schema is skipped when the tables exist.
#
#   1. schema     supabase/migrations/*.sql through the Management API (and recorded for a later `supabase db push`)
#   2. secrets    supabase/keys/secrets.env (LICENSE_SIGNING_KEY)        -> supabase secrets set
#   3. function   supabase/functions/license                             -> supabase functions deploy
#   4. templates  supabase/templates/*.html, subjects from config.toml   -> auth email templates (code, not link)
param(
  [Parameter(Mandatory = $true)][string]$ProjectRef,
  [switch]$SkipSchema, [switch]$SkipSecrets, [switch]$SkipFunction, [switch]$SkipTemplates
)
$ErrorActionPreference = "Stop"
$studio = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location -LiteralPath $studio
$npx = if (Get-Command npx.cmd -ErrorAction SilentlyContinue) { "npx.cmd" } else { "npx" }

$token = $env:SUPABASE_ACCESS_TOKEN
if (-not $token) {
  $tf = Join-Path $env:APPDATA "supabase\access-token"
  if (Test-Path -LiteralPath $tf) { $token = (Get-Content -LiteralPath $tf -Raw).Trim() }
}
if (-not $token) { throw "Not signed in to Supabase: run 'npx supabase login' first (or set SUPABASE_ACCESS_TOKEN)." }
$api = "https://api.supabase.com/v1/projects/$ProjectRef"
$headers = @{ Authorization = "Bearer $token"; "Content-Type" = "application/json" }

function Invoke-Mgmt($method, $path, $body) {
  $json = $body | ConvertTo-Json -Depth 6 -Compress
  try { return Invoke-RestMethod -Uri "$api$path" -Method $method -Headers $headers -Body ([System.Text.Encoding]::UTF8.GetBytes($json)) -TimeoutSec 120 }
  catch {
    $detail = ""
    if ($_.Exception.Response) { try { $detail = (New-Object IO.StreamReader($_.Exception.Response.GetResponseStream())).ReadToEnd() } catch {} }
    throw "Management API $method $path failed: $($_.Exception.Message) $detail"
  }
}
function Invoke-Sql($sql) { return Invoke-Mgmt "POST" "/database/query" @{ query = $sql } }

$project = Invoke-Mgmt "GET" "" $null
Write-Host "project: $($project.name) ($ProjectRef, $($project.region), $($project.status))"

# ---- 1. schema
if (-not $SkipSchema) {
  $present = (Invoke-Sql "select to_regclass('public.licenses') is not null as present")[0].present
  if ($present) { Write-Host "schema: public.licenses exists already, migrations skipped" }
  else {
    Invoke-Sql "create schema if not exists supabase_migrations; create table if not exists supabase_migrations.schema_migrations (version text primary key, statements text[], name text);" | Out-Null
    foreach ($m in Get-ChildItem -LiteralPath "supabase\migrations" -Filter "*.sql" | Sort-Object Name) {
      Write-Host "schema: applying $($m.Name)"
      $sql = Get-Content -LiteralPath $m.FullName -Raw
      Invoke-Sql $sql | Out-Null
      $version, $name = $m.BaseName.Split("_", 2)
      $esc = $sql.Replace("'", "''")
      Invoke-Sql "insert into supabase_migrations.schema_migrations (version, name, statements) values ('$version', '$name', array['$esc']) on conflict (version) do nothing" | Out-Null
    }
  }
  $tables = Invoke-Sql "select table_name from information_schema.tables where table_schema = 'public' and table_name in ('licenses', 'license_devices') order by 1"
  Write-Host "schema: tables $(($tables | ForEach-Object { $_.table_name }) -join ', ')"
}

# ---- 2. secrets
if (-not $SkipSecrets) {
  Write-Host "secrets: setting LICENSE_SIGNING_KEY"
  & $npx --yes supabase secrets set --project-ref $ProjectRef --env-file "supabase\keys\secrets.env"
  if ($LASTEXITCODE -ne 0) { throw "supabase secrets set failed" }
}

# ---- 3. function
if (-not $SkipFunction) {
  Write-Host "function: deploying license"
  & $npx --yes supabase functions deploy license --project-ref $ProjectRef --no-verify-jwt
  if ($LASTEXITCODE -ne 0) { throw "supabase functions deploy failed" }
}

# ---- 4. email templates (the app's sign-up / reset flows type a code; a link cannot come back to a desktop app)
if (-not $SkipTemplates) {
  $toml = Get-Content -LiteralPath "supabase\config.toml" -Raw
  function Get-Subject($section, $fallback) {
    $m = [regex]::Match($toml, "(?ms)^\[auth\.email\.template\.$section\]\s*\n(?:[^\[]*?)subject\s*=\s*""([^""]*)""")
    if ($m.Success) { return $m.Groups[1].Value } else { return $fallback }
  }
  $patch = @{
    mailer_subjects_confirmation          = Get-Subject "confirmation" "Your BluxTech Studio confirmation code"
    mailer_templates_confirmation_content = Get-Content -LiteralPath "supabase\templates\confirmation.html" -Raw
    mailer_subjects_recovery              = Get-Subject "recovery" "Your BluxTech Studio password reset code"
    mailer_templates_recovery_content     = Get-Content -LiteralPath "supabase\templates\recovery.html" -Raw
  }
  Write-Host "templates: confirmation + recovery emails carry a code"
  Invoke-Mgmt "PATCH" "/config/auth" $patch | Out-Null
  $auth = Invoke-Mgmt "GET" "/config/auth" $null
  Write-Host "auth: email signup $(if ($auth.external_email_enabled) { 'on' } else { 'OFF' }), confirm email $(if ($auth.mailer_autoconfirm) { 'off (autoconfirm)' } else { 'on' }), confirmation template has code: $($auth.mailer_templates_confirmation_content -match '\{\{ \.Token \}\}')"
}
Write-Host "done"
