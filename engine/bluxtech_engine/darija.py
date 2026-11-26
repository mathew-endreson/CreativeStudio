"""The transcript workflow, after the skill's Whisper step:

    audio/video ─▶ ffmpeg ─▶ Whisper (local) ─▶ Claude Code + darijadz skill ─▶ darija_lint ─▶ .txt / .srt / .json
                  └──── transcribe.py / batch.py transcribe ────┘ └──── the `darija` stage ───┘  └─ apply() here ─┘

Files, next to each word-timed transcript (`work/<k>_words.json` of a product source, `.work/words.json` of a fresh
edit; <p> is `<k>_` or nothing):

    <p>words.whisper.json   Whisper's own words, kept: every correction starts again from it
    <p>transcript.json      segments {id, start, end, raw, text, unsure, note, lint} + status (whisper-draft / claude-corrected)
    <p>transcript.txt/.srt  the corrected text, and subtitles
    <p>words.json           rewritten with the corrected words, re-timed onto Whisper's word times, so captions,
                            the analysis and the asset matcher all read real Darija
    darija.fixed.json       what Claude wrote for one run: {"transcripts": {<key>: {"segments": [{id, text, unsure, note}]}}}

Claude never hears the audio: it corrects Whisper's text, it does not invent it.
"""
import difflib
import hashlib
import importlib.util
import json
import re
import shutil
import time
from pathlib import Path

from pydantic import BaseModel, Field

from . import config
from .store import jdump, jload, rel


# ------------------------------------------------------------------ schema of Claude's file

class FixSeg(BaseModel):
    id: int = Field(description="the segment id from the draft transcript")
    text: str = Field(description="what the speaker said, in Algerian Darija spelling; \"\" for noise / hallucination")
    unsure: list[str] = Field(default_factory=list, description="words you could not settle: keep Whisper's and list them")
    note: str = Field("", description="a short English remark, or \"\"")


class FixTranscript(BaseModel):
    segments: list[FixSeg]


class DarijaFixes(BaseModel):
    transcripts: dict[str, FixTranscript]


# ------------------------------------------------------------------ where things are

def skill_dir():
    return config.ROOT / ".claude" / "skills" / "darijadz"


def paths(words: Path):
    words = Path(words)
    p = words.name[: -len("words.json")]
    d = words.parent
    return {"words": words, "whisper": d / f"{p}words.whisper.json", "doc": d / f"{p}transcript.json",
            "txt": d / f"{p}transcript.txt", "srt": d / f"{p}transcript.srt", "raw_txt": d / f"{p}transcript.raw.txt"}


def targets(d, args):
    """{key: words.json} for one run: product sources by key, or the fresh edit's one footage."""
    d = Path(d)
    if args.get("fresh"):
        return {"footage": d / ".work" / "words.json"}
    return {k: d / "work" / f"{k}_words.json" for k in args.get("keys") or []}


def fixed_file(d, args):
    d = Path(d)
    return (d / ".work" if args.get("fresh") else d / "work") / "darija.fixed.json"


def sha(p: Path):
    return hashlib.sha1(p.read_bytes()).hexdigest() if p.exists() else None


def state(words: Path):
    """none (no transcript yet) / whisper (Whisper's draft only) / corrected (Claude + lint done on this version)."""
    P = paths(words)
    if not P["words"].exists():
        return "none"
    doc = jload(P["doc"]) or {}
    if doc.get("status") == "claude-corrected" and doc.get("words_sha") == sha(P["words"]):
        return "corrected"
    return "whisper"


def summary(words: Path):
    """What the UI shows about a transcript."""
    P = paths(words)
    doc = jload(P["doc"]) or {}
    segs = doc.get("segments") or []
    lint = [f for s in segs for f in s.get("lint") or []]
    return {"state": state(words), "unsure": sorted({u for s in segs for u in s.get("unsure") or []}),
            "lint_high": sum(f.get("level") == "HIGH" for f in lint), "lint": len(lint),
            "changed": sum(1 for s in segs if s.get("text") != s.get("raw")), "segments": len(segs),
            "dropped": sum(1 for s in segs if not s.get("text")),
            "notes": [{"id": s["id"], "note": s["note"]} for s in segs if s.get("note")],
            "files": {k: str(P[k]) for k in ("txt", "srt", "doc") if P[k].exists()}}


# ------------------------------------------------------------------ darija_lint (from the darijadz skill)

_lint = None


