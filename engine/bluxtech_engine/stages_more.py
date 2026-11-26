"""The judgment stages BluxTech Studio adds to camel-studio's analyze / amend / propose:

    graphics  (C)  the animated assets of the ticked mixes, in source time -> beats_<slug>_src.json
    fix       (D)  the place / lint / snapshot problems of one mix -> the same beats file
    revise    (E)  the user's feedback on one finished ad -> beats (and segs), then the app rebuilds and re-renders
    fresh     (F)  one clean footage, steps 3-10 of SKILL.md, rendered -> <project>/.work/fresh_result.json

Since Nov 26 2026 the skill animates the pictures the user uploads for the product (its asset folder and
library.json) in front of the speaker, by the caption: no discs, jar packshots, labels or badges, and no speaker
cutout for a remix. No editing rule lives here: the templates in prompts/ send Claude to the skill."""
import json
import re
import subprocess
from pathlib import Path

from . import assetlib, config, fresh, schemas_more as SM, settings, store
from .stages import FF, FILES, HYPER, PY, Stage, schema_text, source_len
from .store import B, jload

IN_PAD, OUT_PAD = 0.20, 0.25            # map_beats.py: a beat sits this far inside its body segment
GAP = 0.30                              # one asset at a time: between one leaving and the next arriving
MIN_LEN, MAX_LEN = 1.2, 6.05            # the skill plans 2.4-4 s (up to 6 s when he stays on the topic)
REMIX_BOTTOM = 1260                     # asset_lib.py: the pictures' bottom edge in a remix


def beats_file(d, P):
    return Path(d) / (P.get("beats_file") or f"beats_{P['slug']}_src.json")


def draw_cap(args, P=None):
    """How many pictures GPT may draw in this run: only what the user asked for (the request's draw cap, already
    0 on a PC without the Codex drawing tool). MISSING ideas are otherwise reported, not drawn."""
    try:
        return max(0, int((args or {}).get("gpt_cap") or 0))
    except (TypeError, ValueError):
        return 0


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
        busy = ", ".join(f"{b['a']}-{b['b']} ({b.get('what', '')}; {b.get('side', '')})" for b in s.get("busy", [])) or "none"
        rows.append(f"- `{k}` ({s.get('label') or k}): {source_len(d, P, k)} s, hook_end {s.get('hook_end')}, body_start "
                    f"{s.get('body_start')}, cta_start {s.get('cta_start')}; busy: {busy}; transcript "
                    f"`{store.rel(d)}/work/{k}_words.json`, contact sheet `{store.rel(d)}/work/sheet_{k}.jpg`")
    return "\n".join(rows)


def library_context(d, P):
    """What the stages tell Claude about the product's pictures."""
    lib = assetlib.product_lib(d, P)
    own = bool(P.get("asset_lib"))
    folder = assetlib.product_folder(d, P) if own else lib.parent
    listing = assetlib.describe(lib)
    if not listing:
        listing = (f"- none yet: `{store.rel(folder)}` holds no picture. Plan anyway to find what he names (MISSING), "
                   "write no beat, and list those ideas for the user to upload")
    bottom = P.get("asset_bottom") or REMIX_BOTTOM
    return {"lib": store.rel(lib), "img": store.rel(folder), "pictures": listing, "bottom": bottom,
            "bottom_note": f" (product.json `asset_bottom` {bottom}: this product's burned-in captions sit high)"
                           if P.get("asset_bottom") else ""}


def draw_rule(cap, lib, img, plan, where="the notes' `missing`", upload="to the product's pictures"):
    """What Claude does with the MISSING ideas: report them, or (only when the user asked) have GPT draw them."""
    if cap <= 0:
        return (f"Do not draw them: list every one worth showing in {where}, so the user can upload a picture {upload}. "
                "GPT draws a picture only when the user asks for it.")
    return (f"The user asked GPT to draw what is missing: at most {cap} picture(s) this round, only ideas this ad "
            f"really shows. Run `python S/asset_lib.py --lib \"{lib}\" fill {plan} --max {cap}` (1-4 min each), then "
            f"look at every new picture (the output gives its path). Copy each one you keep into `{img}`, run "
            f"`python S/asset_lib.py index \"{img}\"`, write its keywords (`setmany`) and plan again. If GPT fails "
            f"(`python S/gpt_assets.py status`), say so and list those ideas in {where}.")


# ------------------------------------------------------------------ C. graphics

