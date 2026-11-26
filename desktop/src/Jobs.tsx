import { useEffect, useRef, useState } from "react";
import { api, clock, type Job, type LogLine } from "./api";
import { Icon } from "./icons";
import { Button, cx, Dot } from "./ui";

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

const tone = (s: Job["status"]) =>
  s === "done" ? "ok" : s === "running" ? "accent" : s === "failed" ? "bad" : s === "queued" ? "neutral" : "warn";

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

/** A circular progress ring: Final Cut's background-tasks dial. Spins when the job has no ETA. */
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

/** The toolbar's background-tasks button: a dial with the overall progress of what is running. */
export function TasksButton({ jobs, onClick }: { jobs: Job[]; onClick: () => void }) {
  const running = jobs.filter(isActive);
  const now = useNow(running.length > 0);
  const fr = running.map((j) => fraction(j, now));
  const known = fr.filter((x): x is number => x != null);
  const value = running.length === 0 ? 0 : known.length ? known.reduce((a, b) => a + b, 0) / running.length : null;
  const failed = jobs.slice(0, 8).some((j) => j.status === "failed");
  return (
    <button
      onClick={onClick}
      title="Background tasks (Ctrl+9)"
      className={cx(
        "flex h-[28px] items-center gap-2 rounded-[6px] px-2 text-[12px] font-medium transition-colors",
        running.length ? "bg-accent/15 text-accent hover:bg-accent/25" : "text-ink-2 hover:bg-surface-3 hover:text-ink",
      )}
    >
      {running.length ? <Ring value={value} /> : <Icon name="render" size={16} />}
      <span className="num">{running.length ? `${running.length} task${running.length > 1 ? "s" : ""}` : "Tasks"}</span>
      {failed && !running.length && <Dot tone="bad" />}
    </button>
  );
}

/** The banner a page shows for each of its running jobs. */
export function ActiveJobs({ jobs, openJob }: { jobs: Job[]; openJob: (id: number) => void }) {
  const now = useNow(jobs.length > 0);
  if (!jobs.length) return null;
  return (
    <div className="space-y-1.5">
      {jobs.map((j) => (
        <div key={j.id} className="flex items-center gap-3 rounded-[8px] border border-accent/40 bg-accent/10 px-3 py-1.5">
          <Ring value={fraction(j, now)} className="shrink-0 text-accent" />
          <div className="min-w-0 flex-1 truncate">
            <span className="font-medium">{j.title}</span>{" "}
            <span className="num text-[12px] text-ink-2">
              · {j.status} · <JobTiming job={j} />
            </span>
          </div>
          <Button small onClick={() => openJob(j.id)} icon="list">
            Live log
          </Button>
          <Button small variant="danger" onClick={() => api.cancel(j.id).catch(() => {})}>
            Cancel
          </Button>
        </div>
      ))}
    </div>
  );
}

export function JobRow({ job, selected, onSelect }: { job: Job; selected?: boolean; onSelect?: () => void }) {
  const now = useNow(job.status === "running");
  return (
    <button
      onClick={onSelect}
      className={cx(
        "flex w-full items-center gap-2.5 border-b border-line px-3 py-2 text-left last:border-b-0",
        selected ? "bg-accent/15" : "hover:bg-surface-2",
      )}
    >
      {job.status === "running" ? <Ring value={fraction(job, now)} size={16} className="shrink-0 text-accent" /> : (
        <span className="grid w-4 shrink-0 place-items-center">
          <Dot tone={tone(job.status)} />
        </span>
      )}
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[12.5px] font-medium">{job.title}</span>
        <span className="num block truncate text-[11px] text-ink-3">
          #{job.id} · {job.slug} · {job.queue} · {job.status} · <JobTiming job={job} />
        </span>
      </span>
    </button>
  );
}

const kindClass: Record<string, string> = {
  sys: "text-ink-3",
  out: "text-ink-2",
  claude: "text-ink",
  tool: "text-body",
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
      className="tc h-full overflow-auto bg-well px-3 py-2 text-[11.5px] leading-[1.6]"
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
                <button className="ml-2 text-accent underline" onClick={() => setOpenPrompt(openPrompt === l.seq ? null : l.seq)}>
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

/** Background Tasks: a floating HUD window, list on the left and the live log on the right. */
export function JobsPanel({ jobs, open, onClose, focus }: { jobs: Job[]; open: boolean; onClose: () => void; focus: number | null }) {
  const [sel, setSel] = useState<number | null>(null);
  useEffect(() => {
    if (focus != null) setSel(focus);
  }, [focus]);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  const job = jobs.find((j) => j.id === sel) ?? jobs.find(isActive) ?? jobs[0];
  const running = jobs.filter(isActive).length;
  return (
    <div className="fixed inset-0 z-40 flex items-start justify-end bg-black/25 p-3 pt-[52px]" onClick={onClose}>
      <aside
        className="flex h-full w-[min(1100px,94vw)] flex-col overflow-hidden rounded-[10px] border border-line-strong bg-surface/95 shadow-hud backdrop-blur-xl"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label="Background tasks"
      >
        <header className="flex h-[36px] shrink-0 items-center gap-2 border-b border-line px-3">
          <Icon name="render" size={15} className="text-ink-3" />
          <div className="flex-1 text-[12.5px] font-semibold">Background Tasks</div>
          <span className="text-[11.5px] text-ink-3">{running ? `${running} running` : "idle"} · {jobs.length} in the log</span>
          <button onClick={onClose} className="grid h-6 w-6 place-items-center rounded-[5px] text-ink-2 hover:bg-surface-3 hover:text-ink" aria-label="Close">
            <Icon name="x" size={14} />
          </button>
        </header>
        <div className="flex min-h-0 flex-1">
          <div className="w-[330px] shrink-0 overflow-auto border-r border-line">
            {jobs.length === 0 && <div className="p-4 text-ink-3">Nothing has run yet.</div>}
            {jobs.map((j) => (
              <JobRow key={j.id} job={j} selected={job?.id === j.id} onSelect={() => setSel(j.id)} />
            ))}
          </div>
          <div className="flex min-w-0 flex-1 flex-col">
            {job ? (
              <>
                <div className="flex items-center gap-3 border-b border-line px-4 py-2">
                  <Dot tone={tone(job.status)} pulse={job.status === "running"} />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-[13px] font-semibold">{job.title}</div>
                    <div className="num text-[11.5px] text-ink-3">
                      {job.status} · <JobTiming job={job} />
                    </div>
                  </div>
                  {isActive(job) && (
                    <Button variant="danger" small onClick={() => api.cancel(job.id).catch(() => {})}>
                      Cancel
                    </Button>
                  )}
                </div>
                {job.error && <div className="border-b border-line bg-bad-soft px-4 py-2 text-[12.5px] whitespace-pre-wrap text-bad">{job.error}</div>}
                <div className="min-h-0 flex-1">
                  <LogView job={job} />
                </div>
              </>
            ) : (
              <div className="p-6 text-ink-3">Pick a task to see its log.</div>
            )}
          </div>
        </div>
      </aside>
    </div>
  );
}
