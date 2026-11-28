#!/usr/bin/env python3
"""asset_lib: the keyword library between a product's pictures and bluxstudio-skill ads.

The pictures are the ones the user uploads for the product or project (a folder of transparent PNG / WebP
cut-outs, each with its own library.json), or, when the user asks for it, illustrations GPT draws in the GPT
asset studio (Documents/ChatGPT/asstets tool ebox, its own library.json). This script keeps the keyword index,
finds the pictures an ad needs from its word-timed transcript, and drops them into a HyperFrames project as
animated assets IN FRONT of the speaker, by the caption, on the word that names them (asset_motion.js).

  python asset_lib.py index <folder>               index an upload folder -> <folder>/library.json (then setmany)
  python asset_lib.py --lib <lib.json> setmany <keywords.json>   keywords for many pictures at once (you write them)
  python asset_lib.py sync                         re-index the library's folder (adds new files, flags gone ones)
  python asset_lib.py tag [--all] [--replace]      GPT writes keywords (Darija, Arabic, French, English)
  python asset_lib.py set <id> <file.json>         keywords/subject/motion/concept of one picture
  python asset_lib.py list                         what the library holds
  python asset_lib.py search <words ...>           which picture a spoken word would pull
  python asset_lib.py match <words.json>           every keyword hit in a transcript
  python asset_lib.py plan <words.json> --t-body X [--t-cta Z] [--dur D] [--remix] [--hook]
                         [--busy 12.0-15.5 ...] [--max N] [--bottom PX] [--src KEY] --out plan.json
  python asset_lib.py fill <plan.json> [--max 3]   GPT draws what is MISSING (only when the user asks)
  python asset_lib.py place <plan.json> --project <hf project> [--beats beats.json | --out resolved.json]
  python asset_lib.py auto <words.json> --project <dir> --t-body X [--t-cta Z] [--remix] [--generate 0]
Every command takes --lib <library.json> (the upload folder's); without it the GPT studio's library is used.

words.json is transcribe.py's output: [{"start", "end", "text", "words": [{"w", "s", "e", "p"}]}].
A plan's beats are {"kind": "asset", "lib": <id>, "in", "out", keys|breathe|shake}; `place` turns each into a
trimmed PNG in <project>/assets/img/ (GPT's orange illustrations also palette-locked), fills img/w/h/x/top, then
writes them into index.html's ILLUS slot (fresh edit) or into a remix beats.json (remix_broll.py).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
SKILL_DIR = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))
import gpt_assets  # noqa: E402  (same folder)

CONCEPTS_FILE = SKILL_DIR / "assets" / "concepts.json"
IMAGE_EXT = {".png", ".webp"}
LANGS = ("darija", "ar", "fr", "en")
MOTIONS = ("breathe", "shake", "shine")


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def say(*parts) -> None:
    print(*parts, flush=True)


# ------------------------------------------------------------------ text normalisation

_AR_MAP = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي", "ء": "", "ـ": "",
    "ڨ": "ق", "گ": "ك", "ڭ": "ك", "ڤ": "ف", "پ": "ب", "چ": "ج", "ژ": "ز", "ک": "ك", "ی": "ي",
    **{chr(0x0660 + d): str(d) for d in range(10)}, **{chr(0x06F0 + d): str(d) for d in range(10)},
})


@lru_cache(maxsize=None)
def norm_tokens(text: str) -> tuple:
    """Lower-case, no diacritics/accents, unified alef/yaa/taa marbuta/hamza, split on non-letters."""
    s = unicodedata.normalize("NFKD", str(text))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.translate(_AR_MAP).lower()
    s = re.sub(r"[^\w%]+|_", " ", s)
    return tuple(s.split())


_AR = re.compile(r"[؀-ۿ]")
_CONJ = ("و", "ف")
_PREP = ("بال", "فال", "وال", "كال", "عال", "لل", "ال", "ب", "ل", "ك")  # longest first
_SUFF = ("هم", "كم", "ها", "نا", "ني", "ين", "ات", "ون", "ه", "ك", "ي", "و", "ا")


def _prefix_stems(tok: str) -> set:
    out = {tok}
    for p in _CONJ:
        if tok.startswith(p) and len(tok) > 4:
            out.add(tok[1:])
    for c in list(out):
        for p in _PREP:
            if c.startswith(p) and len(c) - len(p) >= 3:
                out.add(c[len(p):])
                break
    return out


@lru_cache(maxsize=None)
def stems(tok: str) -> frozenset:
    """Spoken word: conjunction, preposition+article, then pronoun/plural suffix (a possessed ـت gets its
    ة back: ركبتي -> ركبه, معدتي -> معده). No verb-prefix stripping: يقولون must not reach القولون."""
    if not _AR.search(tok):
        return frozenset({tok, tok[:-1]} if len(tok) > 4 and tok.endswith("s") else {tok})
    out = _prefix_stems(tok)
    for c in list(out):
        for s in _SUFF:
            if c.endswith(s) and len(c) - len(s) >= 3:
                r = c[:-len(s)]
                out.add(r)
                if r.endswith("ت") and len(r) >= 4:
                    out.add(r[:-1] + "ه")
    return frozenset(out)


@lru_cache(maxsize=None)
def kw_stems(tok: str) -> frozenset:
    """Keyword: only conjunction/preposition/article come off. Its last letters are part of the word
    (التنفسي, الدوالي), so stripping them would let unrelated spoken words in."""
    if not _AR.search(tok):
        return frozenset({tok, tok[:-1]} if len(tok) > 4 and tok.endswith("s") else {tok})
    return frozenset(_prefix_stems(tok))


_CONFUSABLE = [set("سص"), set("تط"), set("دذضظز"), set("قكغ"), set("حه")]


@lru_cache(maxsize=None)
def tok_sim(a: str, b: str) -> float:
    """a = spoken token, b = keyword token (both normalised).
    1.0 exact · 0.93 same stem (4+ letters) · 0.90 one look-alike letter (Whisper slip) · 0.86 short stem."""
    if a == b:
        return 1.0
    common = stems(a) & kw_stems(b)
    if common:
        n = max(len(c) for c in common)
        if n >= 4:
            return 0.93
        # a 3-letter stem is weak evidence: only for an inflected spoken word (صدرك ~ الصدر, بالكحة ~ الكحة),
        # never a bare 3-letter word (تعب, شوف, قرح are everyday words or Whisper garble)
        if n == 3 and len(a) >= 4:
            return 0.86
    # Whisper slips between look-alike sounds on longer words (عصل/عسل, طانسيو/تانسيو)
    if len(a) == len(b) >= 5:
        diff = [(x, y) for x, y in zip(a, b) if x != y]
        if len(diff) == 1 and any(diff[0][0] in g and diff[0][1] in g for g in _CONFUSABLE):
            return 0.90
    return 0.0


# Words that never pull a picture on their own (they are in almost every ad).
_STOP_RAW = ["وجع", "الوجع", "مرض", "المرض", "صحة", "الصحة", "صحتك", "الجسم", "جسم", "دوا", "الدوا", "دواء",
             "عسل", "العسل", "خلطة", "الخلطة", "طبيعي", "طبيعية", "حاجة", "بزاف", "مليح", "راحة", "الراحة",
             "تاع", "نتاع", "ديال", "بوكس", "إي", "ebox", "douleur", "sante", "santé", "maladie", "mal",
             "corps", "naturel", "miel", "pain", "health", "body",
             # everyday Darija words that collide with a health word
             "نفسي", "نفسك", "نفسه", "روحي", "روحك", "قريب", "القريب", "شوف", "الشوف", "صغار", "الصغار",
             "النيف", "الظهر", "الضهر", "مقلق", "مقلقة", "ننسى", "الميزان", "القبض", "الحرقة", "الضيقة",
             "السلسلة", "قلبي", "قلبك", "الدوا", "تعب"]
STOP = {t for w in _STOP_RAW for t in norm_tokens(w)}
FILLERS = {t for w in ["تاع", "نتاع", "تاعك", "تاعي", "تاعو", "تاعها", "تاعكم", "ديال", "بتاع", "تبع", "متاع",
                       "انتاع", "في", "فـ", "de", "du", "des", "la", "le", "les"] for t in norm_tokens(w)}


# ------------------------------------------------------------------ library file

def project_dir() -> Path:
    return gpt_assets.gpt_project_dir()


LIB_OVERRIDE: Path | None = None


def set_lib(path) -> None:
    """Use this library.json (an upload folder's) instead of the GPT asset studio's."""
    global LIB_OVERRIDE
    LIB_OVERRIDE = Path(path).resolve()


def lib_path() -> Path:
    if LIB_OVERRIDE:
        return LIB_OVERRIDE
    env = os.environ.get("CAMEL_GPT_LIBRARY")
    return Path(env) if env else project_dir() / "library.json"


def lib_dir() -> Path:
    """Entry files are relative to the folder the library sits in."""
    return lib_path().parent


def is_gpt_library() -> bool:
    try:
        return lib_dir().resolve() == project_dir().resolve()
    except OSError:
        return False


@contextmanager
def _lock(path: Path, timeout: float = 90.0):
    lock = path.with_name(path.name + ".lock")
    t0 = time.time()
    while True:
        try:
            os.close(os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            break
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > 120:  # a crashed writer left it behind
                    lock.unlink()
                    continue
            except OSError:
                pass
            if time.time() - t0 > timeout:
                raise RuntimeError(f"library is locked: {lock}")
            time.sleep(0.15)
    try:
        yield
    finally:
        try:
            lock.unlink()
        except OSError:
            pass


def load_lib(path: Path | None = None) -> dict:
    path = path or lib_path()
    data = json.loads(path.read_text(encoding="utf-8-sig")) if path.is_file() else {}
    data.setdefault("version", 1)
    data.setdefault("note", "Keyword index of the GPT asset studio, kept by bluxstudio-skill/scripts/asset_lib.py. "
                            "file paths are relative to this folder.")
    data.setdefault("assets", [])
    return data


def update_lib(fn, path: Path | None = None):
    """Read-modify-write under a lock file (several GPT jobs may finish at once)."""
    path = path or lib_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with _lock(path):
        data = load_lib(path)
        res = fn(data)
        data["updated"] = now()
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, path)
    return res


def entry_file(e: dict) -> Path:
    p = Path(e["file"])
    return p if p.is_absolute() else lib_dir() / p


def rel_file(path: Path) -> str:
    try:
        return path.resolve().relative_to(lib_dir().resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def look_of(stem: str, size) -> str:
    if stem.startswith("glossy"):
        return "glossy"
    if stem.startswith("flat"):
        return "flat"
    return "flat" if size[0] > size[1] * 1.2 else "glossy"


def subject_box(path: Path):
    from PIL import Image
    im = Image.open(path).convert("RGBA")
    bb = im.getchannel("A").point(lambda v: 255 if v > 12 else 0).getbbox() or (0, 0, im.width, im.height)
    return [bb[2] - bb[0], bb[3] - bb[1]], list(im.size)


def alpha_flags(path: Path) -> dict:
    """opaque = no transparent background (it would show as a rectangle), empty = nothing visible."""
    import numpy as np
    from PIL import Image
    with Image.open(path) as im:
        a = np.asarray(im.convert("RGBA"))[..., 3]
    return {"opaque": bool((a < 250).mean() < 0.02), "empty": bool(not (a > 12).any())}


def merge_kw(a: dict | None, b: dict | None) -> dict:
    out = {}
    for lang in LANGS:
        seen, lst = set(), []
        for w in list((a or {}).get(lang, [])) + list((b or {}).get(lang, [])):
            w = str(w).strip()
            k = " ".join(norm_tokens(w))
            if w and k and k not in seen:
                seen.add(k)
                lst.append(w)
        out[lang] = lst
    return out


def upsert(data: dict, entry: dict, replace_kw: bool = False) -> dict:
    entry = dict(entry)
    kw = entry.pop("keywords", None)
    for e in data["assets"]:
        if e["id"] == entry["id"]:
            e.update({k: v for k, v in entry.items() if v not in (None, "", [])})
            if kw is not None:
                e["keywords"] = merge_kw(None if replace_kw else e.get("keywords"), kw)
            e.pop("missing", None)
            return e
    entry["keywords"] = merge_kw(None, kw)
    data["assets"].append(entry)
    return entry


def base_id(asset_id: str) -> str:
    return re.sub(r"-(v?\d+|gpt|ref)$", "", asset_id)


def load_concepts() -> list:
    if not CONCEPTS_FILE.is_file():
        return []
    return json.loads(CONCEPTS_FILE.read_text(encoding="utf-8-sig"))["concepts"]


def covers(e: dict, c: dict) -> bool:
    """Does library entry e show concept c? By its id (GPT pictures are named after concepts), the concept's
    `assets` list, or the entry's own `concept` (set with setmany for an uploaded picture: الكبد -> glossy-liver)."""
    b = base_id(e["id"])
    return b == c["id"] or b in c.get("assets", []) or e.get("concept") == c["id"]


def lexicon_for(e: dict, concepts: list) -> dict:
    """Curated trigger words of every concept this picture shows (merged into matching)."""
    kw = {}
    for c in concepts:
        if covers(e, c):
            kw = merge_kw(kw, c.get("triggers"))
    return kw


def register_generated(files: list, name: str, look: str, prompt: str, result: dict,
                       extra_keywords: dict | None = None) -> list:
    """Called by gpt_assets.generate after GPT saved its image(s): one library entry per file."""
    ids = []
    gkw = result.get("keywords") if isinstance(result.get("keywords"), dict) else None

    def fn(data):
        for f in files:
            f = Path(f)
            box, size = subject_box(f)
            e = upsert(data, {
                "id": f.stem, "file": rel_file(f), "look": look, "source": "gpt",
                "subject": result.get("subject", ""), "prompt": result.get("prompt") or prompt,
                "motion": result.get("motion") if result.get("motion") in MOTIONS else "",
                "label": result.get("label", ""), "box": box, "size": size,
                "keywords": merge_kw(gkw, extra_keywords),
                "tagged_by": "gpt" if gkw and any(gkw.get(k) for k in LANGS) else "",
                "added": now(), "request": name,
            })
            ids.append(e["id"])
    update_lib(fn)
    return ids


# ------------------------------------------------------------------ sync / tag / set / list

def request_prompts() -> dict:
    out = {}
    for req in sorted((project_dir() / ".gpt-assets").glob("*/request.txt")):
        txt = req.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"<<<\s*\n(.*?)\n>>>", txt, re.S)
        if not m:
            continue
        for t in re.findall(r"^- (.+\.(?:png|webp))\s*$", txt, re.M):
            out[Path(t.strip()).stem] = m.group(1).strip()
    return out


