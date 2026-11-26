// The engine's JSON, typed. Shapes follow bluxtech_engine/schemas*.py, products.py, fresh.py and the skill's batch.py.
// Every URL is relative: the engine serves this UI, so the boot cookie goes with each request (fetch, <img>, <video>, SSE).

export type ProductCard = {
  slug: string;
  name: string;
  name_ar?: string | null;
  sources?: number;
  mixes?: number;
  ads?: number;
  proposals?: number;
  analysis?: boolean;
  ads_dir?: string | null;
  todo?: string[];
  error?: string;
  not_imported?: boolean;
};

export type SourceState = {
  key: string;
  label?: string | null;
  file?: string | null;
  note?: string | null;
  copy: boolean;
  words: boolean;
  scan: boolean;
  darija?: DarijaState;
  frames?: number | null;
  duration?: number | null;
  issues: string[];
  cutouts: [number, number][];
};

export type MixState = {
  id: string;
  name: string;
  locked: boolean;
  duration: number;
  built: boolean;
  raw: boolean;
  ad: boolean;
  ad_path: string | null;
};

export type Usage = {
  claude_runs: number;
  turns: number;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  seconds: number;
  gpt_drawings: number;
  last: { stage: string; at: string; model?: string; five_hour_utilization?: number | null; runner?: string } | null;
};

export type ProductDetail = {
  slug: string;
  dir: string;
  product: Record<string, any>;
  todo: string[];
  sources: SourceState[];
  mixes: MixState[];
  next_mix: number;
  analysis: boolean;
  proposals: boolean;
  session_id?: string | null;
  usage: Usage;
};

export type Word = { w: string; s: number; e: number; p: number };
export type Segment = { start: number; end: number; text: string; raw?: string; words: Word[] };
/** The transcript workflow: Whisper's draft, then Claude + darijadz corrects it and darija_lint checks it. */
export type DarijaState = "none" | "whisper" | "corrected";
export type TranscriptInfo = {
  state: DarijaState;
  unsure: string[];
  lint_high: number;
  lint: number;
  changed: number;
  segments: number;
  dropped: number;
  notes: { id: number; note: string }[];
  files: { txt?: string; srt?: string; doc?: string };
};

export type Scan = {
  key: string;
  fps: number;
  frames: number;
  duration: number;
  flashes: { f0: number; f1: number; t0: number; t1: number; peak_luma: number; kind: string; white: boolean; in_hook_window: boolean }[];
  cuts: { f: number; t: number; diff: number }[];
  black: { f0: number; f1: number; t0: number; t1: number }[];
  silences: { a: number; b: number; dur: number; quietest: number; db: number }[];
  titles: [number, number, number, number, number, number, string][];
  sheet: { file: string; fps: number; cols: number; tile: [number, number]; count: number };
};

export type Curves = { fps: number; luma: number[]; diff: number[]; rms_db: number[]; rms_hop: number };

export type SourceData = { key: string; state: SourceState; words: Segment[]; transcript?: TranscriptInfo; scan: Scan | null; curves: Curves | null; prepare: any };

export type Busy = { a: number; b: number; side: "L" | "R" | "T" | "both" | "full"; what: string };
export type Defect = { kind: string; a: number | null; b: number | null; note: string };
export type Line = { a0: number; a1: number; v0: number | null; v1: number | null; role: "hook" | "body" | "cta"; text: string; said?: string; can_open_body: boolean; note: string };
export type SourceAnalysis = {
  label: string;
  summary: string;
  hook_end: number;
  hook_flash: { f0: number; f1: number; white: boolean } | null;
  hook_hold: number | null;
  hook_kind: string;
  hook_needs_payoff: boolean;
  body_start: number;
  cta_start: number | null;
  offer_group: string;
  shoot: string;
  busy: Busy[];
  defects: Defect[];
  lines: Line[];
  notes: string;
  edited: string[];
};
export type Liftable = { id: string; src: string; a0: number; a1: number; v0: number | null; v1: number | null; kind: string; label: string; text: string; said?: string; why: string };

