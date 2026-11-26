import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Icon, type IconName } from "./icons";

export function cx(...parts: (string | false | null | undefined)[]) {
  return parts.filter(Boolean).join(" ");
}

/** Direction for a note that mixes English with quoted Arabic: the script most of it is written in.
 *  (Pure Arabic text such as a transcript uses dir="auto".) */
export function dirOf(text: string | null | undefined): "rtl" | "ltr" {
  const s = text ?? "";
  const ar = (s.match(/[؀-ۿ]/g) ?? []).length;
  const la = (s.match(/[A-Za-z]/g) ?? []).length;
  return ar > la ? "rtl" : "ltr";
}

/** Seconds as Final Cut timecode, HH:MM:SS:FF. */
export function tc(t: number | null | undefined, fps = 30) {
  if (t == null || !Number.isFinite(t)) return "--:--:--:--";
  const f = Math.max(0, Math.round(t * fps));
  const ff = f % fps;
  const s = Math.floor(f / fps);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(Math.floor(s / 3600))}:${p(Math.floor(s / 60) % 60)}:${p(s % 60)}:${p(ff)}`;
}

/** The shared look of text fields: an inset well, like Final Cut's inspector fields. */
export const field =
  "rounded-[5px] border border-line bg-well px-2 text-[12.5px] text-ink placeholder:text-ink-3 shadow-[inset_0_1px_2px_rgb(0_0_0/0.25)] focus:border-accent focus:outline-none";

type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "default" | "ghost" | "danger"; small?: boolean; icon?: IconName };

export function Button({ variant = "default", small, icon, className, children, ...rest }: BtnProps) {
  return (
    <button
      {...rest}
      className={cx(
        "inline-flex items-center justify-center gap-1.5 rounded-[6px] font-medium whitespace-nowrap transition-[background,filter,color] disabled:opacity-40",
        small ? "h-[24px] px-2 text-[12px]" : "h-[28px] px-3 text-[12.5px]",
        variant === "primary" && "clip bg-accent text-on-accent hover:brightness-110 active:brightness-95",
        variant === "default" && "clip bg-surface-3 text-ink hover:brightness-110 active:brightness-95",
        variant === "ghost" && "bg-transparent text-ink-2 hover:bg-surface-3 hover:text-ink",
        variant === "danger" && "clip bg-surface-3 text-bad hover:bg-bad-soft",
        className,
      )}
    >
      {icon && <Icon name={icon} size={small ? 13 : 14} />}
      {children}
    </button>
  );
}

/** A square toolbar button, lit blue when on (Final Cut's toggles). */
export function IconButton({ icon, on, label, className, size = 16, ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & { icon: IconName; on?: boolean; label: string; size?: number }) {
  return (
    <button
      {...rest}
      aria-label={label}
      title={rest.title ?? label}
      aria-pressed={on}
      className={cx(
        "grid h-[28px] w-[30px] place-items-center rounded-[6px] transition-colors",
        on ? "bg-accent/20 text-accent" : "text-ink-2 hover:bg-surface-3 hover:text-ink",
        className,
      )}
    >
      <Icon name={icon} size={size} />
    </button>
  );
}

/** A plain pane. */
export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return <section className={cx("rounded-[8px] border border-line-strong bg-surface", className)}>{children}</section>;
}

/** A pane with Final Cut's slim header bar: title on the left, actions on the right. */
export function Panel({ title, icon, actions, children, className, bodyClass }: { title: ReactNode; icon?: IconName; actions?: ReactNode; children: ReactNode; className?: string; bodyClass?: string }) {
  return (
    <section className={cx("flex min-h-0 flex-col overflow-hidden rounded-[8px] border border-line-strong bg-surface", className)}>
      <header className="flex h-[30px] shrink-0 items-center gap-2 border-b border-line bg-surface-2/60 px-2.5">
        {icon && <Icon name={icon} size={13} className="text-ink-3" />}
        <div className="min-w-0 flex-1 truncate text-[11.5px] font-semibold text-ink-2">{title}</div>
        {actions}
      </header>
      <div className={cx("min-h-0 flex-1", bodyClass)}>{children}</div>
    </section>
  );
}

/** Final Cut's segmented control (Inspector tabs, Browser view switch). */
export function Segmented<T extends string>({ value, options, onChange, className }: { value: T; options: { id: T; label: ReactNode; icon?: IconName }[]; onChange: (v: T) => void; className?: string }) {
  return (
    <div role="tablist" className={cx("inline-flex rounded-[7px] bg-well p-[2px] shadow-[inset_0_1px_2px_rgb(0_0_0/0.3)]", className)}>
      {options.map((o) => (
        <button
          key={o.id}
          role="tab"
          aria-selected={value === o.id}
          onClick={() => onChange(o.id)}
          className={cx(
            "inline-flex h-[22px] items-center gap-1.5 rounded-[5px] px-2.5 text-[12px] font-medium transition-colors",
            value === o.id ? "clip bg-surface-3 text-ink" : "text-ink-2 hover:text-ink",
          )}
        >
          {o.icon && <Icon name={o.icon} size={13} />}
          {o.label}
        </button>
      ))}
    </div>
  );
}

type Tone = "neutral" | "ok" | "warn" | "bad" | "accent" | "hook" | "body" | "cta";
const tones: Record<Tone, string> = {
  neutral: "border-line text-ink-2 bg-surface-2",
  ok: "border-ok/35 text-ok bg-ok/10",
  warn: "border-warn/35 text-warn bg-warn/10",
  bad: "border-bad/35 text-bad bg-bad/10",
  accent: "border-accent/40 text-accent bg-accent/12",
  hook: "border-hook/45 text-hook bg-hook/12",
  body: "border-body/45 text-body bg-body/12",
  cta: "border-cta/45 text-cta bg-cta/12",
};

/** A small tag, square-cornered like Final Cut's keyword and role tags. */
export function Chip({ tone = "neutral", children, title, className }: { tone?: Tone; children: ReactNode; title?: string; className?: string }) {
  return (
    <span title={title} className={cx("inline-flex h-[20px] items-center gap-1 rounded-[4px] border px-1.5 text-[11.5px] font-medium whitespace-nowrap", tones[tone], className)}>
      {children}
    </span>
  );
}

/** A coloured dot with a label: the status lights in Final Cut's background tasks. */
export function Dot({ tone = "neutral", pulse }: { tone?: Tone; pulse?: boolean }) {
  const c: Record<Tone, string> = { neutral: "bg-ink-3", ok: "bg-ok", warn: "bg-warn", bad: "bg-bad", accent: "bg-accent", hook: "bg-hook", body: "bg-body", cta: "bg-cta" };
  return <span className={cx("inline-block h-[7px] w-[7px] shrink-0 rounded-full", c[tone], pulse && "animate-pulse")} />;
}

export function Label({ children }: { children: ReactNode }) {
  return <div className="text-[10.5px] font-semibold tracking-[0.06em] text-ink-3 uppercase">{children}</div>;
}

/** A label / value row in an inspector. */
export function Prop({ label, children, className }: { label: ReactNode; children: ReactNode; className?: string }) {
  return (
    <div className={cx("grid grid-cols-[96px_minmax(0,1fr)] items-center gap-2 py-[3px]", className)}>
      <div className="truncate text-right text-[11.5px] text-ink-3">{label}</div>
      <div className="min-w-0 text-[12.5px]">{children}</div>
    </div>
  );
}

export function PageHeader({ title, sub, actions, icon }: { title: ReactNode; sub?: ReactNode; actions?: ReactNode; icon?: IconName }) {
  return (
    <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
      <div className="flex min-w-0 items-center gap-2.5">
        {icon && (
          <span className="clip grid h-9 w-9 shrink-0 place-items-center rounded-[8px] bg-surface-3 text-ink-2">
            <Icon name={icon} size={18} />
          </span>
        )}
        <div className="min-w-0">
          <h1 className="truncate text-[17px] leading-tight font-semibold tracking-tight">{title}</h1>
          {sub && <div className="mt-0.5 text-[12.5px] text-ink-2">{sub}</div>}
        </div>
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Empty({ title, children, icon = "film" }: { title: string; children?: ReactNode; icon?: IconName }) {
  return (
    <div className="rounded-[8px] border border-dashed border-line bg-surface/50 px-6 py-10 text-center">
      <Icon name={icon} size={28} className="mx-auto mb-2 text-ink-3" strokeWidth={1.3} />
      <div className="text-[14px] font-semibold">{title}</div>
      {children && <div className="mx-auto mt-1 max-w-xl text-ink-2">{children}</div>}
    </div>
  );
}

export function ErrorNote({ children }: { children: ReactNode }) {
  return (
    <div className="flex gap-2 rounded-[6px] border border-bad/40 bg-bad-soft px-3 py-2 text-[12.5px] whitespace-pre-wrap text-bad">
      <Icon name="alert" size={15} className="mt-px shrink-0" />
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}

export function Loading({ children = "Loading…" }: { children?: ReactNode }) {
  return (
    <div className="flex items-center gap-2 p-2 text-ink-3">
      <span className="spin-slow inline-block h-3.5 w-3.5 rounded-full border-2 border-ink-3/30 border-t-ink-2" />
      {children}
    </div>
  );
}
