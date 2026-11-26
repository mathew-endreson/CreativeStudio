"""The judgment steps Claude does headless. A stage = a prompt template (prompts/<stage>.md), the file it must
write, a schema, and the tools it may use. No editing rule lives here: the templates send Claude to the skill."""
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from pydantic import ValidationError

from . import config, schemas, store

# Tools: files, python, ffmpeg / ffprobe, and the HyperFrames CLI. Nothing else, and no permission bypass.
FILES = ["Read", "Write", "Edit", "Glob", "Grep"]
PY = ["PowerShell(python *)", "Bash(python *)"]
FF = ["PowerShell(ffmpeg *)", "PowerShell(ffprobe *)", "Bash(ffmpeg *)", "Bash(ffprobe *)"]
HYPER = ["PowerShell(npx hyperframes *)", "Bash(npx hyperframes *)"]


@dataclass
class Stage:
    name: str
    title: str
    output: Callable            # (src dir, args) -> the file Claude must write
    context: Callable           # (src dir, product, args) -> template variables
    validate: Callable          # (src dir, product, parsed json) -> list of problems
    allowed: list
    builtin: str = "Read,Write,Edit,Glob,Grep,PowerShell,Bash,Skill"
    schema: type = None
    before: Callable = None     # (src dir, args): clear what an earlier run left where Claude will write
    finish: Callable = None     # (src dir, product, mixes, parsed, args) -> dict: the app's mechanical follow-up
    load: Callable = None       # (slug) -> (dir, product, mixes); default store.product
    own_session: bool = False   # a new Claude session for each job, not the product's shared one


def render(name, ctx):
    text = (config.PROMPTS / f"{name}.md").read_text(encoding="utf-8")
    for k, v in ctx.items():
        text = text.replace("{{" + k + "}}", str(v))
    return text


def schema_text(model):
    return json.dumps(model.model_json_schema(), ensure_ascii=False, indent=1)


def check(stage, d, P, args):
    """Load and validate what the stage wrote. Returns (parsed or None, problems)."""
    out = stage.output(d, args)
    if not out.exists():
        return None, [f"{store.rel(out)} was not written"]
    try:
        raw = json.loads(out.read_text(encoding="utf-8-sig"))
    except ValueError as e:
        return None, [f"{store.rel(out)} is not valid JSON: {e}"]
    try:
        obj = stage.schema.model_validate(raw)
    except ValidationError as e:
        return None, [f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}" for err in e.errors()[:40]]
    probs = stage.validate(d, P, obj, args)
    return (obj if not probs else None), probs


# ------------------------------------------------------------------ A. analyze

def source_len(d, P, k):
    scan = store.jload(d / "work" / f"scan_{k}.json")
    return scan["duration"] if scan else None


def analyze_context(d, P, args):
    keys = store.source_keys(P)
    src = store.rel(d)
    rows = []
    for k in keys:
        s, scan = P["sources"][k], store.jload(d / "work" / f"scan_{k}.json") or {}
        rows.append(f"- `{k}`" + (f" ({s['label']})" if s.get("label") else "")
                    + f": {s.get('file') or s.get('copy')}, {scan.get('duration')} s, {scan.get('frames')} frames. "
                    + f"Copy `{src}/{store.B.copy_path(d, P, k).name}`, transcript `{src}/work/{k}_words.json`, "
                    + f"scan `{src}/work/scan_{k}.json`, contact sheet `{src}/work/sheet_{k}.jpg`"
                    + (f". Note: {s['note']}" if s.get("note") else ""))
    known = []
    for x in P.get("offers") or []:
        known.append(f"- offer: {x.get('label')}" + (f" ({x['note']})" if x.get("note") else ""))
    for x in P.get("duplicates") or []:
        known.append(f"- known duplicate: {x if isinstance(x, str) else x.get('note')}")
    old = store.jload(d / "analysis.json")
    keep = []
    for k, s in ((old or {}).get("sources") or {}).items():
        for f in s.get("edited") or []:
            keep.append(f"- `{k}.{f}` = {s.get(f)} (keep this value and list `{f}` in `edited`)")
    return {
        "slug": P["slug"], "src": src, "name": P.get("name") or P["slug"], "name_ar": P.get("name_ar") or "",
        "sources": "\n".join(rows),
        "known": "\n".join(known) or "- nothing given: work the offers and duplicates out from the footage",
        "keep": "\n".join(keep) or "- none",
        "prepare": f"{src}/work/prepare.json" if (d / "work" / "prepare.json").exists() else "(no prepare report)",
        "look": f"{src}/work/look",
        "output": f"{src}/analysis.json",
        "schema": schema_text(schemas.Analysis),
    }


