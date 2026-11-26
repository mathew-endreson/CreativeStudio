import { useCallback, useEffect, useRef, useState } from "react";
import { api, fmt, frameOf, snap, type Analysis as AnalysisT, type Liftable, type ProductDetail, type SourceAnalysis, type SourceData } from "./api";
import { Icon } from "./icons";
import { ActiveJobs, isActive, useJobs } from "./Jobs";
import { thumb } from "./SegEditor";
import Timeline, { type Field } from "./Timeline";
import { SheetStrip, Transcript, TranscriptStatus } from "./Transcript";
import { useVideo, Viewer } from "./Viewer";
import { Button, Chip, cx, dirOf, Dot, Empty, ErrorNote, field, Label, Loading, Panel, Prop, Segmented, tc } from "./ui";

const clamp = (x: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, x));
const F = 1 / 30;

function TimeField({
  label, tag, tone, value, edited, optional, onChange, onCommit, onPlayhead,
}: {
  label: string; tag: string; tone: string; value: number | null; edited: boolean; optional?: boolean;
  onChange: (v: number | null) => void; onCommit: () => void; onPlayhead: () => void;
}) {
  const [text, setText] = useState(value == null ? "" : value.toFixed(4));
  const focused = useRef(false);
  useEffect(() => {
    if (!focused.current) setText(value == null ? "" : value.toFixed(4));
  }, [value]);
  return (
    <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-2 gap-y-0.5 py-1.5">
      <div className="flex min-w-0 items-center gap-1.5 text-[12px] text-ink-2">
        <span className={cx("rounded-[3px] px-[5px] text-[10px] leading-[15px] font-bold text-black/80", tone)}>{tag}</span>
        <span className="truncate">{label}</span>
        {edited && <Chip tone="accent" title="You set this by hand. A new analysis keeps it.">by you</Chip>}
      </div>
      <span className="tc text-right text-[10.5px] text-ink-3">{value == null ? "" : tc(value)}</span>
      <div className="col-span-2 flex items-center gap-1.5">
        <input
          type="number"
          step={0.0333}
          min={0}
          value={text}
          placeholder={optional ? "none" : ""}
          onFocus={() => (focused.current = true)}
          onChange={(e) => {
            setText(e.target.value);
            const v = parseFloat(e.target.value);
            if (!Number.isNaN(v)) onChange(snap(v));
            else if (optional && e.target.value === "") onChange(null);
          }}
          onBlur={() => {
            focused.current = false;
            setText(value == null ? "" : value.toFixed(4));
            onCommit();
          }}
          onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
          className={cx(field, "num h-[24px] w-[96px]")}
          aria-label={`${label} in seconds`}
        />
        <span className="num w-11 text-[11px] text-ink-3">{value == null ? "" : `f${frameOf(value)}`}</span>
        <Button small variant="ghost" onClick={onPlayhead} title="Use the playhead's time" className="ml-auto">
          Set to playhead
        </Button>
      </div>
    </div>
  );
}

function Section({ title, children, right }: { title: string; children: React.ReactNode; right?: React.ReactNode }) {
  return (
    <div className="border-b border-line px-3 py-2.5 last:border-b-0">
      <div className="mb-1 flex items-center justify-between gap-2">
        <Label>{title}</Label>
        {right}
      </div>
      {children}
    </div>
  );
}

type LeftTab = "lines" | "transcript" | "lift";

