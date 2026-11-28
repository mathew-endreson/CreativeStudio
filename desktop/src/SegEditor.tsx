import { useEffect, useMemo, useRef, useState } from "react";
import { api, fmt, frameOf, snap, type Proposal, type PSeg, type SourceData } from "./api";
import { Icon } from "./icons";
import { Button, Chip, cx, ErrorNote, Label, tc } from "./ui";

type Role = "hook" | "body" | "cta";
type Row = PSeg & { role: Role; gfx: boolean };
type Edge = { i: number; edge: "a0" | "a1" };

export const roleOf = (ad: Pick<Proposal, "body" | "cta">, i: number): Role =>
  i === ad.cta ? "cta" : ad.body.includes(i) || i > Math.min(...ad.body) ? "body" : "hook";

const F = 1 / 30;
const thumb = (slug: string, src: string, frame: number, w = 96) => `/media/${slug}/frame/${src}/${Math.max(0, frame)}.jpg?w=${w}`;

function Modal({ title, onClose, children, wide }: { title: string; onClose: () => void; children: React.ReactNode; wide?: boolean }) {
  useEffect(() => {
    const on = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-40 grid place-items-center bg-black/50 p-4 backdrop-blur-[2px]" onClick={onClose}>
      <div
        role="dialog"
        aria-label={title}
        className={cx("glass glass-strong flex max-h-[94vh] w-full flex-col overflow-hidden rounded-[24px] bg-[rgb(18_18_22/0.85)]", wide ? "max-w-[1240px]" : "max-w-[560px]")}
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex h-[44px] shrink-0 items-center gap-3 border-b border-line px-4">
          <button type="button" onClick={onClose} aria-label="Close" title="Close (Esc)" className="traffic" style={{ background: "#ff5f57" }} />
          <div className="min-w-0 flex-1 truncate text-center text-[13px] font-semibold text-ink">{title}</div>
          <span className="w-3" />
        </header>
        {children}
      </div>
    </div>
  );
}

/** The sound and the frames around one cut: where the silence is, which word it clips, what the picture shows. */
function CutInspector({ slug, row, edge, data, onSet }: { slug: string; row: Row; edge: "a0" | "a1"; data: SourceData | null; onSet: (t: number) => void }) {
  const t = row[edge];
  const f = frameOf(t);
  const W = 1.5;
  const lo = t - W, hi = t + W;
  const x = (s: number) => `${((s - lo) / (2 * W)) * 100}%`;
  const wave = useMemo(() => {
    const v = data?.curves?.rms_db;
    if (!v) return null;
    const hop = data!.curves!.rms_hop;
    const i0 = Math.max(0, Math.floor(lo / hop)), i1 = Math.min(v.length, Math.ceil(hi / hop));
    let d = "";
    for (let i = i0; i < i1; i++) {
      const px = ((i * hop - lo) / (2 * W)) * 1000;
      const py = 100 - Math.min(1, Math.max(0, (v[i] + 60) / 60)) * 100;
      d += `${d ? "L" : "M"}${px.toFixed(1)} ${py.toFixed(1)} `;
    }
    return d ? `M${(((i0 * hop - lo) / (2 * W)) * 1000).toFixed(1)} 100 L${d.slice(1)} L${((((i1 - 1) * hop - lo) / (2 * W)) * 1000).toFixed(1)} 100 Z` : null;
  }, [data, lo, hi]);
  const words = useMemo(() => (data?.words ?? []).flatMap((s) => s.words).filter((w) => w.e > lo && w.s < hi), [data, lo, hi]);
  const sil = (data?.scan?.silences ?? []).filter((s) => s.b > lo && s.a < hi);
  const cuts = (data?.scan?.cuts ?? []).filter((c) => c.t > lo && c.t < hi);
  const inSilence = sil.some((s) => t >= s.a - 0.035 && t <= s.b + 0.035);
  const onCut = cuts.some((c) => Math.abs(c.f - f) <= 1);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <Label>{edge === "a0" ? "Start" : "End"} of this segment</Label>
        <span className="tc font-semibold" title={`${fmt(t, 4)} s`}>
          {tc(t)} · f{f}
        </span>
        <Chip tone={inSilence || onCut ? "ok" : "warn"}>{inSilence ? "in a silence" : onCut ? "on an editor's cut" : "not in a silence or on a cut"}</Chip>
        <div className="flex-1" />
        {[-3, -1, 1, 3].map((n) => (
          <Button key={n} small onClick={() => onSet(snap(t + n * F))}>
            {n > 0 ? `+${n}` : n} f
          </Button>
        ))}
      </div>

      <div>
        <div className="clip relative h-[84px] cursor-pointer overflow-hidden rounded-[6px] border border-black/30 bg-audio" onPointerDown={(e) => {
          const r = e.currentTarget.getBoundingClientRect();
          onSet(snap(lo + ((e.clientX - r.left) / r.width) * 2 * W));
        }}>
          {sil.map((s, i) => (
            <div key={i} className="absolute inset-y-0 bg-black/35" style={{ left: x(s.a), width: `${((s.b - s.a) / (2 * W)) * 100}%` }} title={`silence ${fmt(s.a)}–${fmt(s.b)} s`} />
          ))}
          {wave && (
            <svg viewBox="0 0 1000 100" preserveAspectRatio="none" className="absolute inset-0 h-full w-full text-audio-wave">
              <path d={wave} fill="currentColor" opacity="0.75" />
            </svg>
          )}
          {cuts.map((c) => (
            <div key={c.f} className="absolute inset-y-0 w-px bg-ink-3" style={{ left: x(c.t) }} title={`editor's cut, frame ${c.f}`} />
          ))}
          <div className="absolute inset-y-0 left-1/2 -ml-px w-[2px] bg-playhead shadow-[0_0_0_1px_rgb(0_0_0/0.3)]" />
          {!data && <div className="absolute inset-0 grid place-items-center text-[12px] text-ink-3">loading the sound…</div>}
        </div>
        <div className="relative mt-1 h-6" dir="ltr">
          {words.map((w, i) => (
            <span key={i} className={cx("absolute top-0 -translate-x-1/2 text-[13px] whitespace-nowrap", (edge === "a0" ? w.s >= t - 0.02 : w.e <= t + 0.02) ? "text-ink" : "text-ink-3")}
              style={{ left: x((w.s + w.e) / 2) }} title={`${fmt(w.s)}–${fmt(w.e)} s`}>
              {w.w}
            </span>
          ))}
        </div>
        <div className="text-[11.5px] text-ink-3">3 seconds of voice around the cut. The dark bands are silence; click to move the cut there. Words in full colour stay in the segment.</div>
      </div>

      <div>
        <div className="flex gap-1">
          {[-3, -2, -1, 0, 1, 2, 3].map((n) => (
            <button key={n} type="button" onClick={() => onSet(snap((f + n) / 30))} title={`Cut before frame ${f + n}`}
              className={cx("relative overflow-hidden rounded-[6px] ring-2", n === 0 ? "ring-ink" : "ring-transparent hover:ring-ink-3", n === 0 && "ml-2")}>
              <img src={thumb(slug, row.src, f + n, 160)} alt={`frame ${f + n}`} className="h-[150px] w-[84px] bg-black object-cover" loading="lazy" />
              <span className="num absolute right-0 bottom-0 bg-black/65 px-1 text-[10px] leading-[14px] text-white">{f + n}</span>
            </button>
          ))}
        </div>
        <div className="mt-1 text-[11.5px] text-ink-3">
          The cut falls before the outlined frame: {edge === "a0" ? "it is the first frame of this segment" : "the frame before it is the last one of this segment"}. Click a frame to cut before it.
        </div>
      </div>
    </div>
  );
}