def analyze_validate(d, P, a: schemas.Analysis, args=None):
    probs, keys = [], store.source_keys(P)
    for k in keys:
        if k not in a.sources:
            probs.append(f"sources.{k} is missing: every source of the product needs an entry")
    groups = {g.id for g in a.offer_groups}
    for k, s in a.sources.items():
        if k not in P["sources"]:
            probs.append(f"sources.{k}: no such source in product.json")
            continue
        dur = source_len(d, P, k)
        if dur is None:
            continue
        end = dur + 0.04
        if not 0 < s.hook_end <= s.body_start <= end:
            probs.append(f"sources.{k}: want 0 < hook_end <= body_start <= {dur}, got {s.hook_end} / {s.body_start}")
        if s.hook_hold is not None and not 0 < s.hook_hold <= s.hook_end:
            probs.append(f"sources.{k}.hook_hold {s.hook_hold} must sit before hook_end {s.hook_end}")
        if s.cta_start is not None and not s.body_start < s.cta_start < end:
            probs.append(f"sources.{k}.cta_start {s.cta_start} must be between body_start and the end ({dur})")
        if s.offer_group not in groups:
            probs.append(f"sources.{k}.offer_group '{s.offer_group}' is not in offer_groups")
        for i, b in enumerate(s.busy):
            if not 0 <= b.a < b.b <= end:
                probs.append(f"sources.{k}.busy[{i}]: want 0 <= a < b <= {dur}")
        prev = 0.0
        for i, ln in enumerate(s.lines):
            if not prev - 0.01 <= ln.a0 < ln.a1 <= end:
                probs.append(f"sources.{k}.lines[{i}]: lines go in order without overlap inside 0-{dur}, "
                             f"got {ln.a0}-{ln.a1} after {prev}")
            for name, v in (("v0", ln.v0), ("v1", ln.v1)):
                if v is not None and not ln.a0 <= v <= ln.a1:
                    probs.append(f"sources.{k}.lines[{i}].{name} {v} is outside the line {ln.a0}-{ln.a1}")
            prev = ln.a1
    for g in a.offer_groups:
        for k in g.sources:
            if k not in a.sources:
                probs.append(f"offer_groups.{g.id}: source {k} is not in sources")
    ids = set()
    for i, l in enumerate(a.liftable):
        dur = source_len(d, P, l.src) if l.src in P["sources"] else None
        if dur is None:
            probs.append(f"liftable[{i}].src '{l.src}' is not a scanned source")
        elif not 0 <= l.a0 < l.a1 <= dur + 0.04:
            probs.append(f"liftable[{i}]: want 0 <= a0 < a1 <= {dur}, got {l.a0}-{l.a1}")
        if l.id in ids:
            probs.append(f"liftable[{i}].id {l.id} is used twice")
        ids.add(l.id)
        if not l.text.strip():
            probs.append(f"liftable[{i}].text is empty: give the exact transcript")
    return probs


# ------------------------------------------------------------------ amend: a change to the analysis, in words

def amend_context(d, P, args):
    src = store.rel(d)
    return {"src": src, "name": P.get("name") or P["slug"], "name_ar": P.get("name_ar") or "",
            "feedback": (args.get("feedback") or "").strip(), "look": f"{src}/work/look",
            "output": f"{src}/analysis.json", "schema": schema_text(schemas.Analysis)}


# ------------------------------------------------------------------ B. propose

def seg_line(s):
    hold = "".join(f" {k} {s[k]}" for k in ("v0", "v1") if s.get(k) is not None)
    return f"{s['src']} {s['a0']}-{s['a1']}{hold}"


def propose_context(d, P, args):
    src, M = store.rel(d), store.jload(d / "mixes.json", {}) or {}
    existing = [f"- {m.get('name') or mid} (`{mid}`): " + " | ".join(seg_line(s) for s in m["segs"]) for mid, m in M.items()]
    earlier = []
    for a in store.proposals(d)["ads"]:
        if a["id"] in M:
            continue
        state = f"rejected by the user: {a.get('reject_reason') or 'no reason given'}" if a.get("status") == "rejected" \
            else "proposed, waiting for the user"
        earlier.append(f"- {a['name']} ({state}): " + " | ".join(seg_line(s) for s in a["segs"]))
    ads = Path(P["ads_dir"]) if P.get("ads_dir") else None
    listing = sorted(p.name for p in ads.iterdir() if p.is_file()) if ads and ads.is_dir() else []
    beats = store.B.beats_path(d, P, {})
    return {
        "src": src, "name": P.get("name") or P["slug"], "name_ar": P.get("name_ar") or "",
        "count": int(args.get("count") or 3),
        "note": (args.get("note") or "").strip() or "nothing more: the best new ads this footage allows",
        "existing": "\n".join(existing) or "- none yet",
        "earlier": "\n".join(earlier) or "- none",
        "ads_listing": "\n".join(f"- {n}" for n in listing) or "- (empty)",
        "beats": store.rel(beats) if beats.exists() else "(no beats file yet: every graphic would be new)",
        "gpt_cap": P.get("gpt_cap", 3), "look": f"{src}/work/look",
        "output": f"{src}/work/proposed.json", "schema": schema_text(schemas.Proposed),
    }


