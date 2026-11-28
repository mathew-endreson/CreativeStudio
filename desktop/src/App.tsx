import { useCallback, useEffect, useState, type ReactNode } from "react";
import Activate from "./Activate";
import { api, errText, type AppInfo, type FreshProject, type Job, type LicenseState, type ProductCard } from "./api";
import { useUser } from "./auth";
import { startupCheck, type UpdateCheck } from "./updater";
import Fresh from "./Fresh";
import { BrandMark, Icon, type IconName } from "./icons";
import { isActive, JobsPanel, TasksButton, useJobs, useOnJobEnd } from "./Jobs";
import Library from "./Library";
import Login from "./Login";
import NewProduct from "./NewProduct";
import Product from "./Product";
import Products from "./Products";
import Settings from "./Settings";
import Setup from "./Setup";
import { Button, cx, ErrorNote, IconButton, Loading } from "./ui";

type Theme = "auto" | "light" | "dark";

const store = {
  get: (k: string) => {
    try {
      return localStorage.getItem(k);
    } catch {
      return null;
    }
  },
  set: (k: string, v: string) => {
    try {
      localStorage.setItem(k, v);
    } catch {
      /* private mode: the choice lasts for this session only */
    }
  },
};

function useTheme(): [Theme, () => void] {
  // Final Cut lives in the dark: dark is the default until the user picks otherwise
  const [theme, setTheme] = useState<Theme>(() => (store.get("theme") as Theme) || "dark");
  useEffect(() => {
    const mq = matchMedia("(prefers-color-scheme: dark)");
    const apply = () => document.documentElement.classList.toggle("dark", theme === "dark" || (theme === "auto" && mq.matches));
    apply();
    store.set("theme", theme);
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, [theme]);
  return [theme, () => setTheme(theme === "dark" ? "light" : theme === "light" ? "auto" : "dark")];
}

function useHash() {
  const [hash, setHash] = useState(location.hash.replace(/^#/, "") || "/");
  useEffect(() => {
    const on = () => setHash(location.hash.replace(/^#/, "") || "/");
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return hash;
}

/** The pages, laid out like Resolve's page bar along the bottom. */
const PAGES: { href: string; label: string; match: (p: string[]) => boolean; icon: IconName }[] = [
  { href: "#/", label: "Projects", match: (p) => p.length === 0 || p[0] === "p" || p[0] === "new", icon: "film" },
  { href: "#/fresh", label: "Fresh edit", match: (p) => p[0] === "fresh", icon: "wand" },
  { href: "#/library", label: "Asset Library", match: (p) => p[0] === "library", icon: "images" },
  { href: "#/settings", label: "Settings", match: (p) => p[0] === "settings" || p[0] === "setup", icon: "gear" },
];

/** One row of the Libraries sidebar. */
function SideItem({ href, icon, label, sub, on, depth = 0, dim, tone }: { href: string; icon: IconName; label: ReactNode; sub?: ReactNode; on?: boolean; depth?: number; dim?: boolean; tone?: string }) {
  return (
    <a
      href={href}
      className={cx(
        "group flex h-[26px] items-center gap-2 rounded-[5px] pr-2 text-[12.5px]",
        on ? "bg-accent text-on-accent" : "text-ink hover:bg-surface-3",
        dim && !on && "text-ink-3",
      )}
      style={{ paddingLeft: 8 + depth * 14 }}
    >
      <Icon name={icon} size={14} className={cx("shrink-0", on ? "text-on-accent" : tone ?? "text-ink-3")} />
      <span className="min-w-0 flex-1 truncate">{label}</span>
      {sub != null && <span className={cx("num shrink-0 text-[11px]", on ? "text-on-accent/80" : "text-ink-3")}>{sub}</span>}
    </a>
  );
}

function Disclosure({ label, open, onToggle, children, action }: { label: string; open: boolean; onToggle: () => void; children: ReactNode; action?: ReactNode }) {
  return (
    <div>
      <div className="group flex h-[24px] items-center pr-1">
        <button onClick={onToggle} className="flex min-w-0 flex-1 items-center gap-1 text-[10.5px] font-semibold tracking-[0.06em] text-ink-3 uppercase hover:text-ink-2">
          <Icon name={open ? "chevronDown" : "chevronRight"} size={12} />
          {label}
        </button>
        {action}
      </div>
      {open && <div className="space-y-px pb-2">{children}</div>}
    </div>
  );
}

/** Final Cut's Libraries sidebar: every project ("event") and fresh edit, one click away. */
function Sidebar({ parts, jobs }: { parts: string[]; jobs: Job[] }) {
  const [products, setProducts] = useState<ProductCard[]>([]);
  const [fresh, setFresh] = useState<FreshProject[]>([]);
  const [open, setOpen] = useState<Record<string, boolean>>({ p: true, f: true });
  const load = useCallback(() => {
    api.products().then(setProducts).catch(() => {});
    api.freshList().then(setFresh).catch(() => {});
  }, []);
  const key = parts.slice(0, 2).join("/");
  useEffect(load, [load, key]);
  useOnJobEnd(jobs, load);
  const busy = new Set(jobs.filter(isActive).map((j) => j.slug));
  const add = (href: string, title: string) => (
    <a href={href} title={title} className="grid h-5 w-5 place-items-center rounded-[4px] text-ink-3 opacity-0 group-hover:opacity-100 hover:bg-surface-3 hover:text-ink">
      <Icon name="plus" size={12} />
    </a>
  );

  return (
    <aside className="glass flex w-[232px] shrink-0 flex-col overflow-hidden rounded-[12px]">
      <div className="flex h-[30px] shrink-0 items-center border-b border-line bg-white/[0.03] px-2.5 text-[11.5px] font-semibold text-ink-2">Libraries</div>
      <nav className="min-h-0 flex-1 overflow-auto px-1.5 py-2">
        <div className="mb-2 flex items-center gap-2 px-2 py-1">
          <BrandMark size={18} />
          <span className="truncate text-[12.5px] font-semibold">BluxTech Library</span>
        </div>
        <Disclosure label="Projects" open={open.p} onToggle={() => setOpen((o) => ({ ...o, p: !o.p }))} action={add("#/new", "New project")}>
          <SideItem href="#/" icon="grid" label="All projects" sub={products.length || undefined} on={parts.length === 0} />
          {products.map((p) => (
            <SideItem
              key={p.slug}
              href={p.not_imported || p.error ? "#/" : `#/p/${p.slug}/analysis`}
              icon="star"
              depth={1}
              label={
                <>
                  {p.name || p.slug}
                  {busy.has(p.slug) && <span className="ml-1.5 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-accent align-middle" />}
                </>
              }
              sub={p.ads || undefined}
              on={parts[0] === "p" && parts[1] === p.slug}
              dim={!!(p.not_imported || p.error)}
              tone={p.analysis ? "text-sel" : "text-ink-3"}
            />
          ))}
        </Disclosure>
        <Disclosure label="Fresh edits" open={open.f} onToggle={() => setOpen((o) => ({ ...o, f: !o.f }))} action={add("#/fresh", "New fresh edit")}>
          <SideItem href="#/fresh" icon="wand" label="All fresh edits" sub={fresh.length || undefined} on={parts[0] === "fresh" && !parts[1]} />
          {fresh.map((f) => (
            <SideItem
              key={f.slug}
              href={`#/fresh/${f.slug}`}
              icon="film"
              depth={1}
              label={
                <>
                  {f.name}
                  {busy.has(f.slug) && <span className="ml-1.5 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-accent align-middle" />}
                </>
              }
              on={parts[0] === "fresh" && parts[1] === f.slug}
              tone={f.ad ? "text-ok" : "text-ink-3"}
            />
          ))}
        </Disclosure>
        <Disclosure label="Media" open onToggle={() => {}}>
          <SideItem href="#/library" icon="images" label="GPT asset library" on={parts[0] === "library"} />
          <SideItem href="#/settings" icon="gear" label="Settings" on={parts[0] === "settings"} />
        </Disclosure>
      </nav>
    </aside>
  );
}

const themeIcon: Record<Theme, IconName> = { dark: "moon", light: "sun", auto: "auto" };

function Shell({ info, children, openPanel, jobs, theme, cycle, update }: { info: AppInfo; children: ReactNode; openPanel: () => void; jobs: Job[]; theme: Theme; cycle: () => void; update?: UpdateCheck | null }) {
  const parts = useHash().split("/").filter(Boolean);
  const [side, setSide] = useState(() => store.get("sidebar") !== "0");
  const toggleSide = useCallback(() => setSide((s) => (store.set("sidebar", s ? "0" : "1"), !s)), []);
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      if (!(e.ctrlKey || e.metaKey)) return;
      if (e.key === "9") {
        e.preventDefault();
        openPanel();
      } else if (e.shiftKey && (e.key === "1" || e.code === "Digit1")) {
        e.preventDefault();
        toggleSide();
      }
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, [openPanel, toggleSide]);

  const page = PAGES.find((n) => n.match(parts)) ?? PAGES[0];

  return (
    <div className="flex h-full flex-col">
      {/* the title bar: Resolve's slim top strip, the window's name in the middle */}
      <header className="glass-bar relative z-10 flex h-[38px] shrink-0 items-center gap-1 border-b border-line px-2">
        <IconButton icon="sidebar" label="Show or hide the Libraries sidebar (Ctrl+Shift+1)" on={side} onClick={toggleSide} />
        <a href="#/" className="ml-1 flex items-center" title="Projects">
          <BrandMark size={20} />
        </a>
        <div className="min-w-0 flex-1 truncate px-2 text-center text-[12.5px] font-semibold tracking-tight text-ink-2">
          <span className="hidden sm:inline">BluxTech Studio</span>
          <span className="hidden text-ink-3 sm:inline"> · </span>
          <span className="text-ink">{page.label}</span>
        </div>
        <TasksButton jobs={jobs} onClick={openPanel} />
        <IconButton icon={themeIcon[theme]} label={`Theme: ${theme} (click to change)`} onClick={cycle} />
        <Button small variant="primary" icon="plus" onClick={() => (location.hash = "#/new")} className="ml-1">
          New project
        </Button>
      </header>
      <div className="flex min-h-0 flex-1 gap-[6px] p-[6px]">
        {side && <Sidebar parts={parts} jobs={jobs} />}
        <main className="min-w-0 flex-1 overflow-auto rounded-[12px] px-4 py-3">
          {update?.available && parts[0] !== "settings" && (
            <a href="#/settings" className="glass-2 mb-3 flex items-center gap-2 rounded-[9px] px-3 py-1.5 text-[12.5px] text-ink-2 hover:text-ink">
              <Icon name="sparkles" size={14} className="shrink-0 text-accent" />
              <span>
                BluxTech Studio {update.version} is available. <span className="font-medium text-accent">Open Updates</span>
              </span>
            </a>
          )}
          {children}
        </main>
      </div>
      {/* the page bar: Resolve's row of pages along the bottom, the active one lit amber */}
      <footer className="glass-bar relative z-10 flex h-[54px] shrink-0 items-center border-t border-line px-3">
        <div className="hidden w-[200px] shrink-0 items-center gap-2 text-[11px] text-ink-3 md:flex">
          <BrandMark size={16} />
          <span className="num">v{info.version}</span>
          <span>·</span>
          <span>{info.mode}</span>
        </div>
        <nav className="flex min-w-0 flex-1 justify-center gap-1" aria-label="Pages">
          {PAGES.map((n) => {
            const on = n.match(parts);
            return (
              <a
                key={n.href}
                href={n.href}
                aria-current={on ? "page" : undefined}
                className={cx(
                  "group flex w-[86px] flex-col items-center gap-[3px] rounded-[9px] py-1 text-[10.5px] font-medium transition-colors duration-150",
                  on ? "text-accent" : "text-ink-3 hover:text-ink",
                )}
              >
                <span className={cx("grid h-[24px] w-[36px] place-items-center rounded-[8px] transition-[background,box-shadow,color] duration-150", on ? "glass-2 text-accent" : "group-hover:bg-surface-2")}>
                  <Icon name={n.icon} size={17} />
                </span>
                {n.label}
              </a>
            );
          })}
        </nav>
        <div className="hidden w-[200px] shrink-0 items-center justify-end gap-2 text-[11px] text-ink-3 md:flex">
          {info.license.licensing && info.license.email && <span className="min-w-0 truncate">{info.license.email}</span>}
          <span className="shrink-0">· runner {info.runner}</span>
        </div>
      </footer>
    </div>
  );
}

function Centered({ children }: { children: ReactNode }) {
  return <div className="grid min-h-full place-items-center p-6">{children}</div>;
}

export default function App() {
  const hash = useHash();
  const [theme, cycle] = useTheme();
  const [info, setInfo] = useState<AppInfo | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [panel, setPanel] = useState(false);
  const [focus, setFocus] = useState<number | null>(null);
  const [setupDone, setSetupDone] = useState(() => sessionStorage.getItem("setupDone") === "1");
  const jobs = useJobs();
  const reloadApp = useCallback(() => api.app().then(setInfo).catch((e) => setErr(errText(e))), []);
  useEffect(() => {
    reloadApp();
  }, [reloadApp]);
  const user = useUser(info?.auth ?? null);
  // the startup update check: once per app version, in the background, never blocking or downloading
  const [update, setUpdate] = useState<UpdateCheck | null>(null);
  const version = info?.version;
  useEffect(() => {
    if (!version) return;
    let live = true;
    startupCheck().then((u) => live && setUpdate(u));
    return () => {
      live = false;
    };
  }, [version]);
  const openJob = useCallback((id: number) => {
    setFocus(id);
    setPanel(true);
  }, []);
  const openPanel = useCallback(() => setPanel(true), []);
  const onActivated = (l: LicenseState) => setInfo((i) => (i ? { ...i, license: l } : i));

  if (err) {
    return (
      <Centered>
        <div className="max-w-[520px]">
          <ErrorNote>The engine did not answer: {err}</ErrorNote>
          <p className="mt-2 text-ink-2">Start BluxTech Studio again. If this is a dev session, start the engine (<code>python -m bluxtech_engine --open</code>) and open the link it prints.</p>
          <Button className="mt-3" icon="refresh" onClick={() => (setErr(null), reloadApp())}>
            Try again
          </Button>
        </div>
      </Centered>
    );
  }
  if (!info)
    return (
      <Centered>
        <div className="flex flex-col items-center gap-3">
          <BrandMark size={44} />
          <Loading>Starting…</Loading>
        </div>
      </Centered>
    );

  // 1. account
  if (info.auth) {
    if (user === undefined)
      return (
        <Centered>
          <Loading>Checking the account…</Loading>
        </Centered>
      );
    if (!user) return <Login version={info.version} />;
    // 2. license
    if (!info.license.ok) return <Activate info={info} user={user} license={info.license} onActivated={onActivated} />;
  }
  // 3. the machine, once per session
  const needSetup = !setupDone && (!info.tools.ffmpeg || !info.tools.hyperframes || !info.tools.skill || (info.runner === "cli" && !info.tools.claude));
  if (needSetup || hash === "/setup") {
    return (
      <Setup
        onDone={() => {
          sessionStorage.setItem("setupDone", "1");
          setSetupDone(true);
          reloadApp();
          if (hash === "/setup") location.hash = "#/";
        }}
      />
    );
  }

  const parts = hash.split("/").filter(Boolean);
  let page: ReactNode;
  if (parts[0] === "p" && parts[1]) page = <Product slug={parts[1]} tab={parts[2] || "analysis"} openJob={openJob} />;
  else if (parts[0] === "new") page = <NewProduct openJob={openJob} />;
  else if (parts[0] === "fresh") page = <Fresh slug={parts[1]} openJob={openJob} />;
  else if (parts[0] === "library") page = <Library />;
  else if (parts[0] === "settings") page = <Settings info={info} reloadApp={reloadApp} update={update} />;
  else page = <Products />;

  return (
    <Shell info={info} openPanel={openPanel} jobs={jobs} theme={theme} cycle={cycle} update={update}>
      {info.runner === "sdk" && !info.license.licensing && (
        <div className="mb-2 inline-flex items-center gap-1.5 rounded-[5px] bg-warn/10 px-2 py-0.5 text-[11.5px] text-warn">
          <Icon name="alert" size={12} /> Licensing is off (no supabase.config.json): dev mode.
        </div>
      )}
      {page}
      <JobsPanel jobs={jobs} open={panel} onClose={() => setPanel(false)} focus={focus} />
    </Shell>
  );
}
