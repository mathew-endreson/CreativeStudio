"""BluxTech Studio engine: the local API + UI server behind the desktop app (127.0.0.1 only, boot-token cookie).

    python -m bluxtech_engine [--open]                 dev, http://127.0.0.1:8766
    python -m bluxtech_engine --resources <dir> ...    what the desktop shell runs

Mechanical steps run the camel-gpt skill's scripts (batch.py and friends) as jobs; judgment steps run headless
Claude with the skill (claude_runner: the local CLI login, or the Agent SDK with an API key)."""
import asyncio
import json
import os
import shutil
import subprocess
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import claude_runner, config, darija, environment, fresh, license, products, schemas, schemas_more as SM, security, settings, stages, store
from .jobs import ACTIVE, Jobs, run_cmd

jobs = Jobs()
jobs.register("cmd", run_cmd)
jobs.register("claude", claude_runner.run_stage)
jobs.register("setup", environment.setup_job)
jobs.register("pictures", products.pictures_job)
jobs.register("fresh_init", fresh.init_job)
jobs.register("fresh_transcribe", fresh.transcribe_job)
jobs.register("fresh_cutout", fresh.cutout_job)


@asynccontextmanager
async def lifespan(_app):
    jobs.start()
    yield
    jobs.shutdown()


app = FastAPI(title=config.APP_NAME, version=config.VERSION, lifespan=lifespan)
app.middleware("http")(security.middleware)


@app.exception_handler(store.NotFound)
async def not_found(_req: Request, e: store.NotFound):
    return JSONResponse({"detail": f"not found: {e}"}, status_code=404)


def public(j):
    return {k: j[k] for k in ("id", "slug", "queue", "kind", "title", "status", "depends_on", "grp", "created",
                               "started", "finished", "progress", "eta_s", "error", "result")}


def batch_cmd(sub, d, *args):
    return {"type": "cmd", "cmd": [config.skill_python(), str(config.BATCH), sub, str(d), *args]}


# ------------------------------------------------------------------ boot, app, license, settings, environment

@app.get("/boot/{token}")
def boot(token: str):
    return security.boot_response(token)


@app.get("/api/ping")
def ping():
    return {"ok": True, "app": config.APP_NAME, "version": config.VERSION}


@app.get("/api/app")
def app_info():
    hf = config.HF / "node_modules" / "hyperframes" / "bin" / "hyperframes.mjs"
    return {"app": config.APP_NAME, "version": config.VERSION, "mode": config.MODE, "workspace": str(config.ROOT),
            "data": str(config.DATA), "auth": config.auth_config(), "license": license.state(),
            "device_id": settings.device_id(), "device_name": os.environ.get("COMPUTERNAME") or "this PC",
            "runner": settings.runner(), "tools": {"claude": config.claude_bin(), "python": config.skill_python(),
                                                   "ffmpeg": environment.which("ffmpeg"), "node": environment.which("node"),
                                                   "hyperframes": hf.exists(), "skill": (config.SKILL / "SKILL.md").exists()},
            "gpt_dir": str(config.GPT_DIR), "gpt_library": (config.GPT_DIR / "library.json").exists()}


@app.get("/api/license")
def get_license():
    return license.state()


@app.post("/api/license")
def post_license(body: license.LicensePayload):
    """The UI posts what the `license` Edge Function returned (after a Supabase sign-in)."""
    return license.save(body)


@app.delete("/api/license")
def delete_license():
    license.clear()
    return license.state()


@app.get("/api/settings")
def get_settings():
    return settings.public()


@app.put("/api/settings")
def put_settings(body: dict = Body(...)):
    allowed = {"runner": lambda v: v in ("cli", "sdk", None), "model": lambda v: v is None or isinstance(v, str),
               "effort": lambda v: v in (None, "low", "medium", "high", "xhigh", "max"),
               "max_budget_usd": lambda v: isinstance(v, (int, float)) and 0.5 <= v <= 50,
               "max_turns": lambda v: isinstance(v, int) and 10 <= v <= 500,
               "limits": lambda v: isinstance(v, dict) and all(k in ("heavy", "claude", "light") and isinstance(x, int) and 1 <= x <= 4 for k, x in v.items()),
               "gpt_cap": lambda v: isinstance(v, int) and 0 <= v <= 10, "auto_render": lambda v: isinstance(v, bool)}
    for k, v in body.items():
        if k not in allowed:
            raise HTTPException(400, f"unknown setting {k}")
        if not allowed[k](v):
            raise HTTPException(422, f"bad value for {k}")
        settings.set(k, v)
    return settings.public()


