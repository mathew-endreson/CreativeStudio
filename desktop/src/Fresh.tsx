import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { api, basename, clock, errText, fmt, type FreshMarks, type FreshProject, type Job, type Segment } from "./api";
import { tintFor } from "./brand";
import { Icon } from "./icons";
import { ActiveJobs, isActive, JobTiming, Ring, useJobs, useOnJobEnd } from "./Jobs";
import { inTauri, pickFolder, pickVideo } from "./tauri";
import { TranscriptStatus } from "./Transcript";
import { Button, Card, cx, dirOf, Empty, ErrorNote, field, Glass, Label, Loading, Status, tc, Toggle, Toolbar } from "./ui";
import { useVideo, Viewer } from "./Viewer";

const input = cx(field, "w-full");
type Field = keyof FreshMarks;
const FIELDS: { id: Field; label: string; tone: "hook" | "body" | "cta"; tag: string }[] = [
  { id: "hook_end", label: "Hook end", tone: "hook", tag: "H" },
  { id: "body_start", label: "Body start", tone: "body", tag: "B" },
  { id: "cta_start", label: "CTA start", tone: "cta", tag: "C" },
];
const bgTone = { hook: "bg-hook", body: "bg-body", cta: "bg-cta" } as const;
const short = (s: number) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
const GUTTER = 72;

function Lane({ label, h, children }: { label: string; h: number; children: ReactNode }) {
  return (
    <>
      <div className="flex items-center justify-end pr-3 text-[11px] font-medium text-ink-3" style={{ height: h }}>
        {label}
      </div>
      <div className="relative" style={{ height: h }}>
        {children}
      </div>
    </>
  );
}

/** The timeline: Video (hook / body / CTA clips, with draggable markers), Text (the transcript's segments),
 *  Graphics (the pictures the edit placed) and Voice (speech), under a ruler, with a white playhead. */