function SourceView({
  slug, data, a, lift, setField, save, saving, fixing, onFix,
}: {
  slug: string; data: SourceData; a: SourceAnalysis | null; lift: Liftable[];
  setField: (f: Field, v: number | null) => void; save: () => void; saving: string;
  fixing: boolean; onFix: () => void;
}) {
  const video = useVideo();
  const { t, seek, playRange } = video;
  const scan = data.scan!;
  const dur = scan.duration;
  const [openLift, setOpenLift] = useState<string | null>(null);
  const [tab, setTab] = useState<LeftTab>(a?.lines?.length ? "lines" : "transcript");
  const issues: { tone: "warn" | "bad"; text: string }[] = [
    ...data.state.issues.map((x) => ({ tone: "bad" as const, text: x })),
    ...scan.black.map((b) => ({ tone: "warn" as const, text: `black frames ${b.f0}–${b.f1} (${fmt(b.t0)}–${fmt(b.t1)} s)` })),
    ...(a?.defects ?? []).map((d) => ({ tone: "warn" as const, text: `${d.kind.replace("_", " ")}${d.a != null ? ` at ${fmt(d.a)} s` : ""}: ${d.note}` })),
  ];
  const drag = (f: Field, v: number) => {
    setField(f, v);
    seek(v);
  };
  const tabs: { id: LeftTab; label: string; icon: "list" | "text" | "sparkles" }[] = [
    { id: "lines", label: `Lines${a?.lines ? ` ${a.lines.length}` : ""}`, icon: "list" },
    { id: "transcript", label: "Transcript", icon: "text" },
    ...(lift.length ? [{ id: "lift" as const, label: `Liftable ${lift.length}`, icon: "sparkles" as const }] : []),
  ];

  return (
    <div className="space-y-[3px]">
      <div className="grid gap-[3px] xl:h-[clamp(470px,64vh,720px)] xl:grid-cols-[minmax(0,1fr)_minmax(270px,330px)_minmax(300px,360px)] grid-cols-[minmax(260px,330px)_minmax(0,1fr)]">
        {/* the browser side: lines, transcript, liftable hooks */}
        <Panel
          className="order-3 col-span-2 h-[380px] xl:order-none xl:col-span-1 xl:h-auto"
          title={<Segmented value={tab} onChange={setTab} options={tabs} />}
          bodyClass="overflow-auto"
        >
          {tab === "lines" &&
            (!a?.lines?.length ? (
              <div className="p-3 text-ink-3">No lines yet: they come with the analysis.</div>
            ) : (
              (a.lines ?? []).map((l, i) => {
                const on = t >= l.a0 && t < l.a1;
                return (
                  <div key={i} className={cx("flex items-start gap-2 border-b border-line px-2.5 py-1.5 last:border-b-0", on && "bg-sel/10 shadow-[inset_2px_0_0_var(--sel)]")}>
                    <button className="tc flex w-[92px] shrink-0 items-center gap-1 pt-0.5 text-left text-[11px] text-ink-2 hover:text-accent" onClick={() => playRange(l.a0, l.a1)} title="Play this line">
                      <Icon name="play" size={10} />
                      {fmt(l.a0)}–{fmt(l.a1)}
                    </button>
                    <Chip tone={l.role}>{l.role}</Chip>
                    <div className="min-w-0 flex-1">
                      <div dir="auto" className="text-[14px] leading-snug" title={l.said ? `Whisper wrote: ${l.text}` : "raw Whisper text: no clean wording yet"}>
                        {l.said || l.text}
                      </div>
                      {(l.note || l.v0 != null || l.v1 != null) && (
                        <div dir={dirOf(l.note)} className="text-[11.5px] text-ink-3">
                          {l.v0 != null && `clean picture from ${fmt(l.v0, 3)} s. `}
                          {l.v1 != null && `clean picture until ${fmt(l.v1, 3)} s. `}
                          {l.note}
                        </div>
                      )}
                      {l.can_open_body && (
                        <Chip tone="body" className="mt-0.5" title="A body can start on this line under another hook">
                          can open a body
                        </Chip>
                      )}
                    </div>
                  </div>
                );
              })
            ))}
          {tab === "transcript" && (
            <>
              <TranscriptStatus info={data.transcript} running={fixing} onRedo={onFix} />
              <div className="px-3 py-2">
                <Transcript segments={data.words} t={t} a={a} onSeek={seek} />
              </div>
            </>
          )}
          {tab === "lift" && (
            <div className="space-y-1.5 p-2">
              {lift.map((l) => (
                <button
                  key={l.id}
                  onClick={() => {
                    setOpenLift(openLift === l.id ? null : l.id);
                    playRange(l.a0, l.a1);
                  }}
                  className={cx("block w-full rounded-[6px] border p-2 text-left", openLift === l.id ? "border-sel bg-sel/10" : "border-line bg-surface-2 hover:border-ink-3")}
                  title="Play this line"
                >
                  <div className="flex items-center gap-2 text-[12px]">
                    <Icon name="play" size={10} className="text-sel" />
                    <span className="font-semibold">{l.label}</span>
                    <Chip>{l.kind}</Chip>
                    <span className="tc ml-auto text-[11px] text-ink-3">
                      {fmt(l.a0)}–{fmt(l.a1)} s
                    </span>
                  </div>
                  <div dir="auto" className="font-caption mt-1 text-[16px] leading-relaxed font-black" title={l.said ? `Whisper wrote: ${l.text}` : undefined}>
                    {l.said || l.text}
                  </div>
                  {openLift === l.id && (
                    <div dir={dirOf(l.why)} className="mt-1 text-[12.5px] text-ink-2">
                      {l.why}
                    </div>
                  )}
                </button>
              ))}
            </div>
          )}
        </Panel>

        <Viewer video={video} src={`/media/${slug}/src/${data.key}`} dur={dur} title={<>Viewer · <span className="font-mono">{data.key}</span>{a?.label ? ` · ${a.label}` : ""}</>} className="h-[560px] xl:h-auto" />

        {/* the inspector */}
        <Panel title="Inspector" icon="inspector" className="h-[560px] xl:h-auto" bodyClass="overflow-auto"
          actions={
            <span className={cx("text-[11px]", saving.startsWith("error") ? "text-bad" : "text-ink-3")}>
              {saving === "saving" ? "saving…" : saving === "saved" ? "saved" : saving.startsWith("error") ? saving : ""}
            </span>
          }
        >
          {a ? (
            <>
              <div className="border-b border-line px-3 py-2.5">
                <div className="flex items-center gap-2">
                  <span className="clip grid h-8 w-8 shrink-0 place-items-center rounded-[6px] bg-body text-[12px] font-bold text-white">{data.key}</span>
                  <div className="min-w-0 flex-1 truncate text-[14px] font-semibold">{a.label}</div>
                </div>
                <div dir={dirOf(a.summary)} className="mt-1.5 text-[12.5px] leading-snug text-ink-2">
                  {a.summary}
                </div>
              </div>
              <Section title="Sections">
                <div className="divide-y divide-line">
                  <TimeField label="Hook end" tag="H" tone="bg-hook" value={a.hook_end} edited={!!a.edited?.includes("hook_end")}
                    onChange={(v) => v != null && setField("hook_end", v)} onCommit={save} onPlayhead={() => { setField("hook_end", snap(t)); save(); }} />
                  <TimeField label="Hook hold" tag="h" tone="bg-hook" value={a.hook_hold} edited={!!a.edited?.includes("hook_hold")} optional
                    onChange={(v) => setField("hook_hold", v)} onCommit={save} onPlayhead={() => { setField("hook_hold", snap(t)); save(); }} />
                  <TimeField label="Body start" tag="B" tone="bg-body" value={a.body_start} edited={!!a.edited?.includes("body_start")}
                    onChange={(v) => v != null && setField("body_start", v)} onCommit={save} onPlayhead={() => { setField("body_start", snap(t)); save(); }} />
                  <TimeField label="CTA start" tag="C" tone="bg-cta" value={a.cta_start} edited={!!a.edited?.includes("cta_start")} optional
                    onChange={(v) => setField("cta_start", v)} onCommit={save} onPlayhead={() => { setField("cta_start", snap(t)); save(); }} />
                </div>
              </Section>
              <Section title="Clip">
                {a.offer_group && (
                  <Prop label="Offer group">
                    <Chip title="Offer group: only sources of one group are paired">{a.offer_group}</Chip>
                  </Prop>
                )}
                {a.hook_kind && <Prop label="Hook">
                  <Chip tone="hook" title="What kind of hook this ad opens on">
                    {a.hook_kind}
                    {a.hook_needs_payoff ? " + payoff" : ""}
                  </Chip>
                </Prop>}
                {a.hook_flash && (
                  <Prop label="Hook flash">
                    <span className="num">
                      f{a.hook_flash.f0}–{a.hook_flash.f1}
                      {a.hook_flash.white ? ", white" : ""}
                    </span>
                  </Prop>
                )}
                {a.shoot && (
                  <Prop label="Shoot">
                    <span dir={dirOf(a.shoot)}>{a.shoot}</span>
                  </Prop>
                )}
                <Prop label="Duration">
                  <span className="tc">{tc(dur)}</span>
                </Prop>
                {a.notes && <div dir={dirOf(a.notes)} className="mt-1 text-[12px] text-ink-3">{a.notes}</div>}
              </Section>
              <Section title="Flagged" right={issues.length > 0 && <Chip tone="warn">{issues.length}</Chip>}>
                <Flagged issues={issues} />
              </Section>
            </>
          ) : (
            <>
              <div className="px-3 py-3 text-[12.5px] text-ink-3">Not analysed yet: run the analysis to get hook, body and CTA, the lines and the liftable hooks.</div>
              <Section title="Flagged">
                <Flagged issues={issues} />
              </Section>
            </>
          )}
        </Panel>
      </div>

      <Panel title={<span className="flex items-center gap-2">Timeline <span className="tc font-normal text-ink-3">{tc(t)} / {tc(dur)}</span></span>} icon="film" bodyClass="px-2 pt-2 pb-2.5">
        <Timeline dur={dur} t={t} scan={scan} curves={data.curves} a={a} lift={lift} onSeek={seek} onDrag={drag} onDrop={save} onPlayRange={playRange} />
      </Panel>

      <Panel title="Filmstrip · one frame a second" icon="grid" bodyClass="px-2 pt-2">
        <SheetStrip slug={slug} scan={scan} t={t} onSeek={seek} />
      </Panel>
    </div>
  );
}

