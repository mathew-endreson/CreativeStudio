"""The job queue. SQLite holds the queue, progress and logs only; every result is a file in a batch folder.

Queues: heavy (cutouts, renders: one at a time, they are CPU-bound), claude (one headless run per product,
at most 2 overall), light (probes, scans, joins, snapshots).
"""
import json
import sqlite3
import statistics
import subprocess
import threading
import time

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs(
  id INTEGER PRIMARY KEY AUTOINCREMENT, slug TEXT, queue TEXT, kind TEXT, title TEXT, spec TEXT, status TEXT,
  depends_on INTEGER, grp TEXT, created REAL, started REAL, finished REAL, exit_code INTEGER, pid INTEGER,
  work REAL, progress REAL, eta_s REAL, result TEXT, error TEXT);
CREATE TABLE IF NOT EXISTS logs(job_id INTEGER, seq INTEGER, ts REAL, kind TEXT, text TEXT, PRIMARY KEY(job_id, seq));
CREATE TABLE IF NOT EXISTS speeds(kind TEXT, work REAL, secs REAL, at REAL);
"""
ACTIVE = ("queued", "running", "cancelling")
PRIORS = {"cut": 1 / 2.3}                          # seconds per unit of work before anything was measured


class JobFailed(Exception):
    pass


class Ctx:
    """What a running job gets: a log, a way to spawn its process, its cancel flag."""

    def __init__(self, jobs, job):
        self.jobs, self.job, self.id = jobs, job, job["id"]
        self.cancelled = False
        self.proc = None
        self.cancel_hook = None            # runners without a process handle (the Agent SDK) set this

    def log(self, kind, text):
        self.jobs.log(self.id, kind, text)

    def progress(self, p=None, eta_s=None):
        self.jobs.update(self.id, **{k: v for k, v in (("progress", p), ("eta_s", eta_s)) if v is not None})

    def spawn(self, cmd, cwd=None, stdin_text=None, on_line=None, env=None):
        """Run a process, feed each output line to on_line (default: the log). Returns its exit code."""
        flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        p = subprocess.Popen([str(c) for c in cmd], cwd=str(cwd) if cwd else None, env=env or config.child_env(),
                             stdin=subprocess.PIPE if stdin_text is not None else subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                             errors="replace", creationflags=flags)
        self.proc = p
        self.jobs.update(self.id, pid=p.pid)
        if stdin_text is not None:
            try:
                p.stdin.write(stdin_text)
                p.stdin.close()
            except OSError:
                pass
        for line in p.stdout:
            line = line.rstrip("\r\n")
            if line:
                (on_line or (lambda s: self.log("out", s)))(line)
        code = p.wait()
        self.proc = None
        if self.cancelled:
            raise JobFailed("cancelled")
        return code

    def kill(self):
        """Stop the job's whole process tree (ffmpeg under python under claude ...)."""
        self.cancelled = True
        if self.cancel_hook:
            try:
                self.cancel_hook()
            except Exception:
                pass
        p = self.proc
        if p and p.poll() is None:
            subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)