UPLOAD_EXT = {".png", ".webp", ".jpg", ".jpeg"}     # jpg is indexed only to say it needs a cut-out


def scan_folders() -> list:
    """GPT studio library: generated/ + style/refs/. Any other library: the upload folder it sits in."""
    if is_gpt_library():
        proj = project_dir()
        return [(proj / "generated", "gpt", IMAGE_EXT), (proj / "style" / "refs", "ref", IMAGE_EXT)]
    return [(lib_dir(), "upload", UPLOAD_EXT)]


def upload_id(stem: str) -> str:
    return re.sub(r"[^\w]+", "-", stem.lower()).strip("-_") or "asset"


def name_keywords(stem: str) -> dict:
    """An uploaded file's own name as a first keyword (an Arabic-script name counts as Darija)."""
    words = re.sub(r"\s*\(\d+\)$|[\s_-]+\d+$", "", " ".join(re.split(r"[-_\s]+", stem))).strip()
    return {"darija" if _AR.search(words) else "en": [words]} if words else {}


def cmd_sync(_a=None) -> None:
    prompts = request_prompts() if is_gpt_library() else {}
    found = []
    for folder, source, exts in scan_folders():
        if folder.is_dir():
            found += [(p, source) for p in sorted(folder.iterdir())
                      if p.is_file() and p.suffix.lower() in exts]

    def fn(data):
        known = {str(entry_file(e).resolve()).lower(): e for e in data["assets"]}
        ids = {e["id"] for e in data["assets"]}
        added, gone = [], []
        for p, source in found:
            e = known.get(str(p.resolve()).lower())
            if e:
                e.pop("missing", None)
                e.update(alpha_flags(p))          # the user may have replaced it with a proper cut-out
                continue
            base = upload_id(p.stem) if source == "upload" else p.stem
            eid = base if base not in ids else f"{base}-{source}"
            k = 2
            while eid in ids:
                eid, k = f"{base}-{k}", k + 1
            box, size = subject_box(p)
            data["assets"].append({
                "id": eid, "file": rel_file(p), "source": source,
                "look": "photo" if source == "upload" else look_of(p.stem, size),
                "subject": "", "prompt": prompts.get(p.stem, ""), "motion": "", "label": "",
                "box": box, "size": size, **alpha_flags(p),
                "keywords": merge_kw(None, name_keywords(p.stem) if source == "upload" else None),
                "tagged_by": "", "added": now()})
            ids.add(eid)
            added.append(eid)
        for e in data["assets"]:
            if not entry_file(e).is_file():
                e["missing"] = True
                gone.append(e["id"])
        return added, gone

    added, gone = update_lib(fn)
    lib = load_lib()
    live = [e for e in lib["assets"] if not e.get("missing")]
    untagged = [e["id"] for e in live if not e.get("tagged_by")]
    bad = [f"{e['id']} ({usable(e)})" for e in live if usable(e)]
    say(f"library: {lib_path()}")
    say(f"  {len(lib['assets'])} assets, added {len(added)}: {', '.join(added) or '-'}")
    if gone:
        say(f"  files gone (kept, flagged missing): {', '.join(gone)}")
    if bad:
        say(f"  can't be shown, never planned: {'; '.join(bad)}")
    if untagged:
        lib_arg = "" if is_gpt_library() else f" --lib \"{lib_path()}\""
        say(f"  no keywords yet: {', '.join(untagged)}")
        say(f"  -> look at each picture, write its keywords, then: asset_lib.py{lib_arg} setmany <keywords.json>"
            f"   (or asset_lib.py{lib_arg} tag: GPT writes them)")
    else:
        say("  every picture has keywords")