def propose_validate(d, P, p: schemas.Proposed, args=None):
    probs, want = [], int((args or {}).get("count") or 3)
    M = store.jload(d / "mixes.json", {}) or {}
    old = store.proposals(d)["ads"]
    if not 1 <= len(p.ads) <= want:
        probs.append(f"{len(p.ads)} ads proposed: the user asked for {want} (fewer only if the footage allows no more "
                     "good ones, and then say why in notes)")
    seen = {}
    for i, ad in enumerate(p.ads):
        tag = f"ads[{i}] ({ad.label})"
        m = {"segs": [s.model_dump() for s in ad.segs], "body": ad.body, "cta": ad.cta, "hook_beats": ad.hook_beats}
        _, err = store.skill(store.B.check_mix, f"x-{ad.key}", m, P)
        if err:
            probs.append(f"{tag}: {err.split(': ', 1)[-1]}")
            continue
        for j, s in enumerate(ad.segs):
            dur = source_len(d, P, s.src)
            if dur is None:
                probs.append(f"{tag}.segs[{j}]: source {s.src} is not scanned")
            elif s.a1 > dur + 0.04:
                probs.append(f"{tag}.segs[{j}] ends at {s.a1} s but {s.src} is {dur} s long")
        if ad.cta is not None and ad.cta != len(ad.segs) - 1:
            probs.append(f"{tag}: the CTA is its own last segment (cta = {len(ad.segs) - 1}), got cta = {ad.cta}")
        for mid, x in M.items():
            if store.B.same_segs(x["segs"], m["segs"]):
                probs.append(f"{tag}: these are the segments of {x.get('name') or mid}, which already exists")
        for x in old:
            if store.B.same_segs(x["segs"], m["segs"]):
                probs.append(f"{tag}: already proposed as {x['name']} ({x.get('status')})")
        for k, o in seen.items():
            if store.B.same_segs(o, m["segs"]):
                probs.append(f"{tag}: the same segments as ads[{k}]")
        seen[i] = m["segs"]
        if (config.HF / f"{P.get('id_prefix') or P['slug']}-m{store.B.next_number(d, P, M) + i}-{ad.key}").exists():
            probs.append(f"{tag}: a project with the key '{ad.key}' already exists: pick another key")
    if len({a.key for a in p.ads}) != len(p.ads):
        probs.append("two ads share a key: every key must be different")
    return probs


def propose_finish(d, P, M, p: schemas.Proposed, args):
    made = store.add_proposals(d, P, M, [a.model_dump() for a in p.ads], (args.get("note") or "").strip())
    return {"proposed": made, "notes": p.notes}


def clear_staging(d, args):
    p = Path(d) / "work" / "proposed.json"
    if p.exists():
        p.unlink()                                          # the app's own staging file from the last round


STAGES = {
    "analyze": Stage(
        name="analyze", title="Analyze the sources",
        output=lambda d, args: Path(d) / "analysis.json",
        context=analyze_context, validate=analyze_validate, schema=schemas.Analysis,
        allowed=FILES + PY + FF),
    "amend": Stage(
        name="amend", title="Change the analysis",
        output=lambda d, args: Path(d) / "analysis.json",
        context=amend_context, validate=analyze_validate, schema=schemas.Analysis,
        allowed=FILES + PY + FF),
    "propose": Stage(
        name="propose", title="Propose ads",
        output=lambda d, args: Path(d) / "work" / "proposed.json",
        context=propose_context, validate=propose_validate, schema=schemas.Proposed,
        allowed=FILES + PY + FF, before=clear_staging, finish=propose_finish),
}


from .stages_more import register as _register_more  # noqa: E402
_register_more(STAGES)


def _register_darija(STAGES):
    """The Darija correction of Whisper's transcripts (darija.py): products by source key, fresh edits by footage."""
    from . import darija, fresh
    common = dict(title="Correct the Darija", output=lambda d, args: darija.fixed_file(d, args),
                  context=darija.stage_context, validate=darija.stage_validate, schema=darija.DarijaFixes,
                  allowed=FILES + PY, before=darija.stage_before, finish=darija.stage_finish, own_session=True)
    STAGES["darija"] = Stage(name="darija", **common)
    STAGES["darija_fresh"] = Stage(name="darija", load=fresh.load, **common)


_register_darija(STAGES)