export type PSeg = { src: string; a0: number; a1: number; v0: number | null; v1: number | null; said: string; note: string; text?: string };
export type Graphic = { on: string; kind: "disc" | "pack" | "offer" | "library" | "missing"; what: string; label: string; existing: boolean };
export type Cutout = { src: string; f0: number; f1: number; frames: number; seconds: number; eta_s: number };
export type Proposal = {
  id: string;
  name: string;
  label: string;
  file_name: string;
  segs: PSeg[];
  body: number[];
  cta: number | null;
  hook_beats: boolean;
  angle: string;
  why: string;
  risks: string[];
  graphics: Graphic[];
  status: "proposed" | "rejected" | "accepted";
  picked: boolean;
  reject_reason: string;
  edited: boolean;
  round: number;
  round_note: string;
  proposed_at: string;
  duration: number;
  new_cutouts: Cutout[];
  cutout_eta_s: number;
  checks: string[];
  exists: { id: string; name: string } | null;
  built: boolean;
};
export type ProposalList = { ads: Proposal[]; next_mix: number; gpt_cap: number };
export type Analysis = {
  version: number;
  sources: Record<string, SourceAnalysis>;
  offer_groups: { id: string; label: string; sources: string[] }[];
  duplicates: { sources: string[]; note: string }[];
  liftable: Liftable[];
  notes: string;
};

export type Job = {
  id: number;
  slug: string;
  queue: "heavy" | "claude" | "light";
  kind: string;
  title: string;
  status: "queued" | "running" | "cancelling" | "done" | "failed" | "cancelled" | "interrupted" | "skipped";
  depends_on: number | null;
  grp: string | null;
  created: number;
  started: number | null;
  finished: number | null;
  progress: number | null;
  eta_s: number | null;
  error: string | null;
  result: any;
};
export type LogLine = { seq: number; ts: number; kind: string; text: string };

// ---- BluxTech Studio additions

