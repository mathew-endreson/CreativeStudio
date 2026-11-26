import { useEffect, useMemo, useRef } from "react";
import { api, fmt, type Scan, type Segment, type SourceAnalysis, type TranscriptInfo } from "./api";
import { Icon } from "./icons";
import { Button, Chip, cx } from "./ui";

/** The transcript workflow as a strip of steps:
 *  audio/video ─▶ ffmpeg ─▶ Whisper (local) ─▶ Claude Code + darijadz ─▶ darija_lint ─▶ .txt / .srt / .json */
export function TranscriptStatus({ info, running, onRedo }: { info?: TranscriptInfo; running?: boolean; onRedo?: () => void }) {
  const st = info?.state ?? "none";
  const step = (label: string, done: boolean, active?: boolean, title?: string) => (
    <span title={title} className={cx("flex items-center gap-1 whitespace-nowrap", done ? "text-ink" : active ? "text-accent" : "text-ink-3")}>
      {done ? (
        <span className="grid h-3.5 w-3.5 place-items-center rounded-full bg-ok text-black/80">
          <Icon name="check" size={9} strokeWidth={3.5} />
        </span>
      ) : active ? (
        <span className="spin-slow inline-block h-3.5 w-3.5 rounded-full border-2 border-accent/30 border-t-accent" />
      ) : (
        <span className="h-3.5 w-3.5 rounded-full border-2 border-line" />
      )}
      {label}
    </span>
  );
  const arrow = <Icon name="chevronRight" size={11} className="shrink-0 text-ink-3" />;
  const corrected = st === "corrected";
  return (
    <div className="border-b border-line bg-surface-2/40 px-3 py-2 text-[11.5px]">
      <div className="flex flex-wrap items-center gap-x-1.5 gap-y-1">
        {step("ffmpeg + Whisper", st !== "none", false, "Whisper large-v3-turbo listens on this PC")}
        {arrow}
        {step("Claude · darijadz", corrected, running, "Claude Code corrects Whisper's text into Algerian Darija with the darijadz skill. It never hears the audio.")}
        {arrow}
        {step(corrected && info ? `darija_lint${info.lint_high ? ` · ${info.lint_high} HIGH` : " ✓"}` : "darija_lint", corrected, false, "The darijadz linter flags فصحى and other dialects")}
        {arrow}
        <span className="flex items-center gap-1">
          {(["txt", "srt", "doc"] as const).map((k) =>
            info?.files[k] ? (
              <button key={k} onClick={() => api.reveal(info.files[k]!)} title={`Show ${info.files[k]} in Explorer`} className="rounded-[4px] bg-surface-3 px-1.5 py-px font-mono text-[10.5px] text-ink-2 hover:text-ink">
                .{k === "doc" ? "json" : k}
              </button>
            ) : (
              <span key={k} className="rounded-[4px] border border-dashed border-line px-1.5 font-mono text-[10.5px] text-ink-3">.{k === "doc" ? "json" : k}</span>
            ),
          )}
        </span>
        <div className="flex-1" />
        {corrected ? (
          <Chip tone="ok" title={`${info!.changed} of ${info!.segments} segments corrected${info!.dropped ? `, ${info!.dropped} dropped as noise` : ""}`}>
            Darija ✓ {info!.changed}/{info!.segments} fixed
          </Chip>
        ) : st === "whisper" ? (
          <Chip tone="warn" title="Whisper's raw text: not corrected yet">Whisper draft</Chip>
        ) : null}
        {onRedo && st !== "none" && (
          <Button small variant="ghost" icon="sparkles" disabled={running} onClick={onRedo}>
            {corrected ? "Correct again" : "Correct the Darija"}
          </Button>
        )}
      </div>
      {corrected && info && info.unsure.length > 0 && (
        <div className="mt-1.5 flex flex-wrap items-center gap-1">
          <span className="text-ink-3">Check by ear:</span>
          {info.unsure.map((u) => (
            <Chip key={u} tone="warn">
              <bdi>{u}</bdi>
            </Chip>
          ))}
        </div>
      )}
    </div>
  );
}

const sectionOf = (t: number, a: SourceAnalysis | null) => (!a ? "none" : t < a.hook_end ? "hook" : a.cta_start != null && t >= a.cta_start ? "cta" : "body");
const underline: Record<string, string> = { hook: "decoration-hook", body: "decoration-body", cta: "decoration-cta", none: "decoration-transparent" };

/** The word-timed transcript, right to left. Click a word to go to it; the word being said is highlighted. */
export function Transcript({ segments, t, a, onSeek }: { segments: Segment[]; t: number; a: SourceAnalysis | null; onSeek: (t: number) => void }) {
  const words = useMemo(() => segments.flatMap((s) => s.words), [segments]);
  if (!words.length) return <div className="text-[12.5px] text-ink-3">No transcript yet: run Transcribe.</div>;
  return (
    <div dir="rtl" lang="ar" className="text-[16px] leading-[2.15]">
      {words.map((w, i) => {
        const on = t >= w.s && t < w.e;
        return (
          <button
            key={i}
            onClick={() => onSeek(w.s)}
            title={`${fmt(w.s)}–${fmt(w.e)} s${w.p < 0.5 ? " · unsure: check it by ear" : ""}`}
            className={cx(
              "mx-[1px] rounded-[4px] px-1 underline decoration-2 underline-offset-[7px] hover:bg-surface-3",
              underline[sectionOf(w.s, a)],
              w.p < 0.5 && "decoration-dotted",
              on && "bg-accent text-on-accent hover:bg-accent",
            )}
          >
            {w.w}
          </button>
        );
      })}
    </div>
  );
}

/** The 1 fps contact sheet as a strip: one tile per second, click to go there. */
export function SheetStrip({ slug, scan, t, onSeek }: { slug: string; scan: Scan; t: number; onSeek: (t: number) => void }) {
  const { cols, count, file } = scan.sheet;
  const W = 63, H = 112;
  const url = `/media/${slug}/work/${file.split("/").pop()}`;
  const cur = Math.min(count - 1, Math.floor(t));
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = box.current?.children[cur] as HTMLElement | undefined;
    const b = box.current;
    if (el && b && (el.offsetLeft < b.scrollLeft || el.offsetLeft + W > b.scrollLeft + b.clientWidth)) b.scrollLeft = el.offsetLeft - b.clientWidth / 2;
  }, [cur]);
  return (
    <div ref={box} className="flex gap-[3px] overflow-x-auto pb-2">
      {Array.from({ length: count }, (_, i) => (
        <button
          key={i}
          onClick={() => onSeek(i)}
          title={`${i} s`}
          className={cx("relative shrink-0 overflow-hidden rounded-[3px] ring-2", i === cur ? "ring-sel" : "ring-transparent hover:ring-ink-3")}
          style={{
            width: W,
            height: H,
            backgroundImage: `url("${url}")`,
            backgroundSize: `${cols * W}px auto`,
            backgroundPosition: `-${(i % cols) * W}px -${Math.floor(i / cols) * H}px`,
          }}
        >
          <span className="num absolute right-0 bottom-0 rounded-tl bg-black/65 px-1 text-[10px] leading-[14px] text-white">{i}s</span>
        </button>
      ))}
    </div>
  );
}
