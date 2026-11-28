import { useCallback, useEffect, useRef, useState } from "react";
import { api, type Settings as SettingsT } from "./api";
import { isActive } from "./Jobs";
import { inTauri } from "./tauri";
import { Button, Chip, cx, Dot } from "./ui";
import { checkForUpdate, friendlyUpdateError, installUpdate, mb, onUpdateProgress, updateStatus, type UpdateCheck, type UpdateProgress, type UpdateStatus } from "./updater";

type Phase = "idle" | "checking" | "found" | "uptodate" | "downloading" | "verifying" | "installing" | "error";

/** The Updates section of Settings: version, a check, the automatic-check switch, what is available with its
 *  notes, download progress, install and restart, errors with a retry. Installing waits for running tasks. */
export default function Updates({ version, settings, save, initial }: { version: string; settings: SettingsT; save: (patch: Partial<SettingsT>, what: string) => void; initial?: UpdateCheck | null }) {
  const [status, setStatus] = useState<UpdateStatus | null>(null);
  const [check, setCheck] = useState<UpdateCheck | null>(initial ?? null);
  const [phase, setPhase] = useState<Phase>(initial?.available ? "found" : "idle");
  const [progress, setProgress] = useState<UpdateProgress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [checkedAt, setCheckedAt] = useState<Date | null>(initial ? new Date() : null);
  const [deferred, setDeferred] = useState(false);
  const [waiting, setWaiting] = useState(0); // tasks the install is waiting for
  const installing = useRef(false);

  // asked of the engine directly each time: the Tasks list's own poll can be stale, and it pauses while the window
  // is hidden, so an install must never trust it to know what is running
  const activeJobs = async () => (await api.jobs()).filter(isActive).length;

  useEffect(() => {
    if (!inTauri()) return;
    updateStatus()
      .then(setStatus)
      .catch(() => setStatus({ enabled: false, reason: "The updater is not available in this build.", channel: "", current: version }));
  }, [version]);

  const runCheck = useCallback(() => {
    setPhase("checking");
    setError(null);
    checkForUpdate()
      .then((c) => {
        setCheck(c);
        setCheckedAt(new Date());
        setPhase(c.available ? "found" : "uptodate");
      })
      .catch((e) => {
        setError(friendlyUpdateError(e));
        setPhase("error");
      });
  }, []);

  const runInstall = useCallback(() => {
    if (installing.current) return;
    installing.current = true;
    setDeferred(false);
    setWaiting(0);
    setError(null);
    setPhase("downloading");
    setProgress({ phase: "download", downloaded: 0, total: null });
    let unlisten: (() => void) | null = null;
    onUpdateProgress((p) => {
      setProgress(p);
      if (p.phase === "verify") setPhase("verifying");
      if (p.phase === "install") setPhase("installing");
    })
      .then((u) => (unlisten = u))
      .catch(() => {});
    installUpdate()
      .then(() => {
        // the shell exits during a successful install, so reaching this point means it did not happen
        setError("The installer did not start.");
        setPhase("error");
      })
      .catch((e) => {
        setError(friendlyUpdateError(e));
        setPhase("error");
        // the pending update was consumed by the attempt: a retry checks again first
        setCheck(null);
      })
      .finally(() => {
        installing.current = false;
        unlisten?.();
      });
  }, []);

  // the customer agreed while tasks were running: ask the engine every 2 s and install as soon as none is left
  useEffect(() => {
    if (!deferred || phase !== "found") return;
    let alive = true;
    const tick = async () => {
      try {
        const n = await activeJobs();
        if (!alive) return;
        setWaiting(n);
        if (n === 0) runInstall();
      } catch {
        /* no answer from the engine right now: the next tick asks again */
      }
    };
    const id = setInterval(tick, 2000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [deferred, phase, runInstall]);

  const askInstall = async () => {
    if (!check?.version) return;
    const ok = confirm(`Download BluxTech Studio ${check.version} and install it?\n\nThe app closes, installs the update and opens again. Your projects, pictures, settings and license stay as they are.`);
    if (!ok) return;
    let n = 0;
    try {
      n = await activeJobs();
    } catch {
      /* the engine did not answer: nothing is known to be running */
    }
    if (n > 0) {
      const wait = confirm(`${n} task${n > 1 ? "s are" : " is"} still running. Install when ${n > 1 ? "they finish" : "it finishes"}?\n\nOK: install when the tasks are done. Cancel: keep working, install later.`);
      if (wait) {
        setWaiting(n);
        setDeferred(true);
      }
      return;
    }
    runInstall();
  };

  const retry = () => {
    setError(null);
    if (check?.available && phase !== "error") askInstall();
    else runCheck();
  };

  const pct = progress?.total ? Math.min(100, Math.round((progress.downloaded / progress.total) * 100)) : null;
  const busy = phase === "checking" || phase === "downloading" || phase === "verifying" || phase === "installing";

  const Row = ({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) => (
    <div className="grid grid-cols-[230px_1fr] items-start gap-4 border-b border-line px-4 py-2.5 last:border-b-0">
      <div>
        <div className="font-medium">{label}</div>
        {hint && <div className="text-[12px] leading-snug text-ink-3">{hint}</div>}
      </div>
      <div className="min-w-0">{children}</div>
    </div>
  );

  if (!inTauri()) {
    return (
      <Row label="Current version">
        <span className="num">BluxTech Studio v{version}</span>
        <span className="ml-2 text-[12px] text-ink-3">Updates come with the installed app; this is the browser view.</span>
      </Row>
    );
  }

  return (
    <>
      <Row label="Current version">
        <div className="flex flex-wrap items-center gap-2">
          <span className="num">BluxTech Studio v{version}</span>
          {status && !status.enabled && <Chip title={status.reason}>updates off</Chip>}
          {status?.channel === "override" && <Chip tone="warn">rehearsal channel</Chip>}
          {phase === "uptodate" && <Chip tone="ok">up to date</Chip>}
          {checkedAt && <span className="text-[12px] text-ink-3">checked {checkedAt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>}
        </div>
        {status && !status.enabled && <div className="mt-1 text-[12px] text-ink-3">{status.reason}</div>}
      </Row>
      <Row label="Check for updates" hint="Looks for a newer version on the release channel. Nothing is downloaded until you say so.">
        <div className="flex flex-wrap items-center gap-2">
          <Button icon="refresh" onClick={runCheck} disabled={busy || !status?.enabled}>
            {phase === "checking" ? "Checking…" : "Check for updates"}
          </Button>
          <label className="flex items-center gap-2 text-[12.5px] text-ink-2">
            <input type="checkbox" checked={settings.auto_update_check} onChange={(e) => save({ auto_update_check: e.target.checked }, "automatic update check")} />
            Check automatically when the app starts
          </label>
        </div>
      </Row>
      {check?.available && (
        <Row label="Available" hint="What the new version brings.">
          <div className="flex flex-wrap items-center gap-2">
            <Chip tone="accent">version {check.version}</Chip>
            {check.date && <span className="text-[12px] text-ink-3">published {new Date(check.date * 1000).toLocaleDateString()}</span>}
          </div>
          {check.notes && <div className="mt-2 max-h-[180px] overflow-auto rounded-[8px] bg-well px-3 py-2 text-[12.5px] whitespace-pre-wrap text-ink-2">{check.notes}</div>}
          <div className="mt-2 flex flex-wrap items-center gap-2">
            {phase === "found" && !deferred && (
              <Button variant="primary" icon="share" onClick={askInstall}>
                Download and install
              </Button>
            )}
            {deferred && (
              <>
                <Chip tone="warn">
                  <Dot tone="warn" pulse /> installs when {waiting} running task{waiting > 1 ? "s" : ""} finish{waiting > 1 ? "" : "es"}
                </Chip>
                <Button small variant="ghost" onClick={() => setDeferred(false)}>
                  Cancel
                </Button>
              </>
            )}
            {(phase === "downloading" || phase === "verifying" || phase === "installing") && (
              <div className="min-w-[320px] flex-1">
                <div className="flex items-center justify-between text-[12px] text-ink-2">
                  <span>{phase === "downloading" ? "Downloading…" : phase === "verifying" ? "Checking the signature…" : "Installing… the app will restart"}</span>
                  {phase === "downloading" && progress && (
                    <span className="num">
                      {mb(progress.downloaded)}
                      {progress.total ? ` / ${mb(progress.total)}` : ""}
                    </span>
                  )}
                </div>
                <div className="glass-well mt-1 h-2 overflow-hidden rounded-full">
                  <div className={cx("h-full rounded-full bg-accent transition-[width] duration-300", pct == null && "animate-pulse")} style={{ width: `${pct ?? (phase === "downloading" ? 15 : 100)}%` }} />
                </div>
              </div>
            )}
          </div>
        </Row>
      )}
      {phase === "error" && error && (
        <Row label="Problem">
          <div className="flex flex-wrap items-start gap-2">
            <div className="min-w-0 flex-1 rounded-[9px] border border-bad/40 bg-bad-soft px-3 py-2 text-[12.5px] text-bad">{error}</div>
            <Button small onClick={retry} icon="refresh">
              Retry
            </Button>
          </div>
        </Row>
      )}
    </>
  );
}
