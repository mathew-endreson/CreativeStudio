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

function Get-CliTokenFromCredentialManager {
  # `supabase login` keeps the token in the Windows Credential Manager (generic credential "Supabase CLI:supabase")
  $src = @'
using System; using System.Runtime.InteropServices; using System.Text;
public static class WinCred {
  [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
  public struct CREDENTIAL { public uint Flags; public uint Type; public string TargetName; public string Comment;
    public System.Runtime.InteropServices.ComTypes.FILETIME LastWritten; public uint CredentialBlobSize; public IntPtr CredentialBlob;
    public uint Persist; public uint AttributeCount; public IntPtr Attributes; public string TargetAlias; public string UserName; }
  [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)] static extern bool CredRead(string target, uint type, uint flags, out IntPtr credential);
  [DllImport("advapi32.dll")] static extern void CredFree(IntPtr buffer);
  public static string Read(string target) {
    IntPtr p; if (!CredRead(target, 1, 0, out p)) return null;
    try {
      var c = (CREDENTIAL)Marshal.PtrToStructure(p, typeof(CREDENTIAL));
      var b = new byte[c.CredentialBlobSize]; Marshal.Copy(c.CredentialBlob, b, 0, b.Length);
      var s = Encoding.UTF8.GetString(b); if (s.IndexOf('\0') >= 0) s = Encoding.Unicode.GetString(b);
      return s.Trim('\0');
    } finally { CredFree(p); }
  }
}
'@
  if (-not ("WinCred" -as [type])) { Add-Type -TypeDefinition $src }
  return [WinCred]::Read("Supabase CLI:supabase")
}

$token = $env:SUPABASE_ACCESS_TOKEN
if (-not $token) {
  $tf = Join-Path $env:APPDATA "supabase\access-token"
  if (Test-Path -LiteralPath $tf) { $token = (Get-Content -LiteralPath $tf -Raw).Trim() }
}
if (-not $token) { $token = Get-CliTokenFromCredentialManager }
if (-not $token) { throw "Not signed in to Supabase: run 'npx supabase login' first (or set SUPABASE_ACCESS_TOKEN)." }
$api = "https://api.supabase.com/v1/projects/$ProjectRef"
$headers = @{ Authorization = "Bearer $token"; "Content-Type" = "application/json" }

function Invoke-Mgmt($method, $path, $body) {
  $params = @{ Uri = "$api$path"; Method = $method; Headers = $headers; TimeoutSec = 120 }
  if ($null -ne $body) { $params.Body = [System.Text.Encoding]::UTF8.GetBytes(($body | ConvertTo-Json -Depth 6 -Compress)) }
  try { return Invoke-RestMethod @params }
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
      # the query endpoint takes only a few KB per call: one statement at a time ($$ bodies kept whole)
      $statements = @(); $buf = ""; $inBody = $false
      foreach ($line in (Get-Content -LiteralPath $m.FullName)) {
        $t = $line.Trim()
        if (-not $inBody -and ($t -eq "" -or $t.StartsWith("--"))) { continue }
        $buf += $line + "`n"
        $n = ([regex]::Matches($line, '\$\$')).Count
        if ($n % 2 -eq 1) { $inBody = -not $inBody }
        if (-not $inBody -and $t.EndsWith(";")) { $statements += $buf; $buf = "" }
      }
      if ($buf.Trim()) { $statements += $buf }
      Write-Host "schema: applying $($m.Name) ($($statements.Count) statements)"
      foreach ($s in $statements) { Invoke-Sql $s | Out-Null }
      $version, $name = $m.BaseName.Split("_", 2)
      Invoke-Sql "insert into supabase_migrations.schema_migrations (version, name, statements) values ('$version', '$name', array[]::text[]) on conflict (version) do nothing" | Out-Null
    }
  }
  $tables = Invoke-Sql "select table_name from information_schema.tables where table_schema = 'public' and table_name in ('licenses', 'license_devices') order by 1"
  Write-Host "schema: tables $(($tables | ForEach-Object { $_.table_name }) -join ', ')"
}

# ---- 2. secrets
if (-not $SkipSecrets) {
  Write-Host "secrets: setting LICENSE_SIGNING_KEY"
  # the CLI's own --yes confirms the hosted change (it refuses to ask when it detects a non-interactive run)
  & $npx --yes supabase secrets set "--remote=$ProjectRef" --env-file "supabase\keys\secrets.env" --yes
  if ($LASTEXITCODE -ne 0) { throw "supabase secrets set failed" }
}

# ---- 3. function
if (-not $SkipFunction) {
  Write-Host "function: deploying license"
  & $npx --yes supabase functions deploy license "--remote=$ProjectRef" --no-verify-jwt --yes
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
  try { Invoke-Mgmt "PATCH" "/config/auth" $patch | Out-Null }
  catch {
    if ("$_" -match "entitlement_required") {
      Write-Warning ("Email templates cannot be changed on a free-tier project that uses Supabase's default email provider. " +
        "Sign-up still works: the default email carries a link, which confirms the account once opened, and the user then " +
        "signs in. Password reset from inside the app needs a code, so add a custom SMTP provider (Project Settings > " +
        "Authentication > SMTP), then run this script again.")
    } else { throw }
  }
  $auth = Invoke-Mgmt "GET" "/config/auth" $null
  Write-Host "auth: email signup $(if ($auth.external_email_enabled) { 'on' } else { 'OFF' }), confirm email $(if ($auth.mailer_autoconfirm) { 'off (autoconfirm)' } else { 'on' }), confirmation template has code: $($auth.mailer_templates_confirmation_content -match '\{\{ \.Token \}\}'), code length: $($auth.mailer_otp_length)"
}
Write-Host "done"
