"""Headless Claude Code for the judgment steps.

    claude -p --output-format stream-json --verbose            print mode, one JSON event per line
           --permission-mode acceptEdits --permission-prompts none
                                                               file edits inside the working folders are accepted;
                                                               anything else that would ask is refused (no bypass)
           --tools ... --allowedTools ...                      only what the stage needs
           --session-id <uuid> | --resume <uuid>               one session per product, resumed for "make more",
                                                               fixes and revisions
           --add-dir <product / Ads folders outside the root>

The prompt goes in on stdin. It uses the local Claude Code login: no API key. (Flags checked against
`claude --help` of 2.1.330; --json-schema exists there too, but a stage's result is a file, validated here.)
"""
import json
import uuid
from pathlib import Path

from . import config, stages, store
from .jobs import JobFailed

MAX_FIXES = 2
SYSTEM = ("You are running headless inside BluxTech Studio, a desktop app that drives the camel-gpt skill. Nobody can "
          "answer a question during this run: decide, and say what you were unsure of in your last message. "
          "Run one command per shell call, starting with python, ffmpeg, ffprobe or npx hyperframes: no pipes, no "
          "cd, no variable assignments (PYTHONIOENCODING is already utf-8). Paths with spaces go in double quotes. "
          "Never delete, rename or overwrite source footage, existing _hyperframes projects, finished ads, or "
          "the illustration library (the folder asset_lib.py reports as its library).")


def one_line(s, n=400):
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[:n] + " ..."


def tool_line(name, inp):
    if name in ("Read", "Write", "Edit"):
        return f"{name}  {store.rel(inp.get('file_path', ''))}"
    if name in ("PowerShell", "Bash"):
        return f"$ {one_line(inp.get('command', ''), 600)}"
    if name in ("Glob", "Grep"):
        return f"{name}  {inp.get('pattern', '')}" + (f"  in {store.rel(inp['path'])}" if inp.get("path") else "")
    if name == "Skill":
        return f"Skill  {inp.get('skill', '')}"
    return f"{name}  {one_line(json.dumps(inp, ensure_ascii=False), 300)}"


def result_text(content):
    if isinstance(content, list):
        return " ".join(c.get("text", f"[{c.get('type')}]") if isinstance(c, dict) else str(c) for c in content)
    return str(content)


def command(stage, sid, resume, add_dirs):
    exe = config.claude_bin()
    if not exe:
        raise JobFailed("the claude CLI was not found. Install Claude Code (https://claude.com/claude-code: on Windows "
                        "`irm https://claude.ai/install.ps1 | iex` in PowerShell), run `claude` once to log in, then "
                        "try again. Or set CAMEL_CLAUDE to the path of claude.exe.")
    cfg = config.settings()["claude"]
    cmd = [exe, "-p", "--output-format", "stream-json", "--verbose",
           "--permission-mode", "acceptEdits", "--permission-prompts", "none",
           "--tools", stage.builtin, "--allowedTools", *stage.allowed,
           "--strict-mcp-config", "--append-system-prompt", SYSTEM]
    for d in add_dirs:
        cmd += ["--add-dir", str(d)]
    if cfg.get("model"):
        cmd += ["--model", cfg["model"]]
    if cfg.get("effort"):
        cmd += ["--effort", cfg["effort"]]
    return cmd + (["--resume", sid] if resume else ["--session-id", sid])


def outside_dirs(P):
    out = []
    for key in ("product_dir", "ads_dir"):
        p = P.get(key)
        if p and Path(p).is_dir():
            try:
                Path(p).resolve().relative_to(config.ROOT)
            except ValueError:
                out.append(Path(p))
    return out


