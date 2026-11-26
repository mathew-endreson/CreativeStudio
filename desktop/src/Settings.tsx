import { useEffect, useState, type ReactNode } from "react";
import { api, errText, type AppInfo, type Settings as SettingsT } from "./api";
import { authError, deactivate, signOut } from "./auth";
import Setup from "./Setup";
import { Button, Card, Chip, ErrorNote, PageHeader } from "./ui";

function Row({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[220px_1fr] items-start gap-4 border-b border-line px-4 py-2.5 last:border-b-0">
      <div>
        <div className="font-medium">{label}</div>
        {hint && <div className="text-[12px] leading-snug text-ink-3">{hint}</div>}
      </div>
      <div className="min-w-0">{children}</div>
    </div>
  );
}

const input = "h-[28px] rounded-[5px] border border-line bg-well shadow-[inset_0_1px_2px_rgb(0_0_0/0.25)] focus:border-accent focus:outline-none px-2 text-[13px]";

export default function Settings({ info, reloadApp }: { info: AppInfo; reloadApp: () => void }) {
  const [s, setS] = useState<SettingsT | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [key, setKey] = useState("");
  const [saved, setSaved] = useState<string | null>(null);
  useEffect(() => {
    api.settings().then(setS).catch((e) => setErr(errText(e)));
  }, []);
  const save = (patch: Partial<SettingsT>) =>
    api
      .saveSettings(patch as any)
      .then((x) => {
        setS(x);
        setSaved(Object.keys(patch).join(", "));
        setTimeout(() => setSaved(null), 1500);
        reloadApp();
      })
      .catch((e) => setErr(errText(e)));
  if (!s) return <div className="text-ink-3">Loading…</div>;
  const lic = info.license;

  return (
    <div className="mx-auto max-w-[980px] space-y-4">
      <PageHeader icon="gear" title="Settings" sub="How Claude runs, how many jobs run at once, and where things are." actions={saved && <Chip tone="ok">saved {saved}</Chip>} />
      {err && <ErrorNote>{err}</ErrorNote>}

      <Card>
        <div className="border-b border-line bg-surface-2/60 px-4 py-1.5 text-[10.5px] font-semibold tracking-[0.06em] text-ink-3 uppercase">Claude</div>
        <Row label="Runner" hint="Who makes the Claude calls for the judgment steps.">
          <label className="flex items-start gap-2 py-1">
            <input type="radio" checked={s.runner === "sdk"} onChange={() => save({ runner: "sdk" })} />
            <span>
              <b>API key</b> — the bundled Claude Agent runtime with your Anthropic API key. Works on any PC; billed to the key.
            </span>
          </label>
          <label className="flex items-start gap-2 py-1">
            <input type="radio" checked={s.runner === "cli"} onChange={() => save({ runner: "cli" })} />
            <span>
              <b>Claude Code login</b> — the <code>claude</code> CLI installed on this PC and its own login. For the owner's machine only.
              {!info.tools.claude && <span className="text-bad"> (not found on this PC)</span>}
            </span>
          </label>
        </Row>
        <Row label="Anthropic API key" hint="Stored sealed to this Windows user (DPAPI). Never shown again.">
          <div className="flex flex-wrap items-center gap-2">
            <Chip tone={s.has_api_key ? "ok" : "warn"}>{s.has_api_key ? `key set (${s.api_key_source})` : "no key"}</Chip>
            <input type="password" placeholder="sk-ant-…" value={key} onChange={(e) => setKey(e.target.value)} className={`${input} w-[320px]`} />
            <Button small onClick={() => api.setApiKey(key).then((x) => { setS(x); setKey(""); reloadApp(); }).catch((e) => setErr(errText(e)))} disabled={!key}>
              Save key
            </Button>
            {s.api_key_source === "settings" && (
              <Button small variant="danger" onClick={() => api.setApiKey("").then((x) => { setS(x); reloadApp(); })}>
                Remove
              </Button>
            )}
          </div>
        </Row>
        <Row label="Model and effort" hint="Empty = the runtime's default.">
          <div className="flex flex-wrap items-center gap-2">
            <input className={`${input} w-[220px]`} placeholder="model (e.g. opus)" defaultValue={s.model ?? ""} onBlur={(e) => save({ model: e.target.value.trim() || null })} />
            <select className={input} value={s.effort ?? ""} onChange={(e) => save({ effort: (e.target.value || null) as any })}>
              <option value="">effort: default</option>
              {["low", "medium", "high", "xhigh", "max"].map((x) => (
                <option key={x} value={x}>
                  effort: {x}
                </option>
              ))}
            </select>
          </div>
        </Row>
        <Row label="Limits per run" hint="API-key runner: a run stops at this budget or turn count.">
          <div className="flex flex-wrap items-center gap-3">
            <label className="flex items-center gap-1">
              $<input type="number" step="0.5" min={0.5} max={50} className={`${input} w-[80px]`} defaultValue={s.max_budget_usd} onBlur={(e) => save({ max_budget_usd: Number(e.target.value) })} />
            </label>
            <label className="flex items-center gap-1">
              turns <input type="number" min={10} max={500} className={`${input} w-[80px]`} defaultValue={s.max_turns} onBlur={(e) => save({ max_turns: Number(e.target.value) })} />
            </label>
          </div>
        </Row>
      </Card>

      <Card>
        <div className="border-b border-line bg-surface-2/60 px-4 py-1.5 text-[10.5px] font-semibold tracking-[0.06em] text-ink-3 uppercase">Production</div>
        <Row label="GPT drawings per ad" hint="Each drawing spends your ChatGPT image allowance.">
          <input type="number" min={0} max={10} className={`${input} w-[80px]`} defaultValue={s.gpt_cap} onBlur={(e) => save({ gpt_cap: Number(e.target.value) })} />
        </Row>
        <Row label="Render right after the check" hint="Off: look at the snapshots first, then press Render.">
          <input type="checkbox" checked={s.auto_render} onChange={(e) => save({ auto_render: e.target.checked })} />
        </Row>
        <Row label="Jobs at once" hint="Cutouts and renders are CPU-bound: keep heavy at 1.">
          <div className="flex gap-3">
            {(["heavy", "claude", "light"] as const).map((k) => (
              <label key={k} className="flex items-center gap-1 text-[13px]">
                {k} <input type="number" min={1} max={4} className={`${input} w-[60px]`} defaultValue={s.limits[k]} onBlur={(e) => save({ limits: { ...s.limits, [k]: Number(e.target.value) } })} />
              </label>
            ))}
          </div>
        </Row>
      </Card>

      <Card>
        <div className="border-b border-line bg-surface-2/60 px-4 py-1.5 text-[10.5px] font-semibold tracking-[0.06em] text-ink-3 uppercase">This installation</div>
        <Row label="Account and license">
          {lic.licensing ? (
            <div className="flex flex-wrap items-center gap-2">
              <span>{lic.email}</span>
              <Chip tone={lic.ok ? "ok" : "bad"}>
                {lic.plan} · {lic.reason}
              </Chip>
              {lic.offline_until && <span className="text-[12px] text-ink-3">works offline until {new Date(lic.offline_until * 1000).toLocaleDateString()}</span>}
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
            <Chip>licensing off ({lic.reason})</Chip>
          )}
        </Row>
        <Row label="Version and mode">
          v{info.version} · {info.mode} · runner {info.runner}
        </Row>
        <Row label="Workspace" hint="Projects, cutouts and renders. Finished ads go to each project's own Ads folder.">
          <div className="flex items-center gap-2">
            <code className="truncate">{info.workspace}</code>
            <Button small variant="ghost" onClick={() => api.reveal(info.workspace)}>
              Open
            </Button>
          </div>
        </Row>
        <Row label="Engine data">
          <code className="truncate">{info.data}</code>
        </Row>
        <Row label="GPT asset library" hint="The ChatGPT / Codex app's folder.">
          <div className="flex items-center gap-2">
            <code className="truncate">{info.gpt_dir}</code>
            <Chip tone={info.gpt_library ? "ok" : "warn"}>{info.gpt_library ? "found" : "missing"}</Chip>
          </div>
        </Row>
      </Card>

      <Card className="p-4">
        <div className="mb-2 text-[10.5px] font-semibold tracking-[0.06em] text-ink-3 uppercase">Environment</div>
        <Setup embedded />
      </Card>
    </div>
  );
}
