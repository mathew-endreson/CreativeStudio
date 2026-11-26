import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { snap } from "./api";
import { Icon } from "./icons";
import { cx, tc } from "./ui";

/** A video's clock, frame-accurate seeking, "play this range", and play / pause. */
export function useVideo() {
  const ref = useRef<HTMLVideoElement>(null);
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const stopAt = useRef<number | null>(null);
  useEffect(() => {
    let raf = 0;
    const tick = () => {
      const v = ref.current;
      if (v) {
        if (stopAt.current != null && v.currentTime >= stopAt.current) {
          v.pause();
          stopAt.current = null;
        }
        setT((old) => (Math.abs(old - v.currentTime) > 0.004 ? v.currentTime : old));
        setPlaying((p) => (p === !v.paused ? p : !v.paused));
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);
  const seek = useCallback((x: number) => {
    const v = ref.current;
    stopAt.current = null;
    if (v) v.currentTime = Math.max(0, x) + 0.001; // inside the frame, not on its edge
    setT(Math.max(0, x));
  }, []);
  const playRange = useCallback((a: number, b: number) => {
    const v = ref.current;
    if (!v) return;
    v.currentTime = a + 0.001;
    stopAt.current = b;
    void v.play();
  }, []);
  const toggle = useCallback(() => {
    const v = ref.current;
    if (!v) return;
    stopAt.current = null;
    if (v.paused) void v.play();
    else v.pause();
  }, []);
  return { ref, t, playing, seek, playRange, toggle };
}

const typing = (el: EventTarget | null) => {
  const e = el as HTMLElement | null;
  if (!e) return false;
  return /^(INPUT|TEXTAREA|SELECT|BUTTON)$/.test(e.tagName) || e.isContentEditable || e.getAttribute("role") === "slider";
};

/** Final Cut's viewer: the picture on black, a transport bar, the timecode in the middle.
 *  Space plays or pauses; the arrow keys step one frame (Shift: ten). */
export function Viewer({
  video, src, dur, fps = 30, title, extra, className, placeholder,
}: {
  video: ReturnType<typeof useVideo>; src?: string; dur: number; fps?: number; title?: ReactNode; extra?: ReactNode; className?: string; placeholder?: ReactNode;
}) {
  const { ref, t, playing, seek, toggle } = video;
  const step = useCallback((n: number) => seek(snap(Math.min(dur, Math.max(0, t + n / fps)))), [seek, t, dur, fps]);
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      if (typing(e.target) || e.ctrlKey || e.metaKey || e.altKey || e.defaultPrevented) return;
      if (e.key === " ") {
        e.preventDefault();
        toggle();
      } else if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
        e.preventDefault();
        step((e.key === "ArrowLeft" ? -1 : 1) * (e.shiftKey ? 10 : 1));
      } else if (e.key === "Home") {
        e.preventDefault();
        seek(0);
      } else if (e.key === "End") {
        e.preventDefault();
        seek(dur);
      }
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, [toggle, step, seek, dur]);

  return (
    <section className={cx("glass flex min-h-0 flex-col overflow-hidden rounded-[12px]", className)}>
      <header className="flex h-[30px] shrink-0 items-center gap-2 border-b border-line bg-surface-2/60 px-2.5">
        <Icon name="eye" size={13} className="text-ink-3" />
        <div className="min-w-0 flex-1 truncate text-[11.5px] font-semibold text-ink-2">{title ?? "Viewer"}</div>
        {extra}
      </header>
      <div className="viewer relative grid min-h-0 flex-1 place-items-center">
        {src ? (
          <video ref={ref} src={src} playsInline preload="metadata" onClick={toggle} className="absolute inset-0 h-full w-full cursor-pointer object-contain p-2" />
        ) : (
          <div className="text-[12px] text-white/50">{placeholder ?? "no video"}</div>
        )}
      </div>
      {/* the transport bar */}
      <div className="flex h-[40px] shrink-0 items-center gap-1 border-t border-line px-2">
        <div className="tc w-[84px] text-[10.5px] text-ink-3">{tc(dur, fps)}</div>
        <div className="flex flex-1 items-center justify-center gap-0.5">
          <button onClick={() => step(-1)} title="One frame back (←)" aria-label="One frame back" className="grid h-7 w-8 place-items-center rounded-[5px] text-ink-2 hover:bg-surface-3 hover:text-ink">
            <Icon name="stepBack" size={14} />
          </button>
          <button onClick={toggle} title="Play / pause (Space)" aria-label={playing ? "Pause" : "Play"} className="grid h-7 w-9 place-items-center rounded-[5px] text-ink hover:bg-surface-3">
            <Icon name={playing ? "pause" : "play"} size={16} />
          </button>
          <button onClick={() => step(1)} title="One frame forward (→)" aria-label="One frame forward" className="grid h-7 w-8 place-items-center rounded-[5px] text-ink-2 hover:bg-surface-3 hover:text-ink">
            <Icon name="stepFwd" size={14} />
          </button>
        </div>
        <div className="tc w-[84px] rounded-[4px] bg-well px-1.5 py-0.5 text-right text-[11.5px] text-ink shadow-[inset_0_1px_2px_rgb(0_0_0/0.3)]" title={`${t.toFixed(3)} s · frame ${Math.round(t * fps)}`}>
          {tc(t, fps)}
        </div>
      </div>
      {/* a thin scrub bar under the transport */}
      <Scrub t={t} dur={dur} onSeek={seek} />
    </section>
  );
}

function Scrub({ t, dur, onSeek }: { t: number; dur: number; onSeek: (t: number) => void }) {
  const bar = useRef<HTMLDivElement>(null);
  const down = useRef(false);
  const at = (x: number) => {
    const r = bar.current!.getBoundingClientRect();
    return snap(Math.min(1, Math.max(0, (x - r.left) / r.width)) * dur);
  };
  return (
    <div
      ref={bar}
      className="relative h-[6px] shrink-0 cursor-pointer bg-well"
      onPointerDown={(e) => {
        down.current = true;
        e.currentTarget.setPointerCapture(e.pointerId);
        onSeek(at(e.clientX));
      }}
      onPointerMove={(e) => down.current && onSeek(at(e.clientX))}
      onPointerUp={() => (down.current = false)}
    >
      <div className="absolute inset-y-0 left-0 bg-accent/70" style={{ width: `${dur ? Math.min(100, (t / dur) * 100) : 0}%` }} />
    </div>
  );
}
