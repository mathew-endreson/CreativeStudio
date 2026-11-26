"""Reading and writing the batch folders. batch.py (the skill) is the only thing that knows their layout:
this module asks it, and adds what the app keeps beside it (studio.json: the Claude session and its usage).
Ported from camel-studio by tools/port_from_camel_studio.py; the engine's additions live in products.py."""
import json
import os
import sys
import threading
import time
from pathlib import Path

from . import config

if str(config.SCRIPTS) not in sys.path:
    sys.path.insert(0, str(config.SCRIPTS))
import batch as B  # noqa: E402  (the skill's batch.py: stdlib only at import)

_lock = threading.RLock()


class NotFound(Exception):
    pass


def jload(p, default=None):
    p = Path(p)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8-sig"))


def jdump(p, obj):
    with _lock:
        p = Path(p)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + ".tmp")
        tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, p)


def src_dir(slug):
    if not B.ID_RE.match(slug or ""):
        raise NotFound(slug)
    d = config.HF / f"{slug}_src"
    if not d.is_dir():
        raise NotFound(slug)
    return d


def rel(p):
    """A path as the prompts and the UI show it: relative to the project root when inside it."""
    try:
        return Path(p).resolve().relative_to(config.ROOT).as_posix()
    except ValueError:
        return str(p)


def product(slug):
    d = src_dir(slug)
    P = jload(d / "product.json")
    if P is None:
        raise NotFound(f"{slug}: no product.json (run batch.py import)")
    return d, P, jload(d / "mixes.json", {})


def source_keys(P):
    return [k for k, s in P["sources"].items() if s.get("tag", "finished_ad") in ("finished_ad", "source")]


def source_state(d, P, k):
    from . import darija
    prep = (jload(d / "work" / "prepare.json", {}) or {}).get(k) or {}
    return {"key": k, "label": P["sources"][k].get("label"), "file": P["sources"][k].get("file"),
            "note": P["sources"][k].get("note"), "copy": B.copy_path(d, P, k).exists(),
            "words": (d / "work" / f"{k}_words.json").exists(), "scan": (d / "work" / f"scan_{k}.json").exists(),
            "darija": darija.state(d / "work" / f"{k}_words.json"),
            "frames": prep.get("frames"), "duration": prep.get("duration"), "issues": prep.get("issues", []),
            "cutouts": [[r["f0"], r["f1"]] for r in B.manifest(d).get(k, [])]}


def summary(slug):
    """A product card: counts only."""
    d, P, M = product(slug)
    props = jload(d / "proposals.json", {}) or {}
    states = [B.mix_state(d, P, M, mid) for mid in M]
    return {"slug": slug, "name": P.get("name"), "name_ar": P.get("name_ar"), "sources": len(source_keys(P)),
            "mixes": len(M), "ads": sum(s["ad"] for s in states),
            "proposals": sum(a.get("status") == "proposed" for a in props.get("ads", [])),
            "analysis": (d / "analysis.json").exists(), "ads_dir": P.get("ads_dir"),
            "imported": bool(P.get("imported_from")), "todo": todo(P)}


def todo(P):
    out = []
    if not P.get("name_ar"):
        out.append("Arabic name")
    if not P.get("ads_dir"):
        out.append("Ads folder")
    if not P.get("whisper_prompt"):
        out.append("Whisper key words")
    return out


def products():
    out = []
    for d in sorted(config.HF.glob("*_src")):
        slug = d.name[:-4]
        if (d / "product.json").exists():
            try:
                out.append(summary(slug))
            except Exception as e:                           # one broken folder must not hide the others
                out.append({"slug": slug, "name": slug, "error": str(e)})
        else:
            out.append({"slug": slug, "name": slug, "not_imported": True})
    return out


