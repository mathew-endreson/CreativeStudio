import { useCallback, useEffect, useRef, useState, type PointerEvent as RPointerEvent } from "react";
import { api, basename, clock, errText, fmt, type FreshMarks, type FreshProject, type Job, type Segment } from "./api";
import { Icon } from "./icons";
import { ActiveJobs, isActive, JobTiming, Ring, useJobs, useOnJobEnd } from "./Jobs";
import { inTauri, pickVideo, pickFolder } from "./tauri";
import { TranscriptStatus } from "./Transcript";
import { Button, Chip, cx, dirOf, Empty, ErrorNote, field, Label, Loading, PageHeader, Panel, tc } from "./ui";
import { useVideo, Viewer } from "./Viewer";

const input = cx(field, "h-[28px] w-full");
type Field = keyof FreshMarks;
const FIELDS: { id: Field; label: string; tone: "hook" | "body" | "cta"; tag: string }[] = [
  { id: "hook_end", label: "Hook end", tone: "hook", tag: "H" },
  { id: "body_start", label: "Body start", tone: "body", tag: "B" },
  { id: "cta_start", label: "CTA start", tone: "cta", tag: "C" },
];
const bgTone = { hook: "bg-hook", body: "bg-body", cta: "bg-cta" } as const;
const short = (s: number) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