function Flagged({ issues }: { issues: { tone: "warn" | "bad"; text: string }[] }) {
  if (issues.length === 0)
    return (
      <div className="flex items-center gap-1.5 text-[12px] text-ok">
        <Icon name="check" size={13} /> Nothing flagged: audio phase and frames look fine.
      </div>
    );
  return (
    <div className="space-y-1">
      {issues.map((x, i) => (
        <div key={i} className={cx("flex gap-1.5 rounded-[5px] px-2 py-1 text-[12px]", x.tone === "bad" ? "bg-bad-soft text-bad" : "bg-warn/10 text-ink")}>
          <Icon name="alert" size={12} className={cx("mt-0.5 shrink-0", x.tone === "bad" ? "text-bad" : "text-warn")} />
          <span dir={dirOf(x.text)} className="min-w-0 flex-1">
            {x.text}
          </span>
        </div>
      ))}
    </div>
  );
}

/** A source in the browser: its poster frame and name, outlined yellow when selected (Final Cut's selection). */
function ClipTile({ slug, k, label, name, dur, on, analysed, onClick }: { slug: string; k: string; label: string; name: string; dur?: number | null; on: boolean; analysed: boolean; onClick: () => void }) {
  const [broken, setBroken] = useState(false);
  return (
    <button onClick={onClick} className="group w-[104px] shrink-0 text-left" title={name}>
      <div className={cx("relative h-[150px] overflow-hidden rounded-[5px] bg-black ring-2 ring-offset-0", on ? "ring-sel" : "ring-transparent group-hover:ring-ink-3")}>
        {!broken ? (
          <img src={thumb(slug, k, 45, 160)} alt="" loading="lazy" onError={() => setBroken(true)} className="h-full w-full object-cover" />
        ) : (
          <div className="grid h-full place-items-center text-white/40">
            <Icon name="film" size={22} />
          </div>
        )}
        <span className="absolute top-1 left-1 rounded-[3px] bg-black/70 px-1 font-mono text-[10px] leading-[14px] text-white">{k}</span>
        {dur != null && <span className="tc absolute right-1 bottom-1 rounded-[3px] bg-black/70 px-1 text-[9.5px] leading-[14px] text-white">{fmt(dur, 1)}s</span>}
        <span className={cx("absolute right-0 bottom-0 left-0 h-[3px]", analysed ? "bg-body" : "bg-transparent")} />
      </div>
      <div className={cx("mt-1 truncate text-[11.5px]", on ? "font-semibold text-ink" : "text-ink-2")}>{label || name}</div>
      <bdi className="block truncate text-[10.5px] text-ink-3">{name}</bdi>
    </button>
  );
}