@app.post("/api/settings/apikey")
def put_api_key(body: dict = Body(...)):
    key = (body.get("key") or "").strip()
    if key and not key.startswith("sk-ant-"):
        raise HTTPException(422, "an Anthropic API key starts with sk-ant-")
    settings.set_secret("anthropic_api_key", key)
    return settings.public()


@app.get("/api/environment")
def get_environment():
    return environment.check()


@app.post("/api/environment/setup")
def run_setup():
    if any(j["kind"] == "setup" and j["status"] in ACTIVE for j in jobs.list(None, 20)):
        raise HTTPException(409, "setup is already running")
    jid = jobs.add("-", "light", "setup", "Set up the environment", {"type": "setup"})
    return {"jobs": [public(jobs.get(jid))]}


@app.get("/api/folder")
def folder(path: str):
    return products.list_folder(path)


@app.post("/api/reveal")
def reveal(body: dict = Body(...)):
    products.reveal(body.get("path") or "")
    return {"ok": True}


# ------------------------------------------------------------------ products (projects)

@app.get("/api/products")
def list_products():
    return store.products()


@app.post("/api/products")
def create_product(body: SM.NewProduct):
    license.require()
    try:
        slug, pictures = products.create_product(body)
    except ValueError as e:
        raise HTTPException(422, str(e))
    made = []
    if pictures:
        made.append(public(jobs.get(jobs.add(slug, "light", "pictures", f"Prepare the pictures of {body.name}", {"type": "pictures"}))))
    return {"slug": slug, "jobs": made}


@app.get("/api/products/{slug}")
def product(slug: str):
    return store.detail(slug)


@app.get("/api/products/{slug}/sources/{key}")
def source(slug: str, key: str):
    return store.source_data(slug, key)


@app.get("/api/products/{slug}/analysis")
def get_analysis(slug: str):
    d, _, _ = store.product(slug)
    return store.jload(d / "analysis.json")


@app.put("/api/products/{slug}/analysis")
def put_analysis(slug: str, body: dict = Body(...)):
    d, P, _ = store.product(slug)
    try:
        new = schemas.Analysis.model_validate(body)
    except Exception as e:
        raise HTTPException(422, str(e))
    probs = stages.analyze_validate(d, P, new)
    if probs:
        raise HTTPException(422, "\n".join(probs))
    old = store.jload(d / "analysis.json") or {"sources": {}}
    out = new.model_dump()
    for k, s in out["sources"].items():
        was = old["sources"].get(k) or {}
        for f in ("hook_end", "hook_hold", "body_start", "cta_start"):
            if k in old["sources"] and was.get(f) != s.get(f) and f not in s["edited"]:
                s["edited"].append(f)
    store.jdump(d / "analysis.json", out)
    return out


def seconds_of(d, P, keys):
    tot = 0.0
    for k in keys:
        scan = store.jload(d / "work" / f"scan_{k}.json")
        prep = (store.jload(d / "work" / "prepare.json", {}) or {}).get(k) or {}
        tot += (scan or {}).get("duration") or prep.get("duration") or 40.0
    return tot


class Chain:
    """Jobs queued one after the other (each waits for the one before)."""

    def __init__(self, slug, grp):
        self.slug, self.grp, self.prev, self.made = slug, grp, None, []

    def add(self, queue, kind, title, spec, work=None):
        self.prev = jobs.add(self.slug, queue, kind, title, spec, depends_on=self.prev, grp=self.grp, work=work)
        self.made.append(self.prev)
        return self.prev

    def jobs(self):
        return [public(jobs.get(i)) for i in self.made]


def claude_running(slug, stage):
    return any(j["queue"] == "claude" and j["status"] in ACTIVE and j["kind"] == stage for j in jobs.list(slug))