/** The three section markers over the footage, drawn as a Final Cut storyline: drag a marker, or click to move the playhead. */
function MarksBar({ dur, fps, t, marks, words, onSeek, onChange, onDrop }: { dur: number; fps: number; t: number; marks: FreshMarks; words: Segment[]; onSeek: (t: number) => void; onChange: (f: Field, t: number) => void; onDrop: () => void }) {
  const track = useRef<HTMLDivElement>(null);
  const skim = useRef<HTMLDivElement>(null);
  const drag = useRef<Field | null>(null);
  const pct = (x: number) => `${Math.min(100, Math.max(0, (x / dur) * 100))}%`;
  const timeAt = (e: RPointerEvent) => {
    const r = track.current!.getBoundingClientRect();
    const x = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)) * dur;
    return Math.round(x * fps) / fps;
  };
  const end = () => {
    if (drag.current) {
      drag.current = null;
      onDrop();
    }
  };
  const clip = "clip absolute top-[24px] h-[34px] overflow-hidden rounded-[5px] border border-black/30 px-2 text-[11.5px] leading-[32px] font-semibold";
  return (
    <div className="rounded-[6px] bg-well px-3 pt-1 pb-2 select-none">
      <div
        ref={track}
        className="relative h-[108px] cursor-pointer"
        onPointerDown={(e) => {
          if (!drag.current) onSeek(timeAt(e));
        }}
        onPointerMove={(e) => {
          if (drag.current) onChange(drag.current, timeAt(e));
          const r = track.current!.getBoundingClientRect();
          if (skim.current) {
            skim.current.style.opacity = "1";
            skim.current.style.left = `${e.clientX - r.left}px`;
          }
        }}
        onPointerUp={end}
        onPointerLeave={() => {
          end();
          if (skim.current) skim.current.style.opacity = "0";
        }}
      >
        {/* ruler */}
        <div className="absolute inset-x-0 top-0 h-[18px] border-b border-line">
          {Array.from({ length: Math.floor(dur) + 1 }, (_, i) => i).map((x) => (
            <div key={x} className="absolute bottom-0" style={{ left: pct(x) }}>
              <div className={cx("w-px bg-ink-3", x % 5 === 0 ? "h-[7px]" : "h-[3px]")} />
              {x % 5 === 0 && <span className="tc absolute bottom-[8px] left-[3px] text-[9.5px] text-ink-3">{short(x)}</span>}
            </div>
          ))}
        </div>
        {/* the storyline */}
        <div className={cx(clip, "bg-hook text-black/80")} style={{ left: 0, width: pct(marks.hook_end) }}>
          Hook
        </div>
        <div className={cx(clip, "bg-body text-white")} style={{ left: pct(marks.body_start), width: pct(marks.cta_start - marks.body_start) }}>
          Body
        </div>
        <div className={cx(clip, "right-0 bg-cta text-white")} style={{ left: pct(marks.cta_start) }}>
          CTA
        </div>
        {/* speech, as an audio clip */}
        <div className="clip absolute inset-x-0 top-[62px] h-[40px] overflow-hidden rounded-[5px] border border-black/30 bg-audio">
          {words.map((s, i) => (
            <div key={i} className="absolute inset-y-[8px] rounded-[2px] bg-audio-wave/70" style={{ left: pct(s.start), width: pct(Math.max(0.05, s.end - s.start)) }} title={s.text} />
          ))}
        </div>
        {/* skimmer and playhead */}
        <div ref={skim} className="pointer-events-none absolute top-0 bottom-0 z-20 w-px bg-skim opacity-0" />
        <div className="pointer-events-none absolute top-0 bottom-0 z-20 -ml-px w-[2px] bg-playhead" style={{ left: pct(t) }}>
          <div className="absolute -top-px left-1/2 h-0 w-0 -translate-x-1/2 border-x-[6px] border-t-[8px] border-x-transparent border-t-playhead" />
        </div>
        {/* the markers */}
        {FIELDS.map((f) => (
          <div
            key={f.id}
            className="absolute top-0 bottom-0 z-30 -ml-[6px] w-[13px] cursor-col-resize"
            style={{ left: pct(marks[f.id]) }}
            title={`${f.label}: drag to move it`}
            onPointerDown={(e) => {
              e.stopPropagation();
              drag.current = f.id;
              (e.currentTarget.parentElement as HTMLElement).setPointerCapture(e.pointerId);
            }}
          >
            <div className={cx("absolute top-[18px] bottom-0 left-[5px] w-[3px] rounded-sm shadow-[0_0_0_1px_rgb(0_0_0/0.35)]", bgTone[f.tone])} />
            <span className={cx("absolute top-[1px] left-1/2 -translate-x-1/2 rounded-[3px] px-[5px] text-[10px] leading-[15px] font-bold text-black/80", bgTone[f.tone])}>{f.tag}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function Steps({ f, jobs, openJob }: { f: FreshProject; jobs: Job[]; openJob: (id: number) => void }) {
  const live = (kind: string) => jobs.find((j) => j.kind === kind && isActive(j));
  const rows: { label: string; done: boolean; kind: string }[] = [
    { label: "Project (1080×1920 copy, audio, sheet)", done: f.project, kind: "fresh_init" },
    { label: "Transcript (ffmpeg + Whisper, word times)", done: f.words, kind: "transcribe" },
    { label: "Darija (Claude + darijadz, darija_lint)", done: f.darija === "corrected", kind: "darija" },
    { label: "Speaker cutout (for the particles and route behind him)", done: f.cutout, kind: "cut" },
    { label: "Edit with Claude (captions, pictures, render)", done: f.ad, kind: "fresh" },
  ];
  return (
    <div className="space-y-1.5">
      {rows.map((r) => {
        const j = live(r.kind);
        return (
          <div key={r.kind} className="flex items-center gap-2 text-[12.5px]">
            {r.done ? (
              <span className="grid h-4 w-4 shrink-0 place-items-center rounded-full bg-ok text-black/80">
                <Icon name="check" size={11} strokeWidth={3} />
              </span>
            ) : j ? (
              <Ring value={null} size={16} className="shrink-0 text-accent" />
            ) : (
              <span className="h-4 w-4 shrink-0 rounded-full border-2 border-line" />
            )}
            <span className={cx("min-w-0 flex-1", !r.done && !j && "text-ink-2")}>{r.label}</span>
            {j && (
              <button className="text-[11.5px] text-accent underline" onClick={() => openJob(j.id)}>
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
    <div className="border-b border-line px-3 py-2.5">
      <div className="mb-1 flex items-center justify-between gap-2">
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
      <div className="mt-1 flex flex-wrap gap-1">
        <Chip tone={n ? "ok" : "neutral"}>
          {n} picture{n === 1 ? "" : "s"}
        </Chip>
        {lib && lib.untagged > 0 && (
          <Chip tone="warn" title="Claude writes them when it edits">
            {lib.untagged} without keywords
          </Chip>
        )}
        {lib && lib.pictures > lib.usable && <Chip tone="bad">{lib.pictures - lib.usable} can't be shown</Chip>}
      </div>
      <form
        className="mt-1.5 flex gap-1.5"
        onSubmit={(e) => {
          e.preventDefault();
          if (path.trim()) set(path.trim());
        }}
      >
        <input className={cx(field, "h-[24px] min-w-0 flex-1")} placeholder="another folder: C:\…\assets" value={path} onChange={(e) => setPath(e.target.value)} aria-label="Pictures folder" />
        <Button small type="submit" disabled={!path.trim()}>
          Use
        </Button>
      </form>
      {f.assets && (
        <button className="mt-1 text-[11.5px] text-accent underline" onClick={() => set(null)}>
          Use this project's own folder instead
        </button>
      )}
      <p className="mt-1.5 text-[11.5px] leading-snug text-ink-3">
        Transparent PNG / WebP cut-outs of what he talks about (the herbs, the jar, a moon…). Claude writes their keywords and shows each one in front of him on the word that names it. No pictures: captions, route and CTA only.
      </p>
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
  const load = useCallback(() => api.fresh(slug).then((x) => (setF(x), setMarks((m) => m ?? x.marks ?? (x.duration ? { hook_end: Math.min(3, x.duration / 4), body_start: Math.min(3, x.duration / 4), cta_start: Math.max(x.duration * 0.75, x.duration - 6) } : null)))).catch((e) => setErr(errText(e))), [slug]);
  useEffect(() => {
    load();
  }, [load]);
  useOnJobEnd(jobs, load);
  if (err) return <ErrorNote>{err}</ErrorNote>;
  if (!f) return <Loading />;
  const fps = f.fps ?? 30;
  const dur = f.duration ?? 0;
  const running = jobs.some((j) => j.kind === "fresh" && isActive(j));
  const save = () => marks && api.freshMarks(slug, marks).then(setF).catch((e) => setErr(errText(e)));
  const change = (k: Field, x: number) => setMarks((m) => (m ? { ...m, [k]: Math.min(dur, Math.max(0, x)) } : m));
  const res = f.result;
  const unsaved = !!(f.marks && marks && JSON.stringify(f.marks) !== JSON.stringify(marks));

  return (
    <div className="space-y-[3px]">
      <div className="flex flex-wrap items-center gap-3 glass rounded-[12px] px-3 py-2.5">
        <span className="clip grid h-9 w-9 shrink-0 place-items-center rounded-[8px] bg-surface-3 text-ink-2">
          <Icon name="wand" size={17} />
        </span>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-[17px] leading-tight font-semibold tracking-tight">{f.name}</h1>
          <div className="truncate text-[11.5px] text-ink-3" dir="auto">
            {f.footage} · {dur ? `${tc(dur, fps)} · ${fps} fps` : "probing…"} · output <span>{basename(f.ad_path ?? f.out_path)}</span>
          </div>
        </div>
        <Chip title="Claude runs for this edit">
          Claude: {f.usage.claude_runs} run{f.usage.claude_runs === 1 ? "" : "s"}
          {f.usage.cost_usd ? ` · $${f.usage.cost_usd.toFixed(2)}` : ""}
        </Chip>
        <label className="flex items-center gap-1.5 text-[12.5px]" title="Off: ideas he names that no picture shows are listed for you. On: GPT draws some of them (your ChatGPT image allowance).">
          <input type="checkbox" checked={draw} onChange={(e) => setDraw(e.target.checked)} /> let GPT draw missing pictures
        </label>
        <Button variant="primary" icon="sparkles" disabled={!f.words || !marks || running} onClick={() => save()?.then(() => api.freshRun(slug, draw)).then((r) => r && r.jobs[0] && openJob(r.jobs[0].id)).then(load).catch((e) => setErr(errText(e)))}>
          {running ? "Editing…" : f.ad ? "Edit again" : "Edit with Claude"}
        </Button>
      </div>
      <ActiveJobs jobs={jobs.filter(isActive)} openJob={openJob} />

      <div className="grid grid-cols-[minmax(260px,330px)_minmax(0,1fr)] gap-[3px] xl:h-[clamp(470px,64vh,720px)] xl:grid-cols-[minmax(270px,340px)_minmax(0,1fr)_minmax(280px,340px)]">
        <Viewer video={video} src={f.project ? `/media/fresh/${slug}/footage` : undefined} dur={dur} fps={fps} title="Viewer · footage" placeholder="preparing the project…" className="h-[560px] xl:h-auto" />

        <Panel title="Transcript · click a word to go to it" icon="text" className="order-3 col-span-2 h-[300px] xl:order-none xl:col-span-1 xl:h-auto" bodyClass="overflow-auto">
          <TranscriptStatus
            info={f.transcript}
            running={jobs.some((j) => j.kind === "darija" && isActive(j))}
            onRedo={() => api.freshDarija(slug).then((r) => openJob(r.jobs[0].id)).catch((e) => setErr(errText(e)))}
          />
          <div className="px-3 py-2">
          {f.words_data && f.words_data.length > 0 ? (
            <div dir="rtl" className="text-[16px] leading-[2.15]">
              {f.words_data.map((s, i) => {
                const sec = marks && s.start < marks.hook_end ? "decoration-hook" : marks && s.start >= marks.cta_start ? "decoration-cta" : "decoration-body";
                return (
                  <span key={i} className="mr-1">
                    {s.words.map((w, j) => (
                      <button
                        key={j}
                        onClick={() => seek(w.s)}
                        title={w.p < 0.5 ? "unsure: check it by ear" : undefined}
                        className={cx("rounded-[4px] px-0.5 underline decoration-2 underline-offset-[7px] hover:bg-surface-3", sec, w.p < 0.5 && "decoration-dotted", t >= w.s && t < w.e && "bg-accent text-on-accent hover:bg-accent")}
                      >
                        {w.w}
                      </button>
                    ))}
                  </span>
                );
              })}
            </div>
          ) : (
            <div className="text-[12.5px] text-ink-3">The transcript appears once Whisper has run.</div>
          )}
          </div>
        </Panel>

        <Panel title="Inspector" icon="inspector" className="h-[560px] xl:h-auto" bodyClass="overflow-auto">
          <div className="border-b border-line px-3 py-2.5">
            <div className="mb-1.5">
              <Label>Steps</Label>
            </div>
            <Steps f={f} jobs={jobs} openJob={openJob} />
            {!f.cutout && f.project && !jobs.some((j) => j.kind === "cut" && isActive(j)) && (
              <Button small icon="scissors" className="mt-2" onClick={() => api.freshCutout(slug).then((r) => openJob(r.jobs[0].id))}>
                Start the cutout
              </Button>
            )}
          </div>
          <PicturesFolder f={f} onChange={setF} onError={setErr} />
          <div className="border-b border-line px-3 py-2.5">
            <div className="mb-1 flex items-center justify-between">
              <Label>Sections</Label>
              <div className="flex items-center gap-1.5">
                {unsaved && <Chip tone="warn">unsaved</Chip>}
                <Button small onClick={save} disabled={!marks}>
                  Save
                </Button>
              </div>
            </div>
            {marks ? (
              <div className="divide-y divide-line">
                {FIELDS.map((x) => (
                  <div key={x.id} className="flex items-center gap-2 py-1.5">
                    <span className={cx("rounded-[3px] px-[5px] text-[10px] leading-[15px] font-bold text-black/80", bgTone[x.tone])}>{x.tag}</span>
                    <span className="min-w-0 flex-1 truncate text-[12px] text-ink-2">{x.label}</span>
                    <input
                      type="number"
                      step={1 / fps}
                      min={0}
                      max={dur}
                      value={marks[x.id]}
                      onChange={(e) => change(x.id, Number(e.target.value))}
                      onBlur={save}
                      className={cx(field, "num h-[24px] w-[78px]")}
                      aria-label={`${x.label} in seconds`}
                    />
                    <Button small variant="ghost" title="Set from the playhead" onClick={() => (change(x.id, Math.round(t * fps) / fps), save())}>
                      Playhead
                    </Button>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-[12px] text-ink-3">The markers appear once the project is prepared.</div>
            )}
            <p className="mt-2 text-[11.5px] leading-snug text-ink-3">
              Transition 1 lands exactly on the hook end, transition 2 on the CTA start. The body normally starts where the hook ends; a later body start leaves a gap inside the transition.
            </p>
          </div>
          {f.sheet && (
            <div className="px-3 py-2.5">
              <div className="mb-1.5">
                <Label>Framing</Label>
              </div>
              <img src={`/media/fresh/${slug}/work/sheet.jpg`} alt="contact sheet" className="w-full rounded-[4px]" />
            </div>
          )}
        </Panel>
      </div>

      <Panel
        title={
          <span className="flex items-center gap-2">
            Timeline · hook, body, CTA
            <span className="tc font-normal text-ink-3">
              {tc(t, fps)} / {tc(dur, fps)}
            </span>
          </span>
        }
        icon="film"
        bodyClass="p-2"
      >
        {marks && dur > 0 ? (
          <MarksBar dur={dur} fps={fps} t={t} marks={marks} words={f.words_data ?? []} onSeek={seek} onChange={change} onDrop={save} />
        ) : (
          <div className="p-2 text-[12.5px] text-ink-3">The markers appear once the project is prepared.</div>
        )}
      </Panel>

      {(res || f.snaps.length > 0) && (
        <Panel
          title="Result"
          icon="share"
          bodyClass="p-3"
          actions={
            <>
              {f.ad && (
                <Chip tone="ok" title={f.ad_path ?? ""}>
                  {basename(f.ad_path)}
                </Chip>
              )}
              {f.ad_path && (
                <Button small variant="ghost" icon="folder" onClick={() => api.reveal(f.ad_path!)}>
                  Show in Explorer
                </Button>
              )}
            </>
          }
        >
          <div className="grid gap-3 lg:grid-cols-[220px_1fr]">
            <div>
              {f.ad ? (
                <video src={`/media/fresh/${slug}/ad?v=${res?.size_mb ?? ""}`} controls playsInline preload="metadata" className="aspect-[9/16] w-full rounded-[6px] bg-black" />
              ) : (
                f.final_sheet && <img src={`/media/fresh/${slug}/work/final_sheet.jpg`} alt="final sheet" className="w-full rounded-[6px]" />
              )}
            </div>
            <div className="min-w-0 space-y-3 text-[12.5px]">
              {res && (
                <div className="flex flex-wrap gap-1.5">
                  <Chip>{fmt(res.duration, 1)} s</Chip>
                  {res.loudness_after != null && <Chip tone={Math.abs(res.loudness_after + 15) < 1 ? "ok" : "warn"}>{fmt(res.loudness_after, 1)} LUFS</Chip>}
                  {res.peak_dbfs != null && <Chip>peak {fmt(res.peak_dbfs, 1)} dB</Chip>}
                  {res.size_mb != null && <Chip>{fmt(res.size_mb, 1)} MB</Chip>}
                  <Chip>{res.captions} captions</Chip>
                  <Chip tone={res.black_frames.length ? "bad" : "ok"}>{res.black_frames.length} black frames</Chip>
                </div>
              )}
              {f.snaps.length > 0 && (
                <div className="flex gap-[3px] overflow-x-auto pb-1">
                  {f.snaps.map((s) => (
                    <img key={s} src={`/media/fresh/${slug}/snap/${s}`} alt={s} title={s} className="h-[150px] w-[84px] shrink-0 rounded-[3px] bg-black object-cover" loading="lazy" />
                  ))}
                </div>
              )}
              {res && res.beats.length > 0 && (
                <table className="w-full text-[12px]">
                  <tbody>
                    {res.beats.map((b, i) => (
                      <tr key={i} className="border-b border-line last:border-b-0">
                        <td className="tc w-[60px] py-1 text-ink-3">{fmt(b.t)}</td>
                        <td className="w-[36px] py-1">
                          <Chip>{b.side}</Chip>
                        </td>
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
                <div className="flex flex-wrap gap-1">
                  {res.library_pictures.map((p) => (
                    <Chip key={p} tone="ok">
                      {p}
                    </Chip>
                  ))}
                  {res.gpt_drawings.map((g, i) => (
                    <Chip key={i} tone="warn" title={g.prompt}>
                      GPT: {basename(g.path)}
                    </Chip>
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
        </Panel>
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
    <Panel title="New fresh edit" icon="plus" bodyClass="p-3">
      <p className="mb-3 text-[12.5px] text-ink-2">One clean talking-head footage (no burned-in captions). The app prepares it, you mark hook / body / CTA, Claude edits and renders it into the Edited Ads folder beside the footage.</p>
      {err && (
        <div className="mb-3">
          <ErrorNote>{err}</ErrorNote>
        </div>
      )}
      <div className="grid gap-3 md:grid-cols-2">
        <div className="md:col-span-2">
          <Label>Footage file</Label>
          <div className="mt-1 flex gap-2">
            <input className={input} placeholder="C:\…\Footage 05.mov" value={footage} onChange={(e) => setFootage(e.target.value)} />
            <Button icon="folder" onClick={() => pickVideo().then((p) => p && setFootage(p))}>
              Browse…
            </Button>
          </div>
        </div>
        <div>
          <Label>Name (optional)</Label>
          <input className={cx(input, "mt-1")} value={name} onChange={(e) => setName(e.target.value)} placeholder={basename(footage).replace(/\.[^.]+$/, "")} />
        </div>
        <div>
          <Label>Output folder (default: Edited Ads beside the footage)</Label>
          <div className="mt-1 flex gap-2">
            <input className={input} value={outDir} onChange={(e) => setOutDir(e.target.value)} />
            <Button icon="folder" onClick={() => pickFolder().then((p) => p && setOutDir(p))}>
              Browse…
            </Button>
          </div>
        </div>
        <div className="md:col-span-2">
          <Label>Key words for Whisper (optional: product, organ, symptoms, brand)</Label>
          <input dir="auto" className={cx(input, "mt-1")} value={prompt} onChange={(e) => setPrompt(e.target.value)} />
        </div>
        <div className="md:col-span-2">
          <Label>Pictures folder (optional: transparent PNG / WebP cut-outs for this ad; default: a folder inside the project)</Label>
          <div className="mt-1 flex gap-2">
            <input className={input} placeholder="C:\…\Product\assets" value={assets} onChange={(e) => setAssets(e.target.value)} />
            <Button icon="folder" onClick={() => pickFolder().then((p) => p && setAssets(p))}>
              Browse…
            </Button>
          </div>
        </div>
      </div>
      <Button variant="primary" icon="plus" className="mt-3" disabled={!footage.trim() || busy} onClick={go}>
        {busy ? "Creating…" : "Create and prepare"}
      </Button>
    </Panel>
  );
}

export default function Fresh({ slug, openJob }: { slug?: string; openJob: (id: number) => void }) {
  const [list, setList] = useState<FreshProject[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const jobs = useJobs();
  const load = useCallback(() => api.freshList().then(setList).catch((e) => setErr(errText(e))), []);
  useEffect(() => {
    if (!slug) load();
  }, [load, slug]);
  useOnJobEnd(jobs, () => !slug && load());
  if (slug) return <Editor slug={slug} openJob={openJob} />;
  return (
    <div className="space-y-3">
      <PageHeader icon="wand" title="Fresh edits" sub="One footage, one ad in the camel style: captions, hook / body / CTA transitions, your pictures animated in front of the speaker, rendered at −15 LUFS." />
      <NewFresh
        onCreated={(s, j) => {
          if (j) openJob(j);
          location.hash = `#/fresh/${s}`;
        }}
      />
      {err && <ErrorNote>{err}</ErrorNote>}
      {list && list.length === 0 && <Empty title="No fresh edit yet" icon="wand" />}
      <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-3">
        {list?.map((f) => (
          <a key={f.slug} href={`#/fresh/${f.slug}`} className="glass block rounded-[12px] p-3 ring-2 ring-transparent transition-shadow hover:ring-sel">
            <div className="flex items-start justify-between gap-2">
              <div className="flex min-w-0 items-center gap-2.5">
                <span className="clip grid h-8 w-8 shrink-0 place-items-center rounded-[6px] bg-surface-3 text-ink-2">
                  <Icon name="film" size={15} />
                </span>
                <div className="min-w-0">
                  <div className="truncate text-[13.5px] font-semibold">{f.name}</div>
                  <div className="truncate text-[11.5px] text-ink-3" dir="auto">
                    {basename(f.footage)} · {f.duration ? clock(f.duration) : "…"}
                  </div>
                </div>
              </div>
              <Chip tone={f.ad ? "ok" : f.cutout && f.words ? "accent" : "neutral"}>{f.ad ? "rendered" : f.marks ? "ready to edit" : f.project ? "set the sections" : "preparing"}</Chip>
            </div>
            <div className="mt-3 flex gap-[3px]">
              {[f.project, f.words, f.cutout, f.ad].map((d, i) => (
                <span key={i} className={cx("h-[5px] flex-1 rounded-full", d ? "bg-ok" : "bg-well")} />
              ))}
            </div>
            <div className="mt-1 text-[10.5px] text-ink-3">project · transcript · cutout · ad</div>
          </a>
        ))}
      </div>
    </div>
  );
}
