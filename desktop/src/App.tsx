import { useCallback, useEffect, useState, type ReactNode } from "react";
import Activate from "./Activate";
import { api, errText, type AppInfo, type Job, type LicenseState, type ProductCard } from "./api";
import { useUser } from "./auth";
import { BrandMark, PRODUCT_NAME, tintFor } from "./brand";
import { WindowControls } from "./chrome";
import Fresh from "./Fresh";
import { Icon, type IconName } from "./icons";
import { isActive, JobsPage, useJobs, useOnJobEnd } from "./Jobs";
import Library from "./Library";
import Login from "./Login";
import NewProduct from "./NewProduct";
import Product from "./Product";
import Products from "./Products";
import Settings from "./Settings";
import Setup from "./Setup";
import { Button, cx, ErrorNote, Loading, Status } from "./ui";
import { startupCheck, type UpdateCheck } from "./updater";

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

function useHash() {
  const [hash, setHash] = useState(location.hash.replace(/^#/, "") || "/");
  useEffect(() => {
    const on = () => setHash(location.hash.replace(/^#/, "") || "/");
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return hash;
}

const NAV: { href: string; label: string; match: (p: string[]) => boolean; icon: IconName }[] = [
  { href: "#/", label: "Projects", match: (p) => p.length === 0 || p[0] === "p" || p[0] === "new", icon: "grid" },
  { href: "#/fresh", label: "Fresh edit", match: (p) => p[0] === "fresh", icon: "film" },
  { href: "#/library", label: "Library", match: (p) => p[0] === "library", icon: "images" },
  { href: "#/jobs", label: "Jobs", match: (p) => p[0] === "jobs", icon: "render" },
  { href: "#/settings", label: "Settings", match: (p) => p[0] === "settings" || p[0] === "setup", icon: "gear" },
];

function NavItem({ href, icon, label, on, count }: { href: string; icon: IconName; label: string; on: boolean; count?: number }) {
  return (
    <a
      href={href}
      aria-current={on ? "page" : undefined}
      className={cx("press flex h-[36px] items-center gap-2.5 rounded-[12px] px-3 text-[13px] font-medium", on ? "glass-active text-ink" : "text-ink-2 hover:bg-hover hover:text-ink")}
    >
      <Icon name={icon} size={16} className={cx("shrink-0", on ? "text-ink" : "text-ink-3")} />
      <span className="min-w-0 flex-1 truncate">{label}</span>
      {count != null && count > 0 && <span className="num text-[12px] text-ink-3">{count}</span>}
    </a>
  );
}

/** The floating glass sidebar: window controls, the name, the five places, recent products, the account. */
function Sidebar({ parts, jobs, info }: { parts: string[]; jobs: Job[]; info: AppInfo }) {
  const [products, setProducts] = useState<ProductCard[]>([]);
  const load = useCallback(() => {
    api.products().then(setProducts).catch(() => {});
  }, []);
  const key = parts.slice(0, 2).join("/");
  useEffect(load, [load, key]);
  useOnJobEnd(jobs, load);
  const busy = new Set(jobs.filter(isActive).map((j) => j.slug));
  const running = jobs.filter(isActive).length;
  const recent = products.filter((p) => !p.not_imported && !p.error).slice(0, 6);
  const email = info.license.email ?? "";

  return (
    <aside className="glass flex w-[236px] shrink-0 flex-col overflow-hidden rounded-[24px]">
      <div className="px-4 pt-4 pb-1" data-tauri-drag-region>
        <WindowControls />
      </div>
      <a href="#/" className="flex items-center gap-2.5 px-4 pt-2 pb-4" data-tauri-drag-region>
        <BrandMark size={28} tile />
        <span className="truncate text-[15px] font-semibold tracking-tight">{PRODUCT_NAME}</span>
      </a>
      <nav className="space-y-0.5 px-2.5" aria-label="Main">
        {NAV.map((n) => (
          <NavItem key={n.href} href={n.href} icon={n.icon} label={n.label} on={n.match(parts)} count={n.href === "#/jobs" ? running : undefined} />
        ))}
      </nav>
      {recent.length > 0 && (
        <>
          <div className="px-4 pt-5 pb-1 text-[11px] font-medium text-ink-4">Recent</div>
          <div className="min-h-0 flex-1 space-y-0.5 overflow-auto px-2.5">
            {recent.map((p) => {
              const on = parts[0] === "p" && parts[1] === p.slug;
              return (
                <a key={p.slug} href={`#/p/${p.slug}/analysis`} className={cx("press flex h-[32px] items-center gap-2.5 rounded-[10px] px-3 text-[12.5px]", on ? "glass-active text-ink" : "text-ink-2 hover:bg-hover hover:text-ink")}>
                  <span className="h-[14px] w-[14px] shrink-0 rounded-[4px]" style={{ background: tintFor(p.slug).bg }} aria-hidden="true" />
                  <span className="min-w-0 flex-1 truncate">{p.name || p.slug}</span>
                  {busy.has(p.slug) && <span className="h-[7px] w-[7px] shrink-0 animate-pulse rounded-full bg-info" aria-label="working" />}
                </a>
              );
            })}
          </div>
        </>
      )}
      <div className="mt-auto p-3">
        <a href="#/settings" className="press flex items-center gap-2.5 rounded-[16px] px-3 py-2.5 hover:bg-hover">
          <span className="grid h-[30px] w-[30px] shrink-0 place-items-center rounded-full bg-white/[0.1] text-[12px] font-semibold text-ink">{(email[0] ?? "C").toUpperCase()}</span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-[12.5px] font-medium text-ink">{email || "Local account"}</span>
            <Status tone="ok">Engine running</Status>
          </span>
        </a>
      </div>
    </aside>
  );
}

function Shell({ info, children, jobs, update }: { info: AppInfo; children: ReactNode; jobs: Job[]; update?: UpdateCheck | null }) {
  const parts = useHash().split("/").filter(Boolean);
  const [side, setSide] = useState(() => store.get("sidebar") !== "0");
  const toggleSide = useCallback(() => setSide((s) => (store.set("sidebar", s ? "0" : "1"), !s)), []);
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      if (!(e.ctrlKey || e.metaKey)) return;
      if (e.key === "9") {
        e.preventDefault();
        location.hash = "#/jobs";
      } else if (e.shiftKey && (e.key === "1" || e.code === "Digit1")) {
        e.preventDefault();
        toggleSide();
      }
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, [toggleSide]);
  // the one subtle glow: purple on Projects, warm everywhere else
  useEffect(() => {
    document.body.dataset.glow = parts.length === 0 ? "purple" : "warm";
  }, [parts.length]);

  return (
    <div className="flex h-full gap-[10px] p-[10px]">
      {side && <Sidebar parts={parts} jobs={jobs} info={info} />}
      <main className="min-w-0 flex-1 overflow-auto rounded-[24px]">
        {update?.available && parts[0] !== "settings" && (
          <a href="#/settings" className="glass mb-[10px] flex items-center gap-3 rounded-full px-4 py-2 text-[12.5px] text-ink-2 hover:text-ink">
            <Icon name="share" size={14} className="shrink-0 text-ink-3" />
            <span>
              {PRODUCT_NAME} {update.version} is available. <span className="font-medium text-accent-text">Open Updates</span>
            </span>
          </a>
        )}
        {children}
      </main>
    </div>
  );
}

/** The screens outside the shell (sign-in, activation, setup, starting): the window still needs its controls
 *  and a strip to drag it by, since it draws no native title bar. */
function Bare({ children }: { children: ReactNode }) {
  return (
    <div className="relative h-full">
      <div className="absolute inset-x-0 top-0 z-20 h-[44px]" data-tauri-drag-region>
        <WindowControls className="absolute top-4 left-4" />
      </div>
      {children}
    </div>
  );
}

function Centered({ children }: { children: ReactNode }) {
  return (
    <Bare>
      <div className="grid min-h-full place-items-center p-6">{children}</div>
    </Bare>
  );
}

export default function App() {
  const hash = useHash();
  const [info, setInfo] = useState<AppInfo | null>(null);
  const [err, setErr] = useState<string | null>(null);
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
    location.hash = `#/jobs/${id}`;
  }, []);
  const onActivated = (l: LicenseState) => setInfo((i) => (i ? { ...i, license: l } : i));

  if (err) {
    return (
      <Centered>
        <div className="max-w-[520px]">
          <ErrorNote>The engine did not answer: {err}</ErrorNote>
          <p className="mt-2 text-ink-2">
            Start {PRODUCT_NAME} again. If this is a dev session, start the engine (<code>python -m bluxtech_engine --open</code>) and open the link it prints.
          </p>
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
          <BrandMark size={44} tile />
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
    if (!user)
      return (
        <Bare>
          <Login version={info.version} />
        </Bare>
      );
    // 2. license
    if (!info.license.ok)
      return (
        <Bare>
          <Activate info={info} user={user} license={info.license} onActivated={onActivated} />
        </Bare>
      );
  }
  // 3. the machine, once per session
  const needSetup = !setupDone && (!info.tools.ffmpeg || !info.tools.hyperframes || !info.tools.skill || (info.runner === "cli" && !info.tools.claude));
  if (needSetup || hash === "/setup") {
    return (
      <Bare>
        <div className="h-full overflow-auto pt-[34px]">
          <Setup
            onDone={() => {
              sessionStorage.setItem("setupDone", "1");
              setSetupDone(true);
              reloadApp();
              if (hash === "/setup") location.hash = "#/";
            }}
          />
        </div>
      </Bare>
    );
  }

  const parts = hash.split("/").filter(Boolean);
  let page: ReactNode;
  if (parts[0] === "p" && parts[1]) page = <Product slug={parts[1]} tab={parts[2] || "analysis"} openJob={openJob} />;
  else if (parts[0] === "new") page = <NewProduct openJob={openJob} />;
  else if (parts[0] === "fresh") page = <Fresh slug={parts[1]} openJob={openJob} />;
  else if (parts[0] === "library") page = <Library />;
  else if (parts[0] === "jobs") page = <JobsPage jobs={jobs} focus={parts[1] ? Number(parts[1]) : null} />;
  else if (parts[0] === "settings") page = <Settings info={info} reloadApp={reloadApp} update={update} />;
  else page = <Products jobs={jobs} openJob={openJob} />;

  return (
    <Shell info={info} jobs={jobs} update={update}>
      {info.runner === "sdk" && !info.license.licensing && (
        <div className="mb-2 px-1">
          <Status tone="warn">Licensing is off (no supabase.config.json): dev mode.</Status>
        </div>
      )}
      {page}
    </Shell>
  );
}