@app.post("/api/products/{slug}/run")
def run(slug: str, body: dict = Body(...)):
    """Queue a step. `analyze` first queues the mechanical steps a source still lacks (copy, transcript, scan)."""
    license.require()
    d, P, _ = store.product(slug)
    step, force = body.get("step"), bool(body.get("force"))
    keys = [k for k in (body.get("keys") or store.source_keys(P)) if k in P["sources"]]
    ch = Chain(slug, f"{step}-{int(time.time())}")

    def mechanical(name, missing_only=True, only=None):
        st = {k: store.source_state(d, P, k) for k in keys}
        if name == "darija":
            # Claude + the darijadz skill correct Whisper's text, then darija_lint; one run for every source due
            todo = only if only is not None else [k for k in keys if not missing_only or st[k]["darija"] != "corrected"]
            if todo and not claude_running(slug, "darija"):
                ch.add("claude", "darija", f"Correct the Darija of {' '.join(todo)} with Claude",
                       {"type": "claude", "stage": "darija", "args": {"keys": todo}}, work=len(todo))
            return todo
        if name == "prepare":
            todo = [k for k in keys if not st[k]["copy"]] if missing_only else keys
            if todo:
                ch.add("light", "prepare", f"Prepare {' '.join(todo)}", batch_cmd("prepare", d, *todo), seconds_of(d, P, todo))
        elif name == "transcribe":
            todo = [k for k in keys if not st[k]["words"]] if missing_only else keys
            if todo:
                ch.add("heavy", "transcribe", f"Transcribe {' '.join(todo)}",
                       batch_cmd("transcribe", d, *todo, *(["--force"] if not missing_only else [])), seconds_of(d, P, todo))
            return todo
        elif name == "scan":
            todo = [k for k in keys if not st[k]["scan"]] if missing_only else keys
            if todo:
                ch.add("light", "scan", f"Scan {' '.join(todo)}",
                       batch_cmd("scan", d, *todo, *(["--force"] if not missing_only else [])), seconds_of(d, P, todo))

    if step in ("prepare", "transcribe", "scan", "darija"):
        done = mechanical(step, missing_only=not force)
        if step == "transcribe" and done:
            mechanical("darija", only=done)                 # a new Whisper draft is corrected again
        if step == "darija" and done and claude_running(slug, "darija") and not ch.made:
            raise HTTPException(409, "a Darija correction of this product is already queued or running")
        if not ch.made:
            return {"jobs": [], "note": f"nothing to do: every source already has its {step} (force to redo)"}
    elif step == "analyze":
        if claude_running(slug, "analyze"):
            raise HTTPException(409, "an analysis of this product is already queued or running")
        for name in ("prepare", "transcribe", "darija", "scan"):
            mechanical(name)
        ch.add("claude", "analyze", f"Analyze {P.get('name') or slug} with Claude", {"type": "claude", "stage": "analyze"},
               work=len(store.source_keys(P)))
    else:
        raise HTTPException(400, f"unknown step: {step}")
    return {"jobs": ch.jobs()}


def claude_job(slug, P, stage, title, args, work=1):
    if claude_running(slug, stage):
        raise HTTPException(409, f"this product already has a '{stage}' run queued or running")
    jid = jobs.add(slug, "claude", stage, title, {"type": "claude", "stage": stage, "args": args}, work=work)
    return public(jobs.get(jid))


@app.post("/api/products/{slug}/amend")
def amend(slug: str, body: dict = Body(...)):
    license.require()
    d, P, _ = store.product(slug)
    text = (body.get("feedback") or "").strip()
    if not text:
        raise HTTPException(400, "say what to change")
    if not (d / "analysis.json").exists():
        raise HTTPException(409, "there is no analysis yet: run the analysis first")
    return {"jobs": [claude_job(slug, P, "amend", f"Change the analysis of {P.get('name') or slug}", {"feedback": text})]}


@app.get("/api/products/{slug}/proposals")
def get_proposals(slug: str):
    return store.proposal_list(slug)


@app.post("/api/products/{slug}/propose")
def propose(slug: str, body: dict = Body(default={})):
    license.require()
    d, P, _ = store.product(slug)
    if not (d / "analysis.json").exists():
        raise HTTPException(409, "analyze the sources first: proposals are made from analysis.json")
    count = max(1, min(12, int(body.get("count") or 3)))
    args = {"count": count, "note": (body.get("note") or "").strip()}
    return {"jobs": [claude_job(slug, P, "propose", f"Propose {count} ad{'s' if count > 1 else ''} for {P.get('name') or slug}", args, work=count)]}