export function SegEditor({ slug, ad, labels, onClose, onSaved }: { slug: string; ad: Proposal; labels: Record<string, string>; onClose: () => void; onSaved: (p: Proposal) => void }) {
  const [rows, setRows] = useState<Row[]>(() => ad.segs.map((s, i) => ({ ...s, role: roleOf(ad, i), gfx: ad.body.includes(i) })));
  const [hookBeats, setHookBeats] = useState(ad.hook_beats);
  const [sel, setSel] = useState<Edge>({ i: 0, edge: "a1" });
  const [srcData, setSrcData] = useState<Record<string, SourceData>>({});
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const cur = rows[Math.min(sel.i, rows.length - 1)];

  useEffect(() => {
    if (cur && !srcData[cur.src]) api.source(slug, cur.src).then((d) => setSrcData((m) => ({ ...m, [cur.src]: d }))).catch(() => {});
  }, [cur, slug, srcData]);

  const patch = (i: number, p: Partial<Row>) => setRows((r) => r.map((x, k) => (k === i ? { ...x, ...p } : x)));
  const setEdge = (i: number, edge: "a0" | "a1", t: number) => {
    const r = rows[i];
    if (edge === "a0") patch(i, { a0: Math.max(0, Math.min(t, r.a1 - F)), v0: r.v0 != null && r.v0 < t ? null : r.v0 });
    else patch(i, { a1: Math.max(t, r.a0 + F), v1: r.v1 != null && r.v1 > t ? null : r.v1 });
  };
  const move = (i: number, d: number) => {
    const j = i + d;
    if (j < 0 || j >= rows.length) return;
    setRows((r) => {
      const c = [...r];
      [c[i], c[j]] = [c[j], c[i]];
      return c;
    });
    setSel((s) => ({ ...s, i: j }));
  };
  const total = rows.reduce((n, r) => n + (frameOf(r.a1) - frameOf(r.a0)), 0) / 30;

  const save = async () => {
    setErr(null);
    const cta = rows.findIndex((r) => r.role === "cta");
    if (rows.filter((r) => r.role === "cta").length > 1 || (cta >= 0 && cta !== rows.length - 1)) return setErr("The CTA is one segment, and it is the last one.");
    if (rows[0]?.role !== "hook") return setErr("The first segment is the hook.");
    const body = rows.map((r, i) => (i > 0 && r.role !== "hook" && r.gfx ? i : -1)).filter((i) => i >= 0);
    if (!body.length) return setErr("At least one body segment has to carry B-roll.");
    setBusy(true);
    try {
      onSaved(await api.patchProposal(slug, ad.id, {
        segs: rows.map(({ src, a0, a1, v0, v1, note }) => ({ src, a0, a1, v0, v1, note })),
        body, cta: cta >= 0 ? cta : null, hook_beats: hookBeats,
      }));
      onClose();
    } catch (e: any) {
      setErr(String(e.message || e));
    } finally {
      setBusy(false);
    }
  };

  const num = (i: number, k: "a0" | "a1" | "v0" | "v1") => (
    <input
      type="number" step={0.0333} value={rows[i][k] ?? ""} placeholder="none"
      onFocus={() => (k === "a0" || k === "a1") && setSel({ i, edge: k })}
      onChange={(e) => {
        const v = e.target.value === "" ? null : snap(parseFloat(e.target.value));
        if (k === "a0" || k === "a1") v != null && !Number.isNaN(v) && setEdge(i, k, v);
        else patch(i, { [k]: v != null && Number.isNaN(v) ? null : v } as Partial<Row>);
      }}
      className={cx("field num min-h-[32px] w-[90px] text-[12.5px]", sel.i === i && sel.edge === k && "border-sel")}
      aria-label={`${k} of segment ${i + 1}`}
    />
  );

  return (
    <Modal title={`Edit the segments of ${ad.name}`} onClose={onClose} wide>
      <div className="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)_minmax(0,640px)] overflow-hidden">
        <div className="overflow-auto border-r border-line p-3">
          <div className="mb-2 flex items-center justify-between text-[12.5px] text-ink-2">
            <span>In playing order. Times in seconds, at 30 frames a second.</span>
            <span className="num font-semibold text-ink">{fmt(total)} s</span>
          </div>
          <div className="space-y-2">
            {rows.map((r, i) => (
              <div key={i} className={cx("rounded-[14px] border-l-[3px] bg-well p-3 ring-2", r.role === "hook" ? "border-hook" : r.role === "cta" ? "border-cta" : "border-body", sel.i === i ? "ring-sel" : "ring-transparent")} onClick={() => sel.i !== i && setSel({ i, edge: sel.edge })}>
                <div className="flex items-center gap-2">
                  <span className="num w-4 text-[12px] text-ink-3">{i + 1}</span>
                  <select value={r.role} onChange={(e) => patch(i, { role: e.target.value as Role, gfx: e.target.value === "body" })}
                    className="field min-h-[32px] text-[12.5px]" aria-label={`Role of segment ${i + 1}`}>
                    <option value="hook">Hook</option>
                    <option value="body">Body</option>
                    <option value="cta">CTA</option>
                  </select>
                  <Chip>{labels[r.src] ?? r.src}</Chip>
                  <span className="num text-[12px] text-ink-3">{fmt((frameOf(r.a1) - frameOf(r.a0)) / 30)} s</span>
                  <div className="flex-1" />
                  {r.role !== "hook" && (
                    <label className="flex items-center gap-1 text-[12px] text-ink-2" title="Graphics may sit behind him in this segment (it needs a cutout)">
                      <input type="checkbox" checked={r.gfx} onChange={(e) => patch(i, { gfx: e.target.checked })} /> B-roll
                    </label>
                  )}
                  <Button small variant="ghost" disabled={i === 0} onClick={() => move(i, -1)} title="Move up" aria-label="Move up"><Icon name="up" size={13} /></Button>
                  <Button small variant="ghost" disabled={i === rows.length - 1} onClick={() => move(i, 1)} title="Move down" aria-label="Move down"><Icon name="down" size={13} /></Button>
                  <Button small variant="danger" disabled={rows.length <= 2} onClick={() => { setRows((x) => x.filter((_, k) => k !== i)); setSel({ i: Math.max(0, i - 1), edge: "a1" }); }} title="Remove this segment" aria-label="Remove this segment"><Icon name="trash" size={13} /></Button>
                </div>
                <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-[12px] text-ink-3">
                  start {num(i, "a0")} end {num(i, "a1")}
                  <span title="First clean picture time: the picture is held from it back to the start">picture from {num(i, "v0")}</span>
                  <span title="Time of the last clean frame: the picture is held from it to the end">until {num(i, "v1")}</span>
                </div>
                <div dir="auto" className="mt-1 text-[14px]">{r.said || r.text}</div>
              </div>
            ))}
          </div>
          <label className="mt-3 flex items-center gap-2 text-[13px] text-ink-2">
            <input type="checkbox" checked={hookBeats} onChange={(e) => setHookBeats(e.target.checked)} />
            The hook is lifted from a body: it keeps its graphics and its cutout
          </label>
        </div>
        <div className="overflow-auto p-3">
          {cur && <CutInspector slug={slug} row={cur} edge={sel.edge} data={srcData[cur.src] ?? null} onSet={(t) => setEdge(Math.min(sel.i, rows.length - 1), sel.edge, t)} />}
        </div>
      </div>
      <footer className="flex items-center gap-3 border-t border-line px-4 py-2.5">
        <div className="min-w-0 flex-1">{err && <ErrorNote>{err}</ErrorNote>}</div>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="primary" icon="check" disabled={busy} onClick={save}>
          {busy ? "Saving…" : "Save the segments"}
        </Button>
      </footer>
    </Modal>
  );
}