/** desktop/supabase.config.json: the project URL and its publishable (anon) key, both public. */
export type AuthCfg = { url: string; publishableKey: string };
export type LicenseState = {
  ok: boolean;
  reason: string;
  licensing: boolean;
  device_id: string;
  grace_days: number;
  uid?: string;
  email?: string;
  plan?: string;
  status?: string;
  expires_at?: number | null;
  checked_at?: number;
  signed?: boolean;
  offline_until?: number;
};
export type AppInfo = {
  app: string;
  version: string;
  mode: "dev" | "installed";
  workspace: string;
  data: string;
  auth: AuthCfg | null;
  license: LicenseState;
  device_id: string;
  device_name: string;
  runner: "cli" | "sdk";
  tools: { claude: string | null; python: string; ffmpeg: string | null; node: string | null; hyperframes: boolean; skill: boolean };
  gpt_dir: string;
  gpt_library: boolean;
};
export type EnvItem = { id: string; label: string; ok: boolean; detail: string; required: boolean; fix: string | null };
export type EnvCheck = { ok: boolean; items: EnvItem[]; mode: string; workspace: string; runner: string; resources: string };
export type Settings = {
  runner: "cli" | "sdk";
  model: string | null;
  effort: string | null;
  max_budget_usd: number;
  max_turns: number;
  limits: { heavy: number; claude: number; light: number };
  gpt_cap: number;
  auto_render: boolean;
  has_api_key: boolean;
  api_key_source: "settings" | "env" | null;
};
export type LicensePayload = {
  uid: string;
  email: string;
  status: string;
  plan: string;
  expires_at: number | null;
  max_devices: number;
  device_id: string;
  device_name: string;
  token: string | null;
};
export type FolderEntry = { name: string; path: string; kind: "folder" | "video" | "image" | "other"; size?: number; duration?: number | null; fps?: number | null; w?: number | null; h?: number | null; audio_rate?: number | null };
export type Folder = { path: string; parent: string | null; entries: FolderEntry[] };
export type NewSource = { file: string; tag: "finished_ad" | "source" | "packshot" | "offer" | "illustration" | "ignore"; label: string; note: string };
export type NewProduct = {
  name: string;
  name_ar: string;
  whisper_prompt: string;
  product_dir: string;
  ads_dir: string;
  sources: NewSource[];
  offers: { label: string; photo: string; note: string }[];
  duplicates: string[];
  gpt_cap: number;
  name_pattern?: string;
  slug?: string | null;
};
export type BeatLine = { in: number; out: number; side: string; graphic: string; label: string; check?: string | null };
export type Report = {
  out: string;
  duration: number;
  size_mb: number;
  video: string;
  loudness_before: number;
  gain_db: number;
  loudness_after: number;
  peak_dbfs: number;
  black_frames: any[];
  render_secs: number;
  render_fps: number;
  joins: number[];
  finished_at: string;
};
export type ResultMix = MixState & {
  angle: string;
  segs: PSeg[];
  body: number[];
  cta: number | null;
  build: { built_at: string; dur: number; t_body: number; t_cta: number | null; beats: number; no_cutout: string[]; place_warnings: string[] } | null;
  check: { times: number[]; lint_exit: number; snapshot_exit: number; files: string[] } | null;
  report: Report | null;
  beats: BeatLine[];
  revision: { changed: string[]; notes: string } | null;
  gpt_drawings: { path: string; prompt: string }[];
  unsure: string[];
  snaps: string[];
  sheets: string[];
  warnings: string[];
};
export type Results = { mixes: ResultMix[]; ads_dir: string | null };
export type FreshMarks = { hook_end: number; body_start: number; cta_start: number };
export type FreshResult = {
  output: string;
  duration: number;
  loudness_after: number | null;
  peak_dbfs: number | null;
  size_mb: number | null;
  black_frames: any[];
  captions: number;
  beats: { t: number; side: string; graphic: string; words: string }[];
  library_pictures: string[];
  gpt_drawings: { path: string; prompt: string }[];
  unsure: string[];
  notes: string;
};
export type FreshProject = {
  slug: string;
  name: string;
  footage: string;
  out_dir: string | null;
  whisper_prompt: string;
  marks: FreshMarks | null;
  created: string;
  duration: number | null;
  fps: number | null;
  frames: number | null;
  size?: string;
  dir: string;
  main: string | null;
  project: boolean;
  words: boolean;
  darija?: DarijaState;
  transcript?: TranscriptInfo;
  cutout: boolean;
  sheet: boolean;
  final_sheet: boolean;
  result: FreshResult | null;
  ad: boolean;
  ad_path: string | null;
  out_path: string;
  session_id: string | null;
  usage: Usage;
  snaps: string[];
  finished?: boolean;
  words_data?: Segment[];
  error?: string;
};
export type LibraryAsset = {
  id: string;
  file: string;
  look: string;
  source: string;
  subject: string;
  prompt?: string;
  label?: string;
  motion?: string;
  keywords?: { darija?: string[]; ar?: string[]; fr?: string[]; en?: string[] };
};
export type Library = { dir: string; updated: string | null; assets: LibraryAsset[]; exists: boolean };

async function req<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, init);
  if (!r.ok) {
    let msg = `${r.status} ${r.statusText}`;
    try {
      const j = await r.json();
      if (j?.detail) msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch {
      /* not JSON */
    }
    throw new Error(msg);
  }
  return r.json();
}

const json = (method: string, body: unknown): RequestInit => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
const q = (s: string) => encodeURIComponent(s);

