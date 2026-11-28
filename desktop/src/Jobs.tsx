import { useEffect, useRef, useState } from "react";
import { api, clock, type Job, type LogLine } from "./api";
import { Icon } from "./icons";
import { Button, Card, cx, Dot, Glass, Progress, Toolbar, type Tone } from "./ui";

const ACTIVE = ["queued", "running", "cancelling"];
export const isActive = (j: Job) => ACTIVE.includes(j.status);

/** Jobs, polled while the tab is visible. Logs come over SSE in <LogView>. */
export function useJobs(slug?: string) {
  const [jobs, setJobs] = useState<Job[]>([]);
  useEffect(() => {
    let alive = true;
    const load = () => {
      if (document.hidden) return;
      api.jobs(slug).then((j) => alive && setJobs(j)).catch(() => {});
    };
    load();
    const id = setInterval(load, 1500);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [slug]);
  return jobs;
}

/** Run `fn` each time one of these jobs ends: what it wrote is on disk, so read it again. */
export function useOnJobEnd(jobs: Job[], fn: () => void) {
  const ended = jobs.filter((j) => !isActive(j)).map((j) => `${j.id}${j.status}`).join(",");
  const first = useRef(true);
  const cb = useRef(fn);
  cb.current = fn;
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    cb.current();
  }, [ended]);
}

function useNow(on: boolean) {
  const [now, setNow] = useState(Date.now() / 1000);
  useEffect(() => {
    if (!on) return;
    const id = setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => clearInterval(id);
  }, [on]);
  return now;
}

export const jobTone = (s: Job["status"]): Tone => (s === "done" ? "ok" : s === "running" ? "info" : s === "failed" ? "bad" : s === "queued" ? "neutral" : "warn");

/** How far along a running job is, from its ETA (the engine reports no progress of its own). */
function fraction(job: Job, now: number) {
  if (job.status !== "running" || !job.started) return job.status === "done" ? 1 : 0;
  if (!job.eta_s) return null;
  return Math.min(0.97, Math.max(0.02, (now - job.started) / job.eta_s));
}

export function JobTiming({ job }: { job: Job }) {
  const now = useNow(job.status === "running");
  if (job.status === "queued") return <span>waiting{job.eta_s ? `, about ${clock(job.eta_s)} once it starts` : ""}</span>;
  if (!job.started) return null;
  const ran = (job.finished ?? now) - job.started;
  if (job.status !== "running") return <span>{clock(ran)}</span>;
  const left = job.eta_s ? job.eta_s - ran : null;
  return (
    <span>
      {clock(ran)}
      {left != null && (left > 5 ? `, about ${clock(left)} left` : ", almost done")}
    </span>
  );
}

/** Where a task stands, in plain words. */
export function jobNote(job: Job, now: number): string {
  if (job.status === "queued") return "Waiting to start";
  if (job.status === "cancelling") return "Stopping";
  if (job.status === "running") {
    if (!job.started) return "Starting";
    const ran = now - job.started;
    const left = job.eta_s ? job.eta_s - ran : null;
    return left == null ? `Working, ${clock(ran)} so far` : left > 5 ? `About ${clock(left)} left` : "Almost done";
  }
  const words: Record<string, string> = { done: "Done", failed: "Failed", cancelled: "Cancelled", interrupted: "Interrupted", skipped: "Skipped" };
  const word = words[job.status] ?? job.status;
  return job.started && job.finished ? `${word} · ${clock(job.finished - job.started)}` : word;
}

/** A circular progress ring. Spins when the job has no ETA. */
export function Ring({ value, size = 18, className }: { value: number | null; size?: number; className?: string }) {
  const r = (size - 3) / 2;
  const c = 2 * Math.PI * r;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className={cx(value == null && "spin-slow", className)} aria-hidden="true">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="currentColor" strokeOpacity="0.22" strokeWidth="2.2" />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeDasharray={`${(value ?? 0.28) * c} ${c}`}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
        style={{ transition: "stroke-dasharray .8s linear" }}
      />
    </svg>
  );
}