def cmd_index(a) -> None:
    folder = Path(a.folder)
    if not folder.is_dir():
        raise SystemExit(f"not a folder: {folder}")
    if not LIB_OVERRIDE:
        set_lib(folder / "library.json")
    elif LIB_OVERRIDE.parent != folder.resolve():
        raise SystemExit(f"--lib must sit in the folder it indexes ({folder})")
    cmd_sync(a)


TAG_ITEM = {
    "type": "object",
    "properties": {"id": {"type": "string"}, **gpt_assets.KEYWORD_PROPS},
    "required": ["id", *gpt_assets.KEYWORD_PROPS.keys()],
    "additionalProperties": False,
}
TAG_SCHEMA = {
    "type": "object",
    "properties": {"assets": {"type": "array", "items": TAG_ITEM}},
    "required": ["assets"],
    "additionalProperties": False,
}


def gpt_tag(entries: list, replace: bool = False) -> list:
    """One Codex/GPT call per batch of <= 8 images: GPT looks at them and writes their keywords."""
    codex = gpt_assets.find_codex()
    if not codex:
        raise RuntimeError("Codex CLI not found (open the ChatGPT Codex desktop app, or set CODEX_CLI_PATH).")
    proj = project_dir()
    done = []
    for k in range(0, len(entries), 8):
        batch = entries[k:k + 8]
        lines = []
        for i, e in enumerate(batch, 1):
            hint = (e.get("prompt") or e.get("subject") or "").replace("\n", " ")
            hint = (hint[:420] + " ...") if len(hint) > 420 else hint
            lines.append(f'{i}. id "{e["id"]}" ({e.get("look", "?")} look)' + (f' - made from: "{hint}"' if hint else ""))
        request = "\n".join([
            "Keyword request from Claude (bluxstudio-skill asset_lib). This is NOT an image request: do not generate, "
            "edit or save any image, and do not change any file in this folder.",
            "",
            "The attached images, in this order, are illustrations from this asset studio:",
            *lines,
            "",
            "For each image write its keywords.",
            gpt_assets.KEYWORD_RULES,
            'End with JSON only: {"assets": [{"id": "<id exactly as given>", "subject": "...", "motion": "...", '
            '"label": "...", "keywords": {"darija": [...], "ar": [...], "fr": [...], "en": [...]}}]}',
        ])
        workdir = proj / ".gpt-assets" / f"{time.strftime('%Y%m%d-%H%M%S')}-tag-keywords"
        workdir.mkdir(parents=True, exist_ok=True)
        (workdir / "request.txt").write_text(request, encoding="utf-8")
        images = [entry_file(e) for e in batch]
        say(f"GPT is tagging {len(batch)} image(s) ... (log: {workdir})")
        rc, last, log = gpt_assets.run_codex(codex, proj, request, images, workdir, schema=TAG_SCHEMA,
                                             sandbox="read-only",
                                             on_tick=lambda s: print(f"  ... GPT working ({int(s)} s)",
                                                                     file=sys.stderr, flush=True))
        try:
            res = json.loads(last.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as exc:
            raise RuntimeError(f"GPT returned no keywords (exit {rc}): {exc}\n{gpt_assets.tail(log)}")
        by_id = {e["id"]: e for e in batch}
        got = [r for r in res.get("assets", []) if r.get("id") in by_id]

        def fn(data, got=got):
            for r in got:
                upsert(data, {"id": r["id"], "subject": r.get("subject", ""),
                              "motion": r.get("motion") if r.get("motion") in MOTIONS else "",
                              "label": r.get("label", ""), "keywords": r.get("keywords") or {},
                              "tagged_by": "gpt", "tagged": now()}, replace_kw=replace)
        update_lib(fn)
        done += [r["id"] for r in got]
        missed = [i for i in by_id if i not in {r["id"] for r in got}]
        if missed:
            say(f"  GPT skipped: {', '.join(missed)}")
    return done


def cmd_tag(a) -> None:
    lib = load_lib()
    pick = [e for e in lib["assets"] if not e.get("missing")
            and (a.all or not e.get("tagged_by") or e["id"] in (a.ids or []))]
    if a.ids:
        pick = [e for e in pick if e["id"] in a.ids]
    if not pick:
        say("nothing to tag (every asset has keywords; use --all to redo them)")
        return
    done = gpt_tag(pick, replace=a.replace)
    say(f"tagged {len(done)}: {', '.join(done)}")
    cmd_list(None)


def cmd_set(a) -> None:
    upd = json.loads(Path(a.file).read_text(encoding="utf-8-sig"))

    def fn(data):
        if not any(e["id"] == a.id for e in data["assets"]):
            raise SystemExit(f"unknown asset id: {a.id} (run sync first)")
        upsert(data, {"id": a.id, **{k: upd[k] for k in ("subject", "motion", "label", "concept") if k in upd},
                      "keywords": upd.get("keywords", {}), "tagged_by": upd.get("tagged_by", "claude"),
                      "tagged": now()}, replace_kw=a.replace)
    update_lib(fn)
    say(f"updated {a.id}")


def cmd_setmany(a) -> None:
    """{"<id>": {"keywords": {"darija": [...], "ar": [...], "fr": [...], "en": [...]}, "motion": "shine",
    "concept": "glossy-liver", "subject": "..."}, ...}: what you write after looking at the uploaded pictures."""
    upd = json.loads(Path(a.file).read_text(encoding="utf-8-sig"))
    items = upd.get("assets", upd) if isinstance(upd, dict) else {}

    def fn(data):
        ids = {e["id"] for e in data["assets"]}
        unknown = [i for i in items if i not in ids]
        if unknown:
            raise SystemExit(f"unknown asset id(s): {', '.join(unknown)} (run index / sync first)")
        for i, u in items.items():
            upsert(data, {"id": i, **{k: u[k] for k in ("subject", "motion", "label", "concept") if k in u},
                          "keywords": u.get("keywords", {}), "tagged_by": u.get("tagged_by", "claude"),
                          "tagged": now()}, replace_kw=a.replace)
    update_lib(fn)
    say(f"updated {len(items)}: {', '.join(items)}")
    cmd_list(None)


def cmd_list(_a) -> None:
    lib = load_lib()
    say(f"library: {lib_path()}  ({len(lib['assets'])} assets)")
    for e in lib["assets"]:
        kw = e.get("keywords") or {}
        n = " ".join(f"{k}:{len(kw.get(k, []))}" for k in LANGS)
        flag = (" MISSING" if e.get("missing") else "") + (" NO-ALPHA" if e.get("opaque") else "") \
            + (f" ={e['concept']}" if e.get("concept") else "")
        say(f"  {e['id']:34s} {e.get('look', '?'):6s} {e.get('motion') or '-':7s} {n:28s} "
            f"{e.get('tagged_by') or 'untagged':8s} {e['file']}{flag}")
        if kw.get("darija"):
            say(f"      darija: {'، '.join(kw['darija'][:10])}")


# ------------------------------------------------------------------ matching

def load_words(path, t0=None, t1=None) -> list:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    segs = data.get("segments", []) if isinstance(data, dict) else data
    toks, wi = [], 0
    for s in segs:
        for w in s.get("words", []):
            for part in norm_tokens(w["w"]):
                toks.append({"n": part, "raw": w["w"].strip(), "wi": wi, "s": float(w["s"]), "e": float(w["e"])})
            wi += 1
    if t0 is not None:
        toks = [t for t in toks if t["s"] >= t0]
    if t1 is not None:
        toks = [t for t in toks if t["s"] < t1]
    return toks


def phrase_index(items: list) -> list:
    """items: [(owner id, keywords dict)] -> [(owner, lang, rank, n, tokens, text)]"""
    out = []
    for owner, kw in items:
        for lang in LANGS:
            lst = (kw or {}).get(lang, [])
            for r, text in enumerate(lst):
                t = norm_tokens(text)
                if not t or (len(t) == 1 and (t[0] in STOP or len(t[0]) < 3)):
                    continue
                out.append((owner, lang, r, len(lst), t, text))
    return out


def library_items(lib: dict, concepts: list) -> list:
    return [(e["id"], merge_kw(e.get("keywords"), lexicon_for(e, concepts)))
            for e in lib["assets"] if not e.get("missing")]


def _phrase_at(toks, i, kt):
    j, scores = i, []
    for k, ktok in enumerate(kt):
        if j >= len(toks):
            return None
        s = tok_sim(toks[j]["n"], ktok)
        if s < 0.80 and k > 0 and toks[j]["n"] in FILLERS and j + 1 < len(toks):
            j += 1
            s = tok_sim(toks[j]["n"], ktok)
        if s < 0.80:
            return None
        scores.append(s)
        j += 1
    score = sum(scores) / len(scores)
    mode = "exact" if all(s == 1.0 for s in scores) else "slip" if 0.90 in scores else "stem"
    return (score, j - 1, mode) if score >= 0.85 else None


def match(toks: list, phrases: list) -> list:
    best = {}
    firsts = {}
    for p in phrases:
        firsts.setdefault(p[4][0], []).append(p)
    for i, t in enumerate(toks):
        for first, plist in firsts.items():
            if tok_sim(t["n"], first) < 0.80:
                continue
            for owner, lang, r, n, kt, text in plist:
                res = _phrase_at(toks, i, kt)
                if not res:
                    continue
                score, j, mode = res
                adj = score + 0.04 * (1 - r / max(1, n)) + 0.03 * (len(kt) - 1) - (0.05 if lang == "en" else 0)
                key = (owner, i)
                if key not in best or adj > best[key]["score"]:
                    seen, said = set(), []
                    for x in toks[i:j + 1]:
                        if x["wi"] not in seen:
                            seen.add(x["wi"])
                            said.append(x["raw"])
                    best[key] = {"asset": owner, "lang": lang, "kw": text, "said": " ".join(said), "mode": mode,
                                 "t": round(toks[i]["s"], 3), "end": round(toks[j]["e"], 3),
                                 "score": round(adj, 3), "i": i, "j": j}
    # one hit per asset per stretch of words: keep the strongest of overlapping spans
    kept = []
    for h in sorted(best.values(), key=lambda h: -h["score"]):
        if not any(k["asset"] == h["asset"] and not (h["j"] < k["i"] or h["i"] > k["j"]) for k in kept):
            kept.append(h)
    return sorted(kept, key=lambda h: (h["t"], -h["score"]))


def cmd_match(a) -> None:
    lib, concepts = load_lib(), load_concepts()
    hits = match(load_words(a.words, a.t0, a.t1), phrase_index(library_items(lib, concepts)))
    for h in hits:
        say(f"  {h['t']:7.2f}  {h['asset']:32s} {h['score']:.2f}  {h['lang']:6s} said «{h['said']}»  ~ «{h['kw']}»")
    say(f"{len(hits)} hit(s)")


def cmd_search(a) -> None:
    text = " ".join(a.words)
    toks = [{"n": t, "raw": t, "wi": k, "s": float(k), "e": float(k) + 0.5} for k, t in enumerate(norm_tokens(text))]
    lib, concepts = load_lib(), load_concepts()
    hits = match(toks, phrase_index(library_items(lib, concepts)))
    for h in sorted(hits, key=lambda h: -h["score"]):
        say(f"  {h['asset']:32s} {h['score']:.2f}  ~ «{h['kw']}» ({h['lang']})")
    chits = match(toks, phrase_index([(c["id"], c.get("triggers")) for c in concepts]))
    for h in chits:
        say(f"  (concept) {h['asset']} ~ «{h['kw']}»")
    if not hits and not chits:
        say("  no picture for that")


# ------------------------------------------------------------------ layout (in front of the speaker, by the caption)

BOX = {"fresh": 420, "remix": 380}          # max display side of one asset
BOTTOM = {"fresh": 1330, "remix": 1260}     # its bottom edge. fresh: tucked under the caption pill (top 1262), like
                                            # the editor's ads; remix: just above the burned-in captions (set
                                            # product.json asset_bottom when a product's captions sit higher)
SIDE_CX = {"C": 540, "L": 330, "R": 750}    # centre x per side: C unless his hands or the product are in the way
EDGE = 24                                   # min gap to the frame edge


def layout(w0: float, h0: float, side: str = "C", bottom: int = BOTTOM["fresh"], box: int = BOX["fresh"],
           x=None) -> dict:
    """Display size and position of one asset (screen px): fits in box x box, bottom edge at `bottom`."""
    s = min(box / w0, box / h0)
    W, H = max(1, round(w0 * s)), max(1, round(h0 * s))
    if x is None:
        x = round(min(max(SIDE_CX.get(side, 540) - W / 2, EDGE), 1080 - EDGE - W))
    return {"w": W, "h": H, "x": int(x), "top": int(round(bottom - H))}


# ------------------------------------------------------------------ planning

def concept_prompt(c: dict) -> str:
    """The GPT prompt for a concept ('' when it has no subject: then only an uploaded picture can show it), in the
    colours of the library folder's brand (brand_guide.palette: the house orange, word for word, without a
    brand.json there)."""
    if c.get("prompt"):
        return c["prompt"]
    if not c.get("subject"):
        return ""
    import brand_guide
    P = brand_guide.palette(project_dir())
    hue = P["hue"]
    if c["look"] == "glossy":
        return (f"Semi-realistic 3D medical illustration of {c['subject']}, straight front view, centered, a single "
                f"isolated object. Entirely monochrome vivid {hue} ({P['main']}): a glossy, translucent {hue} gel / "
                f"gummy-candy surface with a soft inner glow, {c.get('inner', 'soft inner structure')} visible inside "
                f"the surface in darker {P['deep_word']} ({P['inner']}), small {P['pale_word']} specular highlight "
                f"streaks along the upper rims, deeper {hue} toward the bottom edges. "
                f"{(c['tube'].strip() + ' ') if c.get('tube') else ''}No outline strokes. Isolated on a transparent "
                "background, no shadow, no text, no labels, no other colors.")
    if c.get("cutaway"):
        detail = (f"A cut-away cross-section shows {c['cutaway']} as recessed, debossed channels in dark "
                  f"{P['deep_word']} ({P['recess']}) with a soft inner shadow, like shapes pressed into clay.")
    else:
        detail = (f"A few thin tapered {P['line_word']} ({P['line']}) strokes mark the "
                  f"{c.get('marks', 'ear, the closed eye and the neck line')}.")
    action = (c["action"].strip() + " ") if c.get("action") else ""
    return (f"Minimal flat health icon illustration: side-profile silhouette of {c['subject']}, facing right, cropped "
            f"at the {c.get('crop', 'chest')}. One solid vivid {hue} ({P['main']}) shape with a soft gradient from "
            f"lighter {hue} at the top to deeper {hue} ({P['flatdeep']}) at the bottom left, smooth matte finish, no "
            f"outline. {detail} {action}Overlapping parts are separated by a thin gap of empty background. Isolated "
            "on a transparent background, no shadow, no text, no other colors.")


def _parse_busy(specs) -> list:
    """Time windows where no asset may show (a burned-in card at chest height, full-screen B-roll, the CTA mockup):
    12.0-15.5, or the older SIDE:12.0-15.5 form (the side no longer matters: assets sit by the caption)."""
    out = []
    for s in specs or []:
        m = re.match(r"^(?:[LRTC]:)?([\d.]+)-([\d.]+)$", s.strip())
        if not m:
            raise SystemExit(f"--busy wants START-END like 12.0-15.5, got {s!r}")
        out.append(("C", float(m.group(1)), float(m.group(2))))
    return out


def _avoid_from(path) -> list:
    if not path or not Path(path).is_file():
        return []
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    beats = data.get("beats", []) if isinstance(data, dict) else data
    return [(b.get("side", "C"), float(b["in"]), float(b["out"])) for b in beats if "lib" not in b]


def usable(e: dict) -> str:
    """'' when the picture can be shown, else why not."""
    if e.get("opaque"):
        return "no transparent background (ask the user for a PNG/WebP cut-out)"
    if e.get("empty"):
        return "the picture is fully transparent"
    return ""


def _key_of(e: dict) -> str:
    m = e.get("motion") if e.get("motion") in MOTIONS else ("shake" if e.get("look") == "flat" else "shine")
    return {"breathe": "breathe", "shake": "shake", "shine": "keys"}[m]


def do_plan(words, t_body, t_cta=None, dur=None, remix=False, hook=False, avoid=None, busy=None,
            max_beats=None, src=None, bottom=None) -> dict:
    """One asset on screen at a time, by the caption, on the words that name it."""
    lib, concepts = load_lib(), load_concepts()
    entries = {e["id"]: e for e in lib["assets"] if not e.get("missing")}
    toks = load_words(words)
    if not toks:
        raise SystemExit(f"no words in {words}")
    dur = dur or round(toks[-1]["e"] + 1.0, 2)
    t_body = float(t_body or 0.0)
    body = (t_body + 0.30, (float(t_cta) if t_cta else dur) - 0.25)
    sections = ([(0.15, t_body - 0.25)] if hook and not remix and t_body > 1.0 else []) + [body]

    def section_of(t):
        return next((s for s in sections if s[0] - 0.25 <= t <= s[1] - 1.0), None)

    hits = match(toks, phrase_index(library_items(lib, concepts)))
    hits = [h for h in hits if h["asset"] in entries]

    # clusters = hits on the same (or touching) words: competing pictures for one phrase
    clusters = []
    for h in (h for h in hits if section_of(h["t"])):
        c = next((c for c in clusters[-2:] if any(h["i"] <= x["j"] + 1 and x["i"] <= h["j"] + 1
                                                   for x in c["hits"])), None)
        if c:
            c["hits"].append(h)
        else:
            clusters.append({"hits": [h]})
    for c in clusters:
        c["t0"] = min(h["t"] for h in c["hits"])
        c["score"] = max(h["score"] for h in c["hits"])
    if max_beats and len(clusters) > max_beats:
        keep = sorted(clusters, key=lambda c: -c["score"])[:max_beats]
        clusters = [c for c in clusters if c in keep]

    # every asset sits by the caption, so they share one lane: one at a time, 0.3 s apart
    occupied = [(a - 0.3, b + 0.3) for _side, a, b in list(busy or []) + list(avoid or [])]

    def free(a, b, ignore=None):
        return all(b <= x0 or a >= x1 for (x0, x1, *rest) in occupied if not rest or rest[0] is not ignore)

    def extend(b, mine, sec):
        """The speaker is still on this picture's topic: keep it up a little longer, add a key."""
        top_hit = max(mine, key=lambda x: x["score"])
        t_end = max(x["end"] for x in mine)
        new_out = round(min(max(b["out"], t_end + 1.3), b["in"] + 6.0, sec[1]), 2)
        if new_out > b["out"] and not free(b["out"], new_out, ignore=b):
            return False
        for oc in occupied:
            if len(oc) > 2 and oc[2] is b:
                occupied.remove(oc)
                break
        b["out"] = max(b["out"], new_out)
        occupied.append((b["in"] - 0.3, b["out"] + 0.3, b))
        mk = _key_of(entries[b["lib"]])
        key_t = round(top_hit["t"] + 0.05, 2)
        if key_t - b[mk][-1] > 1.4 and key_t < b["out"] - 0.6:
            b[mk].append(key_t)
        return True

    beats, skipped, last_used = [], [], {}
    for c in clusters:
        by = {}
        for h in c["hits"]:
            by.setdefault(h["asset"], []).append(h)
        sec = section_of(c["t0"])
        # 1) a picture still on screen (or just gone) that fits these words: keep it, one idea = one picture
        live = [b for b in beats if b["lib"] in by and c["t0"] - b["out"] < 2.0]
        if live and extend(live[-1], by[live[-1]["lib"]], sec):
            last_used[live[-1]["lib"]] = c["t0"]
            continue
        # 2) else the best picture for these words; on a tie the one shown longest ago
        cands = sorted(by, key=lambda a: (-round(max(x["score"] for x in by[a]), 2), last_used.get(a, -1e9),
                                          -sum(x["score"] for x in by[a])))
        why_not = []
        for aid in cands:
            e, mine = entries[aid], by[aid]
            bad = usable(e)
            if bad:
                why_not.append(f"{aid}: {bad}")
                continue
            first = min(mine, key=lambda x: x["t"])
            top_hit = max(mine, key=lambda x: x["score"])
            t0, t_end = first["t"], max(x["end"] for x in mine)
            prev = next((b for b in reversed(beats) if b["lib"] == aid), None)
            if prev and t0 - prev["out"] < 6.0:
                why_not.append(f"{aid}: same picture < 6 s ago")
                continue
            tin = round(max(t0 - 0.25, sec[0]), 2)
            tout = round(min(max(t_end + 1.3, tin + 2.4), tin + 4.0, sec[1]), 2)
            if tout - tin < 1.3:
                why_not.append(f"{aid}: too close to a cut")
                continue
            if not free(tin, tout):
                why_not.append(f"{aid}: another asset or a busy window is on screen")
                continue
            key_t = round(top_hit["t"] + 0.05, 2)
            b = {"kind": "asset", "lib": aid, "side": "C", "in": tin, "out": tout, _key_of(e): [key_t]}
            if bottom is not None:
                b["bottom"] = bottom
            if src:
                b["src"] = src
            b["why"] = (f"«{top_hit['said']}» @{top_hit['t']:.2f} ~ «{top_hit['kw']}» "
                        f"({top_hit['lang']} {top_hit['score']:.2f})")
            beats.append(b)
            occupied.append((tin - 0.3, tout + 0.3, b))
            last_used[aid] = t0
            break
        else:
            h0 = min(c["hits"], key=lambda x: x["t"])
            skipped.append({"lib": "/".join(by), "t": h0["t"], "said": h0["said"], "why": "; ".join(why_not)})

    # concepts he names that no asset covers yet: the user is asked for a picture (GPT draws one only if they ask)
    covered = {k for h in hits for k in range(h["i"] - 1, h["j"] + 2)}
    cby = {c["id"]: c for c in concepts}
    missing = {}
    for h in match(toks, phrase_index([(c["id"], c.get("triggers")) for c in concepts])):
        if not section_of(h["t"]) or any(k in covered for k in range(h["i"], h["j"] + 1)):
            continue
        c = cby[h["asset"]]
        if any(covers(e, c) for e in entries.values()):
            continue
        m = missing.setdefault(c["id"], {"id": c["id"], "look": c.get("look", ""), "count": 0, "t": h["t"],
                                         "said": h["said"], "prompt": concept_prompt(c)})
        m["count"] += 1
    miss = sorted(missing.values(), key=lambda m: (-m["count"], m["t"]))
    return {"words": str(words), "t_body": t_body, "t_cta": t_cta, "dur": dur, "remix": remix, "hook": hook,
            "asset_bottom": bottom, "beats": beats, "skipped": skipped, "missing": miss, "hits": hits}


def print_plan(p: dict) -> None:
    say(f"plan: {len(p['beats'])} asset beat(s)   (body {p['t_body']} -> {p['t_cta'] or 'end'}, dur {p['dur']})")
    for b in p["beats"]:
        mo = ",".join(f"{k} {v}" for k, v in b.items() if k in ("breathe", "shake", "keys"))
        say(f"  {b['in']:6.2f}-{b['out']:6.2f}  {b['lib']:30s} {mo:18s} {b['why']}")
    for s in p["skipped"]:
        say(f"  skipped {s['t']:6.2f} {s['lib']} «{s['said']}»: {s['why']}")
    for m in p["missing"]:
        say(f"  MISSING {m['id']}: said {m['count']}x, first «{m['said']}» @{m['t']:.2f}  -> ask the user for a picture"
            + ("  (or asset_lib.py fill: GPT draws it, only if they ask)" if m.get("prompt") else ""))


def cmd_plan(a) -> dict:
    p = do_plan(a.words, a.t_body, a.t_cta, a.dur, a.remix, a.hook, _avoid_from(a.avoid), _parse_busy(a.busy),
                a.max, a.src, a.bottom)
    out = Path(a.out) if a.out else Path(a.words).with_name("illus_plan.json")
    out.write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
    print_plan(p)
    say(f"wrote {out}")
    return p


# ------------------------------------------------------------------ generating what's missing (GPT, on request)

def do_fill(plan: dict, max_n: int = 3, workers: int = 3) -> list:
    cby = {c["id"]: c for c in load_concepts()}
    want = [m for m in plan.get("missing", []) if m["id"] in cby]
    no_prompt = [m["id"] for m in want if not concept_prompt(cby[m["id"]])]
    todo = [m for m in want if concept_prompt(cby[m["id"]])][:max_n]
    if no_prompt:
        say(f"no GPT prompt for {', '.join(no_prompt)}: only an uploaded picture can show them")
    if not todo:
        say("nothing for GPT to draw")
        return []

    def one(m):
        c = cby[m["id"]]
        t0 = time.time()
        try:
            res = gpt_assets.generate(c["id"], c["look"], concept_prompt(c), extra_keywords=c.get("triggers"),
                                      on_tick=lambda s, n=c["id"]: print(f"  ... GPT drawing {n} ({int(s)} s)",
                                                                          file=sys.stderr, flush=True))
            return m["id"], True, (f"{', '.join(res.get('library_ids', []))} in {int(time.time() - t0)} s -> "
                                   f"{', '.join(res.get('files', []))}")
        except Exception as exc:  # noqa: BLE001 - report and keep the others going
            return m["id"], False, str(exc)

    say(f"GPT is drawing {len(todo)} picture(s): {', '.join(m['id'] for m in todo)} (1-4 min each)")
    out = []
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(todo)))) as ex:
        for mid, ok, msg in ex.map(one, todo):
            say(f"  {'ok  ' if ok else 'FAIL'} {mid}: {msg}")
            out.append((mid, ok, msg))
    return out


