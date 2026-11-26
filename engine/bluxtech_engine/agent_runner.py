"""Headless Claude through the Agent SDK: the `sdk` runner.

Same judgment stages as claude_runner.one_run_cli, but the Claude Code runtime comes bundled inside the SDK package
(no install on the machine) and the credential is the user's Anthropic API key (Settings, sealed with DPAPI). This is
the runner a shipped BluxTech Studio uses: Anthropic does not allow claude.ai logins inside third-party products.

    ClaudeAgentOptions(cwd=workspace, setting_sources=["project"])   loads .claude/skills/camel-gpt from the workspace
    permission_mode="acceptEdits" + can_use_tool -> deny                edits inside the workspace, nothing that would
                                                                        ask a question (same as --permission-prompts none)
    tools / allowed_tools                                               only what the stage lists
    resume / session_id                                                 one session per product, resumed for revisions
"""
import asyncio

from claude_agent_sdk import (AssistantMessage, ClaudeAgentOptions, ClaudeSDKClient, PermissionResultDeny,
                              ResultMessage, SystemMessage, TextBlock, ToolResultBlock, ToolUseBlock, UserMessage)

from . import config, settings
from .jobs import JobFailed

USAGE_KEYS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")


def one_run(ctx, stage, prompt, sid, resume, add_dirs):
    """One Agent SDK session turn. Returns (run, result) like the cli runner, or None when the session to resume
    is gone (the caller starts a new one)."""
    from .claude_runner import SYSTEM, one_line, result_text, tool_line

    key = settings.api_key()
    if not key:
        raise JobFailed("no Anthropic API key: add one in Settings (the API-key runner needs it), or switch the "
                        "runner to your Claude Code login")
    cfg = config.settings()["claude"]

    async def deny(tool, inp, context):
        return PermissionResultDeny(message=f"{tool} is not on this stage's list in BluxTech Studio", interrupt=False)

    env = config.child_env({"ANTHROPIC_API_KEY": key, "CLAUDE_AGENT_SDK_CLIENT_APP": "bluxtech-studio"})
    opts = ClaudeAgentOptions(
        cwd=str(config.ROOT), add_dirs=[str(d) for d in add_dirs],
        tools=[t.strip() for t in stage.builtin.split(",") if t.strip()], allowed_tools=list(stage.allowed),
        permission_mode="acceptEdits", can_use_tool=deny,
        system_prompt={"type": "preset", "preset": "claude_code", "append": SYSTEM},
        setting_sources=["project"], strict_mcp_config=True,
        model=cfg.get("model") or None, effort=cfg.get("effort") or None,
        max_turns=settings.get("max_turns"), max_budget_usd=settings.get("max_budget_usd"),
        env={"ANTHROPIC_API_KEY": key, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1", "PYTHONUNBUFFERED": "1",
             "CLAUDE_AGENT_SDK_CLIENT_APP": "bluxtech-studio", "PATH": env["PATH"]},
        stderr=lambda line: ctx.log("out", line.rstrip()) if line.strip() else None,
        **({"resume": sid} if resume else {"session_id": sid}),
    )
    state = {"result": None, "model": None, "limit": None, "tools": None}

    def handle(m):
        if isinstance(m, SystemMessage):
            if m.subtype == "init":
                state["model"] = m.data.get("model")
                ctx.log("sys", f"session {m.data.get('session_id')}  model {m.data.get('model')}  "
                               f"tools {', '.join(m.data.get('tools') or [])}")
            elif m.subtype:
                ctx.log("sys", f"{m.subtype}: {one_line(m.data, 300)}")
        elif isinstance(m, AssistantMessage):
            state["model"] = m.model or state["model"]
            if m.error:
                ctx.log("error", f"assistant error: {m.error}")
            for b in m.content:
                if isinstance(b, TextBlock) and b.text.strip():
                    ctx.log("claude", b.text.strip())
                elif isinstance(b, ToolUseBlock):
                    ctx.log("tool", tool_line(b.name, b.input or {}))
        elif isinstance(m, UserMessage):
            content = m.content if isinstance(m.content, list) else []
            for b in content:
                if isinstance(b, ToolResultBlock):
                    ctx.log("error" if b.is_error else "result", one_line(result_text(b.content)))
        elif isinstance(m, ResultMessage):
            state["result"] = m
        else:
            info = getattr(m, "rate_limit_info", None) or getattr(m, "data", None)
            if info is not None:
                ctx.log("sys", f"{type(m).__name__}: {one_line(info, 300)}")

    async def go():
        client = ClaudeSDKClient(options=opts)
        loop = asyncio.get_running_loop()

        def cancel():
            asyncio.run_coroutine_threadsafe(client.disconnect(), loop)

        ctx.cancel_hook = cancel
        try:
            await client.connect()
            await client.query(prompt)
            async for m in client.receive_response():
                handle(m)
        finally:
            ctx.cancel_hook = None
            try:
                await client.disconnect()
            except Exception:
                pass

    try:
        asyncio.run(go())
    except JobFailed:
        raise
    except Exception as e:
        if ctx.cancelled:
            raise JobFailed("cancelled")
        msg = str(e)
        if resume and "No conversation found" in msg:
            return None
        raise JobFailed(f"the Claude run failed: {type(e).__name__}: {one_line(msg, 600)}")
    if ctx.cancelled:
        raise JobFailed("cancelled")
    r = state["result"]
    if r is None:
        raise JobFailed("the Claude run ended without a result")
    if resume and r.is_error and "No conversation found" in (r.result or ""):
        return None
    usage = r.usage or {}
    run = {"stage": stage.name, "job": ctx.id, "session_id": r.session_id or sid, "turns": r.num_turns,
           "duration_ms": r.duration_ms, "cost_usd": r.total_cost_usd, "model": state["model"], "is_error": bool(r.is_error),
           "usage": {k: usage.get(k) for k in USAGE_KEYS}, "five_hour_utilization": None, "runner": "sdk",
           "denied": [one_line(x, 300) for x in (r.permission_denials or [])], "subtype": r.subtype}
    ctx.log("usage", f"{run['turns']} turns, {round((run['duration_ms'] or 0) / 1000)} s, "
                     f"in {sum(v or 0 for k, v in run['usage'].items() if k != 'output_tokens'):,} tok, "
                     f"out {run['usage']['output_tokens'] or 0:,} tok, ${run['cost_usd'] or 0:.2f} (API key)")
    for x in run["denied"]:
        ctx.log("error", f"tool call refused (not on this stage's list): {x}")
    if r.subtype in ("error_max_turns", "error_max_budget_usd"):
        ctx.log("error", f"the run stopped early: {r.subtype} (raise max_turns / max_budget_usd in Settings if the stage needs more)")
    result = {"session_id": run["session_id"], "is_error": r.is_error, "result": r.result, "subtype": r.subtype,
              "permission_denials": r.permission_denials or [], "errors": r.errors or []}
    return run, result
