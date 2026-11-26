import { useCallback, useEffect, useState } from "react";
import { api, errText, type EnvCheck, type Job } from "./api";
import { useDevMode } from "./devmode";
import { isActive, LogView, useJobs, useOnJobEnd } from "./Jobs";
import { allReady, readiness } from "./readiness";
import { Button, Card, Chip, cx, Dot, ErrorNote, field, Loading, PageHeader } from "./ui";

/** The system readiness panel, with the setup job that fetches what a download can fetch. Technical details
 *  (file locations, the raw check) only in developer mode. */
export default function Setup({ onDone, embedded }: { onDone?: () => void; embedded?: boolean }) {
  const [env, setEnv] = useState<EnvCheck | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [dev] = useDevMode();
  const jobs = useJobs("-");
  const load = useCallback(() => api.environment().then(setEnv).catch((e) => setErr(errText(e))), []);
  useEffect(() => {
    load();
  }, [load]);
  useOnJobEnd(jobs, load);
  const live = job ? (jobs.find((j) => j.id === job.id) ?? job) : (jobs.find((j) => j.kind === "setup") ?? null);
  const running = !!live && isActive(live);
  const fixable = env?.items.some((i) => !i.ok && i.fix === "setup");
  const ready = !!env && allReady(env);
  const rows = env ? readiness(env) : [];

  const run = () =>
    api
      .setup()
      .then((r) => setJob(r.jobs[0]))
      .catch((e) => setErr(errText(e)));

  // the API-key runner with no key yet: the one thing here a download cannot fix
  const [key, setKey] = useState("");
  const [keyBusy, setKeyBusy] = useState(false);
  const needsKey = !!env && env.runner === "sdk" && env.items.some((i) => i.id === "claude" && !i.ok);
  const saveKey = () => {
    setKeyBusy(true);
    api
      .setApiKey(key.trim())
      .then(() => {
        setKey("");
        load();
      })
      .catch((e) => setErr(errText(e)))
      .finally(() => setKeyBusy(false));
  };

  return (
    <div className={embedded ? "" : "mx-auto min-h-full max-w-[760px] p-6"}>
      {!embedded && (
        <PageHeader
          icon="gear"
          title="Set up this PC"
          sub="BluxTech Studio produces the ads on this machine. The first start fetches a few large pieces once; after that only the Claude calls leave this PC."
        />
      )}
      {err && <ErrorNote>{err}</ErrorNote>}
      <Card>
        {!env && <Loading>Checking this PC…</Loading>}
        {rows.map((r) => (
          <div key={r.id} className="flex items-start gap-3 border-b border-line px-4 py-2.5 last:border-b-0">
            <Dot tone={r.tone} />
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-3">
                <span className="font-medium">{r.label}</span>
                <span className={cx("shrink-0 text-[12px] font-medium", r.tone === "ok" ? "text-ok" : r.tone === "bad" ? "text-bad" : "text-warn")}>{r.status}</span>
              </div>
              {r.hint && <div className="mt-0.5 text-[12px] leading-snug text-ink-3">{r.hint}</div>}
            </div>
          </div>
        ))}
      </Card>
      {needsKey && (
        <Card className="mt-3 p-4">
          <div className="font-medium">Anthropic API key</div>
          <div className="mt-0.5 text-[12.5px] text-ink-3">The editing steps run on Claude through your own key (console.anthropic.com → API keys). It is stored encrypted on this computer and never shown again.</div>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <input
              type="password"
              placeholder="sk-ant-…"
              value={key}
              onChange={(e) => setKey(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && key.trim() && saveKey()}
              className={cx(field, "h-[28px] w-[360px]")}
              aria-label="Anthropic API key"
            />
            <Button variant="primary" small onClick={saveKey} disabled={keyBusy || !key.trim()}>
              {keyBusy ? "Saving…" : "Save key"}
            </Button>
          </div>
        </Card>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Button onClick={load} icon="refresh">
          Check again
        </Button>
        {fixable && (
          <Button variant="primary" onClick={run} disabled={running}>
            {running ? "Setting up…" : "Run setup"}
          </Button>
        )}
        {onDone && (
          <Button variant={ready ? "primary" : "default"} onClick={onDone} disabled={!env}>
            {ready ? "Continue" : "Continue anyway"}
          </Button>
        )}
        {env && !fixable && ready && <Chip tone="ok">everything is in place</Chip>}
      </div>
      {dev && env && (
        <Card className="mt-3">
          <div className="border-b border-line px-4 py-1.5 text-[10.5px] font-semibold tracking-[0.06em] text-ink-3 uppercase">Developer details</div>
          {env.items.map((i) => (
            <div key={i.id} className="flex items-start gap-3 border-b border-line px-4 py-2 last:border-b-0">
              <Dot tone={i.ok ? "ok" : i.required ? "bad" : "warn"} />
              <div className="min-w-0 flex-1">
                <div className="text-[12.5px] font-medium">
                  {i.label} <span className="font-mono text-[11px] text-ink-3">{i.id}</span>
                </div>
                <div className="truncate font-mono text-[11.5px] text-ink-3" title={i.detail}>
                  {i.detail}
                </div>
              </div>
            </div>
          ))}
          <div className="px-4 py-2 font-mono text-[11.5px] text-ink-3">
            workspace {env.workspace} · mode {env.mode} · runner {env.runner}
            {env.resources && <> · resources {env.resources}</>}
          </div>
        </Card>
      )}
      {live && (
        <Card className="mt-3 h-[260px] overflow-hidden">
          <div className="flex items-center gap-2 border-b border-line px-3 py-1.5 text-[12.5px]">
            <Chip tone={live.status === "done" ? "ok" : live.status === "failed" ? "bad" : "accent"}>{live.status}</Chip>
            {live.title}
            {live.error && <span className="text-bad">{live.error}</span>}
          </div>
          <div className="h-[220px]">
            <LogView job={live} />
          </div>
        </Card>
      )}
    </div>
  );
}
