import { useEffect, useState, type ReactNode } from "react";
import { api, errText, type AppInfo, type EnvCheck, type Library, type Settings as SettingsT } from "./api";
import { authError, deactivate, signOut } from "./auth";
import { PRODUCT_NAME } from "./brand";
import { useDevMode } from "./devmode";
import Setup from "./Setup";
import { Button, Card, cx, ErrorNote, field, Status, Toggle, Toolbar } from "./ui";
import Updates from "./Updates";
import type { UpdateCheck } from "./updater";

/** One group of settings: a rounded section with a title and rows, as in System Settings. */
function Section({ title, sub, children }: { title: string; sub?: string; children: ReactNode }) {
  return (
    <Card className="overflow-hidden">
      <div className="px-5 pt-4 pb-2">
        <h2 className="text-[14px] font-semibold">{title}</h2>
        {sub && <div className="mt-0.5 text-[12.5px] leading-snug text-ink-3">{sub}</div>}
      </div>
      <div className="px-2 pb-2">{children}</div>
    </Card>
  );
}

export function Row({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[240px_1fr] items-start gap-4 border-b border-line px-3 py-3 last:border-b-0">
      <div>
        <div className="text-[13px] font-medium">{label}</div>
        {hint && <div className="mt-0.5 text-[12px] leading-snug text-ink-3">{hint}</div>}
      </div>
      <div className="min-w-0">{children}</div>
    </div>
  );
}

const input = field;
const MODELS = [
  { id: "", label: "Default (recommended)" },
  { id: "opus", label: "Opus — best quality" },
  { id: "sonnet", label: "Sonnet — faster and cheaper" },
  { id: "haiku", label: "Haiku — fastest" },
];
const EFFORTS = [
  { id: "", label: "Default" },
  { id: "low", label: "Low — quick passes" },
  { id: "medium", label: "Medium" },
  { id: "high", label: "High — more careful" },
  { id: "xhigh", label: "Very high" },
  { id: "max", label: "Maximum — slowest, costs the most" },
];

