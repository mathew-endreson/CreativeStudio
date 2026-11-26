import { useMemo, useRef, type PointerEvent as RPointerEvent, type ReactNode } from "react";
import { fmt, frameOf, snap, type Curves, type Liftable, type Scan, type SourceAnalysis } from "./api";
import { cx, tc } from "./ui";

export type Field = "hook_end" | "hook_hold" | "body_start" | "cta_start";

type Props = {
  dur: number;
  t: number;
  scan: Scan;
  curves: Curves | null;
  a: SourceAnalysis | null;
  lift: Liftable[];
  onSeek: (t: number) => void;
  onDrag: (f: Field, t: number) => void;
  onDrop: () => void;
  onPlayRange: (a: number, b: number) => void;
};

const GUTTER = 76;

function Row({ label, h, children }: { label: string; h: number; children: ReactNode }) {
  return (
    <>
      <div className="flex items-center justify-end pr-2.5 text-[10.5px] font-medium text-ink-3" style={{ height: h }}>
        {label}
      </div>
      <div className="relative" style={{ height: h }}>
        {children}
      </div>
    </>
  );
}

const titleTone: Record<string, string> = { orange: "border-hook bg-hook/15", green: "border-ok bg-ok/15", white: "border-ink-3 bg-ink-3/10" };
const short = (s: number) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

/** A 20 ms RMS curve as a filled, mirrored waveform: -60 dB is the centre line, 0 dB fills the lane. */
export function useWave(curves: Curves | null) {
  return useMemo(() => {
    if (!curves?.rms_db?.length) return null;
    const v = curves.rms_db;
    const step = Math.max(1, Math.floor(v.length / 1400));
    const top: string[] = [];
    const bot: string[] = [];
    for (let i = 0; i < v.length; i += step) {
      let m = -90;
      for (let k = i; k < Math.min(v.length, i + step); k++) m = Math.max(m, v[k]);
      const h = Math.min(1, Math.max(0, (m + 60) / 60)) * 48;
      top.push(`L${i} ${(50 - h).toFixed(1)}`);
      bot.unshift(`L${i} ${(50 + h).toFixed(1)}`);
    }
    return { d: `M0 50 ${top.join(" ")} L${v.length} 50 ${bot.join(" ")} Z`, n: v.length };
  }, [curves]);
}