def cmd_fill(a) -> None:
    do_fill(json.loads(Path(a.plan).read_text(encoding="utf-8-sig")), a.max, a.workers)


# ------------------------------------------------------------------ placing into a HyperFrames project

class AssetError(Exception):
    pass


def prep_image(src: Path, dst: Path, mirror: bool = False, palette: bool = False) -> tuple:
    """Trim to the subject, <= 900 px, flip if asked. palette = lock GPT's illustrations onto the house ramp, or
    the ramp of the library folder's brand (finish_asset); the user's own pictures keep their colours. Returns (w, h)."""
    import numpy as np
    from PIL import Image

    if dst.is_file() and dst.stat().st_mtime >= src.stat().st_mtime:
        with Image.open(dst) as im:
            return im.size
    im = Image.open(src).convert("RGBA")
    if mirror:
        im = im.transpose(Image.FLIP_LEFT_RIGHT)
    a = np.asarray(im)[..., 3]
    if (a < 250).mean() < 0.02:
        raise AssetError("no transparent background (ask the user for a PNG/WebP cut-out)")
    ys, xs = np.nonzero(a > 12)
    if not len(xs):
        raise AssetError("the picture is fully transparent")
    if palette:
        import finish_asset
        finish_asset.load_brand(project_dir())          # a brand's ramp when the GPT folder is drawn in one
        arr = np.asarray(im).astype(np.float32)
        rgb, alpha = arr[..., :3], arr[..., 3] / 255.0
        alpha = np.where(alpha >= 0.97, 1.0, np.where(alpha <= 0.02, 0.0, alpha))
        rgb = finish_asset.palette_lock(rgb, alpha, 1.0, False)
        out = np.dstack([np.clip(rgb, 0, 255), np.clip(alpha * 255, 0, 255)]).astype(np.uint8)
        out[out[..., 3] == 0, :3] = 0
        im = Image.fromarray(out, "RGBA")
    pad = 6
    im = im.crop((max(0, xs.min() - pad), max(0, ys.min() - pad),
                  min(im.width, xs.max() + pad + 1), min(im.height, ys.max() + pad + 1)))
    s = 900 / max(im.size)
    if s < 1:
        im = im.convert("RGBa").resize((round(im.width * s), round(im.height * s)), Image.LANCZOS).convert("RGBA")
    dst.parent.mkdir(parents=True, exist_ok=True)
    im.save(dst, optimize=True)
    return im.size


