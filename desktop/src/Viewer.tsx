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

/** The player: the picture on black with 28 px corners, glass transport controls floating over its bottom edge.
 *  Space plays or pauses; the arrow keys step one frame (Shift: ten). */
export function Viewer({
  video,
  src,
  dur,
  fps = 30,
  title,
  extra,
  className,
  placeholder,
}: {
  video: ReturnType<typeof useVideo>;
  src?: string;
  dur: number;
  fps?: number;
  title?: ReactNode;
  extra?: ReactNode;
  className?: string;
  placeholder?: ReactNode;
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

  const ctl = "press grid h-[36px] w-[36px] place-items-center rounded-full text-white/85 hover:bg-white/[0.12] hover:text-white";
  return (
    <section className={cx("viewer relative flex min-h-0 flex-col overflow-hidden rounded-[28px]", className)}>
      {(title || extra) && (
        <div className="pointer-events-none absolute inset-x-0 top-0 z-10 flex items-start justify-between gap-2 p-3">
          {title ? <div className="player-bar pointer-events-auto px-3 py-1 text-[12px] font-medium text-white/85">{title}</div> : <span />}
          {extra && <div className="pointer-events-auto">{extra}</div>}
        </div>
      )}
      <div className="relative min-h-0 flex-1">
        {src ? (
          <video ref={ref} src={src} playsInline preload="metadata" onClick={toggle} className="absolute inset-0 h-full w-full cursor-pointer object-contain" />
        ) : (
          <div className="grid h-full place-items-center text-[12px] text-white/50">{placeholder ?? "no video"}</div>
        )}
      </div>
      {/* the transport, floating over the bottom of the picture */}
      <div className="pointer-events-none absolute inset-x-0 bottom-3 z-10 flex justify-center px-3">
        <div className="player-bar pointer-events-auto flex items-center gap-1 py-1 pr-3 pl-3">
          <span className="tc w-[82px] text-[11px] text-white/70" title={`${t.toFixed(3)} s · frame ${Math.round(t * fps)}`}>
            {tc(t, fps)}
          </span>
          <button type="button" onClick={() => step(-1)} title="One frame back (←)" aria-label="One frame back" className={ctl}>
            <Icon name="stepBack" size={14} />
          </button>
          <button type="button" onClick={toggle} title="Play / pause (Space)" aria-label={playing ? "Pause" : "Play"} className={cx(ctl, "text-white")}>
            <Icon name={playing ? "pause" : "play"} size={16} />
          </button>
          <button type="button" onClick={() => step(1)} title="One frame forward (→)" aria-label="One frame forward" className={ctl}>
            <Icon name="stepFwd" size={14} />
          </button>
          <Scrub t={t} dur={dur} onSeek={seek} />
          <span className="tc w-[82px] text-right text-[11px] text-white/50">{tc(dur, fps)}</span>
        </div>
      </div>
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
      role="slider"
      aria-label="Position"
      aria-valuemin={0}
      aria-valuemax={Math.round(dur)}
      aria-valuenow={Math.round(t)}
      className="relative mx-2 h-[6px] w-[140px] cursor-pointer rounded-full bg-white/[0.18]"
      onPointerDown={(e) => {
        down.current = true;
        e.currentTarget.setPointerCapture(e.pointerId);
        onSeek(at(e.clientX));
      }}
      onPointerMove={(e) => down.current && onSeek(at(e.clientX))}
      onPointerUp={() => (down.current = false)}
    >
      <div className="absolute inset-y-0 left-0 rounded-full bg-white/85" style={{ width: `${dur ? Math.min(100, (t / dur) * 100) : 0}%` }} />
    </div>
  );
}