@app.patch("/api/products/{slug}/proposals/{pid}")
def patch_proposal(slug: str, pid: str, body: dict = Body(...)):
    try:
        return store.patch_proposal(slug, pid, body)
    except ValueError as e:
        raise HTTPException(422, str(e))


# ------------------------------------------------------------------ build queue + results

@app.post("/api/products/{slug}/build")
def build(slug: str, body: dict = Body(...)):
    """Ticked proposals -> mixes, then: cutouts -> graphics (Claude) -> build -> check [-> render]."""
    license.require()
    d, P, M = store.product(slug)
    ids = list(body.get("ids") or [])
    render = body.get("render") if body.get("render") is not None else settings.get("auto_render")
    try:
        mids = products.commit_proposals(slug, ids)
    except ValueError as e:
        raise HTTPException(422, str(e))
    if claude_running(slug, "graphics"):
        raise HTTPException(409, "a graphics run for this product is already queued or running")
    ch = Chain(slug, f"build-{int(time.time())}")
    frames, _ = products.cut_work(slug, mids)
    if frames:
        ch.add("heavy", "cut", f"Cut out the speaker for {len(mids)} mix{'es' if len(mids) > 1 else ''}", batch_cmd("cut", d, *mids), work=frames)
    ch.add("claude", "graphics", f"Plan the graphics of {len(mids)} mix{'es' if len(mids) > 1 else ''} with Claude",
           {"type": "claude", "stage": "graphics", "args": {"ids": mids, "gpt_cap": int(body.get("gpt_cap") or P.get("gpt_cap", settings.get("gpt_cap")))}},
           work=len(mids))
    ch.add("light", "build", f"Build {' '.join(mids)}", batch_cmd("build", d, *mids))
    ch.add("light", "check", f"Lint and snapshot {' '.join(mids)}", batch_cmd("check", d, *mids))
    if render:
        ch.add("heavy", "render", f"Render {' '.join(mids)}", batch_cmd("render", d, *mids), work=sum(M.get(m, {}).get("duration", 35) if isinstance(M.get(m, {}).get("duration"), (int, float)) else 35 for m in mids))
    return {"mixes": mids, "jobs": ch.jobs()}


@app.post("/api/products/{slug}/render")
def render(slug: str, body: dict = Body(...)):
    license.require()
    d, P, M = store.product(slug)
    ids = [i for i in (body.get("ids") or []) if i in M]
    if not ids:
        raise HTTPException(422, "no known mix id")
    ch = Chain(slug, f"render-{int(time.time())}")
    for mid in ids:
        if not (config.HF / mid / ".work" / "beats.json").exists():
            raise HTTPException(409, f"{mid} is not built yet")
        args = [mid] + (["--replace", "--force"] if body.get("replace") else [])
        ch.add("heavy", "render", f"Render {mid}", batch_cmd("render", d, *args), work=35)
    return {"jobs": ch.jobs()}


@app.post("/api/products/{slug}/fix")
def fix(slug: str, body: dict = Body(...)):
    """Stage D on one mix, then build + check again."""
    license.require()
    d, P, M = store.product(slug)
    mid = body.get("id")
    if mid not in M:
        raise HTTPException(404, "no such mix")
    if claude_running(slug, "fix") or claude_running(slug, "revise"):
        raise HTTPException(409, "a fix or revision of this product is already running")
    ch = Chain(slug, f"fix-{int(time.time())}")
    ch.add("claude", "fix", f"Fix {mid} with Claude", {"type": "claude", "stage": "fix", "args": {"id": mid, "note": (body.get("note") or "").strip()}})
    ch.add("light", "build", f"Build {mid}", batch_cmd("build", d, mid, "--force"))
    ch.add("light", "check", f"Lint and snapshot {mid}", batch_cmd("check", d, mid, "--force"))
    return {"jobs": ch.jobs()}