def resolve(beats: list, img_dir: Path, img_prefix: str, bottom=None, remix: bool = False) -> tuple:
    """Prepare each asset's PNG and fill img / w / h / x / top. A beat may carry side (C|L|R), x, bottom and size
    to move or resize it by hand. Returns (resolved beats, problems)."""
    entries = {e["id"]: e for e in load_lib()["assets"]}
    mode = "remix" if remix else "fresh"
    out, problems = [], []
    for b in sorted((b for b in beats if "lib" in b), key=lambda b: b["in"]):
        e = entries.get(b["lib"])
        if not e:
            raise SystemExit(f"{b['lib']} is not in the library ({lib_path()})")
        mirror = bool(b.get("mirror"))
        name = f"lib-{b['lib']}{'-m' if mirror else ''}.png"
        try:
            w0, h0 = prep_image(entry_file(e), img_dir / name, mirror, palette=e.get("source") in ("gpt", "ref"))
        except (AssetError, OSError) as exc:
            problems.append(f"{b['in']:6.2f} {b['lib']}: WARNING {exc}: left out")
            continue
        lay = layout(w0, h0, b.get("side", "C"), b.get("bottom") or bottom or BOTTOM[mode],
                     b.get("size") or BOX[mode], b.get("x"))
        r = {k: v for k, v in b.items() if k not in ("why", "hidden", "warn", "check", "labels", "badge", "mirror")}
        r.update(kind="asset", img=img_prefix + name, w=lay["w"], h=lay["h"], x=lay["x"], top=lay["top"])
        if mirror:
            r["mirror"] = True
        out.append(r)
    return out, problems