def lint_line(text):
    global _lint
    if _lint is None:
        path = skill_dir() / "scripts" / "darija_lint.py"
        if path.exists():
            spec = importlib.util.spec_from_file_location("darija_lint", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _lint = mod.lint_line
        else:
            _lint = lambda _t: []  # noqa: E731  (the environment check reports the missing skill)
    return [{k: f[k] for k in ("word", "level", "dialect", "use")} for f in _lint(text or "")]


# ------------------------------------------------------------------ outputs

def srt_time(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def write_texts(doc, P):
    segs = doc["segments"]
    spoken = [s for s in segs if s["text"]]
    P["raw_txt"].write_text("\n".join(s["raw"] for s in segs) + "\n", encoding="utf-8")
    P["txt"].write_text("\n".join(s["text"] for s in spoken) + "\n", encoding="utf-8")
    P["srt"].write_text("\n".join(f"{n}\n{srt_time(s['start'])} --> {srt_time(s['end'])}\n{s['text']}\n"
                                  for n, s in enumerate(spoken, 1)), encoding="utf-8")


# ------------------------------------------------------------------ before Claude: the draft

def low_words(seg):
    return [w["w"] for w in seg.get("words") or [] if w.get("p", 1) < 0.5]


def draft(words: Path):
    """Keep Whisper's version, then write the draft transcript Claude corrects. Returns the draft doc.
    A words.json Whisper wrote since the last correction replaces the kept copy; a corrected one never does."""
    P = paths(words)
    if not P["words"].exists():
        raise FileNotFoundError(f"{rel(P['words'])} does not exist: transcribe first")
    prev = jload(P["doc"]) or {}
    ours = prev.get("words_sha") if prev.get("status") == "claude-corrected" else prev.get("corrected_sha")
    if not P["whisper"].exists() or sha(P["words"]) != ours:
        shutil.copy2(P["words"], P["whisper"])              # words.json is Whisper's (new) output, not our correction
    base = jload(P["whisper"]) or []
    segs = []
    for i, s in enumerate(base):
        segs.append({"id": i, "start": round(s["start"], 2), "end": round(s["end"], 2), "raw": s.get("text", "").strip(),
                     "text": s.get("text", "").strip(), "unsure": [], "note": "", "doubtful": low_words(s),
                     "lint": lint_line(s.get("text", ""))})
    doc = {"input": rel(P["whisper"]), "status": "whisper-draft", "segments": segs,
           "made": time.strftime("%Y-%m-%dT%H:%M:%S"), "corrected_sha": ours if sha(P["words"]) == ours else None}
    jdump(P["doc"], doc)
    write_texts(doc, P)
    return doc


# ------------------------------------------------------------------ after Claude: re-time the corrected words

_HARAKAT = re.compile("[ً-ْٰـ]")
_PUNCT = re.compile(r"[\s\.,!?;:\"'«»()\[\]…،؛؟\-–—]+")


def norm(w):
    w = _HARAKAT.sub("", w.lower())
    w = w.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ى", "ي").replace("ة", "ه")
    return _PUNCT.sub("", w)


def retime(raw_words, tokens, seg_start, seg_end):
    """Give each corrected token a time: a token Whisper also heard keeps its exact times; a changed stretch
    shares the times of the Whisper words it replaces, in proportion to its letters."""
    if not tokens:
        return []
    if not raw_words:
        return spread(tokens, seg_start, seg_end, 0.5)
    sm = difflib.SequenceMatcher(a=[norm(w["w"]) for w in raw_words], b=[norm(t) for t in tokens], autojunk=False)
    blocks = []                                             # [raw lo, raw hi, new lo, new hi, equal?]
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            blocks += [[i1 + k, i1 + k + 1, j1 + k, j1 + k + 1, True] for k in range(i2 - i1)]
        else:
            blocks.append([i1, i2, j1, j2, False])
    # a stretch Claude added (no Whisper word under it) borrows the time of a neighbouring block
    while any(b[0] == b[1] and b[2] < b[3] for b in blocks) and len(blocks) > 1:
        i = next(i for i, b in enumerate(blocks) if b[0] == b[1] and b[2] < b[3])
        j = i - 1 if i > 0 else i + 1
        a, b = sorted((i, j))
        blocks[a:b + 1] = [[blocks[a][0], blocks[b][1], blocks[a][2], blocks[b][3], False]]
    out = []
    for r0, r1, n0, n1, eq in blocks:
        if n0 == n1:
            continue                                        # words Claude removed: their time is simply not used
        if r0 == r1:                                        # nothing Whisper heard at all: the segment's span
            out += spread(tokens[n0:n1], seg_start, seg_end, 0.5)
            continue
        ws = raw_words[r0:r1]
        if eq:
            out.append({"w": tokens[n0], "s": ws[0]["s"], "e": ws[0]["e"], "p": ws[0].get("p", 1.0)})
        else:
            out += spread(tokens[n0:n1], ws[0]["s"], ws[-1]["e"], min(w.get("p", 1.0) for w in ws))
    return out


def spread(tokens, s, e, p):
    weights = [len(norm(t)) + 1 for t in tokens]
    tot, t, out = sum(weights), s, []
    for tok, w in zip(tokens, weights):
        dt = (e - s) * w / tot
        out.append({"w": tok, "s": round(t, 3), "e": round(t + dt, 3), "p": round(p, 2)})
        t += dt
    return out


# ------------------------------------------------------------------ apply

def problems(d, args, fixes: DarijaFixes):
    """What is wrong with Claude's file, against the drafts it was given."""
    probs = []
    for key, words in targets(d, args).items():
        got = fixes.transcripts.get(key)
        if got is None:
            probs.append(f"transcripts.{key} is missing")
            continue
        base = jload(paths(words)["whisper"]) or []
        want = set(range(len(base)))
        ids = [s.id for s in got.segments]
        if len(ids) != len(set(ids)):
            probs.append(f"transcripts.{key}: a segment id appears twice")
        if set(ids) - want:
            probs.append(f"transcripts.{key}: ids {sorted(set(ids) - want)} are not in the draft (ids are 0..{len(base) - 1})")
        if want - set(ids):
            probs.append(f"transcripts.{key}: no entry for ids {sorted(want - set(ids))}: include every id, with Whisper's text when it was right")
        for s in got.segments:
            if not s.text.strip() and not s.note.strip():
                probs.append(f"transcripts.{key} id {s.id}: the text is empty: say in `note` why (noise, music, hallucination)")
    extra = set(fixes.transcripts) - set(targets(d, args))
    if extra:
        probs.append(f"transcripts has keys this run did not ask for: {sorted(extra)}")
    return probs


def apply(words: Path, fix: FixTranscript):
    """Merge Claude's fixes, lint, and write words.json, transcript.json/.txt/.srt."""
    P = paths(words)
    base = jload(P["whisper"]) or []
    by_id = {s.id: s for s in fix.segments}
    segs, out_words = [], []
    for i, s in enumerate(base):
        f = by_id.get(i)
        raw = s.get("text", "").strip()
        text = " ".join((f.text if f else raw).split())
        unsure = list(f.unsure) if f else []
        segs.append({"id": i, "start": round(s["start"], 2), "end": round(s["end"], 2), "raw": raw, "text": text,
                     "unsure": unsure, "note": (f.note if f else "").strip(), "lint": lint_line(text)})
        if not text:
            continue                                        # noise or a Whisper hallucination: out of the captions
        ws = retime(s.get("words") or [], text.split(), s["start"], s["end"])
        doubt = {norm(u) for u in unsure}
        for w in ws:
            if norm(w["w"]) in doubt:
                w["p"] = min(w["p"], 0.4)                   # the app underlines it as unsure
        out_words.append({"start": s["start"], "end": s["end"], "text": text, "raw": raw, "words": ws})
    jdump(P["words"], out_words)
    doc = {"input": rel(P["whisper"]), "status": "claude-corrected", "segments": segs,
           "made": time.strftime("%Y-%m-%dT%H:%M:%S"), "words_sha": sha(P["words"])}
    jdump(P["doc"], doc)
    write_texts(doc, P)
    return summary(words)


# ------------------------------------------------------------------ the stage's hooks

def stage_context(d, P, args):
    rows = []
    for key, words in targets(d, args).items():
        doc = jload(paths(words)["doc"]) or {}
        segs = doc.get("segments") or []
        dur = segs[-1]["end"] if segs else 0
        rows.append(f"- `{key}`: draft `{rel(paths(words)['doc'])}` ({len(segs)} segment{'s' if len(segs) != 1 else ''}, "
                    f"{dur:.1f} s), Whisper's words with their confidence in `{rel(paths(words)['whisper'])}`")
    hints = [x for x in (P.get("name_ar"), P.get("name"), P.get("whisper_prompt") or (P.get("fresh") or {}).get("whisper_prompt"),
                         (P.get("fresh") or {}).get("product_note")) if x]
    return {"name": P.get("name") or P.get("slug"), "files": "\n".join(rows),
            "hints": " · ".join(hints) or "none given", "skill": rel(skill_dir()),
            "output": rel(fixed_file(d, args)), "schema": json.dumps(DarijaFixes.model_json_schema(), ensure_ascii=False, indent=1)}


def stage_before(d, args):
    f = fixed_file(d, args)
    if f.exists():
        f.unlink()
    for words in targets(d, args).values():
        draft(words)


def stage_validate(d, P, fixes, args=None):
    return problems(d, args or {}, fixes)


def stage_finish(d, P, M, fixes, args):
    out = {}
    for key, words in targets(d, args).items():
        s = apply(words, fixes.transcripts[key])
        out[key] = f"{s['changed']} of {s['segments']} segments corrected, {s['dropped']} dropped, " \
                   f"{len(s['unsure'])} unsure, {s['lint_high']} HIGH lint"
    return out