/** The rows a page shows for each of its running jobs. */
export function ActiveJobs({ jobs, openJob }: { jobs: Job[]; openJob: (id: number) => void }) {
  const now = useNow(jobs.length > 0);
  if (!jobs.length) return null;
  return (
    <div className="space-y-2">
      {jobs.map((j) => (
        <Card key={j.id} className="flex items-center gap-3 px-4 py-2.5">
          <div className="min-w-0 flex-1">
            <div className="flex items-center justify-between gap-3">
              <span className="truncate text-[13px] font-medium">{j.title}</span>
              <span className="num shrink-0 text-[12px] text-ink-3">{jobNote(j, now)}</span>
            </div>
            <Progress value={fraction(j, now)} className="mt-2" />
          </div>
          <Button small onClick={() => openJob(j.id)}>
            Log
          </Button>
          <Button small variant="danger" onClick={() => api.cancel(j.id).catch(() => {})}>
            Cancel
          </Button>
        </Card>
      ))}
    </div>
  );
}

/** The Activity panel of the Projects screen: what is running now, in plain words, and what just finished. */
export function ActivityPanel({ jobs, openJob, className }: { jobs: Job[]; openJob: (id: number) => void; className?: string }) {
  const active = jobs.filter(isActive);
  const recent = jobs.filter((j) => !isActive(j)).slice(0, 4);
  const now = useNow(active.length > 0);
  return (
    <Glass className={cx("flex flex-col overflow-hidden", className)}>
      <div className="flex items-center justify-between px-5 pt-4 pb-2">
        <div className="text-[13px] font-semibold">Activity</div>
        <span className="num text-[12px] text-ink-3">{active.length ? `${active.length} running` : "Idle"}</span>
      </div>
      <div className="min-h-0 flex-1 overflow-auto px-2 pb-2">
        {jobs.length === 0 && <div className="px-3 py-6 text-center text-[12.5px] text-ink-4">Nothing has run yet.</div>}
        {active.map((j) => (
          <button key={j.id} type="button" onClick={() => openJob(j.id)} className="press block w-full rounded-[14px] px-3 py-2.5 text-left hover:bg-hover">
            <div className="truncate text-[12.5px] font-medium">{j.title}</div>
            <div className="num mt-0.5 text-[12px] text-ink-3">{jobNote(j, now)}</div>
            <Progress value={fraction(j, now)} className="mt-2" />
          </button>
        ))}
        {recent.length > 0 && active.length > 0 && <div className="px-3 pt-3 pb-1 text-[11px] font-medium text-ink-4">Earlier</div>}
        {recent.map((j) => (
          <button key={j.id} type="button" onClick={() => openJob(j.id)} className="press flex w-full items-center gap-2.5 rounded-[14px] px-3 py-2 text-left hover:bg-hover">
            <Dot tone={jobTone(j.status)} />
            <span className="min-w-0 flex-1 truncate text-[12.5px] text-ink-2">{j.title}</span>
            <span className="num shrink-0 text-[11.5px] text-ink-4">{jobNote(j, now)}</span>
          </button>
        ))}
      </div>
      <a href="#/jobs" className="press m-2 rounded-[14px] px-3 py-2 text-center text-[12.5px] font-medium text-accent-text hover:bg-hover">
        All jobs
      </a>
    </Glass>
  );
}

export function JobRow({ job, selected, onSelect }: { job: Job; selected?: boolean; onSelect?: () => void }) {
  const now = useNow(job.status === "running");
  return (
    <button type="button" onClick={onSelect} className={cx("press flex w-full items-center gap-3 rounded-[14px] px-3 py-2.5 text-left", selected ? "glass-active" : "hover:bg-hover")}>
      {job.status === "running" ? <Ring value={fraction(job, now)} size={16} className="shrink-0 text-info" /> : (
        <span className="grid w-4 shrink-0 place-items-center">
          <Dot tone={jobTone(job.status)} />
        </span>
      )}
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[13px] font-medium">{job.title}</span>
        <span className="num block truncate text-[11.5px] text-ink-3">
          {job.slug} · {jobNote(job, now)}
        </span>
      </span>
    </button>
  );
}

const kindClass: Record<string, string> = {
  sys: "text-ink-3",
  out: "text-ink-2",
  claude: "text-ink",
  tool: "text-info",
  result: "text-ink-3",
  error: "text-bad",
  usage: "text-ok",
  prompt: "text-ink-3",
};
const kindTag: Record<string, string> = { claude: "Claude", tool: "tool", result: "  ↳", error: "error", usage: "usage", prompt: "prompt", sys: "app", out: "" };

