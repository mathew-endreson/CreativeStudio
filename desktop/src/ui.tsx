import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from "react";
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

/** Seconds as timecode, HH:MM:SS:FF. */
export function tc(t: number | null | undefined, fps = 30) {
  if (t == null || !Number.isFinite(t)) return "--:--:--:--";
  const f = Math.max(0, Math.round(t * fps));
  const ff = f % fps;
  const s = Math.floor(f / fps);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(Math.floor(s / 3600))}:${p(Math.floor(s / 60) % 60)}:${p(s % 60)}:${p(ff)}`;
}

/** The shared look of text fields: a solid inset well with 14 px corners. */
export const field = "field";

type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "default" | "ghost" | "danger"; small?: boolean; icon?: IconName };

/** Buttons are glass pills; the primary one is the single filled accent pill of its screen. */
export function Button({ variant = "default", small, icon, className, children, ...rest }: BtnProps) {
  return (
    <button
      type={rest.type ?? "button"}
      {...rest}
      className={cx(
        "press inline-flex items-center justify-center gap-1.5 rounded-full font-medium whitespace-nowrap disabled:opacity-40 disabled:active:scale-100",
        small ? "h-[32px] px-3 text-[12.5px]" : "h-[36px] px-4 text-[13px]",
        variant === "primary" && "pill-accent text-on-accent hover:brightness-110",
        variant === "default" && "glass-pill text-ink hover:bg-white/[0.1]",
        variant === "ghost" && "bg-transparent text-ink-2 hover:bg-hover hover:text-ink",
        variant === "danger" && "bg-transparent text-bad hover:bg-bad-soft",
        className,
      )}
    >
      {icon && <Icon name={icon} size={small ? 13 : 14} />}
      {children}
    </button>
  );
}

/** A round icon-only button with an accessible label; a lighter glass pill when on. */
export function IconButton({ icon, on, label, className, size = 16, ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & { icon: IconName; on?: boolean; label: string; size?: number }) {
  return (
    <button
      type="button"
      {...rest}
      aria-label={label}
      title={rest.title ?? label}
      aria-pressed={on}
      className={cx("press grid h-[36px] w-[36px] place-items-center rounded-full", on ? "glass-active text-ink" : "text-ink-2 hover:bg-hover hover:text-ink", className)}
    >
      <Icon name={icon} size={size} />
    </button>
  );
}

/** Solid content surface, 22 px corners. */
export function Card({ children, className, ...rest }: HTMLAttributes<HTMLElement> & { children: ReactNode; className?: string }) {
  return (
    <section {...rest} className={cx("rounded-[22px] border border-line bg-surface", className)}>
      {children}
    </section>
  );
}

/** A floating glass layer: sidebar, toolbars, inspector, floating bars, card strips. `img` is the darker recipe
 *  for glass lying on footage; `strong` the 40 px blur of the login card. */
export function Glass({ children, className, img, strong, ...rest }: HTMLAttributes<HTMLDivElement> & { children?: ReactNode; className?: string; img?: boolean; strong?: boolean }) {
  return (
    <div {...rest} className={cx(img ? "glass-img" : "glass", strong && "glass-strong", "rounded-[24px]", className)}>
      {children}
    </div>
  );
}

/** A content pane with a plain title row; `glass` for the ones that float (an inspector, a bin). */
export function Panel({ title, icon, actions, children, className, bodyClass, glass }: { title: ReactNode; icon?: IconName; actions?: ReactNode; children: ReactNode; className?: string; bodyClass?: string; glass?: boolean }) {
  return (
    <section className={cx("flex min-h-0 flex-col overflow-hidden rounded-[22px]", glass ? "glass" : "border border-line bg-surface", className)}>
      <header className="flex h-[44px] shrink-0 items-center gap-2 px-4">
        {icon && <Icon name={icon} size={14} className="text-ink-3" />}
        <div className="min-w-0 flex-1 truncate text-[13px] font-semibold text-ink">{title}</div>
        {actions}
      </header>
      <div className={cx("min-h-0 flex-1", bodyClass)}>{children}</div>
    </section>
  );
}

/** A segmented control: a glass pill with the active segment as a lighter pill. */
export function Segmented<T extends string>({ value, options, onChange, className, small }: { value: T; options: { id: T; label: ReactNode; icon?: IconName }[]; onChange: (v: T) => void; className?: string; small?: boolean }) {
  return (
    <div role="tablist" className={cx("glass-pill inline-flex p-[3px]", className)}>
      {options.map((o) => (
        <button
          key={o.id}
          type="button"
          role="tab"
          aria-selected={value === o.id}
          onClick={() => onChange(o.id)}
          className={cx(
            "press inline-flex items-center gap-1.5 rounded-full font-medium",
            small ? "h-[26px] px-3 text-[12px]" : "h-[30px] px-3.5 text-[12.5px]",
            value === o.id ? "glass-active text-ink" : "text-ink-2 hover:text-ink",
          )}
        >
          {o.icon && <Icon name={o.icon} size={13} />}
          {o.label}
        </button>
      ))}
    </div>
  );
}

export type Tone = "neutral" | "ok" | "warn" | "bad" | "accent" | "info" | "hook" | "body" | "cta";
const dotColor: Record<Tone, string> = {
  neutral: "bg-muted",
  ok: "bg-ok",
  warn: "bg-warn",
  bad: "bg-bad",
  accent: "bg-info",
  info: "bg-info",
  hook: "bg-hook",
  body: "bg-body",
  cta: "bg-cta",
};

/** A 7 px status dot. */
export function Dot({ tone = "neutral", pulse }: { tone?: Tone; pulse?: boolean }) {
  return <span className={cx("inline-block h-[7px] w-[7px] shrink-0 rounded-full", dotColor[tone], pulse && "animate-pulse")} />;
}

/** Status as plain text with its dot: never a filled badge. */
export function Status({ tone = "neutral", children, title, className, pulse }: { tone?: Tone; children: ReactNode; title?: string; className?: string; pulse?: boolean }) {
  return (
    <span title={title} className={cx("inline-flex items-center gap-1.5 text-[12px] whitespace-nowrap text-ink-2", className)}>
      <Dot tone={tone} pulse={pulse} />
      {children}
    </span>
  );
}
/** The old name of Status, kept so every screen reads the same. */
export const Chip = Status;

export function Label({ children }: { children: ReactNode }) {
  return <div className="text-[11px] font-medium tracking-[0.02em] text-ink-3">{children}</div>;
}

/** A label / value row in an inspector. */
export function Prop({ label, children, className }: { label: ReactNode; children: ReactNode; className?: string }) {
  return (
    <div className={cx("grid grid-cols-[104px_minmax(0,1fr)] items-center gap-3 py-[5px]", className)}>
      <div className="truncate text-[12px] text-ink-3">{label}</div>
      <div className="num min-w-0 text-[13px] text-ink">{children}</div>
    </div>
  );
}

/** The screen's toolbar: a floating glass row with the title on the left and the controls on the right. */
export function Toolbar({ title, sub, children, className, back }: { title?: ReactNode; sub?: ReactNode; children?: ReactNode; className?: string; back?: string }) {
  return (
    <header className={cx("glass mb-[10px] flex min-h-[56px] flex-wrap items-center gap-3 rounded-[24px] px-4 py-2", className)} data-tauri-drag-region>
      {back && (
        <a href={back} className="press grid h-[36px] w-[36px] shrink-0 place-items-center rounded-full text-ink-2 hover:bg-hover hover:text-ink" aria-label="Back">
          <Icon name="chevronLeft" size={18} />
        </a>
      )}
      {(title || sub) && (
        <div className="min-w-0 flex-1">
          {title && <h1 className="truncate text-[17px] leading-tight font-semibold tracking-tight">{title}</h1>}
          {sub && <div className="mt-0.5 truncate text-[12px] text-ink-3">{sub}</div>}
        </div>
      )}
      {children && <div className="ml-auto flex flex-wrap items-center gap-2">{children}</div>}
    </header>
  );
}

/** Kept for screens that still call it: the same toolbar. */
export function PageHeader({ title, sub, actions }: { title: ReactNode; sub?: ReactNode; actions?: ReactNode; icon?: IconName }) {
  return (
    <Toolbar title={title} sub={sub}>
      {actions}
    </Toolbar>
  );
}

/** A glass search pill. */
export function Search({ value, onChange, placeholder = "Search", className }: { value: string; onChange: (v: string) => void; placeholder?: string; className?: string }) {
  return (
    <label className={cx("glass-pill flex h-[36px] items-center gap-2 px-3", className)}>
      <Icon name="search" size={14} className="shrink-0 text-ink-3" />
      <input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} dir="auto" aria-label={placeholder} className="w-[160px] bg-transparent text-[13px] text-ink placeholder:text-ink-4 focus:outline-none" />
      {value && (
        <button type="button" aria-label="Clear search" onClick={() => onChange("")} className="grid h-5 w-5 place-items-center rounded-full text-ink-3 hover:text-ink">
          <Icon name="x" size={12} />
        </button>
      )}
    </label>
  );
}

/** A thin progress bar; `value` 0..1, or null for indeterminate. */
export function Progress({ value, className }: { value: number | null; className?: string }) {
  return (
    <div className={cx("h-[6px] w-full overflow-hidden rounded-full bg-white/[0.08]", className)} role="progressbar" aria-valuenow={value == null ? undefined : Math.round(value * 100)} aria-valuemin={0} aria-valuemax={100}>
      <div className={cx("h-full rounded-full bg-info transition-[width] duration-500", value == null && "animate-pulse")} style={{ width: `${Math.round((value ?? 0.25) * 100)}%` }} />
    </div>
  );
}

/** An iOS-style switch. */
export function Toggle({ on, onChange, label, disabled }: { on: boolean; onChange: (v: boolean) => void; label: string; disabled?: boolean }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!on)}
      className={cx("press relative h-[28px] w-[48px] shrink-0 rounded-full transition-colors disabled:opacity-40", on ? "bg-ok" : "bg-white/[0.14]")}
    >
      <span className={cx("absolute top-[3px] h-[22px] w-[22px] rounded-full bg-white shadow-[0_2px_6px_rgb(0_0_0/0.35)] transition-[left] duration-200", on ? "left-[23px]" : "left-[3px]")} />
    </button>
  );
}

export function Empty({ title, children, icon = "film" }: { title: string; children?: ReactNode; icon?: IconName }) {
  return (
    <div className="rounded-[22px] border border-line bg-surface px-6 py-12 text-center">
      <Icon name={icon} size={28} className="mx-auto mb-3 text-ink-4" strokeWidth={1.3} />
      <div className="text-[15px] font-semibold">{title}</div>
      {children && <div className="mx-auto mt-1 max-w-xl text-[13px] text-ink-3">{children}</div>}
    </div>
  );
}

export function ErrorNote({ children }: { children: ReactNode }) {
  return (
    <div className="flex gap-2 rounded-[14px] border border-bad/30 bg-bad-soft px-3 py-2 text-[12.5px] whitespace-pre-wrap text-bad">
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
