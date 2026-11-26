/**
 * BluxTech Studio licensing Edge Function. The desktop app calls it signed in (Supabase Auth access token):
 *
 *   POST { action: "activate" | "check" | "deactivate", deviceId, deviceName?, appVersion? }
 *   -> { status, plan, expiresAt (ms) | null, maxDevices, devices: [{ id, name, lastSeen }], token }
 *   errors -> { code: "unauthenticated" | "invalid-argument" | "permission-denied" | "failed-precondition"
 *                     | "resource-exhausted" | "internal", message }
 *
 * The device limit, trials and expiry live in Postgres (migrations/*_licensing.sql). This function checks the user and
 * signs the RS256 token the app verifies offline with license_public_key.pem.
 *
 * Secrets (supabase secrets set): LICENSE_SIGNING_KEY = the RSA private key (PEM, or the PEM in base64 on one line).
 * Optional: TRIAL_DAYS (7), TRIAL_DEVICES (1), LICENSE_TOKEN_DAYS (14).
 */
import { createClient } from "npm:@supabase/supabase-js@2";
import { importPKCS8, SignJWT } from "npm:jose@5";

const admin = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!, {
  auth: { persistSession: false, autoRefreshToken: false },
});

const int = (name: string, fallback: number) => {
  const v = Number(Deno.env.get(name));
  return Deno.env.get(name) && Number.isFinite(v) ? Math.trunc(v) : fallback;
};
const TRIAL_DAYS = int("TRIAL_DAYS", 7);
const TRIAL_DEVICES = int("TRIAL_DEVICES", 1);
const TOKEN_DAYS = int("LICENSE_TOKEN_DAYS", 14);

const HTTP: Record<string, number> = {
  "invalid-argument": 400,
  unauthenticated: 401,
  "permission-denied": 403,
  "failed-precondition": 412,
  "resource-exhausted": 429,
  internal: 500,
};
const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

class Fail extends Error {
  constructor(readonly code: string, message: string) {
    super(message);
  }
}

type Answer = {
  status: string;
  plan: string;
  expiresAt: number | null;
  maxDevices: number;
  devices: { id: string; name: string; lastSeen: number }[];
  token?: string | null;
};

let keyPromise: Promise<CryptoKey> | null = null;
function signingKey(): Promise<CryptoKey> | null {
  const raw = (Deno.env.get("LICENSE_SIGNING_KEY") ?? "").trim();
  if (!raw) return null;
  const pem = raw.startsWith("-----") ? raw.replace(/\\n/g, "\n") : atob(raw);
  return (keyPromise ??= importPKCS8(pem, "RS256"));
}

async function sign(uid: string, deviceId: string, a: Answer): Promise<string | null> {
  const key = signingKey();
  if (!key || !["trial", "active"].includes(a.status)) return null;
  return await new SignJWT({
    dev: deviceId,
    status: a.status,
    plan: a.plan,
    license_exp: a.expiresAt ? Math.floor(a.expiresAt / 1000) : null,
  })
    .setProtectedHeader({ alg: "RS256" })
    .setSubject(uid)
    .setIssuedAt()
    .setExpirationTime(Math.floor(Date.now() / 1000) + TOKEN_DAYS * 86400)
    .sign(await key);
}

async function rpc<T>(fn: string, args: Record<string, unknown>): Promise<T> {
  const { data, error } = await admin.rpc(fn, args);
  if (error) throw new Fail(error.hint && error.hint in HTTP ? error.hint : "internal", error.message);
  return data as T;
}

function deviceArgs(body: Record<string, unknown>) {
  const { deviceId, deviceName, appVersion } = body;
  if (typeof deviceId !== "string" || !/^[0-9a-f-]{36}$/i.test(deviceId)) {
    throw new Fail("invalid-argument", "deviceId must be the app's UUID.");
  }
  return {
    deviceId,
    deviceName: typeof deviceName === "string" && deviceName.trim() ? deviceName.slice(0, 80) : "PC",
    appVersion: typeof appVersion === "string" ? appVersion.slice(0, 20) : "",
  };
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { ...CORS, "Content-Type": "application/json" } });

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  try {
    if (req.method !== "POST") throw new Fail("invalid-argument", "Use POST.");
    const jwt = (req.headers.get("Authorization") ?? "").replace(/^Bearer\s+/i, "").trim();
    const { data: auth, error: authErr } = jwt ? await admin.auth.getUser(jwt) : { data: { user: null }, error: null };
    const user = auth.user;
    if (authErr || !user) throw new Fail("unauthenticated", "Sign in first.");

    const body = ((await req.json().catch(() => ({}))) ?? {}) as Record<string, unknown>;
    const { deviceId, deviceName, appVersion } = deviceArgs(body);
    let answer: Answer;
    switch (body.action) {
      case "activate":
        answer = await rpc<Answer>("activate_device", {
          p_user: user.id,
          p_email: user.email ?? "",
          p_device: deviceId,
          p_name: deviceName,
          p_version: appVersion,
          p_trial_days: TRIAL_DAYS,
          p_trial_devices: TRIAL_DEVICES,
        });
        break;
      case "check":
        answer = await rpc<Answer>("check_device", { p_user: user.id, p_device: deviceId });
        break;
      case "deactivate":
        await rpc("deactivate_device", { p_user: user.id, p_device: deviceId });
        return json({ ok: true });
      default:
        throw new Fail("invalid-argument", "action must be activate, check or deactivate.");
    }
    answer.token = await sign(user.id, deviceId, answer);
    return json(answer);
  } catch (e) {
    const f = e instanceof Fail ? e : new Fail("internal", (e as Error)?.message ?? String(e));
    if (f.code === "internal") console.error(e);
    return json({ code: f.code, message: f.message }, HTTP[f.code] ?? 500);
  }
});