@app.post("/api/products/{slug}/revise")
def revise(slug: str, body: dict = Body(...)):
    """Stage E: the user's feedback on one ad; rebuilt and re-rendered under the same file name."""
    license.require()
    d, P, M = store.product(slug)
    mid, text = body.get("id"), (body.get("feedback") or "").strip()
    if mid not in M:
        raise HTTPException(404, "no such mix")
    if not text:
        raise HTTPException(400, "say what to change")
    if claude_running(slug, "fix") or claude_running(slug, "revise"):
        raise HTTPException(409, "a fix or revision of this product is already running")
    ch = Chain(slug, f"revise-{int(time.time())}")
    ch.add("claude", "revise", f"Revise {mid} with Claude", {"type": "claude", "stage": "revise", "args": {"id": mid, "feedback": text}})
    ch.add("light", "build", f"Build {mid}", batch_cmd("build", d, mid, "--force"))
    ch.add("light", "check", f"Lint and snapshot {mid}", batch_cmd("check", d, mid, "--force"))
    ch.add("heavy", "render", f"Render {mid} (same file name)", batch_cmd("render", d, mid, "--replace", "--force"), work=35)
    return {"jobs": ch.jobs()}


@app.get("/api/products/{slug}/results")
def get_results(slug: str):
    return products.results(slug)


# ------------------------------------------------------------------ fresh edits

@app.get("/api/fresh")
def list_fresh():
    return fresh.list_all()


@app.post("/api/fresh")
def create_fresh(body: dict = Body(...)):
    """One footage -> a project; queues step 1 (project), the transcript and the cutout."""
    license.require()
    try:
        slug = fresh.create(body.get("footage") or "", body.get("slug"), body.get("out_dir"), body.get("name"), body.get("whisper_prompt") or "")
    except ValueError as e:
        raise HTTPException(422, str(e))
    f = fresh.info(slug)
    ch = Chain(slug, f"fresh-{int(time.time())}")
    ch.add("light", "fresh_init", f"Set up the project {slug}", {"type": "fresh_init"})
    tr = ch.add("heavy", "transcribe", f"Transcribe {slug}", {"type": "fresh_transcribe"}, work=60)
    # beside the cutout, not before it: a Claude problem must not hold up a 30-minute cutout
    ch.made.append(jobs.add(slug, "claude", "darija", f"Correct the Darija of {slug} with Claude", FRESH_DARIJA,
                            depends_on=tr, grp=ch.grp, work=1))
    ch.add("heavy", "cut", f"Cut out the speaker of {slug}", {"type": "fresh_cutout"}, work=60 * 30)
    return {"slug": slug, "fresh": f, "jobs": ch.jobs()}


FRESH_DARIJA = {"type": "claude", "stage": "darija_fresh", "args": {"fresh": True}}


@app.post("/api/fresh/{slug}/darija")
def darija_fresh(slug: str):
    """Correct (again) the Darija of the fresh edit's transcript: Claude + darijadz, then darija_lint."""
    license.require()
    f = fresh.info(slug)
    if not f["words"]:
        raise HTTPException(409, "the transcript is not ready yet")
    if claude_running(slug, "darija"):
        raise HTTPException(409, "the Darija correction is already queued or running")
    jid = jobs.add(slug, "claude", "darija", f"Correct the Darija of {f.get('name') or slug} with Claude", FRESH_DARIJA, work=1)
    return {"jobs": [public(jobs.get(jid))]}


@app.get("/api/fresh/{slug}")
def get_fresh(slug: str):
    f = fresh.info(slug)
    proj = config.HF / slug
    f["words_data"] = store.jload(proj / ".work" / "words.json", [])
    f["transcript"] = darija.summary(proj / ".work" / "words.json")
    return f


@app.put("/api/fresh/{slug}/marks")
def put_marks(slug: str, body: SM.FreshMarks):
    try:
        return fresh.set_marks(slug, body)
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.post("/api/fresh/{slug}/run")
def run_fresh(slug: str, body: dict = Body(default={})):
    """Stage F: Claude does steps 3-10 and renders. Waits for the cutout if it is still running."""
    license.require()
    f = fresh.info(slug)
    if not f.get("marks"):
        raise HTTPException(409, "set the hook end, body and CTA on the timeline first")
    if not f["words"]:
        raise HTTPException(409, "the transcript is not ready yet")
    if claude_running(slug, "fresh"):
        raise HTTPException(409, "this edit is already running")
    dep = next((j["id"] for j in jobs.list(slug) if j["kind"] == "cut" and j["status"] in ACTIVE), None)
    fix = next((j["id"] for j in jobs.list(slug) if j["kind"] == "darija" and j["status"] in ACTIVE), None)
    if fix is None and darija.state(config.HF / slug / ".work" / "words.json") != "corrected":
        fix = jobs.add(slug, "claude", "darija", f"Correct the Darija of {f.get('name') or slug} with Claude", FRESH_DARIJA, work=1)
    dep = dep or fix                                        # the cutout takes far longer than the correction
    jid = jobs.add(slug, "claude", "fresh", f"Edit {f.get('name') or slug} with Claude",
                   {"type": "claude", "stage": "fresh", "args": {"gpt_cap": int(body.get("gpt_cap") or settings.get("gpt_cap"))}},
                   depends_on=dep, work=1)
    return {"jobs": [public(jobs.get(jid))]}