export default function Timeline({ dur, t, scan, curves, a, lift, onSeek, onDrag, onDrop, onPlayRange }: Props) {
  const track = useRef<HTMLDivElement>(null);
  const skim = useRef<HTMLDivElement>(null);
  const skimTag = useRef<HTMLDivElement>(null);
  const drag = useRef<Field | null>(null);
  const pct = (x: number) => `${Math.min(100, Math.max(0, (x / dur) * 100))}%`;
  const span = (x0: number, x1: number, min = 0) => ({ left: pct(x0), width: `max(${min}px, ${((Math.max(x1, x0) - x0) / dur) * 100}%)` });

  const timeAt = (clientX: number) => {
    const r = track.current!.getBoundingClientRect();
    return snap(Math.min(1, Math.max(0, (clientX - r.left) / r.width)) * dur);
  };

  // the skimmer follows the pointer without re-rendering the lanes
  const moveSkim = (clientX: number | null) => {
    const el = skim.current, tag = skimTag.current, tr = track.current;
    if (!el || !tag || !tr) return;
    const r = tr.getBoundingClientRect();
    if (clientX == null || clientX < r.left || clientX > r.right) {
      el.style.opacity = "0";
      return;
    }
    const x = clientX - r.left;
    el.style.opacity = "1";
    el.style.left = `${x}px`;
    tag.textContent = tc(timeAt(clientX));
    tag.style.left = x > r.width - 90 ? "auto" : "4px";
    tag.style.right = x > r.width - 90 ? "4px" : "auto";
  };

  const wave = useWave(curves);

  const handle = (f: Field, at: number | null | undefined, tone: string, tag: string) =>
    at == null ? null : (
      <div
        key={f}
        role="slider"
        aria-label={f.replace("_", " ")}
        aria-valuenow={at}
        tabIndex={0}
        title={`${f.replace("_", " ")}: ${fmt(at, 4)} s (frame ${frameOf(at)}). Drag, or use the arrow keys.`}
        className={cx("absolute top-0 bottom-0 z-20 -ml-[6px] w-[13px] cursor-ew-resize touch-none", tone)}
        style={{ left: pct(at) }}
        onPointerDown={(e: RPointerEvent<HTMLDivElement>) => {
          e.stopPropagation();
          e.currentTarget.setPointerCapture(e.pointerId);
          drag.current = f;
        }}
        onPointerMove={(e) => drag.current === f && onDrag(f, timeAt(e.clientX))}
        onPointerUp={(e) => {
          if (drag.current === f) {
            e.currentTarget.releasePointerCapture(e.pointerId);
            drag.current = null;
            onDrop();
          }
        }}
        onKeyDown={(e) => {
          if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
            e.preventDefault();
            onDrag(f, snap(at + (e.key === "ArrowLeft" ? -1 : 1) / 30));
            onDrop();
          }
        }}
      >
        <div className={cx("absolute top-[18px] bottom-0 left-[5px] w-[3px] rounded-sm bg-current shadow-[0_0_0_1px_rgb(0_0_0/0.35)]", f === "hook_hold" && "opacity-60")} />
        {/* a marker flag like Final Cut's markers */}
        <div className="absolute top-[1px] left-1/2 -translate-x-1/2 rounded-[3px] bg-current px-[5px] text-[10px] leading-[15px] font-bold shadow-[0_1px_2px_rgb(0_0_0/0.4)]">
          <span className="text-black/80">{tag}</span>
        </div>
      </div>
    );

  const ticks = [];
  for (let s = 0; s <= dur; s++) ticks.push(s);
  const bodyEnd = a ? (a.cta_start ?? dur) : dur;

  return (
    <div className="select-none">
      {/* click anywhere on the lanes to seek; the overlay only measures and carries the playhead, the skimmer and the handles */}
      <div
        className="relative grid cursor-pointer gap-y-[3px] rounded-[6px] bg-well py-1 pr-3"
        style={{ gridTemplateColumns: `${GUTTER}px minmax(0,1fr)` }}
        onPointerDown={(e) => {
          if (e.clientX >= track.current!.getBoundingClientRect().left) onSeek(timeAt(e.clientX));
        }}
        onPointerMove={(e) => moveSkim(e.clientX)}
        onPointerLeave={() => moveSkim(null)}
      >
        <div className="pointer-events-none absolute top-0 right-3 bottom-0 z-10 [&>[role=slider]]:pointer-events-auto" style={{ left: GUTTER }} ref={track}>
          {/* skimmer */}
          <div ref={skim} className="absolute top-0 bottom-0 z-30 w-px bg-skim opacity-0 transition-opacity duration-75">
            <div ref={skimTag} className="tc absolute top-[2px] rounded-[3px] bg-skim px-1 text-[10px] leading-[14px] whitespace-nowrap text-white" />
          </div>
          {/* playhead */}
          <div className="absolute top-0 bottom-0 z-30 -ml-px w-[2px] bg-playhead shadow-[0_0_0_1px_rgb(0_0_0/0.3)]" style={{ left: pct(t) }}>
            <div className="absolute -top-px left-1/2 h-0 w-0 -translate-x-1/2 border-x-[6px] border-t-[8px] border-x-transparent border-t-playhead" />
          </div>
          {a && handle("hook_end", a.hook_end, "text-hook", "H")}
          {a && handle("hook_hold", a.hook_hold, "text-hook", "h")}
          {a && handle("body_start", a.body_start, "text-body", "B")}
          {a && handle("cta_start", a.cta_start, "text-cta", "C")}
        </div>

        <Row label="" h={18}>
          <div className="absolute inset-x-0 top-0 bottom-0 border-b border-line">
            {ticks.map((s) => (
              <div key={s} className="absolute bottom-0" style={{ left: pct(s) }}>
                <div className={cx("w-px bg-ink-3", s % 5 === 0 ? "h-[7px]" : "h-[3px]")} />
                {s % 5 === 0 && <div className="tc absolute bottom-[8px] left-[3px] text-[9.5px] text-ink-3">{short(s)}</div>}
              </div>
            ))}
          </div>
        </Row>

        <Row label="burned in" h={16}>
          {scan.titles.map((w, i) => (
            <div
              key={i}
              className={cx("absolute inset-y-[2px] rounded-[3px] border", titleTone[w[6]] ?? "border-ink-3")}
              style={span(w[0], w[1], 3)}
              title={`${w[6]} box found by the scan, ${fmt(w[0])}–${fmt(w[1])} s, x ${w[2]}–${w[4]}, y ${w[3]}–${w[5]}`}
            />
          ))}
          {a?.busy?.map((b, i) => (
            <div key={`b${i}`} className="hatch absolute inset-y-[2px] rounded-[3px] text-bad/70" style={span(b.a, b.b, 3)} title={`busy (${b.side}) ${fmt(b.a)}–${fmt(b.b)} s: ${b.what}`} />
          ))}
        </Row>

        <Row label="storyline" h={34}>
          {a ? (
            <>
              <div className="clip absolute inset-y-0 flex items-center overflow-hidden rounded-[5px] border border-black/30 bg-hook px-2 text-[11.5px] font-semibold text-black/80" style={span(0, a.hook_end)}>
                Hook
              </div>
              <div className="hatch absolute inset-y-[6px] text-ink-3/50" style={span(a.hook_end, a.body_start)} title="the hook's own flash" />
              <div className="clip absolute inset-y-0 flex items-center overflow-hidden rounded-[5px] border border-black/30 bg-body px-2 text-[11.5px] font-semibold text-white" style={span(a.body_start, bodyEnd)}>
                Body
              </div>
              {a.cta_start != null && (
                <div className="clip absolute inset-y-0 flex items-center overflow-hidden rounded-[5px] border border-black/30 bg-cta px-2 text-[11.5px] font-semibold text-white" style={span(a.cta_start, dur)}>
                  CTA
                </div>
              )}
            </>
          ) : (
            <div className="absolute inset-0 flex items-center rounded-[5px] border border-dashed border-line px-2 text-[11.5px] text-ink-3">
              not analysed yet: hook, body and CTA appear here after the analysis
            </div>
          )}
        </Row>

        {a && (
          <Row label="lines" h={18}>
            {(a.lines ?? []).map((l, i) => (
              <div
                key={i}
                className={cx(
                  "absolute inset-y-[1px] rounded-[3px] border border-black/25",
                  l.role === "hook" ? "bg-hook/45" : l.role === "cta" ? "bg-cta/45" : l.can_open_body ? "bg-body/70" : "bg-body/35",
                )}
                style={span(l.a0, l.a1, 2)}
                title={`${l.role} line ${fmt(l.a0)}–${fmt(l.a1)} s${l.can_open_body ? " · a body can start here" : ""}${l.note ? ` · ${l.note}` : ""}`}
              />
            ))}
            {lift.map((l) => (
              <button
                key={l.id}
                className="absolute bottom-0 z-20 h-[5px] rounded-full bg-sel"
                style={span(l.a0, l.a1, 4)}
                title={`liftable hook "${l.label}" ${fmt(l.a0)}–${fmt(l.a1)} s. Click to play it.`}
                onPointerDown={(e) => {
                  e.stopPropagation();
                  onPlayRange(l.a0, l.a1);
                }}
              />
            ))}
          </Row>
        )}

        <Row label="voice" h={46}>
          <div className="clip absolute inset-0 overflow-hidden rounded-[5px] border border-black/30 bg-audio">
            {scan.silences.map((s, i) => (
              <div key={i} className="absolute inset-y-0 bg-black/35" style={span(s.a, s.b, 2)} title={`silence ${fmt(s.a)}–${fmt(s.b)} s (${s.dur} s): a place to cut`} />
            ))}
            {wave && (
              <svg viewBox={`0 0 ${wave.n} 100`} preserveAspectRatio="none" className="absolute inset-0 h-full w-full text-audio-wave">
                <path d={wave.d} fill="currentColor" opacity="0.9" />
              </svg>
            )}
          </div>
        </Row>

        <Row label="flashes, cuts" h={14}>
          <div className="absolute inset-0 rounded-[3px] bg-surface-2/60">
            {scan.cuts.map((c) => (
              <div key={c.f} className="absolute inset-y-0.5 w-px bg-ink-2" style={{ left: pct(c.t) }} title={`editor's cut at ${fmt(c.t, 3)} s (frame ${c.f})`} />
            ))}
            {scan.black.map((b) => (
              <div key={b.f0} className="absolute inset-y-0 bg-black ring-1 ring-ink-3" style={span(b.t0, b.t1, 3)} title={`black frames ${b.f0}–${b.f1}`} />
            ))}
            {scan.flashes.map((f) => (
              <div
                key={f.f0}
                className={cx("absolute inset-y-0 rounded-[2px] bg-[#f5c518]", f.white && "ring-1 ring-white")}
                style={span(f.t0, f.t1, 4)}
                title={`${f.white ? "white " : ""}${f.kind.replace("_", " ")} at ${fmt(f.t0, 3)} s (frames ${f.f0}–${f.f1}, luma ${Math.round(f.peak_luma)})`}
              />
            ))}
          </div>
        </Row>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-ink-3" style={{ paddingLeft: GUTTER }}>
        <span className="flex items-center gap-1.5">
          <i className="inline-block h-2.5 w-3 rounded-[2px] bg-audio ring-1 ring-black/30" /> voice
        </span>
        <span className="flex items-center gap-1.5">
          <i className="inline-block h-2.5 w-3 rounded-[2px] bg-black/50 ring-1 ring-audio" /> silence (a place to cut)
        </span>
        <span className="flex items-center gap-1.5">
          <i className="inline-block h-2.5 w-1.5 rounded-[2px] bg-[#f5c518]" /> flash
        </span>
        <span className="flex items-center gap-1.5">
          <i className="inline-block h-2.5 w-px bg-ink-2" /> editor's cut
        </span>
        <span className="flex items-center gap-1.5">
          <i className="inline-block h-2.5 w-3 rounded-[2px] border border-hook" /> title found by colour
        </span>
        {a && (
          <>
            <span className="flex items-center gap-1.5">
              <i className="hatch inline-block h-2.5 w-3 rounded-[2px] text-bad" /> busy window
            </span>
            <span className="flex items-center gap-1.5">
              <i className="inline-block h-[5px] w-3 rounded-full bg-sel" /> liftable hook
            </span>
            <span>Drag the H, B, C markers to move the hook end, body start and CTA start.</span>
          </>
        )}
        <span className="flex items-center gap-1.5">
          <i className="inline-block h-2.5 w-px bg-skim" /> skimmer
        </span>
      </div>
    </div>
  );
}