def graphics_context(d, P, args):
    M = jload(Path(d) / "mixes.json", {}) or {}
    bf = beats_file(d, P)
    existing = jload(bf)
    lc = library_context(d, P)
    if existing:
        olds = sum(1 for b in existing.get("beats", []) if b.get("kind") != SM.ASSET or not b.get("lib"))
        state = (f"`{store.rel(bf)}` has {len(existing.get('beats', []))} beats and {len(existing.get('sfx', []))} sfx"
                 + (f"; {olds} of them in the old disc / jar style (no picture)" if olds else ""))
    else:
        state = f"`{store.rel(bf)}` does not exist yet"
    src = store.rel(d)
    return {"src": src, "name": P.get("name") or P["slug"], "name_ar": P.get("name_ar") or "",
            "ids": ", ".join(args.get("ids") or []), "mixes": mix_rows(d, P, M, args.get("ids") or []),
            "sources": source_rows(d, P), "beats_state": state, **lc,
            "draw_rule": draw_rule(draw_cap(args, P), lc["lib"], lc["img"], f"{src}/work/illus_<k>.json"),
            "look": f"{src}/work/look", "output": store.rel(bf), "notes_out": f"{src}/work/graphics_notes.json",
            "schema": schema_text(SM.BeatsFile), "notes_schema": schema_text(SM.GraphicsNotes)}


def _inside(x, s):
    return x.src == s["src"] and x.in_ >= s["a0"] + IN_PAD - 0.01 and x.out <= s["a1"] - OUT_PAD + 0.01


def _carrying(m):
    """The segments of a mix whose beats map_beats keeps: the body, and a lifted hook (hook_beats)."""
    idx = list(m.get("body") or []) + ([0] if m.get("hook_beats") else [])
    return [(i, m["segs"][i]) for i in idx if 0 <= i < len(m.get("segs") or [])]


def beats_validate(d, P, b: SM.BeatsFile, args=None):
    """Every beat `batch.py build` maps into these mixes must be an asset that `asset_lib.py place` can show: a
    `lib` of the product's library (an unknown id stops the build), one at a time, its key move inside it."""
    probs = []
    lib = assetlib.product_lib(d, P)
    pics = assetlib.entries(lib)
    folder = assetlib.product_folder(d, P) if P.get("asset_lib") else lib.parent
    ana = (jload(Path(d) / "analysis.json") or {}).get("sources", {})
    for i, x in enumerate(b.beats):
        tag = f"beats[{i}] ({x.src} {x.in_}-{x.out} {x.lib or x.kind})"
        dur = source_len(d, P, x.src) if x.src in P["sources"] else None
        if dur is None:
            probs.append(f"{tag}: source {x.src} is not a scanned source of this product")
            continue
        if not 0 <= x.in_ < x.out <= dur + 0.04:
            probs.append(f"{tag}: want 0 <= in < out <= {dur}")
        if x.lib:                                   # place resolves every beat with a lib, whatever its kind
            e = pics.get(x.lib)
            if not e:
                probs.append(f"{tag}: '{x.lib}' is not in {store.rel(lib)}: asset_lib.py place would stop the build. "
                             f"Use the id of one of the product's pictures, or delete the beat (a GPT studio picture "
                             f"can be copied into {store.rel(folder)} and indexed: it keeps its id)")
            elif assetlib.unusable(e):
                probs.append(f"{tag}: picture '{x.lib}' cannot be shown ({assetlib.unusable(e)}): use another one or "
                             "delete the beat, and tell the user")
        if not x.is_asset():
            continue                                # an older disc / jar beat: checked against the ticked mixes below
        if x.side not in SM.ASSET_SIDES:
            probs.append(f"{tag}: side '{x.side}': an asset is C (by the caption), or L / R")
        if not x.key_times():
            probs.append(f"{tag}: no key move: give it `keys` (or `breathe` / `shake`, the picture's motion) on the word")
        for name in ("keys", "breathe", "shake"):
            for t in getattr(x, name):
                if not x.in_ - 0.05 <= t <= x.out - 0.3:
                    probs.append(f"{tag}.{name} {t}: the key word must fall while it is on screen (in .. out - 0.3)")
        if not MIN_LEN <= x.out - x.in_ <= MAX_LEN:
            probs.append(f"{tag}: on screen {x.out - x.in_:.2f} s: an asset stays 2.4-4 s (up to 6 s on one topic)")
        if x.bottom is not None and not 600 <= x.bottom <= 1800:
            probs.append(f"{tag}: bottom {x.bottom} px is off the speaker's chest (600-1800)")
        for w in (ana.get(x.src) or {}).get("busy") or []:
            if w.get("side") == "full" and x.in_ < w["b"] and x.out > w["a"]:
                probs.append(f"{tag} overlaps {w.get('what') or 'a full-screen element'} ({w['a']}-{w['b']}): "
                             "nothing goes over full-screen B-roll or the CTA mockup")
    by_src = {}
    for i, x in enumerate(b.beats):
        if x.is_asset():
            by_src.setdefault(x.src, []).append((i, x))
    for k, xs in by_src.items():
        xs.sort(key=lambda t: t[1].in_)
        for (i, a), (j, c) in zip(xs, xs[1:]):
            if c.in_ < a.out + GAP - 0.01:
                probs.append(f"beats[{i}] and beats[{j}] ({k} {a.in_}-{a.out} {a.lib}, {c.in_}-{c.out} {c.lib}): one "
                             f"asset at a time, at least {GAP} s between one leaving and the next arriving")
    for i, s in enumerate(b.sfx):
        if s.src not in P["sources"]:
            probs.append(f"sfx[{i}]: unknown source {s.src}")
    M = jload(Path(d) / "mixes.json", {}) or {}
    all_segs = [s for m in M.values() for _, s in _carrying(m)]
    for mid in (args or {}).get("ids") or []:
        m = M.get(mid)
        if not m:
            continue
        for si, s in _carrying(m):
            for i, x in enumerate(b.beats):
                if x.src != s["src"]:
                    continue
                tag = f"beats[{i}] ({x.src} {x.in_}-{x.out} {x.lib or x.kind})"
                if _inside(x, s) and not x.is_asset():
                    probs.append(f"{mid}: {tag} sits in segment {si} but is not an asset beat with a `lib`: build drops "
                                 "it (the disc / jar style is gone). Replace it with one of the product's pictures, "
                                 "or delete it")
                elif x.is_asset() and x.in_ < s["a1"] and x.out > s["a0"] and not _inside(x, s) \
                        and not any(_inside(x, o) for o in all_segs):
                    probs.append(f"{mid}: {tag} straddles segment {si} ({s['a0']}-{s['a1']}): map_beats.py keeps a beat "
                                 f"only >= {IN_PAD} s after a segment starts and >= {OUT_PAD} s before it ends")
    return probs


