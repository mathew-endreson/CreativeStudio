import { useCallback, useEffect, useState } from "react";
import { api, errText, type EnvCheck, type Job } from "./api";
import { isActive, LogView, useJobs, useOnJobEnd } from "./Jobs";
import { Button, Card, Chip, Dot, ErrorNote, PageHeader } from "./ui";

/** The environment check, with the setup job that fixes what a download can fix. */
export default function Setup({ onDone, embedded }: { onDone?: () => void; embedded?: boolean }) {
  const [env, setEnv] = useState<EnvCheck | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const jobs = useJobs("-");
  const load = useCallback(() => api.environment().then(setEnv).catch((e) => setErr(errText(e))), []);
  useEffect(() => {
    load();
  }, [load]);
  useOnJobEnd(jobs, load);
  const live = job ? jobs.find((j) => j.id === job.id) ?? job : jobs.find((j) => j.kind === "setup") ?? null;
  const running = !!live && isActive(live);
  const fixable = env?.items.some((i) => !i.ok && i.fix === "setup");
  const requiredOk = !!env && env.items.filter((i) => i.required).every((i) => i.ok);

  const run = () =>
    api
      .setup()
      .then((r) => setJob(r.jobs[0]))
      .catch((e) => setErr(errText(e)));

  // the API-key runner with no key yet: the one thing on this screen a download cannot fix
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
    <div className={embedded ? "" : "mx-auto min-h-full max-w-[900px] bg-bg p-6"}>
      {!embedded && <PageHeader icon="gear" title="Set up this PC" sub="BluxTech Studio renders on this machine. Everything below must be in place once; the big downloads (Whisper model, HyperFrames) happen here." />}
      {err && <ErrorNote>{err}</ErrorNote>}
      <Card>
        {!env && <div className="p-4 text-ink-3">Checking…</div>}
        {env?.items.map((i) => (
          <div key={i.id} className="flex items-start gap-3 border-b border-line px-4 py-2.5 last:border-b-0">
            <span className="mt-0.5 flex w-[78px] shrink-0 items-center gap-1.5 text-[11.5px] font-medium">
              <Dot tone={i.ok ? "ok" : i.required ? "bad" : "warn"} />
              <span className={i.ok ? "text-ok" : i.required ? "text-bad" : "text-warn"}>{i.ok ? "ready" : i.required ? "missing" : "optional"}</span>
            </span>
            <div className="min-w-0 flex-1">
              <div className="font-medium">{i.label}</div>
              <div className="truncate text-[12.5px] text-ink-3" title={i.detail}>
                {i.detail}
              </div>
            </div>
          </div>
        ))}
      </Card>
      {needsKey && (
        <Card className="mt-3 p-4">
          <div className="font-medium">Anthropic API key</div>
          <div className="mt-0.5 text-[12.5px] text-ink-3">
            The editing steps run on Claude through your own API key (console.anthropic.com → API keys). It is stored sealed to this Windows user and never shown again.
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <input
              type="password"
              placeholder="sk-ant-…"
              value={key}
              onChange={(e) => setKey(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && key.trim() && saveKey()}
              className="h-[28px] w-[360px] rounded-[5px] border border-line bg-well px-2 text-[13px] shadow-[inset_0_1px_2px_rgb(0_0_0/0.25)] focus:border-accent focus:outline-none"
            />
            <Button variant="primary" small onClick={saveKey} disabled={keyBusy || !key.trim()}>
              {keyBusy ? "Saving…" : "Save key"}
            </Button>
          </div>
        </Card>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Button onClick={load}>Check again</Button>
        {fixable && (
          <Button variant="primary" onClick={run} disabled={running}>
            {running ? "Setting up…" : "Run setup"}
          </Button>
        )}
        {onDone && (
          <Button variant={requiredOk ? "primary" : "default"} onClick={onDone} disabled={!env}>
            {requiredOk ? "Continue" : "Continue anyway"}
          </Button>
        )}
        {env && <span className="text-[12.5px] text-ink-3">Workspace: <code>{env.workspace}</code></span>}
      </div>
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
