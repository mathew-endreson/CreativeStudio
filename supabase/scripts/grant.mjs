#!/usr/bin/env node
// Grant or change a license from the command line (no dependencies: calls grant_license() over the REST API).
// You can also run the same thing in Supabase > SQL Editor:
//   select grant_license('user@example.com', p_plan => 'pro', p_days => 365, p_devices => 2);
//
//   $env:SUPABASE_URL = "https://<ref>.supabase.co"
//   $env:SUPABASE_SECRET_KEY = "sb_secret_..."        (Project Settings > API Keys; the legacy service_role key works too)
//   node scripts/grant.mjs user@example.com --plan pro --days 365 --devices 2
//   node scripts/grant.mjs user@example.com --status suspended
//   node scripts/grant.mjs user@example.com --show
const [email, ...rest] = process.argv.slice(2);
if (!email) {
  console.error("usage: node grant.mjs <email> [--plan pro] [--days 365] [--devices 2] [--status active|suspended] [--show]");
  process.exit(2);
}
const opt = {};
for (let i = 0; i < rest.length; i++) if (rest[i].startsWith("--")) opt[rest[i].slice(2)] = rest[i + 1] && !rest[i + 1].startsWith("--") ? rest[++i] : true;

const url = (process.env.SUPABASE_URL ?? "").replace(/\/+$/, "");
const key = process.env.SUPABASE_SECRET_KEY ?? process.env.SUPABASE_SERVICE_ROLE_KEY;
if (!url || !key) {
  console.error("set SUPABASE_URL and SUPABASE_SECRET_KEY first");
  process.exit(2);
}
const headers = { apikey: key, "Content-Type": "application/json" };
if (!key.startsWith("sb_")) headers.Authorization = `Bearer ${key}`; // legacy service_role JWT

async function call(path, init) {
  const r = await fetch(`${url}/rest/v1/${path}`, { headers, ...init });
  const body = await r.json().catch(() => null);
  if (!r.ok) {
    console.error(`error ${r.status}:`, body?.message ?? body);
    process.exit(1);
  }
  return body;
}

if (opt.show) {
  const rows = await call(`licenses?select=*,license_devices(*)&email=ilike.${encodeURIComponent(email)}`);
  console.log(rows.length ? JSON.stringify(rows[0], null, 2) : "no license for this email");
  process.exit(0);
}
const args = { p_email: email };
if (opt.plan) args.p_plan = String(opt.plan);
if (opt.days) args.p_days = Number(opt.days);
if (opt.devices) args.p_devices = Number(opt.devices);
if (opt.status) args.p_status = String(opt.status);
const lic = await call("rpc/grant_license", { method: "POST", body: JSON.stringify(args) });
console.log(`license of ${email}:`, lic);
