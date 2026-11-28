// The in-app updater, as the shell exposes it: three commands and one progress event. Everything here is a no-op
// outside the desktop app (the same UI runs in a browser for development).
import { invoke } from "@tauri-apps/api/core";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";
import { api } from "./api";
import { inTauri } from "./tauri";

/** Whether this installation may update, and from which channel. Never a URL: the channel's name only. */
export type UpdateStatus = { enabled: boolean; reason: string; channel: "release" | "override" | ""; current: string };
/** `date` is the publication time in unix seconds. */
export type UpdateCheck = { available: boolean; current: string; version: string | null; notes: string | null; date: number | null };
export type UpdateProgress = { phase: "download" | "verify" | "install"; downloaded: number; total: number | null };

export const updateStatus = () => invoke<UpdateStatus>("update_status");
/** Asks the channel; never downloads. */
export const checkForUpdate = () => invoke<UpdateCheck>("update_check");
/** Downloads (progress events), verifies the signature, stops the engine and hands over to the installer, which
 *  relaunches the app. Resolves only when something failed. */
export const installUpdate = () => invoke<void>("update_install");
export const onUpdateProgress = (cb: (p: UpdateProgress) => void): Promise<UnlistenFn> => listen<UpdateProgress>("update-progress", (e) => cb(e.payload));

/** The startup check: in the background, never blocking, never downloading. null = nothing to announce. */
export async function startupCheck(): Promise<UpdateCheck | null> {
  if (!inTauri()) return null;
  try {
    const s = await api.settings();
    if (!s.auto_update_check) return null;
    const st = await updateStatus();
    if (!st.enabled) return null;
    const c = await checkForUpdate();
    return c.available ? c : null;
  } catch {
    return null; // offline, or a channel that is not there yet: the customer can check by hand in Settings
  }
}

/** The shell's error texts, in the customer's words. */
export function friendlyUpdateError(e: unknown): string {
  const raw = String((e as { message?: string })?.message ?? e ?? "");
  const s = raw.toLowerCase();
  if (s.includes("signature") || s.includes("verify") || s.includes("minisign")) return "The downloaded update failed its signature check and was not installed. Try again later; if it keeps failing, contact support.";
  if (s.includes("dns") || s.includes("connect") || s.includes("sending request") || s.includes("timed out") || s.includes("timeout") || s.includes("network"))
    return "Could not reach the update server. Check the internet connection and try again.";
  // the connection dropped while the installer was coming down
  if (s.includes("decoding response body") || s.includes("reset") || s.includes("closed") || s.includes("incomplete") || s.includes("eof") || s.includes("body"))
    return "The download was interrupted before it finished. Nothing was changed; check the connection and try again.";
  if (s.includes("404") || s.includes("not found")) return "No release is published on the update channel yet.";
  // the plugin's wording for both "no manifest at that address yet" (a 404 page) and a broken manifest
  if (s.includes("could not fetch a valid release json") || s.includes("json")) return "No update is published on the release channel yet, or the server answered with something unexpected. Try again later.";
  if (s.includes("check for updates first")) return "Check for updates first.";
  return raw || "The update failed.";
}

export const mb = (n: number) => `${(n / 1048576).toFixed(n < 10485760 ? 1 : 0)} MB`;
