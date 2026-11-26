"""The judgment stages BluxTech Studio adds to camel-studio's analyze / amend / propose:

    graphics  (C)  the B-roll of the ticked mixes, in source time -> beats_<slug>_src.json
    fix       (D)  the place / lint / snapshot problems of one mix -> the same beats file
    revise    (E)  the user's feedback on one finished ad -> beats (and segs), then the app rebuilds and re-renders
    fresh     (F)  one clean footage, steps 3-10 of SKILL.md, rendered -> <project>/.work/fresh_result.json

No editing rule lives here: the templates in prompts/ send Claude to the skill."""
import json
import subprocess
from pathlib import Path

from . import config, fresh, schemas_more as SM, store
from .stages import FF, FILES, HYPER, PY, Stage, schema_text, source_len
from .store import B, jload

DISC_KINDS = {"pack", "liver", "oil", "seeds", "combo", "snow", "shield", "lab", "gift", "plant", "research", "truck",
              "thyroid", "hormone", "balance", "tea", "duo", "calendar", "comments", "calendar6", "battery", "heart",
              "people", "honey"}


def beats_file(d, P):
    return Path(d) / (P.get("beats_file") or f"beats_{P['slug']}_src.json")


def mix_rows(d, P, M, ids):
    rows = []
    for mid in ids:
        m = M.get(mid)
        if not m:
            continue
        segs = []
        for i, s in enumerate(m["segs"]):
            role = "hook" if i == 0 and not (i in m["body"]) else "cta" if m.get("cta") == i and i not in m["body"] else "body" if i in m["body"] else "no-broll"
            segs.append(f"    {i}: {s['src']} {s['a0']}-{s['a1']} [{role}] {s.get('text', '')[:90]}")
        rows.append(f"- `{mid}` {m.get('name')}: body {m['body']}, cta {m.get('cta')}, hook_beats {m.get('hook_beats', False)}\n" + "\n".join(segs))
    return "\n".join(rows) or "- none"


def source_rows(d, P):
    a = (jload(Path(d) / "analysis.json") or {}).get("sources", {})
    rows = []
    for k in store.source_keys(P):
        s = a.get(k) or {}
        busy = ", ".join(f"{b['side']}:{b['a']}-{b['b']} ({b.get('what', '')})" for b in s.get("busy", [])) or "none"
        rows.append(f"- `{k}` ({s.get('label') or k}): {source_len(d, P, k)} s, hook_end {s.get('hook_end')}, body_start "
                    f"{s.get('body_start')}, cta_start {s.get('cta_start')}; busy: {busy}; transcript "
                    f"`{store.rel(d)}/work/{k}_words.json`")
    return "\n".join(rows)


# ------------------------------------------------------------------ C. graphics

def graphics_context(d, P, args):
    M = jload(Path(d) / "mixes.json", {}) or {}
    bf = beats_file(d, P)
    existing = jload(bf)
    return {"src": store.rel(d), "name": P.get("name") or P["slug"], "name_ar": P.get("name_ar") or "",
            "ids": ", ".join(args.get("ids") or []), "mixes": mix_rows(d, P, M, args.get("ids") or []),
            "sources": source_rows(d, P),
            "beats_state": f"`{store.rel(bf)}` has {len(existing.get('beats', []))} beats and {len(existing.get('sfx', []))} sfx"
                           if existing else f"`{store.rel(bf)}` does not exist yet",
            "assets": ", ".join(f"{a['to']} ({a.get('tag', '')})" for a in P.get("project_assets", [])) or "the default EBOX jar (assets/img/jar.png)",
            "gpt_cap": args.get("gpt_cap", P.get("gpt_cap", 3)), "look": f"{store.rel(d)}/work/look",
            "output": store.rel(bf), "notes_out": f"{store.rel(d)}/work/graphics_notes.json",
            "schema": schema_text(SM.BeatsFile), "notes_schema": schema_text(SM.GraphicsNotes)}