@app.post("/api/fresh/{slug}/cutout")
def redo_cutout(slug: str):
    license.require()
    fresh.info(slug)
    jid = jobs.add(slug, "heavy", "cut", f"Cut out the speaker of {slug}", {"type": "fresh_cutout"}, work=60 * 30)
    return {"jobs": [public(jobs.get(jid))]}


# ------------------------------------------------------------------ library (GPT pictures)

@app.get("/api/library")
def library():
    lib = store.jload(config.GPT_DIR / "library.json") or {}
    return {"dir": str(config.GPT_DIR), "updated": lib.get("updated"), "assets": lib.get("assets", []),
            "exists": (config.GPT_DIR / "library.json").exists()}


@app.get("/api/library/search")
def library_search(q: str):
    r = subprocess.run([config.skill_python(), str(config.SCRIPTS / "asset_lib.py"), "search", q], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=60, cwd=str(config.ROOT), env=config.child_env())
    return {"q": q, "output": (r.stdout + r.stderr).strip()}


@app.get("/api/library/gpt-status")
def gpt_status():
    try:
        r = subprocess.run([config.skill_python(), str(config.SCRIPTS / "gpt_assets.py"), "status"], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=40, cwd=str(config.ROOT), env=config.child_env())
        text = r.stdout.strip()
        try:
            return json.loads(text[text.index("{"):])
        except (ValueError, IndexError):
            return {"raw": (text + "\n" + r.stderr).strip(), "exit": r.returncode}
    except subprocess.TimeoutExpired:
        return {"raw": "gpt_assets.py status timed out", "exit": -1}


# ------------------------------------------------------------------ jobs

@app.get("/api/jobs")
def list_jobs(slug: str | None = None, limit: int = 60):
    return [public(j) for j in jobs.list(slug, limit)]


@app.get("/api/jobs/{jid}")
def get_job(jid: int):
    j = jobs.get(jid)
    if not j:
        raise HTTPException(404, "no such job")
    return public(j)


@app.post("/api/jobs/{jid}/cancel")
def cancel_job(jid: int):
    if not jobs.cancel(jid):
        raise HTTPException(409, "this job is not queued or running")
    return public(jobs.get(jid))


@app.get("/api/jobs/{jid}/logs")
def job_logs(jid: int, after: int = 0):
    return jobs.logs(jid, after)


@app.get("/api/jobs/{jid}/stream")
async def job_stream(jid: int, request: Request, after: int = 0):
    if not jobs.get(jid):
        raise HTTPException(404, "no such job")

    async def gen():
        seq, last = after, None
        while True:
            if await request.is_disconnected():
                return
            rows = await asyncio.to_thread(jobs.logs, jid, seq)
            for r in rows:
                seq = r["seq"]
                yield f"id: {seq}\ndata: {json.dumps(r, ensure_ascii=False)}\n\n"
            j = await asyncio.to_thread(jobs.get, jid)
            st = (j["status"], j["progress"], j["eta_s"])
            if st != last:
                last = st
                yield f"event: status\ndata: {json.dumps(public(j), ensure_ascii=False)}\n\n"
            if j["status"] not in ACTIVE and not rows:
                yield "event: end\ndata: {}\n\n"
                return
            await asyncio.sleep(0.3 if rows else 0.6)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ------------------------------------------------------------------ media

def picture(p, cache="max-age=86400"):
    return FileResponse(p, headers={"Cache-Control": cache})


@app.get("/media/{slug}/src/{key}")
def media_source(slug: str, key: str):
    d, P, _ = store.product(slug)
    if key not in P["sources"]:
        raise HTTPException(404, "no such source")
    p = store.B.copy_path(d, P, key)
    if not p.exists():
        raise HTTPException(404, "this source has no copy yet: run Prepare")
    return FileResponse(p, media_type="video/mp4")