class Jobs:
    def __init__(self, path=None):
        config.DATA.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path or config.DATA / "studio.db"), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        with self.lock:
            self.db.executescript(SCHEMA)
            self.db.execute("PRAGMA journal_mode=WAL")
            # whatever was running when the app last stopped is gone; its files (cutouts, transcripts) are not
            self.db.execute("UPDATE jobs SET status='interrupted', finished=?, error='the app was closed while this "
                            "ran; run it again (finished work is kept)' WHERE status IN ('queued','running','cancelling')",
                            (time.time(),))
            self.db.commit()
        self.executors, self.ctx, self.seq = {}, {}, {}
        self.stop = False

    # ---------------------------------------------------------- storage
    def q(self, sql, args=()):
        with self.lock:
            cur = self.db.execute(sql, args)
            rows = cur.fetchall()
            self.db.commit()
            return rows, cur.lastrowid

    @staticmethod
    def row(r):
        d = dict(r)
        for k in ("spec", "result"):
            d[k] = json.loads(d[k]) if d.get(k) else None
        return d

    def add(self, slug, queue, kind, title, spec, depends_on=None, grp=None, work=None):
        eta = self.estimate(kind, work)
        _, jid = self.q("INSERT INTO jobs(slug,queue,kind,title,spec,status,depends_on,grp,created,work,eta_s) "
                        "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                        (slug, queue, kind, title, json.dumps(spec, ensure_ascii=False), "queued", depends_on, grp,
                         time.time(), work, eta))
        return jid

    def get(self, jid):
        rows, _ = self.q("SELECT * FROM jobs WHERE id=?", (jid,))
        return self.row(rows[0]) if rows else None

    def list(self, slug=None, limit=60):
        if slug:
            rows, _ = self.q("SELECT * FROM jobs WHERE slug=? ORDER BY id DESC LIMIT ?", (slug, limit))
        else:
            rows, _ = self.q("SELECT * FROM jobs ORDER BY id DESC LIMIT ?", (limit,))
        return [self.row(r) for r in rows]

    def update(self, jid, **kw):
        if kw:
            self.q(f"UPDATE jobs SET {', '.join(k + '=?' for k in kw)} WHERE id=?", (*kw.values(), jid))

    def log(self, jid, kind, text):
        with self.lock:
            n = self.seq.get(jid)
            if n is None:
                n = self.db.execute("SELECT COALESCE(MAX(seq),0) FROM logs WHERE job_id=?", (jid,)).fetchone()[0]
            n += 1
            self.seq[jid] = n
            self.db.execute("INSERT INTO logs VALUES(?,?,?,?,?)", (jid, n, time.time(), kind, text[:20000]))
            self.db.commit()

    def logs(self, jid, after=0, limit=2000):
        rows, _ = self.q("SELECT seq,ts,kind,text FROM logs WHERE job_id=? AND seq>? ORDER BY seq LIMIT ?",
                         (jid, after, limit))
        return [dict(r) for r in rows]

    # ---------------------------------------------------------- ETA from measured speeds
    def estimate(self, kind, work):
        if not work:
            return None
        rows, _ = self.q("SELECT work,secs FROM speeds WHERE kind=? AND work>0 ORDER BY at DESC LIMIT 7", (kind,))
        rates = [r["secs"] / r["work"] for r in rows]
        rate = statistics.median(rates) if rates else PRIORS.get(kind)
        return round(work * rate, 1) if rate else None

    def measured(self, kind, work, secs):
        if work and secs > 0:
            self.q("INSERT INTO speeds VALUES(?,?,?,?)", (kind, work, secs, time.time()))

    # ---------------------------------------------------------- running
    def register(self, type_, fn):
        self.executors[type_] = fn

    def cancel(self, jid):
        j = self.get(jid)
        if not j or j["status"] not in ACTIVE:
            return False
        if j["status"] == "queued":
            self.update(jid, status="cancelled", finished=time.time())
            return True
        self.update(jid, status="cancelling")
        c = self.ctx.get(jid)
        if c:
            self.log(jid, "sys", "cancel requested: stopping the process tree")
            c.kill()
        return True

    def _run(self, job):
        jid, ctx = job["id"], Ctx(self, job)
        self.ctx[jid] = ctx
        t0 = time.time()
        self.update(jid, status="running", started=t0)
        status, err, result = "done", None, None
        try:
            result = self.executors[job["spec"]["type"]](ctx, job, job["spec"])
        except JobFailed as e:
            status, err = ("cancelled", None) if ctx.cancelled else ("failed", str(e))
        except Exception as e:                              # a bug in the app, not in the job: say so
            status, err = "failed", f"{type(e).__name__}: {e}"
        if ctx.cancelled:
            status, err = "cancelled", None
        secs = time.time() - t0
        if err:
            self.log(jid, "error", err)
        self.log(jid, "sys", f"{status} in {int(secs)} s")
        if status == "done":
            self.measured(job["kind"], job.get("work"), secs)
        self.update(jid, status=status, finished=time.time(), error=err, pid=None,
                    result=json.dumps(result, ensure_ascii=False) if result is not None else None,
                    progress=1.0 if status == "done" else None)
        self.ctx.pop(jid, None)

    def _tick(self):
        limits = config.settings()["limits"]
        rows, _ = self.q("SELECT * FROM jobs WHERE status IN ('queued','running','cancelling') ORDER BY id")
        jobs = [self.row(r) for r in rows]
        running = [j for j in jobs if j["status"] != "queued"]
        for j in jobs:
            if j["status"] != "queued":
                continue
            if j["depends_on"]:
                dep = self.get(j["depends_on"])
                if dep and dep["status"] in ("failed", "cancelled", "interrupted", "skipped"):
                    self.update(j["id"], status="skipped", finished=time.time(),
                                error=f"not run: the step before it ({dep['title']}) {dep['status']}")
                    continue
                if dep and dep["status"] != "done":
                    continue
            q = j["queue"]
            if sum(r["queue"] == q for r in running) >= limits.get(q, 1):
                continue
            if q == "claude" and any(r["queue"] == "claude" and r["slug"] == j["slug"] for r in running):
                continue                                    # one headless run per product
            running.append(j)
            self.update(j["id"], status="running", started=time.time())
            threading.Thread(target=self._run, args=(j,), daemon=True, name=f"job-{j['id']}").start()

    def start(self):
        def loop():
            while not self.stop:
                try:
                    self._tick()
                except Exception as e:                      # never let the dispatcher die
                    print("dispatcher:", e, flush=True)
                time.sleep(0.25)
        threading.Thread(target=loop, daemon=True, name="dispatcher").start()

    def shutdown(self):
        self.stop = True
        for c in list(self.ctx.values()):
            c.kill()


def run_cmd(ctx, job, spec):
    """A mechanical step: one of the skill's scripts, its output straight into the log."""
    ctx.log("sys", "$ " + " ".join(str(c) for c in spec["cmd"]))
    code = ctx.spawn(spec["cmd"], cwd=spec.get("cwd") or config.ROOT)
    if code != 0:
        raise JobFailed(f"exit code {code}")
    return {"exit": code}
