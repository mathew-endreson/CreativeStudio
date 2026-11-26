// Native pickers when the UI runs inside the Tauri shell; in a browser (dev) the forms fall back to typed paths.
export const inTauri = () => typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;

export async function pickFolder(): Promise<string | null> {
  if (!inTauri()) return null;
  const { open } = await import("@tauri-apps/plugin-dialog");
  const r = await open({ directory: true, multiple: false, title: "Choose a folder" });
  return typeof r === "string" ? r : null;
}

export async function pickVideo(): Promise<string | null> {
  if (!inTauri()) return null;
  const { open } = await import("@tauri-apps/plugin-dialog");
  const r = await open({ multiple: false, title: "Choose the footage", filters: [{ name: "Video", extensions: ["mp4", "mov", "m4v", "mkv", "webm", "mts"] }] });
  return typeof r === "string" ? r : null;
}