def beats_validate(d, P, b: SM.BeatsFile, args=None):
    probs = []
    for i, x in enumerate(b.beats):
        tag = f"beats[{i}] ({x.src} {x.in_}-{x.out} {x.lib or x.kind})"
        dur = source_len(d, P, x.src) if x.src in P["sources"] else None
        if dur is None:
            probs.append(f"{tag}: source {x.src} is not a scanned source of this product")
            continue
        if not 0 <= x.in_ < x.out <= dur + 0.04:
            probs.append(f"{tag}: want 0 <= in < out <= {dur}")
        if x.kind not in DISC_KINDS:
            probs.append(f"{tag}: unknown kind '{x.kind}' (remix.md lists the disc kinds; a picture is kind 'pack' with 'lib')")
        if x.kind == "pack" and x.img and not x.lib and not any(a["to"] == x.img for a in P.get("project_assets", [])) and x.img != "assets/img/jar.png":
            probs.append(f"{tag}: img '{x.img}' is not one of this product's project assets")
        for j, l in enumerate(x.labels):
            if not x.in_ - 0.05 <= l.t <= x.out + 0.05:
                probs.append(f"{tag}.labels[{j}] at {l.t} is outside the beat")
        for name in ("keys", "pops", "breathe", "shake"):
            for t in getattr(x, name):
                if not x.in_ - 0.05 <= t <= x.out + 0.05:
                    probs.append(f"{tag}.{name} {t} is outside the beat")
    for i, s in enumerate(b.sfx):
        if s.src not in P["sources"]:
            probs.append(f"sfx[{i}]: unknown source {s.src}")
    M = jload(Path(d) / "mixes.json", {}) or {}
    for mid in (args or {}).get("ids") or []:
        m = M.get(mid)
        if not m:
            continue
        hit = False
        for i in m["body"]:
            s = m["segs"][i]
            for x in b.beats:
                if x.src == s["src"] and x.in_ >= s["a0"] + 0.2 - 0.01 and x.out <= s["a1"] - 0.25 + 0.01:
                    hit = True
        if not hit:
            probs.append(f"{mid}: no beat sits inside its body segments (>= 0.20 s after a start, >= 0.25 s before an end): "
                         "map_beats.py would drop everything, so this mix would render without B-roll")
    return probs


# ------------------------------------------------------------------ D. fix

def fix_context(d, P, args):
    mid = args["id"]
    proj = config.HF / mid
    M = jload(Path(d) / "mixes.json", {}) or {}
    build = jload(proj / ".work" / "build.json") or {}
    check = jload(proj / ".work" / "check.json") or {}
    problems = [f"- place: {w}" for w in build.get("place_warnings", [])] + [f"- cutout: {w}" for w in build.get("no_cutout", [])]
    if check.get("lint_exit"):
        problems.append(f"- lint exited with {check['lint_exit']} (see `{store.rel(proj)}/.work/lint.log`)")
    if args.get("note"):
        problems.append(f"- the user says: {args['note']}")
    return {"src": store.rel(d), "name": P.get("name") or P["slug"], "id": mid, "proj": store.rel(proj),
            "mix": mix_rows(d, P, M, [mid]), "problems": "\n".join(problems) or "- (none listed: look at the snapshots)",
            "snaps": "\n".join(f"- `{store.rel(proj)}/.work/snaps/{f}`" for f in check.get("files", [])) or "- none yet",
            "beats": store.rel(beats_file(d, P)), "output": store.rel(beats_file(d, P)), "schema": schema_text(SM.BeatsFile)}


# ------------------------------------------------------------------ E. revise

def revise_context(d, P, args):
    mid = args["id"]
    proj = config.HF / mid
    M = jload(Path(d) / "mixes.json", {}) or {}
    rep = jload(proj / ".work" / "final_report.json") or {}
    return {"src": store.rel(d), "name": P.get("name") or P["slug"], "id": mid, "proj": store.rel(proj),
            "feedback": (args.get("feedback") or "").strip(), "mix": mix_rows(d, P, M, [mid]),
            "ad": rep.get("out") or "(not rendered yet)", "beats": store.rel(beats_file(d, P)),
            "output": f"{store.rel(proj)}/.work/revision.json", "schema": schema_text(SM.Revision),
            "beats_schema": schema_text(SM.BeatsFile)}


def revise_validate(d, P, r: SM.Revision, args=None):
    bf = beats_file(d, P)
    probs = []
    if bf.exists():
        try:
            beats = SM.BeatsFile.model_validate(jload(bf))
            probs += beats_validate(d, P, beats, {})
        except Exception as e:
            probs.append(f"{store.rel(bf)} no longer validates: {str(e)[:300]}")
    try:
        M = jload(Path(d) / "mixes.json", {}) or {}
        if (args or {}).get("id") in M:
            _, err = store.skill(B.check_mix, args["id"], M[args["id"]], P)
            if err:
                probs.append(f"mixes.json: {err.split(': ', 1)[-1]}")
    except Exception as e:
        probs.append(f"mixes.json: {e}")
    return probs