def one_run_cli(ctx, stage, prompt, sid, resume, add_dirs):
    """One claude process. Returns its result event (or raises)."""
    state = {"result": None, "init": None, "noise": []}

    def on_line(line):
        try:
            e = json.loads(line)
        except ValueError:
            state["noise"].append(line)
            ctx.log("out", line)
            return
        t = e.get("type")
        if t == "system" and e.get("subtype") == "init":
            state["init"] = e
            ctx.log("sys", f"session {e.get('session_id')}  model {e.get('model')}  tools {', '.join(e.get('tools', []))}")
        elif t == "assistant":
            for c in e["message"].get("content", []):
                if c.get("type") == "text" and c.get("text", "").strip():
                    ctx.log("claude", c["text"].strip())
                elif c.get("type") == "tool_use":
                    ctx.log("tool", tool_line(c.get("name"), c.get("input") or {}))
        elif t == "user":
            content = e["message"].get("content")
            for c in content if isinstance(content, list) else []:
                if c.get("type") == "tool_result":
                    ctx.log("error" if c.get("is_error") else "result", one_line(result_text(c.get("content"))))
        elif t == "rate_limit_event":
            w = (e.get("rate_limit_info") or {}).get("unifiedWindows", {}).get("five_hour", {})
            if w.get("utilization") is not None:
                state["limit"] = w["utilization"]
        elif t == "result":
            state["result"] = e

    code = ctx.spawn(command(stage, sid, resume, add_dirs), cwd=config.ROOT, stdin_text=prompt, on_line=on_line)
    r = state["result"]
    if r is None:
        tail = " | ".join(state["noise"][-3:])
        if resume and "No conversation found" in tail:
            return None                                     # the session is gone: the caller starts a new one
        raise JobFailed(f"claude exited with code {code} and no result. {tail}")
    u = r.get("usage") or {}
    run = {"stage": stage.name, "job": ctx.id, "session_id": r.get("session_id") or sid, "turns": r.get("num_turns"),
           "duration_ms": r.get("duration_ms"), "cost_usd": r.get("total_cost_usd"),
           "model": (state["init"] or {}).get("model"), "is_error": bool(r.get("is_error")),
           "usage": {k: u.get(k) for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens",
                                           "cache_read_input_tokens")},
           "five_hour_utilization": state.get("limit"), "runner": "cli",
           "denied": [one_line(json.dumps(x, ensure_ascii=False), 300) for x in r.get("permission_denials") or []]}
    ctx.log("usage", f"{run['turns']} turns, {round((run['duration_ms'] or 0) / 1000)} s, "
                     f"in {sum(v or 0 for k, v in run['usage'].items() if k != 'output_tokens'):,} tok, "
                     f"out {run['usage']['output_tokens'] or 0:,} tok, list price ${run['cost_usd'] or 0:.2f}"
                     + (f", 5-hour limit at {round(run['five_hour_utilization'] * 100)}%"
                        if run.get("five_hour_utilization") is not None else ""))
    for x in run["denied"]:
        ctx.log("error", f"tool call refused (not on this stage's list): {x}")
    return run, r


def run_stage(ctx, job, spec):
    """Prompt -> Claude -> the stage's file -> validate. A file that fails goes back to the same session with
    the problems, at most twice; then the job fails and shows them."""
    stage = stages.STAGES[spec["stage"]]
    d, P, M = (stage.load or store.product)(job["slug"])
    args = spec.get("args") or {}
    if stage.before:                                        # first: a stage's context may describe what it prepares
        stage.before(d, args)
    prompt = stages.render(stage.name, stage.context(d, P, args))
    add_dirs = outside_dirs(P)
    sid = None if stage.own_session else store.studio(d).get("session_id")
    resume = bool(sid)
    sid = sid or str(uuid.uuid4())
    ctx.log("sys", f"stage {stage.name}: {'resuming' if resume else 'new'} session {sid}")
    ctx.log("prompt", prompt)
    runs, probs = [], []
    for attempt in range(MAX_FIXES + 1):
        got = one_run(ctx, stage, prompt, sid, resume, add_dirs)
        if got is None:                                     # stale session id: start a fresh one, once
            sid, resume = str(uuid.uuid4()), False
            ctx.log("sys", f"the old session could not be resumed: new session {sid}")
            got = one_run(ctx, stage, prompt, sid, resume, add_dirs)
            if got is None:
                raise JobFailed("claude could not start a session")
        run, result = got
        sid, resume = run["session_id"], True
        if not stage.own_session:
            store.studio_update(d, lambda st: st.update(session_id=sid))
        obj, probs = stages.check(stage, d, P, args)
        run["ok"] = not probs
        runs.append(run)
        store.record_run(d, run)
        if result.get("is_error"):
            raise JobFailed(f"claude stopped with an error: {one_line(result.get('result') or result.get('subtype'), 600)}")
        if not probs:
            ctx.log("sys", f"{store.rel(stage.output(d, args))} is valid")
            extra = stage.finish(d, P, M, obj, args) if stage.finish else {}
            if extra:
                ctx.log("sys", "; ".join(f"{k}: {v}" for k, v in extra.items() if v))
            return {"stage": stage.name, "output": store.rel(stage.output(d, args)), "attempts": attempt + 1,
                    "runs": runs, "final": result.get("result"), **extra}
        ctx.log("error", f"validation failed ({len(probs)} problem(s)):\n" + "\n".join(f"- {p}" for p in probs))
        if attempt < MAX_FIXES:
            prompt = (f"The app validated `{store.rel(stage.output(d, args))}` and found these problems:\n\n"
                      + "\n".join(f"- {p}" for p in probs)
                      + "\n\nFix the file in place (keep everything that was right), following the same schema and "
                        "rules as before. Do not render anything.")
            ctx.log("prompt", prompt)
    raise JobFailed(f"{store.rel(stage.output(d, args))} is still invalid after {MAX_FIXES} fixes:\n"
                    + "\n".join(f"- {p}" for p in probs))


def one_run(ctx, stage, prompt, sid, resume, add_dirs):
    """The runner the settings choose: `cli` = the local claude.exe and its login (the owner's own machine),
    `sdk` = the Agent SDK with the user's API key (the shipped product)."""
    from . import settings
    if settings.runner() == "sdk":
        from . import agent_runner
        return agent_runner.one_run(ctx, stage, prompt, sid, resume, add_dirs)
    return one_run_cli(ctx, stage, prompt, sid, resume, add_dirs)