def do_place(plan_or_beats, project=None, beats_file=None, out_file=None, img_dir=None,
             img_prefix="assets/img/", bottom=None) -> list:
    data = plan_or_beats
    beats = data["beats"] if isinstance(data, dict) else data
    remix = bool(beats_file) or (isinstance(data, dict) and bool(data.get("remix")))
    if bottom is None and isinstance(data, dict):
        bottom = data.get("asset_bottom")
    if not img_dir:
        if not project:
            raise SystemExit("place needs --project (or --img-dir)")
        img_dir = Path(project) / "assets" / "img"
    spec = None
    if beats_file:
        p = Path(beats_file)
        spec = json.loads(p.read_text(encoding="utf-8-sig")) if p.is_file() else {"beats": []}
    resolved, problems = resolve(beats, Path(img_dir), img_prefix, bottom, remix)
    if beats_file:
        others = [b for b in spec.get("beats", []) if "lib" not in b]
        spec["beats"] = sorted(others + resolved, key=lambda b: b["in"])
        p.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
        say(f"merged {len(resolved)} asset beat(s) into {p}" + (f" ({len(others)} other beats kept)" if others else ""))
    elif out_file:
        Path(out_file).write_text(json.dumps(resolved, ensure_ascii=False, indent=1), encoding="utf-8")
        say(f"wrote {len(resolved)} resolved beat(s) to {out_file}")
    else:
        index = Path(project) / "index.html"
        html = index.read_text(encoding="utf-8-sig")
        m = re.search(r"/\*ILLUS\*/.*?/\*END-ILLUS\*/", html, re.S)
        if not m:
            raise SystemExit(f"{index} has no ILLUS slot. Fresh edits get it from this skill's reference.html "
                             "(new_project.py); for a remix pass --beats <beats.json> instead.")
        body = json.dumps(resolved, ensure_ascii=False, indent=1)
        index.write_text(html[:m.start()] + "/*ILLUS*/" + body + "/*END-ILLUS*/" + html[m.end():], encoding="utf-8")
        say(f"wrote {len(resolved)} asset beat(s) into {index} (ILLUS)")
    for r in resolved:
        say(f"  {r['in']:6.2f}-{r['out']:6.2f} {r['img']:44s} {r['w']}x{r['h']} at x {r['x']}, top {r['top']}")
    for line in problems:
        say("  " + line)
    return resolved