/** Live log of one job: every line already stored, then new ones as the server writes them. */
export function LogView({ job }: { job: Job }) {
  const [lines, setLines] = useState<LogLine[]>([]);
  const [openPrompt, setOpenPrompt] = useState<number | null>(null);
  const box = useRef<HTMLDivElement>(null);
  const stick = useRef(true);

  useEffect(() => {
    setLines([]);
    const es = new EventSource(`/api/jobs/${job.id}/stream`);
    es.onmessage = (e) => setLines((l) => [...l, JSON.parse(e.data)]);
    es.addEventListener("end", () => es.close());
    es.onerror = () => es.close();
    return () => es.close();
  }, [job.id]);

  useEffect(() => {
    const el = box.current;
    if (el && stick.current) el.scrollTop = el.scrollHeight;
  }, [lines]);

  return (
    <div
      ref={box}
      onScroll={(e) => {
        const el = e.currentTarget;
        stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
      }}
      className="tc h-full overflow-auto bg-well px-4 py-3 text-[11.5px] leading-[1.6]"
    >
      {lines.length === 0 && <div className="text-ink-3">no output yet</div>}
      {lines.map((l) => {
        const long = l.kind === "prompt" && l.text.length > 300;
        const shown = long && openPrompt !== l.seq ? l.text.slice(0, 300) + " …" : l.text;
        return (
          <div key={l.seq} className={cx("flex gap-2", kindClass[l.kind] ?? "text-ink-2")}>
            <span className="w-12 shrink-0 text-right text-ink-3 select-none">{kindTag[l.kind] ?? l.kind}</span>
            <span dir="auto" className="min-w-0 flex-1 break-words whitespace-pre-wrap">
              {shown}
              {long && (
                <button type="button" className="ml-2 text-accent-text underline" onClick={() => setOpenPrompt(openPrompt === l.seq ? null : l.seq)}>
                  {openPrompt === l.seq ? "less" : "whole prompt"}
                </button>
              )}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/** The Jobs screen: every task on the left, the selected one's live log on the right. */
export function JobsPage({ jobs, focus }: { jobs: Job[]; focus: number | null }) {
  const [sel, setSel] = useState<number | null>(focus);
  useEffect(() => {
    if (focus != null) setSel(focus);
  }, [focus]);
  const job = jobs.find((j) => j.id === sel) ?? jobs.find(isActive) ?? jobs[0];
  const running = jobs.filter(isActive).length;
  const now = useNow(running > 0);
  return (
    <div className="flex h-full min-h-0 flex-col">
      <Toolbar title="Jobs" sub={running ? `${running} running · ${jobs.length} in the log` : `${jobs.length} in the log`} />
      <div className="grid min-h-0 flex-1 grid-cols-[340px_minmax(0,1fr)] gap-[10px]">
        <Card className="min-h-0 overflow-auto p-2">
          {jobs.length === 0 && <div className="p-4 text-ink-3">Nothing has run yet.</div>}
          {jobs.map((j) => (
            <JobRow key={j.id} job={j} selected={job?.id === j.id} onSelect={() => setSel(j.id)} />
          ))}
        </Card>
        <Card className="flex min-h-0 flex-col overflow-hidden">
          {job ? (
            <>
              <div className="flex items-center gap-3 px-5 py-3">
                <Dot tone={jobTone(job.status)} pulse={job.status === "running"} />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-[14px] font-semibold">{job.title}</div>
                  <div className="num text-[12px] text-ink-3">
                    {job.slug} · {job.queue} · {jobNote(job, now)}
                  </div>
                </div>
                {isActive(job) && (
                  <Button small variant="danger" onClick={() => api.cancel(job.id).catch(() => {})}>
                    Cancel
                  </Button>
                )}
              </div>
              {job.status === "running" && <Progress value={fraction(job, now)} className="mx-5 mb-3" />}
              {job.error && <div className="mx-5 mb-3 rounded-[14px] bg-bad-soft px-3 py-2 text-[12.5px] whitespace-pre-wrap text-bad">{job.error}</div>}
              <div className="min-h-0 flex-1 border-t border-line">
                <LogView job={job} />
              </div>
            </>
          ) : (
            <div className="flex flex-1 flex-col items-center justify-center gap-2 p-6 text-ink-3">
              <Icon name="render" size={24} className="text-ink-4" />
              Pick a task to see its log.
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