# ------------------------------------------------------------------ D. fix

def fix_context(d, P, args):
    mid = args["id"]
    proj = config.HF / mid
    M = jload(Path(d) / "mixes.json", {}) or {}
    build = jload(proj / ".work" / "build.json") or {}
    check = jload(proj / ".work" / "check.json") or {}
    problems = [f"- place: {w}" for w in build.get("place_warnings", [])]
    if check.get("lint_exit"):
        problems.append(f"- lint exited with {check['lint_exit']} (see `{store.rel(proj)}/.work/lint.log`)")
    if args.get("note"):
        problems.append(f"- the user says: {args['note']}")
    return {"src": store.rel(d), "name": P.get("name") or P["slug"], "id": mid, "proj": store.rel(proj),
            "mix": mix_rows(d, P, M, [mid]), "problems": "\n".join(problems) or "- (none listed: look at the snapshots)",
            "snaps": "\n".join(f"- `{store.rel(proj)}/.work/snaps/{f}`" for f in check.get("files", [])) or "- none yet",
            **library_context(d, P),
            "beats": store.rel(beats_file(d, P)), "output": store.rel(beats_file(d, P)), "schema": schema_text(SM.BeatsFile)}


def fix_validate(d, P, b: SM.BeatsFile, args=None):
    return beats_validate(d, P, b, {"ids": [args["id"]]} if (args or {}).get("id") else {})


# ------------------------------------------------------------------ E. revise

def revise_context(d, P, args):
    mid = args["id"]
    proj = config.HF / mid
    M = jload(Path(d) / "mixes.json", {}) or {}
    rep = jload(proj / ".work" / "final_report.json") or {}
    lc = library_context(d, P)
    cap = P.get("gpt_cap", settings.get("gpt_cap")) if config.codex_bin() else 0
    return {"src": store.rel(d), "name": P.get("name") or P["slug"], "id": mid, "proj": store.rel(proj),
            "feedback": (args.get("feedback") or "").strip(), "mix": mix_rows(d, P, M, [mid]),
            "ad": rep.get("out") or "(not rendered yet)", "beats": store.rel(beats_file(d, P)), **lc,
            "gpt_rule": (f"only when this feedback asks GPT to draw one: at most {cap}, `asset_lib.py --lib {lc['lib']} "
                         f"fill`, then copy it into `{lc['img']}` and `index` it") if cap else
                        "GPT cannot draw on this PC: name the picture the user should upload",
            "output": f"{store.rel(proj)}/.work/revision.json", "schema": schema_text(SM.Revision),
            "beats_schema": schema_text(SM.BeatsFile)}