export default function Analysis({ p, reload, openJob }: { p: ProductDetail; reload: () => void; openJob: (id: number) => void }) {
  const slug = p.slug;
  const [analysis, setAnalysis] = useState<AnalysisT | null | undefined>(undefined);
  const [sel, setSel] = useState(p.sources[0]?.key ?? "");
  const [data, setData] = useState<SourceData | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [saving, setSaving] = useState("");
  const [ask, setAsk] = useState("");
  const jobs = useJobs(slug);
  const active = jobs.filter(isActive);
  const latest = useRef<AnalysisT | null>(null);
  const dirty = useRef(false);
  latest.current = analysis ?? null;

  const loadAnalysis = useCallback(() => {
    api.analysis(slug).then(setAnalysis).catch((e) => setErr(String(e.message || e)));
  }, [slug]);
  const loadSource = useCallback(() => {
    if (sel) api.source(slug, sel).then(setData).catch((e) => setErr(String(e.message || e)));
  }, [slug, sel]);

  useEffect(loadAnalysis, [loadAnalysis]);
  useEffect(() => {
    setData(null);
    loadSource();
  }, [loadSource]);

  // when a job of this product ends, what it wrote is on disk: read it again
  const ended = jobs.filter((j) => !isActive(j)).map((j) => `${j.id}${j.status}`).join(",");
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    reload();
    loadAnalysis();
    loadSource();
  }, [ended]); // eslint-disable-line react-hooks/exhaustive-deps

  const run = async (step: string, force = false) => {
    setErr(null);
    try {
      const r = await api.run(slug, step, { force });
      if (r.jobs.length) openJob(r.jobs[r.jobs.length - 1].id);
      else if (r.note) setErr(r.note);
    } catch (e: any) {
      setErr(String(e.message || e));
    }
  };

  const setField = (f: Field, v: number | null) => {
    setAnalysis((a) => {
      if (!a || !a.sources[sel]) return a;
      const s = { ...a.sources[sel] };
      const dur = data?.scan?.duration ?? 9999;
      if (v != null) {
        if (f === "hook_end") v = clamp(v, F, s.body_start);
        if (f === "hook_hold") v = clamp(v, F, s.hook_end);
        if (f === "body_start") v = clamp(v, s.hook_end, (s.cta_start ?? dur) - F);
        if (f === "cta_start") v = clamp(v, s.body_start + F, dur - F);
        v = snap(v);
      } else if (f === "hook_end" || f === "body_start") return a;
      if (s[f] === v) return a;
      (s as any)[f] = v;
      if (f === "hook_end" && s.hook_hold != null && s.hook_hold > s.hook_end) s.hook_hold = s.hook_end;
      dirty.current = true;
      return { ...a, sources: { ...a.sources, [sel]: s } };
    });
  };

  const save = useCallback(() => {
    // after the state update that preceded this call has landed
    setTimeout(async () => {
      if (!dirty.current || !latest.current) return;
      dirty.current = false;
      setSaving("saving");
      try {
        setAnalysis(await api.saveAnalysis(slug, latest.current));
        setSaving("saved");
      } catch (e: any) {
        setSaving(`error: ${e.message || e}`);
      }
    }, 0);
  }, [slug]);

  const n = p.sources.length;
  const count = (k: "copy" | "words" | "scan") => p.sources.filter((s) => s[k]).length;
  const fixing = active.some((j) => j.kind === "darija");
  const fixOne = async (key: string) => {
    setErr(null);
    try {
      const r = await api.run(slug, "darija", { keys: [key], force: true });
      if (r.jobs.length) openJob(r.jobs[r.jobs.length - 1].id);
      else if (r.note) setErr(r.note);
    } catch (e: any) {
      setErr(String(e.message || e));
    }
  };
  const analyzing = active.some((j) => j.kind === "analyze");
  const a = analysis && sel ? (analysis.sources[sel] ?? null) : null;
  const lift = analysis ? (analysis.liftable ?? []).filter((l) => l.src === sel) : [];
  const lastRun = [...jobs].find((j) => j.kind === "analyze" && j.status === "failed");
  const stat = (label: string, done: number) => (
    <span className="flex items-center gap-1.5 text-[12px] text-ink-2">
      <Dot tone={done === n ? "ok" : "warn"} />
      {label} <span className="num text-ink">{done}/{n}</span>
    </span>
  );

  return (
    <div className="space-y-[3px]">
      {/* the analysis toolbar */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 glass rounded-[12px] px-3 py-2">
        {stat("copies", count("copy"))}
        {stat("transcripts", count("words"))}
        {stat("Darija ✓", p.sources.filter((s) => s.darija === "corrected").length)}
        {stat("scans", count("scan"))}
        <span className="flex items-center gap-1.5 text-[12px] text-ink-2">
          <Dot tone={analysis ? "ok" : "neutral"} />
          {analysis ? `analysis: ${Object.keys(analysis.sources).length} sources, ${(analysis.liftable ?? []).length} liftable hooks` : "no analysis yet"}
        </span>
        <div className="flex-1" />
        <details className="relative">
          <summary className="flex h-[28px] cursor-pointer list-none items-center gap-1 rounded-[6px] px-2.5 text-[12.5px] text-ink-2 hover:bg-surface-3 hover:text-ink">
            <Icon name="refresh" size={13} /> Redo a step <Icon name="chevronDown" size={12} />
          </summary>
          <div className="absolute right-0 z-20 mt-1 w-56 glass rounded-[12px] p-1">
            <button className="block w-full rounded-[5px] px-2 py-1.5 text-left hover:bg-accent hover:text-on-accent" onClick={() => run("prepare", true)}>Check the copies again</button>
            <button className="block w-full rounded-[5px] px-2 py-1.5 text-left hover:bg-accent hover:text-on-accent" onClick={() => run("transcribe", true)}>Transcribe again (then correct)</button>
            <button className="block w-full rounded-[5px] px-2 py-1.5 text-left hover:bg-accent hover:text-on-accent" onClick={() => run("darija", true)}>Correct the Darija again</button>
            <button className="block w-full rounded-[5px] px-2 py-1.5 text-left hover:bg-accent hover:text-on-accent" onClick={() => run("scan", true)}>Scan again</button>
          </div>
        </details>
        <Button
          variant="primary"
          icon="sparkles"
          disabled={analyzing}
          onClick={() => {
            if (!analysis || window.confirm("Analyze again? Claude rewrites analysis.json. The times you set by hand are kept.")) void run("analyze");
          }}
        >
          {analyzing ? "Analyzing…" : analysis ? "Analyze again with Claude" : "Analyze with Claude"}
        </Button>
      </div>

      {analysis && (
        <form
          className="flex items-center gap-2 glass rounded-[10px] px-2 py-1.5"
          onSubmit={async (e) => {
            e.preventDefault();
            if (!ask.trim()) return;
            setErr(null);
            try {
              const r = await api.amend(slug, ask);
              setAsk("");
              openJob(r.jobs[0].id);
            } catch (x: any) {
              setErr(String(x.message || x));
            }
          }}
        >
          <Icon name="sparkles" size={14} className="ml-1 shrink-0 text-ink-3" />
          <input value={ask} onChange={(e) => setAsk(e.target.value)} dir="auto" aria-label="A change to the analysis"
            placeholder="Something wrong in the analysis? Say it here: “the CTA of V6 starts on the cut at 31.27”, “L6 is not a hook”"
            className={cx(field, "h-[28px] min-w-0 flex-1")} />
          <Button type="submit" disabled={!ask.trim() || active.some((j) => j.kind === "amend")}>Ask Claude to change it</Button>
        </form>
      )}

      {err && <ErrorNote>{err}</ErrorNote>}
      {!analyzing && lastRun && jobs[0]?.id === lastRun.id && (
        <ErrorNote>
          The last analysis failed: {lastRun.error}{" "}
          <button className="underline" onClick={() => openJob(lastRun.id)}>Open its log</button>
        </ErrorNote>
      )}
      <ActiveJobs jobs={active} openJob={openJob} />

      {/* the browser: every source as a clip */}
      <Panel title={`Browser · ${n} clip${n === 1 ? "" : "s"}`} icon="film" bodyClass="overflow-x-auto">
        <div className="flex gap-3 px-3 pt-2.5 pb-2">
          {p.sources.map((s) => {
            const sa = analysis?.sources[s.key];
            return (
              <ClipTile
                key={s.key}
                slug={slug}
                k={s.key}
                label={sa?.label ?? s.label ?? ""}
                name={s.file?.split(/[\\/]/).pop()?.replace(/\.[a-z0-9]+$/i, "") ?? s.key}
                dur={s.duration}
                on={sel === s.key}
                analysed={!!sa}
                onClick={() => setSel(s.key)}
              />
            );
          })}
        </div>
      </Panel>

      {!data ? (
        <Loading>Loading the source…</Loading>
      ) : !data.state.copy ? (
        <Empty title="This source has no copy yet">Run the analysis: it first makes the 48 kHz copy, the transcript and the scan.</Empty>
      ) : !data.scan ? (
        <Empty title="This source is not scanned yet">
          Run the analysis: it first transcribes and scans what is missing, then Claude reads the result.
        </Empty>
      ) : (
        <SourceView key={data.key} slug={slug} data={data} a={a} lift={lift} setField={setField} save={save} saving={saving} fixing={fixing} onFix={() => void fixOne(data.key)} />
      )}

      {analysis && (
        <Panel title="Project notes" icon="list" bodyClass="grid gap-4 p-3 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
          <div>
            <Label>Offer groups</Label>
            <div className="mt-1.5 space-y-1">
              {(analysis.offer_groups ?? []).map((g) => (
                <div key={g.id} className="flex items-baseline gap-2">
                  <Chip>{g.id}</Chip>
                  <span dir={dirOf(g.label)} className="min-w-0 flex-1">{g.label}</span>
                  <span className="font-mono text-[11.5px] text-ink-3">{g.sources.join(" ")}</span>
                </div>
              ))}
            </div>
            {analysis.notes && <div dir={dirOf(analysis.notes)} className="mt-2 text-[12.5px] text-ink-2">{analysis.notes}</div>}
          </div>
          <div>
            <Label>Duplicates</Label>
            <div className="mt-1.5 space-y-1 text-[13px]">
              {!analysis.duplicates?.length && <div className="text-ink-3">None found: no two sources share a hook or a body.</div>}
              {(analysis.duplicates ?? []).map((d, i) => (
                <div key={i} className="flex items-baseline gap-2">
                  <span className="font-mono text-[11.5px] text-ink-3">{d.sources.join(" = ")}</span>
                  <span dir={dirOf(d.note)} className="min-w-0 flex-1">{d.note}</span>
                </div>
              ))}
            </div>
          </div>
        </Panel>
      )}
    </div>
  );
}