function FreshTimeline({
  dur,
  fps,
  t,
  marks,
  words,
  beats,
  onSeek,
  onChange,
  onDrop,
}: {
  dur: number;
  fps: number;
  t: number;
  marks: FreshMarks;
  words: Segment[];
  beats: { t: number; graphic: string; words?: string }[];
  onSeek: (t: number) => void;
  onChange: (f: Field, t: number) => void;
  onDrop: () => void;
}) {
  const track = useRef<HTMLDivElement>(null);
  const skim = useRef<HTMLDivElement>(null);
  const drag = useRef<Field | null>(null);
  const pct = (x: number) => `${Math.min(100, Math.max(0, (x / dur) * 100))}%`;
  const span = (x0: number, x1: number, min = 0) => ({ left: pct(x0), width: `max(${min}px, ${((Math.max(x1, x0) - x0) / dur) * 100}%)` });
  const timeAt = (clientX: number) => {
    const r = track.current!.getBoundingClientRect();
    const x = Math.min(1, Math.max(0, (clientX - r.left) / r.width)) * dur;
    return Math.round(x * fps) / fps;
  };
  const end = () => {
    if (drag.current) {
      drag.current = null;
      onDrop();
    }
  };
  const clip = "clip absolute inset-y-[3px] flex items-center overflow-hidden px-2.5 text-[11.5px] font-semibold whitespace-nowrap";
  const ticks = [];
  for (let s = 0; s <= dur; s++) ticks.push(s);
  return (
    <div className="select-none">
      <div
        className="relative grid cursor-pointer gap-y-[4px] rounded-[16px] bg-well py-1.5 pr-3"
        style={{ gridTemplateColumns: `${GUTTER}px minmax(0,1fr)` }}
        onPointerDown={(e) => {
          if (!drag.current && e.clientX >= track.current!.getBoundingClientRect().left) onSeek(timeAt(e.clientX));
        }}
        onPointerMove={(e) => {
          if (drag.current) onChange(drag.current, timeAt(e.clientX));
          const r = track.current!.getBoundingClientRect();
          if (skim.current) {
            const inside = e.clientX >= r.left && e.clientX <= r.right;
            skim.current.style.opacity = inside ? "1" : "0";
            skim.current.style.left = `${e.clientX - r.left}px`;
          }
        }}
        onPointerUp={end}
        onPointerLeave={() => {
          end();
          if (skim.current) skim.current.style.opacity = "0";
        }}
      >
        <div className="pointer-events-none absolute top-0 right-3 bottom-0 z-10 [&>.marker]:pointer-events-auto" style={{ left: GUTTER }} ref={track}>
          <div ref={skim} className="absolute top-0 bottom-0 z-30 w-px bg-skim opacity-0" />
          <div className="absolute top-0 bottom-0 z-30 -ml-px w-[2px] bg-playhead shadow-[0_0_0_1px_rgb(0_0_0/0.35)]" style={{ left: pct(t) }}>
            <div className="absolute -top-px left-1/2 h-0 w-0 -translate-x-1/2 border-x-[6px] border-t-[8px] border-x-transparent border-t-playhead" />
          </div>
          {FIELDS.map((f) => (
            <div
              key={f.id}
              role="slider"
              aria-label={f.label}
              aria-valuenow={marks[f.id]}
              tabIndex={0}
              className="marker absolute top-0 bottom-0 z-30 -ml-[6px] w-[13px] cursor-col-resize touch-none"
              style={{ left: pct(marks[f.id]) }}
              title={`${f.label}: drag to move it, or use the arrow keys`}
              onPointerDown={(e) => {
                e.stopPropagation();
                drag.current = f.id;
                (e.currentTarget.parentElement as HTMLElement).setPointerCapture(e.pointerId);
              }}
              onKeyDown={(e) => {
                if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
                  e.preventDefault();
                  onChange(f.id, marks[f.id] + (e.key === "ArrowLeft" ? -1 : 1) / fps);
                  onDrop();
                }
              }}
            >
              <div className={cx("absolute top-[18px] bottom-0 left-[5px] w-[3px] rounded-sm shadow-[0_0_0_1px_rgb(0_0_0/0.35)]", bgTone[f.tone])} />
              <span className={cx("absolute top-[1px] left-1/2 -translate-x-1/2 rounded-[4px] px-[5px] text-[10px] leading-[15px] font-bold text-black/80", bgTone[f.tone])}>{f.tag}</span>
            </div>
          ))}
        </div>

        <Lane label="" h={18}>
          <div className="absolute inset-x-0 top-0 bottom-0 border-b border-line">
            {ticks.map((x) => (
              <div key={x} className="absolute bottom-0" style={{ left: pct(x) }}>
                <div className={cx("w-px bg-ink-4", x % 5 === 0 ? "h-[7px]" : "h-[3px]")} />
                {x % 5 === 0 && <span className="tc absolute bottom-[8px] left-[3px] text-[9.5px] text-ink-4">{short(x)}</span>}
              </div>
            ))}
          </div>
        </Lane>
        <Lane label="Video" h={40}>
          <div className={cx(clip, "bg-hook text-black/80")} style={{ left: 0, width: pct(marks.hook_end) }}>
            Hook
          </div>
          <div className={cx(clip, "bg-body text-black/80")} style={{ left: pct(marks.body_start), width: pct(marks.cta_start - marks.body_start) }}>
            Body
          </div>
          <div className={cx(clip, "right-0 bg-cta text-black/80")} style={{ left: pct(marks.cta_start) }}>
            CTA
          </div>
        </Lane>
        <Lane label="Text" h={22}>
          {words.length === 0 && <div className="absolute inset-y-[3px] left-0 flex items-center text-[11px] text-ink-4">appears after the transcript</div>}
          {words.map((s, i) => (
            <div key={i} className="clip absolute inset-y-[3px] bg-white/[0.14]" style={span(s.start, Math.max(0.05, s.end), 3)} title={s.text} />
          ))}
        </Lane>
        <Lane label="Graphics" h={22}>
          {beats.length === 0 && <div className="absolute inset-y-[3px] left-0 flex items-center text-[11px] text-ink-4">the pictures appear here after the edit</div>}
          {beats.map((b, i) => (
            <div key={i} className="clip absolute inset-y-[3px] bg-accent-text/70" style={span(b.t, b.t + 1.2, 6)} title={`${fmt(b.t)} s · ${b.graphic}${b.words ? ` · ${b.words}` : ""}`} />
          ))}
        </Lane>
        <Lane label="Voice" h={40}>
          <div className="clip absolute inset-y-[3px] inset-x-0 overflow-hidden bg-audio">
            {words.map((s, i) => (
              <div key={i} className="absolute inset-y-[9px] rounded-[2px] bg-audio-wave/70" style={span(s.start, Math.max(0.05, s.end), 2)} title={s.text} />
            ))}
          </div>
        </Lane>
      </div>
    </div>
  );
}