export default function Settings({ info, reloadApp, update }: { info: AppInfo; reloadApp: () => void; update?: UpdateCheck | null }) {
  const [s, setS] = useState<SettingsT | null>(null);
  const [env, setEnv] = useState<EnvCheck | null>(null);
  const [lib, setLib] = useState<Library | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [key, setKey] = useState("");
  const [saved, setSaved] = useState<string | null>(null);
  const [dev, setDev] = useDevMode();
  useEffect(() => {
    api.settings().then(setS).catch((e) => setErr(errText(e)));
    api.environment().then(setEnv).catch(() => {});
    api.library().then(setLib).catch(() => {});
  }, []);
  const save = (patch: Partial<SettingsT>, what?: string) =>
    api
      .saveSettings(patch as any)
      .then((x) => {
        setS(x);
        setSaved(what ?? Object.keys(patch).join(", "));
        setTimeout(() => setSaved(null), 1500);
        reloadApp();
      })
      .catch((e) => setErr(errText(e)));
  if (!s) return <div className="p-2 text-ink-3">Loading…</div>;
  const lic = info.license;
  const codexOk = env?.items.find((i) => i.id === "codex")?.ok ?? false;
  const knownModel = MODELS.some((m) => m.id === (s.model ?? ""));
  const claudeReady = s.runner === "sdk" ? s.has_api_key : !!info.tools.claude;

  return (
    <div className="mx-auto max-w-[980px]">
      <Toolbar title="Settings" sub="How Claude works for you, what the ads use, and where your work lives.">
        {saved && <Status tone="ok">Saved {saved}</Status>}
      </Toolbar>
      {err && <ErrorNote>{err}</ErrorNote>}
      <div className="space-y-[10px]">
        {/* 1. Claude */}
        <Section title="Claude" sub="Claude plans each ad: the captions, the graphics and the timing. Every run is billed to the account chosen here.">
          <Row label="Runner" hint="Which Claude account does the work.">
            <label className="flex items-start gap-2.5 py-1">
              <input type="radio" className="mt-1" checked={s.runner === "sdk"} onChange={() => save({ runner: "sdk" }, "runner")} />
              <span>
                <span className="font-medium">Anthropic API key</span> <span className="text-[12px] text-ink-4">recommended</span>
                <span className="block text-[12px] text-ink-3">Your own Anthropic account, billed per run. Works on any PC.</span>
              </span>
            </label>
            <label className="flex items-start gap-2.5 py-1">
              <input type="radio" className="mt-1" checked={s.runner === "cli"} onChange={() => save({ runner: "cli" }, "runner")} />
              <span>
                <span className="font-medium">Claude Code login</span>
                {!info.tools.claude && <span className="ml-2 text-[12px] text-warn">not installed on this PC</span>}
                <span className="block text-[12px] text-ink-3">The Claude Code app signed in on this computer. For the owner's machine only.</span>
              </span>
            </label>
          </Row>
          <Row label="Anthropic API key" hint="Stored encrypted on this computer and never shown again. Get one at console.anthropic.com.">
            <div className="flex flex-wrap items-center gap-2">
              <Status tone={s.has_api_key ? "ok" : s.runner === "sdk" ? "warn" : "neutral"}>{s.has_api_key ? (s.api_key_source === "env" ? "A key is set on this PC" : "A key is saved") : "No key yet"}</Status>
              <input type="password" placeholder={s.has_api_key ? "Paste a new key to replace it" : "sk-ant-…"} value={key} onChange={(e) => setKey(e.target.value)} className={cx(input, "w-[320px]")} aria-label="Anthropic API key" />
              <Button
                small
                onClick={() =>
                  api
                    .setApiKey(key.trim())
                    .then((x) => {
                      setS(x);
                      setKey("");
                      setSaved("the API key");
                      setTimeout(() => setSaved(null), 1500);
                      reloadApp();
                    })
                    .catch((e) => setErr(errText(e)))
                }
                disabled={!key.trim()}
              >
                {s.has_api_key ? "Replace key" : "Save key"}
              </Button>
              {s.api_key_source === "settings" && (
                <Button
                  small
                  variant="danger"
                  onClick={() =>
                    api
                      .setApiKey("")
                      .then((x) => {
                        setS(x);
                        reloadApp();
                      })
                      .catch((e) => setErr(errText(e)))
                  }
                >
                  Remove
                </Button>
              )}
            </div>
            {!claudeReady && <div className="mt-1.5 text-[12px] text-warn">{s.runner === "sdk" ? "No edit can start until a key is saved." : "Claude Code is not installed on this PC: choose the API key runner, or install and sign in to Claude Code."}</div>}
          </Row>
          <Row label="Model" hint="Which Claude model plans the ads. The default follows the runner's current best.">
            <div className="flex flex-wrap items-center gap-2">
              <select className={input} value={knownModel ? (s.model ?? "") : "custom"} onChange={(e) => save({ model: e.target.value === "custom" ? (s.model ?? "") : e.target.value || null }, "model")}>
                {MODELS.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.label}
                  </option>
                ))}
                <option value="custom">Other (type a model name)</option>
              </select>
              {!knownModel && <input className={cx(input, "w-[240px]")} placeholder="model name" defaultValue={s.model ?? ""} onBlur={(e) => save({ model: e.target.value.trim() || null }, "model")} aria-label="Model name" />}
            </div>
          </Row>
          <Row label="Effort" hint="How hard Claude thinks at each step. Higher is slower and costs more; the default is right for most ads.">
            <select className={input} value={s.effort ?? ""} onChange={(e) => save({ effort: (e.target.value || null) as any }, "effort")}>
              {EFFORTS.map((x) => (
                <option key={x.id} value={x.id}>
                  {x.label}
                </option>
              ))}
            </select>
          </Row>
          <Row label="Spending limit per run" hint="A run stops when it reaches this amount (API key runner). A typical ad costs 3 to 5 dollars.">
            <label className="flex items-center gap-1.5">
              $<input type="number" step="0.5" min={0.5} max={50} className={cx(input, "num w-[100px]")} defaultValue={s.max_budget_usd} onBlur={(e) => save({ max_budget_usd: Number(e.target.value) }, "the spending limit")} aria-label="Spending limit per run in dollars" />
            </label>
          </Row>
          <Row label="Maximum turns per run" hint="How many steps one run may take before it stops. Raise it only if runs stop early.">
            <input type="number" min={10} max={500} className={cx(input, "num w-[100px]")} defaultValue={s.max_turns} onBlur={(e) => save({ max_turns: Number(e.target.value) }, "the turns")} aria-label="Maximum turns per run" />
          </Row>
          <Row label="Claude runs at once" hint="How many ads Claude may plan in parallel. More is faster when you build several ads; each run is billed on its own.">
            <input type="number" min={1} max={4} className={cx(input, "num w-[100px]")} defaultValue={s.limits.claude} onBlur={(e) => save({ limits: { ...s.limits, claude: Number(e.target.value) } }, "Claude runs at once")} aria-label="Claude runs at once" />
          </Row>
        </Section>

        {/* 2. GPT image generation */}
        <Section title="GPT image generation" sub="When an ad needs a picture the library does not have, GPT can draw it in the house style through your ChatGPT app.">
          <Row label="Availability" hint="Drawing needs the ChatGPT desktop app with Codex on this PC.">
            {env ? <Status tone={codexOk ? "ok" : "warn"}>{codexOk ? "Available on this PC" : "Not available on this PC: pictures come from the library and your uploads only"}</Status> : <span className="text-ink-3">Checking…</span>}
          </Row>
          <Row label="Drawings per run" hint="The most new pictures one run may ask for, and only when you tick “Draw missing pictures” on the build. Each drawing spends your ChatGPT image allowance.">
            <input type="number" min={0} max={10} className={cx(input, "num w-[100px]")} defaultValue={s.gpt_cap} onBlur={(e) => save({ gpt_cap: Number(e.target.value) }, "drawings per run")} aria-label="Drawings per run" />
          </Row>
        </Section>

        {/* 3. Production */}
        <Section title="Production" sub="What happens when an ad is built.">
          <Row label="Render right after the check" hint="On: the finished video is rendered as soon as the check passes. Off: look at the snapshots first, then press Render.">
            <Toggle on={s.auto_render} onChange={(v) => save({ auto_render: v }, "render after the check")} label="Render right after the check" />
          </Row>
          <Row label="Finished ads" hint="Where the videos go.">
            <span className="text-[13px] text-ink-2">Each project writes its finished ads to its own Ads folder; a fresh edit writes next to its footage, in Edited Ads.</span>
          </Row>
        </Section>

        {/* 4. Performance */}
        <Section title="Performance" sub="How much this PC does at once. Cut-outs and renders use every core; one at a time is right for most PCs.">
          <Row label="Cut-outs and renders at once" hint="Heavy work. Raise it only on a PC with many cores and plenty of memory.">
            <input type="number" min={1} max={4} className={cx(input, "num w-[100px]")} defaultValue={s.limits.heavy} onBlur={(e) => save({ limits: { ...s.limits, heavy: Number(e.target.value) } }, "heavy jobs at once")} aria-label="Cut-outs and renders at once" />
          </Row>
          <Row label="Light tasks at once" hint="Transcriptions, checks, picture preparation.">
            <input type="number" min={1} max={4} className={cx(input, "num w-[100px]")} defaultValue={s.limits.light} onBlur={(e) => save({ limits: { ...s.limits, light: Number(e.target.value) } }, "light jobs at once")} aria-label="Light tasks at once" />
          </Row>
        </Section>

        {/* 5. Asset library */}
        <Section title="Asset library" sub="The pictures the ads can show in front of the speaker: the house illustrations, plus the pictures you upload for each project.">
          <Row label="Illustration library" hint="The illustrations that ship with the app, matched to what the speaker says.">
            <div className="flex flex-wrap items-center gap-3">
              <Status tone={lib?.exists ? "ok" : "warn"}>{lib ? (lib.exists ? `${lib.assets.length} illustrations` : "No library on this PC") : "…"}</Status>
              <Button small icon="images" onClick={() => (location.hash = "#/library")}>
                Open Library
              </Button>
            </div>
          </Row>
          <Row label="Your own pictures" hint="Product packshots, offer photos, illustrations: PNG, WebP or JPEG. They stay with the project across updates.">
            <span className="text-[13px] text-ink-2">Upload them in a project's Pictures tab, or pick a folder of pictures when you start a fresh edit. Each picture is cut out, prepared and tagged with the words that call it.</span>
          </Row>
        </Section>

        {/* 6. Projects */}
        <Section title="Projects" sub="Projects, cut-outs and renders are kept in your Documents, outside the app, so an update never touches them.">
          <Row label="Projects folder">
            <div className="flex flex-wrap items-center gap-2">
              <Button small icon="folder" onClick={() => api.reveal(info.workspace)}>
                Open in Explorer
              </Button>
              <Button small icon="plus" onClick={() => (location.hash = "#/new")}>
                New project
              </Button>
            </div>
          </Row>
        </Section>

        {/* Updates */}
        <Section title="Updates" sub="New versions come from the release channel. The app only checks; you decide when to download and install, and a running task is never cut short.">
          <Updates version={info.version} settings={s} save={save} initial={update} />
        </Section>

        {/* 7. Application */}
        <Section title="Application">
          <Row label="Account and license">
            {lic.licensing ? (
              <div className="flex flex-wrap items-center gap-3">
                <span className="text-[13px]">{lic.email}</span>
                <Status tone={lic.ok ? "ok" : "bad"}>
                  <span className="capitalize">{lic.plan}</span> · {lic.reason === "active" ? "active" : lic.reason}
                </Status>
                {lic.offline_until && <span className="num text-[12px] text-ink-3">works offline until {new Date(lic.offline_until * 1000).toLocaleDateString()}</span>}
                <Button small variant="ghost" onClick={() => signOut().then(reloadApp)}>
                  Sign out
                </Button>
                {lic.status && (
                  <Button
                    small
                    variant="ghost"
                    onClick={() => {
                      if (!confirm("Free this device's slot on your license? You will activate it again before the next ad.")) return;
                      deactivate(info)
                        .then(reloadApp)
                        .catch((e) => setErr(authError(e)));
                    }}
                  >
                    Free this device
                  </Button>
                )}
              </div>
            ) : (
              <Status>Licensing off (development)</Status>
            )}
          </Row>
          <Row label="Version">
            <span className="num text-[13px]">
              {PRODUCT_NAME} v{info.version}
            </span>
            {info.mode === "dev" && <span className="ml-2 text-[12px] text-ink-4">development</span>}
          </Row>
          <Row label="Developer mode" hint="Shows technical details: file locations and the raw environment check.">
            <Toggle on={dev} onChange={setDev} label="Developer mode" />
          </Row>
          {dev && (
            <Row label="Locations" hint="Developer mode only.">
              <div className="space-y-0.5 font-mono text-[11.5px] text-ink-3">
                <div>workspace {info.workspace}</div>
                <div>engine data {info.data}</div>
                <div>illustration library {info.gpt_dir}</div>
                {info.tools.claude && <div>claude {info.tools.claude}</div>}
                <div>runner {info.runner} · device {info.device_id}</div>
              </div>
            </Row>
          )}
          <Row label="System readiness" hint="What this PC has in place. Run setup fetches what is missing.">
            <Setup embedded />
          </Row>
        </Section>
      </div>
    </div>
  );
}