@app.get("/media/{slug}/work/{name}")
def media_work(slug: str, name: str):
    d, _, _ = store.product(slug)
    p = d / "work" / name
    if Path(name).name != name or p.suffix.lower() not in (".jpg", ".jpeg", ".png") or not p.exists():
        raise HTTPException(404, "no such picture")
    return picture(p, "no-cache")


_thumbs = threading.Semaphore(4)


@app.get("/media/{slug}/frame/{key}/{frame}.jpg")
def media_frame(slug: str, key: str, frame: int, w: int = 160):
    d, P, _ = store.product(slug)
    if key not in P["sources"] or frame < 0:
        raise HTTPException(404, "no such source")
    w = min((96, 160, 270, 360), key=lambda x: abs(x - w))
    out = config.DATA / "thumbs" / slug / f"{key}_{frame}_{w}.jpg"
    if not out.exists():
        src = store.B.copy_path(d, P, key)
        if not src.exists():
            raise HTTPException(404, "this source has no copy yet")
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(f".{threading.get_ident()}.tmp.jpg")
        with _thumbs:
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{frame / 30:.4f}", "-i", str(src), "-frames:v", "1",
                            "-vf", f"scale={w}:-2", "-q:v", "4", str(tmp)], capture_output=True, env=config.child_env())
        if not tmp.exists():
            raise HTTPException(404, "no such frame")
        os.replace(tmp, out)
    return picture(out)


@app.get("/media/{slug}/ad/{mid}")
def media_ad(slug: str, mid: str):
    return FileResponse(products.ad_file(slug, mid), media_type="video/mp4")


@app.get("/media/{slug}/sheet/{mid}/{name}")
def media_sheet(slug: str, mid: str, name: str):
    store.product(slug)
    return picture(products.work_file(mid, name), "no-cache")


@app.get("/media/{slug}/snap/{mid}/{name}")
def media_snap(slug: str, mid: str, name: str):
    store.product(slug)
    return picture(products.snap_file(mid, name), "no-cache")


@app.get("/media/fresh/{slug}/footage")
def media_fresh_footage(slug: str):
    fresh.info(slug)
    main = fresh.main_footage(config.HF / slug)
    if not main:
        raise HTTPException(404, "no footage yet")
    return FileResponse(main, media_type="video/mp4" if main.suffix.lower() != ".mov" else "video/quicktime")


@app.get("/media/fresh/{slug}/ad")
def media_fresh_ad(slug: str):
    f = fresh.info(slug)
    if not f.get("ad"):
        raise HTTPException(404, "no ad yet")
    return FileResponse(f["ad_path"], media_type="video/mp4")


@app.get("/media/fresh/{slug}/work/{name}")
def media_fresh_work(slug: str, name: str):
    fresh.info(slug)
    p = config.HF / slug / ".work" / name
    if Path(name).name != name or p.suffix.lower() not in (".jpg", ".png") or not p.exists():
        raise HTTPException(404, "no such picture")
    return picture(p, "no-cache")


@app.get("/media/fresh/{slug}/snap/{name}")
def media_fresh_snap(slug: str, name: str):
    fresh.info(slug)
    return picture(products.snap_file(slug, name), "no-cache")


@app.get("/media/library/{aid}")
def media_library(aid: str):
    lib = store.jload(config.GPT_DIR / "library.json") or {}
    a = next((x for x in lib.get("assets", []) if x.get("id") == aid), None)
    if not a:
        raise HTTPException(404, "no such picture")
    p = config.GPT_DIR / a["file"]
    if not p.exists():
        raise HTTPException(404, "picture file missing")
    return picture(p)


@app.get("/media/thumb")
def media_thumb(path: str, w: int = 160):
    return picture(products.thumb(path, min((96, 160, 270, 360), key=lambda x: abs(x - w))))


@app.get("/media/font/thmanyah.otf")
def font():
    return FileResponse(config.SKILL / "assets" / "thmanyah-sans-black.otf", media_type="font/otf")


# ------------------------------------------------------------------ the built UI

if Path(config.DIST).exists():
    app.mount("/", StaticFiles(directory=str(config.DIST), html=True), name="ui")
else:
    @app.get("/")
    def no_ui():
        return JSONResponse({"detail": f"the UI is not built: run `npm run build` in bluxtech-studio/desktop (expected {config.DIST})"},
                            status_code=503)