function Steps({ f, jobs, openJob }: { f: FreshProject; jobs: Job[]; openJob: (id: number) => void }) {
  const live = (kind: string) => jobs.find((j) => j.kind === kind && isActive(j));
  const rows: { label: string; done: boolean; kind: string }[] = [
    { label: "Project prepared", done: f.project, kind: "fresh_init" },
    { label: "Transcript", done: f.words, kind: "transcribe" },
    { label: "Darija corrected", done: f.darija === "corrected", kind: "darija" },
    { label: "Speaker cut out", done: f.cutout, kind: "cut" },
    { label: "Ad edited and rendered", done: f.ad, kind: "fresh" },
  ];
  return (
    <div className="space-y-2">
      {rows.map((r) => {
        const j = live(r.kind);
        return (
          <div key={r.kind} className="flex items-center gap-2.5 text-[12.5px]">
            {r.done ? (
              <span className="grid h-4 w-4 shrink-0 place-items-center rounded-full bg-ok text-black/80">
                <Icon name="check" size={11} strokeWidth={3} />
              </span>
            ) : j ? (
              <Ring value={null} size={16} className="shrink-0 text-info" />
            ) : (
              <span className="h-4 w-4 shrink-0 rounded-full border-2 border-line-strong" />
            )}
            <span className={cx("min-w-0 flex-1", !r.done && !j && "text-ink-3")}>{r.label}</span>
            {j && (
              <button type="button" className="text-[11.5px] text-accent-text underline" onClick={() => openJob(j.id)}>
                <JobTiming job={j} />
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}

/** The ad's pictures: its own uploads folder, or a folder the user picked. */
function PicturesFolder({ f, onChange, onError }: { f: FreshProject; onChange: (f: FreshProject) => void; onError: (e: string) => void }) {
  const [path, setPath] = useState("");
  const set = (p: string | null) =>
    api
      .freshAssets(f.slug, p)
      .then((x) => (onChange(x), setPath("")))
      .catch((e) => onError(errText(e)));
  const lib = f.assets_library;
  const n = f.assets_count ?? 0;
  return (
    <div className="border-b border-line px-4 py-3">
      <div className="mb-1.5 flex items-center justify-between gap-2">
        <Label>Pictures</Label>
        <div className="flex items-center gap-1">
          {f.assets_dir && f.assets_exists && (
            <Button small variant="ghost" icon="folder" onClick={() => api.reveal(f.assets_dir!).catch((e) => onError(errText(e)))}>
              Open
            </Button>
          )}
          {inTauri() && (
            <Button
              small
              variant="ghost"
              onClick={() =>
                pickFolder().then((p) => {
                  if (p) void set(p);
                })
              }
            >
              Change…
            </Button>
          )}
        </div>
      </div>
      <div className="truncate text-[11.5px] text-ink-3" dir="auto" title={f.assets_dir}>
        {f.assets ? f.assets_dir : `${basename(f.assets_dir) || "uploads"}: this project's own folder`}
      </div>
      <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1">
        <Status tone={n ? "ok" : "neutral"}>
          {n} picture{n === 1 ? "" : "s"}
        </Status>
        {lib && lib.untagged > 0 && (
          <Status tone="warn" title="Claude writes them when it edits">
            {lib.untagged} without keywords
          </Status>
        )}
        {lib && lib.pictures > lib.usable && <Status tone="bad">{lib.pictures - lib.usable} can't be shown</Status>}
      </div>
      <form
        className="mt-2 flex gap-1.5"
        onSubmit={(e) => {
          e.preventDefault();
          if (path.trim()) set(path.trim());
        }}
      >
        <input className={cx(field, "min-h-[32px] min-w-0 flex-1")} placeholder="another folder: C:\…\assets" value={path} onChange={(e) => setPath(e.target.value)} aria-label="Pictures folder" />
        <Button small type="submit" disabled={!path.trim()}>
          Use
        </Button>
      </form>
      {f.assets && (
        <button type="button" className="mt-1.5 text-[11.5px] text-accent-text underline" onClick={() => set(null)}>
          Use this project's own folder instead
        </button>
      )}
      <p className="mt-2 text-[11.5px] leading-snug text-ink-4">Transparent PNG / WebP cut-outs of what he talks about. Each one is shown in front of him on the word that names it. No pictures: captions, route and CTA only.</p>
    </div>
  );
}

function Editor({ slug, openJob }: { slug: string; openJob: (id: number) => void }) {
  const [f, setF] = useState<FreshProject | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [marks, setMarks] = useState<FreshMarks | null>(null);
  const [draw, setDraw] = useState(false);
  const video = useVideo();
  const { t, seek } = video;
  const jobs = useJobs(slug);
  const load = useCallback(
    () =>
      api
        .fresh(slug)
        .then((x) => (setF(x), setMarks((m) => m ?? x.marks ?? (x.duration ? { hook_end: Math.min(3, x.duration / 4), body_start: Math.min(3, x.duration / 4), cta_start: Math.max(x.duration * 0.75, x.duration - 6) } : null))))
        .catch((e) => setErr(errText(e))),
    [slug],
  );
  useEffect(() => {
    load();
  }, [load]);
  useOnJobEnd(jobs, load);
  if (err) return <ErrorNote>{err}</ErrorNote>;
  if (!f) return <Loading />;
  const fps = f.fps ?? 30;
  const dur = f.duration ?? 0;
  const running = jobs.some((j) => j.kind === "fresh" && isActive(j));
  const cutting = jobs.some((j) => j.kind === "cut" && isActive(j));
  const save = () => marks && api.freshMarks(slug, marks).then(setF).catch((e) => setErr(errText(e)));
  const change = (k: Field, x: number) => setMarks((m) => (m ? { ...m, [k]: Math.min(dur, Math.max(0, x)) } : m));
  const res = f.result;
  const unsaved = !!(f.marks && marks && JSON.stringify(f.marks) !== JSON.stringify(marks));
  const tint = tintFor(slug);
  const edit = () =>
    save()
      ?.then(() => api.freshRun(slug, draw))
      .then((r) => r && r.jobs[0] && openJob(r.jobs[0].id))
      .then(load)
      .catch((e) => setErr(errText(e)));

  return (
    <div className="flex h-full min-h-0 flex-col">
      <Toolbar back="#/fresh">
        <div className="mr-auto flex min-w-0 items-center gap-3">
          <span className="h-[28px] w-[28px] shrink-0 rounded-[8px]" style={{ background: tint.bg, boxShadow: `inset 0 0 0 1px ${tint.frame}` }} aria-hidden="true" />
          <div className="min-w-0">
            <h1 className="truncate text-[17px] leading-tight font-semibold tracking-tight">{f.name}</h1>
            <div className="num truncate text-[12px] text-ink-3" dir="auto">
              {basename(f.footage)} · {dur ? `${tc(dur, fps)} · ${fps} fps` : "probing…"} · Claude {f.usage.claude_runs} run{f.usage.claude_runs === 1 ? "" : "s"}
              {f.usage.cost_usd ? ` · $${f.usage.cost_usd.toFixed(2)}` : ""}
            </div>
          </div>
        </div>
        <label className="flex items-center gap-2 text-[12.5px] text-ink-2" title="Off: ideas he names that no picture shows are listed for you. On: the drawing tool makes some of them.">
          <input type="checkbox" checked={draw} onChange={(e) => setDraw(e.target.checked)} /> Draw missing pictures
        </label>
        {f.ad_path && f.ad && (
          <Button icon="folder" onClick={() => api.reveal(f.ad_path!)}>
            Show in Explorer
          </Button>
        )}
        <Button variant="primary" disabled={!f.words || !marks || running} onClick={edit}>
          {running ? "Editing…" : f.ad ? "Edit again" : "Edit the ad"}
        </Button>
      </Toolbar>
      <ActiveJobs jobs={jobs.filter(isActive)} openJob={openJob} />

      <div className="mt-[10px] grid min-h-[560px] grid-cols-[minmax(240px,300px)_minmax(0,1fr)_minmax(280px,340px)] gap-[10px]">
        {/* the footage bin */}
        <Glass className="flex min-h-0 flex-col overflow-hidden">
          <div className="px-4 pt-4 pb-2 text-[13px] font-semibold">Footage</div>
          <div className="grid grid-cols-2 gap-2 px-3">
            <div className="relative aspect-[9/16] overflow-hidden rounded-[14px]" style={{ background: tint.bg }}>
              {f.sheet ? <img src={`/media/fresh/${slug}/work/sheet.jpg`} alt="contact sheet" className="h-full w-full object-cover" /> : <div className="grid h-full place-items-center text-[11px] text-white/60">preparing…</div>}
              <span className="player-bar tc absolute right-2 bottom-2 px-2 py-0.5 text-[10.5px] text-white/90">{dur ? clock(dur) : "…"}</span>
            </div>
            <div className="relative aspect-[9/16] overflow-hidden rounded-[14px] bg-black/40">
              {f.ad && f.snaps[0] ? <img src={`/media/fresh/${slug}/snap/${f.snaps[0]}`} alt="the finished ad" className="h-full w-full object-cover" /> : <div className="grid h-full place-items-center px-3 text-center text-[11px] text-ink-4">the finished ad appears here</div>}
              {f.ad && res && <span className="player-bar tc absolute right-2 bottom-2 px-2 py-0.5 text-[10.5px] text-white/90">{clock(res.duration)}</span>}
            </div>
          </div>
          <div className="mt-3 border-t border-line px-4 pt-3 pb-1">
            <TranscriptStatus info={f.transcript} running={jobs.some((j) => j.kind === "darija" && isActive(j))} onRedo={() => api.freshDarija(slug).then((r) => openJob(r.jobs[0].id)).catch((e) => setErr(errText(e)))} />
          </div>
          <div className="min-h-0 flex-1 overflow-auto px-4 pb-4">
            {f.words_data && f.words_data.length > 0 ? (
              <div dir="rtl" className="text-[15px] leading-[2.1]">
                {f.words_data.map((s, i) => {
                  const sec = marks && s.start < marks.hook_end ? "decoration-hook" : marks && s.start >= marks.cta_start ? "decoration-cta" : "decoration-body";
                  return (
                    <span key={i} className="mr-1">
                      {s.words.map((w, j) => (
                        <button
                          key={j}
                          type="button"
                          onClick={() => seek(w.s)}
                          title={w.p < 0.5 ? "unsure: check it by ear" : undefined}
                          className={cx("rounded-[4px] px-0.5 underline decoration-2 underline-offset-[7px] hover:bg-hover", sec, w.p < 0.5 && "decoration-dotted", t >= w.s && t < w.e && "bg-white/[0.16] text-ink")}
                        >
                          {w.w}
                        </button>
                      ))}
                    </span>
                  );
                })}
              </div>
            ) : (
              <div className="text-[12.5px] text-ink-4">The transcript appears once Whisper has run. Click a word to go to it.</div>
            )}
          </div>
        </Glass>

        {/* the preview */}
        <Viewer video={video} src={f.project ? `/media/fresh/${slug}/footage` : undefined} dur={dur} fps={fps} placeholder="preparing the project…" className="min-h-0" />

        {/* the inspector */}
        <Glass className="flex min-h-0 flex-col overflow-hidden">
          <div className="px-4 pt-4 pb-2 text-[13px] font-semibold">Inspector</div>
          <div className="min-h-0 flex-1 overflow-auto">
            <div className="border-b border-line px-4 py-3">
              <div className="mb-1.5 flex items-center justify-between">
                <Label>Sections</Label>
                <div className="flex items-center gap-2">
                  {unsaved && <Status tone="warn">unsaved</Status>}
                  <Button small variant="ghost" onClick={save} disabled={!marks}>
                    Save
                  </Button>
                </div>
              </div>
              {marks ? (
                <div className="divide-y divide-line">
                  {FIELDS.map((x) => (
                    <div key={x.id} className="flex items-center gap-2 py-1.5">
                      <span className={cx("rounded-[4px] px-[5px] text-[10px] leading-[15px] font-bold text-black/80", bgTone[x.tone])}>{x.tag}</span>
                      <span className="min-w-0 flex-1 truncate text-[12.5px] text-ink-2">{x.label}</span>
                      <input type="number" step={1 / fps} min={0} max={dur} value={marks[x.id]} onChange={(e) => change(x.id, Number(e.target.value))} onBlur={save} className={cx(field, "num min-h-[32px] w-[84px]")} aria-label={`${x.label} in seconds`} />
                      <Button small variant="ghost" title="Set from the playhead" onClick={() => (change(x.id, Math.round(t * fps) / fps), save())}>
                        Playhead
                      </Button>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-[12px] text-ink-4">The markers appear once the project is prepared.</div>
              )}
              <p className="mt-2 text-[11.5px] leading-snug text-ink-4">Transition 1 lands on the hook end, transition 2 on the CTA start.</p>
            </div>
            <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
              <div>
                <div className="text-[13px] font-medium">Cut out the speaker</div>
                <div className="text-[11.5px] text-ink-4">{f.cutout ? "Done: the particles and the route run behind him." : cutting ? "Running…" : "Needed for the particles and the route behind him."}</div>
              </div>
              <Toggle on={f.cutout || cutting} disabled={f.cutout || cutting || !f.project} label="Cut out the speaker" onChange={(v) => v && api.freshCutout(slug).then((r) => openJob(r.jobs[0].id)).catch((e) => setErr(errText(e)))} />
            </div>
            <PicturesFolder f={f} onChange={setF} onError={setErr} />
            <div className="border-b border-line px-4 py-3">
              <div className="mb-2">
                <Label>Steps</Label>
              </div>
              <Steps f={f} jobs={jobs} openJob={openJob} />
            </div>
            {f.sheet && (
              <div className="px-4 py-3">
                <div className="mb-1.5">
                  <Label>Framing</Label>
                </div>
                <img src={`/media/fresh/${slug}/work/sheet.jpg`} alt="contact sheet" className="w-full rounded-[10px]" />
              </div>
            )}
          </div>
        </Glass>
      </div>

      <Card className="mt-[10px] p-3">
        <div className="mb-2 flex items-center justify-between px-1">
          <div className="text-[13px] font-semibold">Timeline</div>
          <div className="tc text-[11.5px] text-ink-3">
            {tc(t, fps)} / {tc(dur, fps)}
          </div>
        </div>
        {marks && dur > 0 ? (
          <FreshTimeline dur={dur} fps={fps} t={t} marks={marks} words={f.words_data ?? []} beats={res?.beats ?? []} onSeek={seek} onChange={change} onDrop={save} />
        ) : (
          <div className="p-2 text-[12.5px] text-ink-4">The timeline appears once the project is prepared.</div>
        )}
      </Card>

      {(res || f.snaps.length > 0) && (
        <Card className="mt-[10px] p-5">
          <div className="mb-3 flex flex-wrap items-center gap-3">
            <div className="text-[14px] font-semibold">Result</div>
            {f.ad && (
              <Status tone="ok" title={f.ad_path ?? ""}>
                {basename(f.ad_path)}
              </Status>
            )}
          </div>
          <div className="grid gap-4 lg:grid-cols-[220px_1fr]">
            <div className="viewer overflow-hidden rounded-[18px]">
              {f.ad ? (
                <video src={`/media/fresh/${slug}/ad?v=${res?.size_mb ?? ""}`} controls playsInline preload="metadata" className="aspect-[9/16] w-full bg-black" />
              ) : (
                f.final_sheet && <img src={`/media/fresh/${slug}/work/final_sheet.jpg`} alt="final sheet" className="w-full" />
              )}
            </div>
            <div className="min-w-0 space-y-3 text-[12.5px]">
              {res && (
                <div className="num flex flex-wrap gap-x-4 gap-y-1 text-ink-2">
                  <span>{fmt(res.duration, 1)} s</span>
                  {res.loudness_after != null && <Status tone={Math.abs(res.loudness_after + 15) < 1 ? "ok" : "warn"}>{fmt(res.loudness_after, 1)} LUFS</Status>}
                  {res.peak_dbfs != null && <span>peak {fmt(res.peak_dbfs, 1)} dB</span>}
                  {res.size_mb != null && <span>{fmt(res.size_mb, 1)} MB</span>}
                  <span>{res.captions} captions</span>
                  <Status tone={res.black_frames.length ? "bad" : "ok"}>{res.black_frames.length} black frames</Status>
                </div>
              )}
              {f.snaps.length > 0 && (
                <div className="flex gap-1.5 overflow-x-auto pb-1">
                  {f.snaps.map((s) => (
                    <img key={s} src={`/media/fresh/${slug}/snap/${s}`} alt={s} title={s} className="h-[150px] w-[84px] shrink-0 rounded-[8px] bg-black object-cover" loading="lazy" />
                  ))}
                </div>
              )}
              {res && res.beats.length > 0 && (
                <table className="w-full text-[12px]">
                  <tbody>
                    {res.beats.map((b, i) => (
                      <tr key={i} className="border-b border-line last:border-b-0">
                        <td className="tc w-[60px] py-1 text-ink-3">{fmt(b.t)}</td>
                        <td className="w-[44px] py-1 text-ink-4">{b.side}</td>
                        <td className="py-1 font-medium">{b.graphic}</td>
                        <td dir="auto" className="py-1 text-ink-2">
                          {b.words}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              {res && (res.library_pictures.length > 0 || res.gpt_drawings.length > 0) && (
                <div className="flex flex-wrap gap-x-3 gap-y-1">
                  {res.library_pictures.map((p) => (
                    <Status key={p} tone="ok">
                      {p}
                    </Status>
                  ))}
                  {res.gpt_drawings.map((g, i) => (
                    <Status key={i} tone="warn" title={g.prompt}>
                      drawn: {basename(g.path)}
                    </Status>
                  ))}
                </div>
              )}
              {res && res.missing && res.missing.length > 0 && (
                <div>
                  <Label>Ideas with no picture</Label>
                  <ul className="mt-1 list-disc pl-4">
                    {res.missing.map((x, i) => (
                      <li key={i}>
                        <span className="font-medium">{x.concept}</span>
                        {x.words && (
                          <span className="text-ink-3">
                            {" · "}
                            <bdi>{x.words}</bdi>
                          </span>
                        )}
                      </li>
                    ))}
                  </ul>
                  <div className="text-ink-3">Put a picture for them in the pictures folder, then edit again.</div>
                </div>
              )}
              {res && res.unsure.length > 0 && (
                <div>
                  <Label>Claude was unsure of</Label>
                  <ul className="mt-1 list-disc pl-4">
                    {res.unsure.map((u, i) => (
                      <li key={i} dir={dirOf(u)}>
                        {u}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {res?.notes && <div className="text-ink-3">{res.notes}</div>}
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}

function NewFresh({ onCreated }: { onCreated: (slug: string, jobId?: number) => void }) {
  const [footage, setFootage] = useState("");
  const [name, setName] = useState("");
  const [outDir, setOutDir] = useState("");
  const [prompt, setPrompt] = useState("");
  const [assets, setAssets] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const go = () => {
    setBusy(true);
    api
      .freshCreate({ footage: footage.trim(), name: name.trim() || undefined, out_dir: outDir.trim() || undefined, whisper_prompt: prompt.trim() || undefined, assets: assets.trim() || undefined })
      .then((r) => onCreated(r.slug, r.jobs[0]?.id))
      .catch((e) => setErr(errText(e)))
      .finally(() => setBusy(false));
  };
  return (
    <Card className="p-5">
      <div className="text-[14px] font-semibold">New fresh edit</div>
      <p className="mt-0.5 mb-4 text-[12.5px] text-ink-3">One clean talking-head footage, no burned-in captions. The app prepares it, you mark hook / body / CTA, and the ad is edited and rendered into the Edited Ads folder beside the footage.</p>
      {err && (
        <div className="mb-3">
          <ErrorNote>{err}</ErrorNote>
        </div>
      )}
      <div className="grid gap-4 md:grid-cols-2">
        <label className="block md:col-span-2">
          <Label>Footage file</Label>
          <div className="mt-1.5 flex gap-2">
            <input className={input} placeholder="C:\…\Footage 05.mov" value={footage} onChange={(e) => setFootage(e.target.value)} />
            <Button icon="folder" onClick={() => pickVideo().then((p) => p && setFootage(p))}>
              Browse…
            </Button>
          </div>
        </label>
        <label className="block">
          <Label>Name (optional)</Label>
          <input className={cx(input, "mt-1.5")} value={name} onChange={(e) => setName(e.target.value)} placeholder={basename(footage).replace(/\.[^.]+$/, "")} />
        </label>
        <label className="block">
          <Label>Output folder (default: Edited Ads beside the footage)</Label>
          <div className="mt-1.5 flex gap-2">
            <input className={input} value={outDir} onChange={(e) => setOutDir(e.target.value)} />
            <Button icon="folder" onClick={() => pickFolder().then((p) => p && setOutDir(p))}>
              Browse…
            </Button>
          </div>
        </label>
        <label className="block md:col-span-2">
          <Label>Key words for Whisper (optional: product, organ, symptoms, brand)</Label>
          <input dir="auto" className={cx(input, "mt-1.5")} value={prompt} onChange={(e) => setPrompt(e.target.value)} />
        </label>
        <label className="block md:col-span-2">
          <Label>Pictures folder (optional: transparent PNG / WebP cut-outs for this ad; default: a folder inside the project)</Label>
          <div className="mt-1.5 flex gap-2">
            <input className={input} placeholder="C:\…\Product\assets" value={assets} onChange={(e) => setAssets(e.target.value)} />
            <Button icon="folder" onClick={() => pickFolder().then((p) => p && setAssets(p))}>
              Browse…
            </Button>
          </div>
        </label>
      </div>
      <Button variant="primary" className="mt-4" disabled={!footage.trim() || busy} onClick={go}>
        {busy ? "Creating…" : "Create and prepare"}
      </Button>
    </Card>
  );
}

export default function Fresh({ slug, openJob }: { slug?: string; openJob: (id: number) => void }) {
  const [list, setList] = useState<FreshProject[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [showNew, setShowNew] = useState(false);
  const jobs = useJobs();
  const load = useCallback(() => api.freshList().then(setList).catch((e) => setErr(errText(e))), []);
  useEffect(() => {
    if (!slug) load();
  }, [load, slug]);
  useOnJobEnd(jobs, () => !slug && load());
  if (slug) return <Editor slug={slug} openJob={openJob} />;
  const busy = new Set(jobs.filter(isActive).map((j) => j.slug));
  const open = showNew || (list !== null && list.length === 0);
  return (
    <div>
      <Toolbar title="Fresh edit" sub="One footage, one ad: captions, hook / body / CTA transitions, your pictures in front of the speaker, rendered at −15 LUFS.">
        <Button variant="primary" icon="plus" onClick={() => setShowNew((v) => !v)}>
          New
        </Button>
      </Toolbar>
      {open && (
        <div className="mb-[10px]">
          <NewFresh
            onCreated={(s, j) => {
              if (j) openJob(j);
              location.hash = `#/fresh/${s}`;
            }}
          />
        </div>
      )}
      {err && <ErrorNote>{err}</ErrorNote>}
      <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-[10px]">
        {list?.map((f) => {
          const tint = tintFor(f.slug);
          const state = busy.has(f.slug) ? { tone: "info" as const, text: "Working" } : f.ad ? { tone: "ok" as const, text: "Rendered" } : f.marks ? { tone: "warn" as const, text: "Ready to edit" } : f.project ? { tone: "warn" as const, text: "Set the sections" } : { tone: "neutral" as const, text: "Preparing" };
          return (
            <a key={f.slug} href={`#/fresh/${f.slug}`} className="press group relative block h-[220px] overflow-hidden rounded-[22px] border border-line focus-visible:outline-2 focus-visible:outline-focus">
              <div className="absolute inset-0" style={{ background: tint.bg }}>
                {f.sheet && <img src={`/media/fresh/${f.slug}/work/sheet.jpg`} alt="" className="h-full w-full object-cover opacity-80" loading="lazy" />}
              </div>
              <div className="glass-img absolute inset-x-0 bottom-0 rounded-none border-x-0 border-b-0 px-4 py-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="truncate text-[14px] font-semibold">{f.name}</div>
                    <div className="num truncate text-[12px] text-ink-3" dir="auto">
                      {basename(f.footage)} · {f.duration ? clock(f.duration) : "…"}
                    </div>
                  </div>
                  <Status tone={state.tone} pulse={state.tone === "info"}>
                    {state.text}
                  </Status>
                </div>
                <div className="mt-2.5 flex gap-1" title="project · transcript · cutout · ad">
                  {[f.project, f.words, f.cutout, f.ad].map((d, i) => (
                    <span key={i} className={cx("h-[4px] flex-1 rounded-full", d ? "bg-ink/80" : "bg-white/[0.12]")} />
                  ))}
                </div>
              </div>
            </a>
          );
        })}
      </div>
      {list && list.length === 0 && !open && <Empty title="No fresh edit yet" />}
    </div>
  );
}
