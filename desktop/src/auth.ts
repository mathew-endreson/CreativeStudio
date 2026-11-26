// Supabase Auth + the `license` Edge Function. The engine only ever sees the function's answer.
// Emails carry a code (not a link) for sign-up confirmation and password reset: a desktop app cannot receive a link's
// redirect. That needs {{ .Token }} in the Supabase email templates (see README, Licensing).
import { createClient, FunctionsFetchError, FunctionsHttpError, type SupabaseClient, type User } from "@supabase/supabase-js";
import { useEffect, useState } from "react";
import { api, type AppInfo, type AuthCfg, type LicenseState } from "./api";

export type { User };

let sb: SupabaseClient | null = null;

export function initAuth(cfg: AuthCfg): SupabaseClient {
  if (!sb) {
    sb = createClient(cfg.url, cfg.publishableKey, {
      auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: false, storageKey: "bluxtech-auth" },
    });
  }
  return sb;
}

/** undefined = still loading, null = signed out. */
export function useUser(cfg: AuthCfg | null): User | null | undefined {
  const [user, setUser] = useState<User | null | undefined>(cfg ? undefined : null);
  useEffect(() => {
    if (!cfg) return;
    const { data } = initAuth(cfg).auth.onAuthStateChange((_event, session) => setUser(session?.user ?? null));
    return () => data.subscription.unsubscribe();
  }, [cfg]);
  return user;
}

const client = () => {
  if (!sb) throw new Error("Supabase is not configured.");
  return sb;
};
const must = <T extends { error: unknown }>(r: T): T => {
  if (r.error) throw r.error;
  return r;
};
const coded = (code: string, message = "") => Object.assign(new Error(message), { code });

export const signIn = async (email: string, password: string) => void must(await client().auth.signInWithPassword({ email, password }));

/** "signed-in" when the project does not confirm emails, "confirm" when a code was emailed. */
export async function createAccount(email: string, password: string): Promise<"signed-in" | "confirm"> {
  const { data } = must(await client().auth.signUp({ email, password }));
  // With email confirmation on, Supabase answers an existing email with a user that has no identities.
  if (data.user && data.user.identities?.length === 0) throw coded("user_already_exists");
  return data.session ? "signed-in" : "confirm";
}
export const confirmSignup = async (email: string, code: string) => void must(await client().auth.verifyOtp({ email, token: code, type: "signup" }));
export const resendSignup = async (email: string) => void must(await client().auth.resend({ type: "signup", email }));
export const sendResetCode = async (email: string) => void must(await client().auth.resetPasswordForEmail(email));
/** The code signs the user in; the new password is set right after. */
export async function resetWithCode(email: string, code: string, password: string) {
  must(await client().auth.verifyOtp({ email, token: code, type: "recovery" }));
  must(await client().auth.updateUser({ password }));
}

export async function signOut() {
  if (sb) await sb.auth.signOut({ scope: "local" }).catch(() => {});
  await api.deleteLicense().catch(() => {});
}

type Activation = {
  status: string;
  plan: string;
  expiresAt: number | null; // milliseconds
  maxDevices: number;
  token: string | null;
  devices?: { id: string; name: string; lastSeen: number }[];
};

async function callLicense<T>(body: Record<string, unknown>): Promise<T> {
  const { data, error } = await client().functions.invoke<T>("license", { body });
  if (!error) return data as T;
  if (error instanceof FunctionsHttpError) {
    const res = error.context as Response;
    const j = (await res.json().catch(() => null)) as { code?: string; message?: string } | null;
    if (res.status === 404 && !j?.code?.includes("-")) throw coded("license/not-deployed");
    throw coded(`license/${j?.code ?? res.status}`, j?.message ?? `HTTP ${res.status}`);
  }
  if (error instanceof FunctionsFetchError) throw coded("network", error.message);
  throw error;
}

/** Ask the cloud for this device's license, then hand the answer to the engine. */
export async function activate(info: AppInfo, user: User): Promise<LicenseState> {
  const a = await callLicense<Activation>({ action: "activate", deviceId: info.device_id, deviceName: info.device_name, appVersion: info.version });
  return api.postLicense({
    uid: user.id,
    email: user.email ?? "",
    status: a.status,
    plan: a.plan,
    expires_at: a.expiresAt ? a.expiresAt / 1000 : null,
    max_devices: a.maxDevices,
    device_id: info.device_id,
    device_name: info.device_name,
    token: a.token ?? null,
  });
}

/** Free this device's slot (Settings), then forget the local license. */
export async function deactivate(info: AppInfo) {
  await callLicense({ action: "deactivate", deviceId: info.device_id });
  await api.deleteLicense();
}

export function errorCode(e: unknown): string {
  const x = e as { code?: string; name?: string } | null;
  if (x?.name === "AuthRetryableFetchError") return "network";
  return x?.code ?? "";
}

export function authError(e: unknown): string {
  const map: Record<string, string> = {
    invalid_credentials: "Wrong email or password.",
    email_not_confirmed: "Confirm the email first: enter the code we sent.",
    email_address_invalid: "That is not an email address.",
    validation_failed: "Check the email and the password.",
    user_already_exists: "An account with this email exists: sign in instead.",
    email_exists: "An account with this email exists: sign in instead.",
    weak_password: "Use a stronger password (at least 6 characters).",
    same_password: "The new password must differ from the old one.",
    otp_expired: "That code is wrong or has expired: send a new one.",
    over_email_send_rate_limit: "Too many emails sent: wait a few minutes and try again.",
    over_request_rate_limit: "Too many attempts: wait a minute and try again.",
    signup_disabled: "New accounts are closed for now.",
    network: "No connection to the server: check the internet.",
    "license/resource-exhausted": "This license is already used on its maximum number of devices.",
    "license/permission-denied": "No active license for this account.",
    "license/failed-precondition": "The license is not active (expired or suspended).",
    "license/not-deployed": "The licensing service is not deployed.",
    "license/unauthenticated": "Sign in again.",
  };
  const code = errorCode(e);
  const server = (e as Error)?.message;
  // The license function's own message names the limit ("allows 2 device(s)"): prefer it when there is one.
  if (code.startsWith("license/") && server && code !== "license/not-deployed" && code !== "license/unauthenticated") return server;
  return map[code] ?? (server || String(e));
}