def clear_revision(d, args):
    p = config.HF / args["id"] / ".work" / "revision.json"
    if p.exists():
        p.unlink()


# ------------------------------------------------------------------ F. fresh

def fresh_context(proj, P, args):
    f = P["fresh"]
    marks = f.get("marks") or {}
    main = fresh.main_footage(proj)
    out = fresh.out_path(f)
    product_note = ""
    if f.get("product_note"):
        product_note = f"\nProduct: {f['product_note']}"
    return {"slug": f["slug"], "proj": store.rel(proj), "footage": f["footage"], "main": main.name if main else "main.mp4",
            "duration": f.get("duration"), "fps": f.get("fps") or 30, "hook_end": marks.get("hook_end"),
            "body_start": marks.get("body_start"), "cta_start": marks.get("cta_start"),
            "cutout_state": "done: `assets/footage/main_cutout.webm` exists" if (proj / "assets" / "footage" / "main_cutout.webm").exists()
                            else "NOT done: run `npx hyperframes remove-background assets/footage/" + (main.name if main else "main.mp4")
                                 + " -o assets/footage/main_cutout.webm --quality best` from the project folder first (it takes minutes)",
            "prompt_note": f", made with the Whisper prompt \"{f['whisper_prompt']}\"" if f.get("whisper_prompt") else "",
            "product_note": product_note, "gpt_cap": args.get("gpt_cap", 3), "out": str(out),
            "output": f"{store.rel(proj)}/.work/fresh_result.json", "schema": schema_text(SM.FreshResult)}


def fresh_validate(proj, P, r: SM.FreshResult, args=None):
    probs = []
    out = Path(r.output)
    if not out.is_file():
        probs.append(f"output {r.output} does not exist: render and finalize the ad, then write its real path")
        return probs
    f = P["fresh"]
    try:
        q = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(out)],
                           capture_output=True, text=True, timeout=30, env=config.child_env())
        dur = float(json.loads(q.stdout)["format"]["duration"])
    except Exception as e:
        probs.append(f"ffprobe could not read {out.name}: {e}")
        return probs
    if f.get("duration") and abs(dur - f["duration"]) > 0.3:
        probs.append(f"{out.name} is {dur:.2f} s, the footage is {f['duration']} s: the ad must keep the footage's length")
    if r.loudness_after is not None and not -16.5 <= r.loudness_after <= -13.5:
        probs.append(f"loudness_after {r.loudness_after} LUFS: finalize.py targets -15; run it again on the raw render")
    if not r.beats:
        probs.append("beats is empty: list every graphic (time, side, graphic, words)")
    return probs


def fresh_finish(proj, P, M, r: SM.FreshResult, args):
    fresh.set_fields(P["slug"], output=r.output, finished=True)
    return {"output": r.output}


def register(STAGES):
    STAGES["graphics"] = Stage(
        name="graphics", title="Plan the graphics",
        output=lambda d, args: beats_file(d, store.product(Path(d).name[:-4])[1]),
        context=graphics_context, validate=beats_validate, schema=SM.BeatsFile,
        allowed=FILES + PY + FF)
    STAGES["fix"] = Stage(
        name="fix", title="Fix a mix",
        output=lambda d, args: beats_file(d, store.product(Path(d).name[:-4])[1]),
        context=fix_context, validate=beats_validate, schema=SM.BeatsFile,
        allowed=FILES + PY + FF + HYPER)
    STAGES["revise"] = Stage(
        name="revise", title="Revise an ad",
        output=lambda d, args: config.HF / args["id"] / ".work" / "revision.json",
        context=revise_context, validate=revise_validate, schema=SM.Revision,
        allowed=FILES + PY + FF + HYPER, before=clear_revision)
    STAGES["fresh"] = Stage(
        name="fresh", title="Fresh edit",
        output=lambda proj, args: Path(proj) / ".work" / "fresh_result.json",
        context=fresh_context, validate=fresh_validate, schema=SM.FreshResult,
        allowed=FILES + PY + FF + HYPER, load=fresh.load, finish=fresh_finish)