def detail(slug):
    d, P, M = product(slug)
    st = studio(d)
    return {"slug": slug, "dir": rel(d), "product": P, "todo": todo(P),
            "sources": [source_state(d, P, k) for k in source_keys(P)],
            "mixes": [B.mix_state(d, P, M, mid) for mid in M], "next_mix": B.next_number(d, P, M),
            "analysis": (d / "analysis.json").exists(), "proposals": (d / "proposals.json").exists(),
            "session_id": st.get("session_id"), "usage": usage(st)}


def source_data(slug, k):
    from . import darija
    d, P, _ = product(slug)
    if k not in P["sources"]:
        raise NotFound(k)
    return {"key": k, "state": source_state(d, P, k), "words": jload(d / "work" / f"{k}_words.json", []),
            "transcript": darija.summary(d / "work" / f"{k}_words.json"),
            "scan": jload(d / "work" / f"scan_{k}.json"), "curves": jload(d / "work" / f"curves_{k}.json"),
            "prepare": (jload(d / "work" / "prepare.json", {}) or {}).get(k)}


# ------------------------------------------------------------------ proposals.json

def skill(fn, *a, **kw):
    """Call into batch.py. It reports a bad mix by exiting: turn that into a message."""
    try:
        return fn(*a, **kw), None
    except SystemExit as e:
        return None, str(e)


def proposals(d):
    return jload(Path(d) / "proposals.json", None) or {"version": 1, "ads": []}


def said_for(analysis, src, a0, a1):
    """The clean wording of a source range: the `said` of the analysis lines whose middle falls in it."""
    lines = ((analysis or {}).get("sources") or {}).get(src, {}).get("lines") or []
    return " ".join(l.get("said") or l["text"] for l in lines if a0 - 0.02 <= (l["a0"] + l["a1"]) / 2 < a1 + 0.02)


def mix_of(ad):
    """A proposal as batch.py sees a mix."""
    return {"name": ad.get("name"), "file_name": ad.get("file_name"), "segs": ad["segs"], "body": ad["body"],
            "cta": ad.get("cta"), "hook_beats": bool(ad.get("hook_beats"))}


def fill_segs(d, analysis, ad):
    """Raw transcript and clean wording of every segment, from the transcripts and the analysis."""
    for s in ad["segs"]:
        s["text"] = B.seg_text(d, s["src"], s["a0"], s["a1"])
        if not s.get("said"):
            s["said"] = said_for(analysis, s["src"], s["a0"], s["a1"]) or s["text"]


def live(d, P, M, ad):
    """A proposal with what changes while it waits: its length, the cutouts it still needs and their cost,
    its cuts checked against the scans, and whether an ad with the same segments now exists."""
    m = mix_of(ad)
    out = dict(ad)
    out["duration"] = B.tt(sum(B.fr(s["a1"]) - B.fr(s["a0"]) for s in ad["segs"]))
    cuts, err = skill(B.plan_cuts, d, P, {ad["id"]: m}, [ad["id"]], all_gfx=True)
    out["new_cutouts"] = cuts or []
    out["cutout_eta_s"] = sum(c["eta_s"] for c in cuts or [])
    notes, _ = skill(B.cut_notes, d, P, m)
    out["checks"] = notes or []
    twin = next((mid for mid, x in M.items() if mid != ad["id"] and B.same_segs(x["segs"], ad["segs"])), None)
    out["exists"] = {"id": twin, "name": M[twin].get("name")} if twin else None
    out["built"] = (config.HF / ad["id"] / "index.html").exists()
    return out


def proposal_list(slug):
    d, P, M = product(slug)
    return {"ads": [live(d, P, M, ad) for ad in proposals(d)["ads"]], "next_mix": B.next_number(d, P, M),
            "gpt_cap": P.get("gpt_cap", 3)}