def revise_validate(d, P, r: SM.Revision, args=None):
    bf = beats_file(d, P)
    probs = []
    if bf.exists():
        try:
            beats = SM.BeatsFile.model_validate(jload(bf))
            probs += beats_validate(d, P, beats, {"ids": [args["id"]]} if (args or {}).get("id") else {})
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
    folder = fresh.assets_folder(proj, f)
    if not f.get("assets"):
        folder.mkdir(exist_ok=True)                         # an edit made before Nov 26 2026 has no uploads folder yet
    lib = folder / "library.json"
    product_note = ""
    if f.get("product_note"):
        product_note = f"\nProduct: {f['product_note']}"
    pics = assetlib.describe(lib) if lib.exists() else ""
    n_files = sum(1 for p in folder.iterdir() if p.is_file() and p.suffix.lower() in (".png", ".webp", ".jpg", ".jpeg")) \
        if folder.is_dir() else 0
    if pics:
        state = f"indexed before:\n{pics}"
    elif n_files:
        state = f"{n_files} picture(s), not indexed yet"
    else:
        state = ("empty: the user gave no pictures for this ad yet. Still index and plan it (to find what he names), "
                 "write an empty ILLUS, and list the ideas worth a picture in `missing` for the user to upload")
    cap = draw_cap(args)
    lib_s = str(lib)
    return {"slug": f["slug"], "proj": store.rel(proj), "footage": f["footage"], "main": main.name if main else "main.mp4",
            "duration": f.get("duration"), "fps": f.get("fps") or 30, "hook_end": marks.get("hook_end"),
            "body_start": marks.get("body_start"), "cta_start": marks.get("cta_start"),
            "cutout_state": "done: `assets/footage/main_cutout.webm` exists" if (proj / "assets" / "footage" / "main_cutout.webm").exists()
                            else "NOT done: run `npx hyperframes remove-background assets/footage/" + (main.name if main else "main.mp4")
                                 + " -o assets/footage/main_cutout.webm --quality best` from the project folder first (it takes minutes)",
            "prompt_note": f", made with the Whisper prompt \"{f['whisper_prompt']}\"" if f.get("whisper_prompt") else "",
            "product_note": product_note, "assets": str(folder), "lib": lib_s, "assets_state": state,
            "draw_rule": draw_rule(cap, lib_s, str(folder), f"{store.rel(proj)}/.work/illus_plan.json",
                                   where="the result's `missing`", upload=f"into `{folder}`"),
            "out": str(out), "output": f"{store.rel(proj)}/.work/fresh_result.json", "schema": schema_text(SM.FreshResult)}


def illus_of(proj):
    """The assets `asset_lib.py place` wrote into index.html's ILLUS slot (None when there is no slot)."""
    try:
        html = (Path(proj) / "index.html").read_text(encoding="utf-8-sig")
    except OSError:
        return None
    m = re.search(r"/\*ILLUS\*/(.*?)/\*END-ILLUS\*/", html, re.S)
    if not m:
        return None
    try:
        v = json.loads(m.group(1))
        return v if isinstance(v, list) else None
    except ValueError:
        return None


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
    illus = illus_of(proj)
    if illus is None:
        probs.append("index.html has no readable ILLUS slot: the assets go in with `asset_lib.py place` (it keeps the "
                     "/*ILLUS*/ ... /*END-ILLUS*/ markers)")
    else:
        gone = [a.get("img") for a in illus if not a.get("img") or not (Path(proj) / a["img"]).is_file()]
        if gone:
            probs.append(f"ILLUS names pictures that are not in the project: {gone}: run `place` again")
        if len(r.beats) != len(illus):
            probs.append(f"beats lists {len(r.beats)} asset(s) but index.html's ILLUS holds {len(illus)}: list every "
                         "asset (time, side, library id, the words it lands on)")
    return probs


def fresh_finish(proj, P, M, r: SM.FreshResult, args):
    fresh.set_fields(P["slug"], output=r.output, finished=True)
    return {"output": r.output, "missing": ", ".join(m.concept for m in r.missing)}


def register(STAGES):
    STAGES["graphics"] = Stage(
        name="graphics", title="Plan the assets",
        output=lambda d, args: beats_file(d, store.product(Path(d).name[:-4])[1]),
        context=graphics_context, validate=beats_validate, schema=SM.BeatsFile,
        allowed=FILES + PY + FF)
    STAGES["fix"] = Stage(
        name="fix", title="Fix a mix",
        output=lambda d, args: beats_file(d, store.product(Path(d).name[:-4])[1]),
        context=fix_context, validate=fix_validate, schema=SM.BeatsFile,
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
