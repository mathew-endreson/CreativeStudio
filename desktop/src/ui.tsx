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

/** The shared look of text fields: an inset glass well. */
export const field =
  "glass-well rounded-[7px] px-2 text-[12.5px] text-ink placeholder:text-ink-3 focus:outline-none focus:ring-2 focus:ring-accent/40";

type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "default" | "ghost" | "danger"; small?: boolean; icon?: IconName };

/** Buttons are pieces of glass; the primary one is amber glass with a glow, Resolve's one strong colour. */
export function Button({ variant = "default", small, icon, className, children, ...rest }: BtnProps) {
  return (
    <button
      {...rest}
      className={cx(
        "inline-flex items-center justify-center gap-1.5 rounded-[8px] font-medium whitespace-nowrap transition-[background,filter,color,transform,box-shadow] duration-150 active:scale-[0.985] disabled:opacity-40 disabled:active:scale-100",
        small ? "h-[24px] px-2 text-[12px]" : "h-[28px] px-3 text-[12.5px]",
        variant === "primary" && "glass-accent text-on-accent hover:brightness-110",
        variant === "default" && "glass-2 text-ink hover:bg-surface-3",
        variant === "ghost" && "bg-transparent text-ink-2 hover:bg-surface-2 hover:text-ink",
        variant === "danger" && "glass-2 text-bad hover:bg-bad-soft",
        className,
      )}
    >
      {icon && <Icon name={icon} size={small ? 13 : 14} />}
      {children}
    </button>
  );
}

/** A square toolbar button, lit amber when on. */
export function IconButton({ icon, on, label, className, size = 16, ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & { icon: IconName; on?: boolean; label: string; size?: number }) {
  return (
    <button
      {...rest}
      aria-label={label}
      title={rest.title ?? label}
      aria-pressed={on}
      className={cx(
        "grid h-[28px] w-[30px] place-items-center rounded-[8px] transition-colors duration-150",
        on ? "bg-accent/18 text-accent shadow-[inset_0_0_0_1px_color-mix(in_srgb,var(--accent)_40%,transparent)]" : "text-ink-2 hover:bg-surface-2 hover:text-ink",
        className,
      )}
    >
      <Icon name={icon} size={size} />
    </button>
  );
}

/** A pane of glass. */
export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return <section className={cx("glass rounded-[12px]", className)}>{children}</section>;
}

/** A pane with a slim header bar: title on the left, actions on the right. */
export function Panel({ title, icon, actions, children, className, bodyClass }: { title: ReactNode; icon?: IconName; actions?: ReactNode; children: ReactNode; className?: string; bodyClass?: string }) {
  return (
    <section className={cx("glass flex min-h-0 flex-col overflow-hidden rounded-[12px]", className)}>
      <header className="flex h-[30px] shrink-0 items-center gap-2 border-b border-line bg-white/[0.03] px-2.5">
        {icon && <Icon name={icon} size={13} className="text-ink-3" />}
        <div className="min-w-0 flex-1 truncate text-[11.5px] font-semibold text-ink-2">{title}</div>
        {actions}
      </header>
      <div className={cx("min-h-0 flex-1", bodyClass)}>{children}</div>
    </section>
  );
}

/** A segmented control: a glass well with the active segment raised. */
export function Segmented<T extends string>({ value, options, onChange, className }: { value: T; options: { id: T; label: ReactNode; icon?: IconName }[]; onChange: (v: T) => void; className?: string }) {
  return (
    <div role="tablist" className={cx("glass-well inline-flex rounded-[9px] p-[3px]", className)}>
      {options.map((o) => (
        <button
          key={o.id}
          role="tab"
          aria-selected={value === o.id}
          onClick={() => onChange(o.id)}
          className={cx(
            "inline-flex h-[22px] items-center gap-1.5 rounded-[7px] px-2.5 text-[12px] font-medium transition-[background,color,box-shadow] duration-150",
            value === o.id ? "glass-2 text-ink" : "text-ink-2 hover:text-ink",
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
  neutral: "border-line-strong text-ink-2 bg-surface-2",
  ok: "border-ok/35 text-ok bg-ok/12",
  warn: "border-warn/35 text-warn bg-warn/12",
  bad: "border-bad/35 text-bad bg-bad/12",
  accent: "border-accent/40 text-accent bg-accent/14",
  hook: "border-hook/45 text-hook bg-hook/14",
  body: "border-body/45 text-body bg-body/14",
  cta: "border-cta/45 text-cta bg-cta/14",
};

/** A small tag: a chip of tinted glass. */
export function Chip({ tone = "neutral", children, title, className }: { tone?: Tone; children: ReactNode; title?: string; className?: string }) {
  return (
    <span title={title} className={cx("inline-flex h-[20px] items-center gap-1 rounded-[6px] border px-1.5 text-[11.5px] font-medium whitespace-nowrap backdrop-blur-sm", tones[tone], className)}>
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
          <span className="glass-2 grid h-9 w-9 shrink-0 place-items-center rounded-[10px] text-accent">
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
    <div className="rounded-[12px] border border-dashed border-line-strong bg-surface/40 px-6 py-10 text-center backdrop-blur-md">
      <Icon name={icon} size={28} className="mx-auto mb-2 text-ink-3" strokeWidth={1.3} />
      <div className="text-[14px] font-semibold">{title}</div>
      {children && <div className="mx-auto mt-1 max-w-xl text-ink-2">{children}</div>}
    </div>
  );
}

export function ErrorNote({ children }: { children: ReactNode }) {
  return (
    <div className="flex gap-2 rounded-[9px] border border-bad/40 bg-bad-soft px-3 py-2 text-[12.5px] whitespace-pre-wrap text-bad backdrop-blur-md">
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