def add_proposals(d, P, M, new, round_note=""):
    """Give Claude's proposals their numbers, ids and names (never one that was used), and append them."""
    data = proposals(d)
    analysis = jload(Path(d) / "analysis.json")
    n = B.next_number(d, P, M)
    rnd = 1 + max((a.get("round", 0) for a in data["ads"]), default=0)
    made = []
    for ad in new:
        ad = dict(ad)
        label, key = ad.pop("label"), ad.pop("key")
        ad["id"] = f"{P.get('id_prefix') or P['slug']}-m{n}-{key}"
        ad["label"] = label
        ad["name"] = f"{P.get('name') or P['slug']} Mix{n:02d} - {label}"
        ad["file_name"] = (P.get("name_pattern") or "{name} Mix{nn} - {label} - {name_ar}.mp4").format(
            name=P.get("name") or P["slug"], nn=f"{n:02d}", label=label, name_ar=P.get("name_ar") or "")
        fill_segs(d, analysis, ad)
        ad.update(status="proposed", picked=False, reject_reason="", edited=False, round=rnd, round_note=round_note,
                  proposed_at=time.strftime("%Y-%m-%dT%H:%M:%S"))
        data["ads"].append(ad)
        made.append(ad["id"])
        n += 1
    jdump(Path(d) / "proposals.json", data)
    return made


def patch_proposal(slug, pid, patch):
    """The user's tick, rejection, or edited segments."""
    d, P, M = product(slug)
    data = proposals(d)
    ad = next((a for a in data["ads"] if a["id"] == pid), None)
    if not ad:
        raise NotFound(pid)
    if "picked" in patch:
        ad["picked"] = bool(patch["picked"])
    if patch.get("status") in ("proposed", "rejected", "accepted"):
        ad["status"] = patch["status"]
        ad["reject_reason"] = (patch.get("reject_reason") or "").strip() if patch["status"] == "rejected" else ""
        if ad["status"] == "rejected":
            ad["picked"] = False
    if "segs" in patch:
        new = dict(ad, segs=[{k: s.get(k) for k in ("src", "a0", "a1", "v0", "v1", "said", "note")} for s in patch["segs"]],
                   body=[int(i) for i in patch["body"]], cta=patch.get("cta"), hook_beats=bool(patch.get("hook_beats")))
        _, err = skill(B.check_mix, pid, mix_of(new), P)
        if err:
            raise ValueError(err)
        for s in new["segs"]:
            dur = (jload(Path(d) / "work" / f"scan_{s['src']}.json") or {}).get("duration")
            if dur and s["a1"] > dur + 0.04:
                raise ValueError(f"a segment ends at {s['a1']} s but {s['src']} is {dur} s long")
            if not s.get("note"):
                s["note"] = ""
            s["said"] = ""                                  # the wording follows the new times
        fill_segs(d, jload(Path(d) / "analysis.json"), new)
        new["edited"] = True
        ad.clear()
        ad.update(new)
    jdump(Path(d) / "proposals.json", data)
    return live(d, P, M, ad)


# ------------------------------------------------------------------ studio.json: the Claude session + usage

def studio(d):
    return jload(Path(d) / "studio.json", {}) or {}


def studio_update(d, fn):
    with _lock:
        st = studio(d)
        fn(st)
        jdump(Path(d) / "studio.json", st)
        return st


def record_run(d, run):
    def add(st):
        st.setdefault("runs", []).append({**run, "at": time.strftime("%Y-%m-%dT%H:%M:%S")})
    return studio_update(d, add)


def usage(st):
    runs = st.get("runs", [])
    tok = lambda k: sum((r.get("usage") or {}).get(k, 0) or 0 for r in runs)
    return {"claude_runs": len(runs), "turns": sum(r.get("turns") or 0 for r in runs),
            "input_tokens": tok("input_tokens") + tok("cache_creation_input_tokens") + tok("cache_read_input_tokens"),
            "output_tokens": tok("output_tokens"), "cost_usd": round(sum(r.get("cost_usd") or 0 for r in runs), 2),
            "seconds": round(sum(r.get("duration_ms") or 0 for r in runs) / 1000),
            "gpt_drawings": len(st.get("gpt_drawings", [])), "last": runs[-1] if runs else None}