def cmd_place(a) -> None:
    do_place(json.loads(Path(a.plan).read_text(encoding="utf-8-sig")), a.project, a.beats, a.out, a.img_dir,
             a.img_prefix, a.bottom)


def cmd_auto(a) -> None:
    proj = Path(a.project)
    out = Path(a.out) if a.out else proj / ".work" / "illus_plan.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    args = (a.words, a.t_body, a.t_cta, a.dur, a.remix, a.hook, _avoid_from(a.avoid or a.beats),
            _parse_busy(a.busy), a.max, None, a.bottom)
    p = do_plan(*args)
    print_plan(p)
    if p["missing"] and a.generate > 0:
        do_fill(p, a.generate)
        say("re-planning with the new pictures ...")
        p = do_plan(*args)
        print_plan(p)
    out.write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
    say(f"wrote {out}")
    do_place(p, proj, a.beats, None, None, "assets/img/", a.bottom)


# ------------------------------------------------------------------ CLI

def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    lib_help = ("the library.json to use (an upload folder's own library; default: the GPT asset studio's, or "
                "CAMEL_GPT_LIBRARY). Before or after the command.")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--lib", default=argparse.SUPPRESS, help=lib_help)   # SUPPRESS: never overwrites the global one
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lib", help=lib_help)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def cmd(name):
        return sub.add_parser(name, parents=[common])

    g = cmd("index")
    g.add_argument("folder", help="the folder of pictures the user uploaded for this product / project")
    g.set_defaults(fn=cmd_index)
    cmd("sync").set_defaults(fn=cmd_sync)
    g = cmd("tag")
    g.add_argument("ids", nargs="*")
    g.add_argument("--all", action="store_true", help="re-tag assets that already have keywords")
    g.add_argument("--replace", action="store_true", help="replace keywords instead of adding to them")
    g.set_defaults(fn=cmd_tag)
    g = cmd("set")
    g.add_argument("id")
    g.add_argument("file")
    g.add_argument("--replace", action="store_true")
    g.set_defaults(fn=cmd_set)
    g = cmd("setmany")
    g.add_argument("file", help='{"<id>": {"keywords": {...}, "motion": "...", "concept": "...", "subject": "..."}}')
    g.add_argument("--replace", action="store_true")
    g.set_defaults(fn=cmd_setmany)
    cmd("list").set_defaults(fn=cmd_list)
    g = cmd("search")
    g.add_argument("words", nargs="+")
    g.set_defaults(fn=cmd_search)
    g = cmd("match")
    g.add_argument("words")
    g.add_argument("--t0", type=float)
    g.add_argument("--t1", type=float)
    g.set_defaults(fn=cmd_match)
    for name in ("plan", "auto"):
        g = cmd(name)
        g.add_argument("words")
        g.add_argument("--t-body", type=float, required=True, help="hook -> body cut (x)")
        g.add_argument("--t-cta", type=float, help="body -> CTA cut (z); nothing is placed after it")
        g.add_argument("--dur", type=float)
        g.add_argument("--remix", action="store_true", help="body only (already-edited footage)")
        g.add_argument("--hook", action="store_true", help="also allow assets in the hook (symptom-led hooks)")
        g.add_argument("--avoid", help="beats.json whose other beats keep their time")
        g.add_argument("--busy", nargs="*", help="windows with no asset, e.g. 12.0-15.5 (a burned-in card, B-roll)")
        g.add_argument("--max", type=int, help="at most N assets (strongest hits)")
        g.add_argument("--bottom", type=int, help="the assets' bottom edge in px (default 1330 fresh, 1260 remix)")
        g.add_argument("--matte", help=argparse.SUPPRESS)   # accepted and ignored: callers from before Nov 26 2026
        g.add_argument("--out")
        if name == "plan":
            g.add_argument("--src", help="tag beats with a source key (multi-source remixes + map_beats.py)")
            g.set_defaults(fn=cmd_plan)
        else:
            g.add_argument("--project", required=True)
            g.add_argument("--beats", help="remix beats.json to merge into (else index.html ILLUS)")
            g.add_argument("--generate", type=int, default=0,
                           help="max pictures GPT may draw for what is MISSING (default 0: the user uploads them)")
            g.set_defaults(fn=cmd_auto)
    g = cmd("fill")
    g.add_argument("plan")
    g.add_argument("--max", type=int, default=3)
    g.add_argument("--workers", type=int, default=3)
    g.set_defaults(fn=cmd_fill)
    g = cmd("place")
    g.add_argument("plan")
    g.add_argument("--project")
    g.add_argument("--beats", help="remix beats.json to merge into")
    g.add_argument("--out", help="just write the resolved beats here")
    g.add_argument("--img-dir", help="where the PNGs go (default <project>/assets/img)")
    g.add_argument("--img-prefix", default="assets/img/")
    g.add_argument("--bottom", type=int, help="the assets' bottom edge in px (default: the plan's, else 1330 / 1260)")
    g.add_argument("--matte", help=argparse.SUPPRESS)       # accepted and ignored: callers from before Nov 26 2026
    g.add_argument("--avoid", help=argparse.SUPPRESS)       # (the assets no longer move to a free side)
    g.set_defaults(fn=cmd_place)
    a = ap.parse_args()
    if a.lib:
        set_lib(a.lib)
    a.fn(a)


if __name__ == "__main__":
    main()
