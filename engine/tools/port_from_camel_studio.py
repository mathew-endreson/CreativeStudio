"""Bring camel-studio's backend modules and prompts into the engine, with the few edits the engine needs.
Run once (and again after a change in camel-studio you want here):  python tools/port_from_camel_studio.py"""
import re
import shutil
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[1]
SRC = ENGINE.parent.parent / "camel-studio"
PKG = ENGINE / "bluxtech_engine"

if not (SRC / "backend" / "app.py").exists():
    sys.exit(f"camel-studio not found at {SRC}")

for name in ("jobs.py", "store.py", "schemas.py", "stages.py", "claude_runner.py"):
    shutil.copy2(SRC / "backend" / name, PKG / name)
(ENGINE / "prompts").mkdir(exist_ok=True)
for p in (SRC / "prompts").glob("*.md"):
    shutil.copy2(p, ENGINE / "prompts" / p.name)


def patch(name, pairs):
    p = PKG / name
    text = p.read_text(encoding="utf-8")
    for old, new in pairs:
        if old not in text:
            sys.exit(f"{name}: expected text not found:\n{old}")
        text = text.replace(old, new, 1)
    p.write_text(text, encoding="utf-8")


# jobs.py: a cancel hook for runners that have no process handle (the Agent SDK).
patch("jobs.py", [
    ("        self.cancelled = False\n        self.proc = None\n",
     "        self.cancelled = False\n        self.proc = None\n        self.cancel_hook = None            # runners without a process handle (the Agent SDK) set this\n"),
    ("        self.cancelled = True\n        p = self.proc\n",
     "        self.cancelled = True\n        if self.cancel_hook:\n            try:\n                self.cancel_hook()\n            except Exception:\n                pass\n        p = self.proc\n"),
])

# claude_runner.py: the cli runner keeps its code; one_run() picks the runner the settings name.
patch("claude_runner.py", [
    ("def one_run(ctx, stage, prompt, sid, resume, add_dirs):\n    \"\"\"One claude process.",
     "def one_run_cli(ctx, stage, prompt, sid, resume, add_dirs):\n    \"\"\"One claude process."),
    ("You are running headless inside Camel Studio, a local app that drives the camel-gpt skill.",
     "You are running headless inside BluxTech Studio, a desktop app that drives the camel-gpt skill."),
    ("           \"five_hour_utilization\": state.get(\"limit\"),\n",
     "           \"five_hour_utilization\": state.get(\"limit\"), \"runner\": \"cli\",\n"),
])
with open(PKG / "claude_runner.py", "a", encoding="utf-8") as f:
    f.write('''

def one_run(ctx, stage, prompt, sid, resume, add_dirs):
    """The runner the settings choose: `cli` = the local claude.exe and its login (the owner's own machine),
    `sdk` = the Agent SDK with the user's API key (the shipped product)."""
    from . import settings
    if settings.runner() == "sdk":
        from . import agent_runner
        return agent_runner.one_run(ctx, stage, prompt, sid, resume, add_dirs)
    return one_run_cli(ctx, stage, prompt, sid, resume, add_dirs)
''')

# store.py: a proposal the user ticked and built is "accepted".
patch("store.py", [
    ('    if patch.get("status") in ("proposed", "rejected"):',
     '    if patch.get("status") in ("proposed", "rejected", "accepted"):'),
    ("batch.py (the skill) is the only thing that knows their layout:\nthis module asks it, and adds what the app keeps beside it (studio.json: the Claude session and its usage).",
     "batch.py (the skill) is the only thing that knows their layout:\nthis module asks it, and adds what the app keeps beside it (studio.json: the Claude session and its usage).\nPorted from camel-studio by tools/port_from_camel_studio.py; the engine's additions live in products.py."),
])


# stages.py: a stage may load its own (dir, product, mixes) triple (the fresh stage has no batch folder).
patch("stages.py", [
    ("    finish: Callable = None     # (src dir, product, mixes, parsed, args) -> dict: the app's mechanical follow-up\n",
     "    finish: Callable = None     # (src dir, product, mixes, parsed, args) -> dict: the app's mechanical follow-up\n"
     "    load: Callable = None       # (slug) -> (dir, product, mixes); default store.product\n"),
])
patch("claude_runner.py", [
    ('    d, P, M = store.product(job["slug"])\n    args = spec.get("args") or {}',
     '    d, P, M = (stage.load or store.product)(job["slug"])\n    args = spec.get("args") or {}'),
])

# stages.py: the fresh / graphics / fix / revise stages register themselves from stages_more.py.
with open(PKG / "stages.py", "a", encoding="utf-8") as f:
    f.write("\n\nfrom .stages_more import register as _register_more  # noqa: E402\n_register_more(STAGES)\n")

print("ported:", ", ".join(p.name for p in PKG.glob("*.py")))
print("prompts:", ", ".join(p.name for p in (ENGINE / "prompts").glob("*.md")))
