import type { EnvCheck } from "./api";

/** The system readiness panel: the engine's technical check folded into the few things a customer needs to know,
 *  with reasons written for them. File locations and tool names stay in developer mode. */
export type Readiness = { id: string; label: string; status: string; tone: "ok" | "warn" | "bad"; hint?: string };

const GROUPS: { id: string; label: string; items: string[]; ready?: string }[] = [
  { id: "media", label: "Media processing", items: ["python", "ffmpeg", "ffprobe"] },
  { id: "render", label: "Video rendering", items: ["node", "hyperframes", "chrome"] },
  { id: "speech", label: "Speech recognition", items: ["whisper"] },
  { id: "cutout", label: "Background removal", items: ["matte", "cutout"] },
  { id: "tools", label: "Creative tools", items: ["skill", "darijadz"] },
  { id: "claude", label: "Claude", items: ["claude"] },
  { id: "images", label: "AI image generation", items: ["gpt", "codex"] },
  { id: "storage", label: "Storage", items: ["workspace", "disk"], ready: "Sufficient" },
];

/** Why a row is not ready, in the customer's terms. The engine's own detail may name files and folders. */
const WHY: Record<string, string> = {
  python: "The media tools are damaged: reinstall BluxTech Studio.",
  ffmpeg: "The media tools are missing: reinstall BluxTech Studio.",
  ffprobe: "The media tools are missing: reinstall BluxTech Studio.",
  node: "The renderer is missing: reinstall BluxTech Studio.",
  hyperframes: "The renderer is installed by Setup.",
  chrome: "The renderer's browser is fetched by Setup (about 270 MB, once).",
  whisper: "The speech model is fetched by Setup (about 1.6 GB, once).",
  matte: "The cutout model is installed by Setup.",
  cutout: "The cutout engine is installed by Setup (about 210 MB, once).",
  skill: "The editing tools are missing: run Setup, or reinstall.",
  darijadz: "The Darija guide is missing: run Setup.",
  claude: "Add an Anthropic API key, or use the Claude Code login on this PC (Settings → Claude).",
  gpt: "No illustration library: ads use the jar and the discs only.",
  codex: "GPT drawing needs the ChatGPT desktop app with Codex on this PC; without it the library is used as it is.",
  workspace: "The projects folder cannot be written: check Documents.",
  disk: "Less than 10 GB free: cut-outs and renders need room.",
};

export function readiness(env: EnvCheck): Readiness[] {
  return GROUPS.map((g) => {
    const items = env.items.filter((i) => g.items.includes(i.id));
    const bad = items.filter((i) => !i.ok);
    if (!items.length || !bad.length) return { id: g.id, label: g.label, status: g.ready ?? "Ready", tone: "ok" };
    const hint = bad.map((i) => WHY[i.id]).filter(Boolean).join(" ");
    if (g.id === "images" && !bad.some((i) => i.id === "gpt")) return { id: g.id, label: g.label, status: "Library only", tone: "warn", hint };
    const required = bad.some((i) => i.required);
    return { id: g.id, label: g.label, status: required ? "Needs setup" : "Optional", tone: required ? "bad" : "warn", hint };
  });
}

/** True when nothing a customer must have is missing. */
export const allReady = (env: EnvCheck) => env.items.filter((i) => i.required).every((i) => i.ok);