export const api = {
  app: () => req<AppInfo>("/api/app"),
  license: () => req<LicenseState>("/api/license"),
  postLicense: (p: LicensePayload) => req<LicenseState>("/api/license", json("POST", p)),
  deleteLicense: () => req<LicenseState>("/api/license", { method: "DELETE" }),
  settings: () => req<Settings>("/api/settings"),
  saveSettings: (patch: Partial<Omit<Settings, "has_api_key" | "api_key_source">>) => req<Settings>("/api/settings", json("PUT", patch)),
  setApiKey: (key: string) => req<Settings>("/api/settings/apikey", json("POST", { key })),
  environment: () => req<EnvCheck>("/api/environment"),
  setup: () => req<{ jobs: Job[] }>("/api/environment/setup", { method: "POST" }),
  folder: (path: string) => req<Folder>(`/api/folder?path=${q(path)}`),
  reveal: (path: string) => req<{ ok: boolean }>("/api/reveal", json("POST", { path })),

  products: () => req<ProductCard[]>("/api/products"),
  createProduct: (spec: NewProduct) => req<{ slug: string; jobs: Job[] }>("/api/products", json("POST", spec)),
  product: (slug: string) => req<ProductDetail>(`/api/products/${slug}`),
  source: (slug: string, key: string) => req<SourceData>(`/api/products/${slug}/sources/${key}`),
  analysis: (slug: string) => req<Analysis | null>(`/api/products/${slug}/analysis`),
  saveAnalysis: (slug: string, a: Analysis) => req<Analysis>(`/api/products/${slug}/analysis`, json("PUT", a)),
  run: (slug: string, step: string, opts: { keys?: string[]; force?: boolean } = {}) =>
    req<{ jobs: Job[]; note?: string }>(`/api/products/${slug}/run`, json("POST", { step, ...opts })),
  amend: (slug: string, feedback: string) => req<{ jobs: Job[] }>(`/api/products/${slug}/amend`, json("POST", { feedback })),
  proposals: (slug: string) => req<ProposalList>(`/api/products/${slug}/proposals`),
  propose: (slug: string, count: number, note: string) => req<{ jobs: Job[] }>(`/api/products/${slug}/propose`, json("POST", { count, note })),
  patchProposal: (slug: string, id: string, patch: Record<string, unknown>) => req<Proposal>(`/api/products/${slug}/proposals/${id}`, json("PATCH", patch)),
  build: (slug: string, ids: string[], render: boolean, gpt_cap?: number) => req<{ mixes: string[]; jobs: Job[] }>(`/api/products/${slug}/build`, json("POST", { ids, render, gpt_cap })),
  render: (slug: string, ids: string[], replace = false) => req<{ jobs: Job[] }>(`/api/products/${slug}/render`, json("POST", { ids, replace })),
  fix: (slug: string, id: string, note = "") => req<{ jobs: Job[] }>(`/api/products/${slug}/fix`, json("POST", { id, note })),
  revise: (slug: string, id: string, feedback: string) => req<{ jobs: Job[] }>(`/api/products/${slug}/revise`, json("POST", { id, feedback })),
  results: (slug: string) => req<Results>(`/api/products/${slug}/results`),

  freshList: () => req<FreshProject[]>("/api/fresh"),
  freshCreate: (body: { footage: string; name?: string; out_dir?: string; whisper_prompt?: string; slug?: string }) =>
    req<{ slug: string; fresh: FreshProject; jobs: Job[] }>("/api/fresh", json("POST", body)),
  fresh: (slug: string) => req<FreshProject>(`/api/fresh/${slug}`),
  freshMarks: (slug: string, m: FreshMarks) => req<FreshProject>(`/api/fresh/${slug}/marks`, json("PUT", m)),
  freshRun: (slug: string, gpt_cap?: number) => req<{ jobs: Job[] }>(`/api/fresh/${slug}/run`, json("POST", { gpt_cap })),
  freshCutout: (slug: string) => req<{ jobs: Job[] }>(`/api/fresh/${slug}/cutout`, { method: "POST" }),
  freshDarija: (slug: string) => req<{ jobs: Job[] }>(`/api/fresh/${slug}/darija`, { method: "POST" }),

  library: () => req<Library>("/api/library"),
  librarySearch: (text: string) => req<{ q: string; output: string }>(`/api/library/search?q=${q(text)}`),
  gptStatus: () => req<Record<string, any>>("/api/library/gpt-status"),

  jobs: (slug?: string) => req<Job[]>(`/api/jobs${slug ? `?slug=${slug}` : ""}`),
  cancel: (id: number) => req<Job>(`/api/jobs/${id}/cancel`, { method: "POST" }),
};

export const thumbUrl = (path: string, w = 96) => `/media/thumb?path=${q(path)}&w=${w}`;

export const FPS = 30;
export const snap = (t: number) => Math.round(Math.round(t * FPS) / FPS * 10000) / 10000;
export const frameOf = (t: number) => Math.round(t * FPS);
export const fmt = (t: number | null | undefined, d = 2) => (t == null ? "–" : t.toFixed(d));
export function clock(s: number) {
  s = Math.max(0, Math.round(s));
  const m = Math.floor(s / 60);
  return m ? `${m} min ${String(s % 60).padStart(2, "0")} s` : `${s} s`;
}
export const basename = (p: string | null | undefined) => (p ?? "").split(/[\\/]/).pop() ?? "";
export const errText = (e: unknown) => (e instanceof Error ? e.message : String(e));