/** A rough preview: the segments played one after another from their sources. Cuts only: no transition,
 *  no hold, no graphics. Enough to hear whether the ad reads as one argument. */
export function Preview({ slug, ad, labels, onClose }: { slug: string; ad: Proposal; labels: Record<string, string>; onClose: () => void }) {
  const srcs = useMemo(() => [...new Set(ad.segs.map((s) => s.src))], [ad]);
  const vids = useRef<Record<string, HTMLVideoElement | null>>({});
  const [idx, setIdx] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [pos, setPos] = useState(0);
  const state = useRef({ idx: 0, playing: false });
  const offs = useMemo(() => ad.segs.reduce<number[]>((a, _s, i) => [...a, i ? a[i - 1] + (ad.segs[i - 1].a1 - ad.segs[i - 1].a0) : 0], []), [ad]);
  const total = ad.segs.reduce((n, s) => n + s.a1 - s.a0, 0);

  const start = (i: number) => {
    Object.values(vids.current).forEach((v) => v?.pause());
    if (i >= ad.segs.length) {
      state.current = { idx: 0, playing: false };
      setIdx(0);
      setPlaying(false);
      return;
    }
    const v = vids.current[ad.segs[i].src];
    if (!v) return;
    v.currentTime = ad.segs[i].a0 + 0.001;
    state.current = { idx: i, playing: true };
    setIdx(i);
    setPlaying(true);
    void v.play();
  };

  useEffect(() => {
    let raf = 0;
    const tick = () => {
      const { idx: i, playing: on } = state.current;
      const s = ad.segs[i];
      const v = s && vids.current[s.src];
      if (v && on) {
        setPos(offs[i] + Math.max(0, v.currentTime - s.a0));
        if (v.currentTime >= s.a1 - 0.005) start(i + 1);
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [ad, offs]); // eslint-disable-line react-hooks/exhaustive-deps

  const seg = ad.segs[idx];
  return (
    <Modal title={`Rough preview of ${ad.name}`} onClose={onClose}>
      <div className="p-4">
        <div className="viewer relative mx-auto aspect-[9/16] w-[270px] overflow-hidden rounded-[18px]">
          {srcs.map((k) => (
            <video key={k} ref={(el) => { vids.current[k] = el; }} src={`/media/${slug}/src/${k}`} preload="auto" playsInline
              className={cx("absolute inset-0 h-full w-full", seg?.src === k ? "opacity-100" : "opacity-0")} />
          ))}
        </div>
        <div dir="auto" className="font-caption mx-auto mt-3 min-h-[52px] max-w-[440px] text-center text-[17px] leading-snug font-black">{seg?.said || seg?.text}</div>
        <div className="mt-3 flex h-[24px] gap-[3px] rounded-[10px] bg-well p-[3px]">
          {ad.segs.map((s, i) => (
            <button key={i} type="button" onClick={() => start(i)} title={`${roleOf(ad, i)} · ${labels[s.src] ?? s.src} ${fmt(s.a0)}–${fmt(s.a1)} s`}
              className={cx("clip h-full", roleOf(ad, i) === "hook" ? "bg-hook" : roleOf(ad, i) === "cta" ? "bg-cta" : "bg-body", i !== idx && "opacity-45", i === idx && "ring-2 ring-ink")}
              style={{ width: `${((s.a1 - s.a0) / total) * 100}%` }} />
          ))}
        </div>
        <div className="mt-3 flex items-center justify-between">
          <span className="tc text-[12px] text-ink-2">{tc(pos)} / {tc(total)}</span>
          <Button variant="primary" icon={playing ? "pause" : "play"} onClick={() => (playing ? (Object.values(vids.current).forEach((v) => v?.pause()), (state.current.playing = false), setPlaying(false)) : start(idx))}>
            {playing ? "Pause" : "Play"}
          </Button>
        </div>
        <p className="mt-3 text-[12.5px] text-ink-3">Cuts only, straight from the source ads: no transition, no picture hold, no graphics. The built ad adds those.</p>
      </div>
    </Modal>
  );
}

export { thumb };
