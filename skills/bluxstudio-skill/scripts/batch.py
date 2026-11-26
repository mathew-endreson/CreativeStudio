#!/usr/bin/env python3
"""One code path for a remix batch: the finished ads of one product -> new ads (references/remix.md).

    python batch.py <command> <src_dir> [...]          src_dir = _hyperframes/<slug>_src (a path, or just the slug)

    prepare    <src_dir> [keys]     48 kHz copies <k>.mp4 of the sources in product.json; phase check + dual-mono
                                    fix; 1-frame black-glitch scan + freezeframes patch; report -> work/prepare.json
    transcribe <src_dir> [keys]     one Whisper load for all sources -> work/<k>_words.json (product whisper_prompt)
    scan       <src_dir> [keys]     hook-flash candidates (first ~10 s), the editor's own cuts, black frames,
                                    silences >= 0.12 s, burned-in title boxes, a 1 fps contact sheet
                                    -> work/scan_<k>.json, work/sheet_<k>.jpg (per-frame numbers: curves_<k>.json)
    frames     <src_dir> <k> 197-204 [...]   those frames' luma / difference and a strip picture of them
                                    -> work/look/<k>_f197-204.jpg  (--width 540 --crop x:y:w:h to read a caption)
    cut        <src_dir> [ids]      NOT NEEDED since Nov 26 2026: the assets sit in front of the speaker, so a remix
                                    has no speaker cutout. --force still cuts each body range out once ->
                                    cut/<k>_cutout.webm + cut/manifest.json; --plan lists what that would take
    cuts       <src_dir> [ids]      every cut of a mix against the scan: in a silence, on an editor's cut or at a
                                    flash? Also names mixes that repeat another's segments. Nothing runs
    build      <src_dir> [ids]      per mix in mixes.json: join spec, picture join, project folder,
                                    beats (map_beats + hook beats), asset_lib place, remix_broll -> index.html
    check      <src_dir> [ids]      lint + snapshot sheets at every beat's key moment -> <project>/.work/snaps
    render     <src_dir> [ids]      hyperframes render + finalize (-15 LUFS) into the product's Ads folder,
                                    the 5-frame strips around every join, a report -> .work/final_report.json
    import     <src_dir>            convert a batch made by hand (build_mixes.py, or j_*.json / ja_*.json join
                                    specs) into product.json / mixes.json / cut/manifest.json. Runs nothing.
    verify     <src_dir> [ids]      prove batch.py reproduces the mixes that exist: join specs and beats against
                                    the files on disk; --rebuild <new id> also rebuilds ONE mix under a new id
                                    and compares the joins frame by frame
    status     <src_dir>            what exists: sources, cutouts, mixes (built / rendered), the next mix number
    match-ads  <src_dir>            ads renamed in the Ads folder -> their mix (length +-1 frame and first frame),
                                    saved in mixes.json as ad_file

Files in <src_dir> (the layout of _hyperframes/ghaba_src):
    product.json      {slug, name, name_ar, whisper_prompt, product_dir, ads_dir, id_prefix, sources: {k: {file,
                       copy?, tag?, label?}}, beats_file, project_assets: [{from, to}], place, alpha_all,
                       asset_lib (the upload folder's library.json, relative to <src_dir>), asset_bottom (px), ...}
    mixes.json        {id: {name, file_name, segs: [{src, a0, a1, v0, v1, text}], body: [], cta, hook_beats}}
                      segs: a0/a1 = the span (audio + length), v0/v1 = a clean picture range cloned to fill it;
                      body = segment indices that carry B-roll; cta = index of the CTA segment (may also be in
                      body when body and CTA are one take); hook_beats = segment 0 is a hook lifted from a body
                      and keeps its beats; locked = imported / finished, never rebuilt without --force
    beats_<slug>_src.json   the B-roll in SOURCE time (a mix may name its own with "beats_file")
    cut/manifest.json {k: [{file, f0, f1}]}   cutout frame 0 == source frame f0
    analysis.json, proposals.json             written by the judgment steps (hook / body / CTA, pairings)
    <k>.mp4, work/, cut/, joins/              copies, transcripts + scans, cutouts, join specs + joins

Everything is 30 fps, 1080x1920, 48 kHz (multi_join.py assumes it); prepare converts what is not.
Nothing here deletes or overwrites a source, an imported project or a finished ad.
"""
import argparse
import contextlib
import hashlib
import importlib.util
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time

Path = pathlib.Path
SKILL = Path(__file__).resolve().parents[1]
S = SKILL / "scripts"
ROOT = Path(__file__).resolve().parents[4]
HF = ROOT / "_hyperframes"
F = 30
CUT_FPS = 2.3                 # remove-background --quality best at 1080x1920 on this CPU (measured Nov 2026)
HOOK_WINDOW = 10.0            # a hook can run past 6 s: scan ~10 s for its flash, not 3-5 s
SILENCE = 0.12                # shortest silence worth cutting in
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
fr = lambda t: int(round(t * F))
tt = lambda n: round(n / F, 4)

for _s in (sys.stdout, sys.stderr):
    with contextlib.suppress(Exception):
        _s.reconfigure(encoding="utf-8", errors="replace")
if str(S) not in sys.path:
    sys.path.insert(0, str(S))


# ------------------------------------------------------------------ small helpers

def say(*parts):
    print(*parts, flush=True)


def jload(p):
    return json.loads(Path(p).read_text(encoding="utf-8-sig"))


def jdump(p, obj):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)


def run(cmd, cwd=None, quiet=False):
    cmd = [str(c) for c in cmd]
    say("  $", " ".join(Path(c).name if os.sep in c else c for c in cmd[:6]), "...")
    subprocess.run(cmd, check=True, cwd=cwd, env=ENV, stdout=subprocess.DEVNULL if quiet else None)


def stream(cmd, cwd=None, log=None):
    """Run a long tool, echo its output (progress lines at most every 2 s) and keep all of it in `log`."""
    cmd = [str(c) for c in cmd]
    say("  $", " ".join(Path(c).name if os.sep in c else c for c in cmd[:7]), "...")
    lf = open(log, "w", encoding="utf-8") if log else None
    last = 0.0
    try:
        with subprocess.Popen(cmd, cwd=cwd, env=ENV, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                              encoding="utf-8", errors="replace") as p:
            for line in p.stdout:
                line = line.rstrip()
                if not line:
                    continue
                if lf:
                    lf.write(line + "\n")
                    lf.flush()
                if re.search(r"\d\s*%|\b\d+\s*/\s*\d+\b", line):          # a progress line
                    if time.time() - last < 2.0:
                        continue
                    last = time.time()
                say("   ", line)
            return p.wait()
    finally:
        if lf:
            lf.close()


def hyperframes():
    """The local HyperFrames CLI (what `npx hyperframes` resolves to from inside _hyperframes/)."""
    js = HF / "node_modules" / "hyperframes" / "bin" / "hyperframes.mjs"
    node = shutil.which("node")
    if js.exists() and node:
        return [node, str(js)]
    npx = shutil.which("npx.cmd") or shutil.which("npx")
    if not npx:
        raise SystemExit("node / npx not found: HyperFrames needs Node.js on PATH")
    return [npx, "hyperframes"]


def src_dir(arg):
    """A batch folder from its slug (ghaba), its name (ghaba_src) or a path. The slug is tried first: on
    Windows `ghaba` would otherwise find the product folder `Ghaba` beside _hyperframes."""
    for c in (HF / f"{arg}_src", HF / arg, Path(arg)):
        if c.is_dir() and (c.name.endswith("_src") or (c / "product.json").exists()):
            return c.resolve()
    raise SystemExit(f"no batch folder: {arg} (expected _hyperframes/<slug>_src)")


def load(D, mixes=True):
    pj = D / "product.json"
    if not pj.exists():
        raise SystemExit(f"{pj} is missing: write it (see batch.py's docstring) or run `batch.py import {D.name}`")
    P = jload(pj)
    M = jload(D / "mixes.json") if mixes and (D / "mixes.json").exists() else {}
    return P, M


def copy_path(D, P, k):
    return D / (P["sources"][k].get("copy") or f"{k}.mp4")


def orig_path(P, k):
    f = P["sources"][k].get("file")
    if not f:
        return None
    f = Path(f)
    return f if f.is_absolute() else (Path(P["product_dir"]) / f if P.get("product_dir") else None)


def keys_of(P, given):
    bad = [k for k in given if k not in P["sources"]]
    if bad:
        raise SystemExit(f"not in product.json sources: {bad}")
    return list(given) or [k for k, s in P["sources"].items() if s.get("tag", "finished_ad") in ("finished_ad", "source")]


def ids_of(M, given):
    bad = [i for i in given if i not in M]
    if bad:
        raise SystemExit(f"not in mixes.json: {bad}")
    return list(given) or list(M)


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-count_packets", "-show_entries",
                          "stream=codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate,sample_rate,channels,"
                          "nb_read_packets:format=duration", "-of", "json", str(path)],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    if out.returncode != 0:
        raise SystemExit(f"ffprobe failed on {path}: {out.stderr.strip()[:300]}")
    d = json.loads(out.stdout)

    def rate(x):
        n, _, den = (x or "0/1").partition("/")
        return float(n) / float(den or 1) if float(den or 1) else 0.0

    info = {"duration": round(float(d["format"]["duration"]), 4)}
    v = next((s for s in d["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in d["streams"] if s["codec_type"] == "audio"), None)
    if v:
        info.update(w=v["width"], h=v["height"], fps=round(rate(v["r_frame_rate"]), 3),
                    avg_fps=round(rate(v["avg_frame_rate"]), 3), frames=int(v.get("nb_read_packets") or 0),
                    vcodec=v["codec_name"])
    if a:
        info.update(sr=int(a["sample_rate"]), ch=int(a["channels"]), acodec=a["codec_name"])
    return info


def frames_of(D, P, k):
    rep = D / "work" / "prepare.json"
    if rep.exists():
        n = jload(rep).get(k, {}).get("frames")
        if n:
            return n
    return probe(copy_path(D, P, k))["frames"]


def luma_diff(path):
    """Per-frame mean luma and mean frame difference at 108x192 (scan.py's measure)."""
    import numpy as np
    W, H = 108, 192
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vf", f"scale={W}:{H},format=gray",
                        "-f", "rawvideo", "-"], capture_output=True)
    a = np.frombuffer(p.stdout, np.uint8).reshape(-1, H * W)
    luma = a.mean(axis=1)
    diff = np.zeros(len(a))
    for i in range(1, len(a), 512):
        j = min(len(a), i + 512)
        diff[i:j] = np.abs(a[i:j].astype(np.int16) - a[i - 1:j - 1]).mean(axis=1)
    return luma, diff


def runs_of(flags, gap=0):
    """[(first, last)] index runs where flags is true, joining runs at most `gap` apart."""
    out = []
    for i, f in enumerate(flags):
        if f:
            if out and i - out[-1][1] <= gap + 1:
                out[-1][1] = i
            else:
                out.append([i, i])
    return out


# ------------------------------------------------------------------ prepare

def phase(path):
    """Level of each channel and of their mono sum. Phase-inverted stereo: each channel ~-15 dB, L+R ~-51 dB."""
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "2", "-ar", "16000", "-f", "s16le",
                          "-"], capture_output=True).stdout
    x = np.frombuffer(raw, np.int16).reshape(-1, 2).astype(np.float32) / 32768
    if not len(x):
        return None
    db = lambda v: round(float(20 * np.log10(np.sqrt(np.mean(v ** 2)) + 1e-9)), 1)
    l, r, m = db(x[:, 0]), db(x[:, 1]), db((x[:, 0] + x[:, 1]) / 2)
    return {"l_db": l, "r_db": r, "mono_db": m, "inverted": bool(m < max(l, r) - 20)}


def black_glitches(luma):
    """1-2 frame black runs (luma < 8) between normal frames: a bad export, not a fade."""
    out = []
    for i, j in runs_of(luma < 8):
        if 0 < i and j < len(luma) - 1 and j - i < 2 and luma[i - 1] >= 20 and luma[j + 1] >= 20:
            out.append([int(i), int(j)])
    return out


def make_copy(src, dst, info, inverted, glitches):
    """<k>.mp4: 30 fps 1080x1920 (video copied when it already is), 48 kHz stereo AAC, dual-mono when the
    channels cancel, black glitches frozen over. Returns True when the picture was re-encoded."""
    chain, last, n = [], "0:v", 0
    for i, j in glitches:
        chain.append(f"[{last}]split=2[m{n}][r{n}];[m{n}][r{n}]freezeframes=first={i}:last={j}:replace={i - 1}[g{n}]")
        last, n = f"g{n}", n + 1
    vf = []
    if (info["w"], info["h"]) != (1080, 1920):
        vf.append("scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920")
    if abs(info["fps"] - F) > 0.02 or abs(info["avg_fps"] - info["fps"]) > 0.02:
        vf.append(f"fps={F}")
    reenc = bool(chain or vf)
    tmp = dst.with_name(dst.stem + ".part.mp4")
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(src)]
    if reenc:
        chain.append(f"[{last}]{','.join(vf + ['format=yuv420p'])}[v]")
        cmd += ["-filter_complex", ";".join(chain), "-map", "[v]", "-map", "0:a:0",
                "-c:v", "libx264", "-preset", "slow", "-crf", "14", "-g", str(F), "-r", str(F)]
    else:
        cmd += ["-map", "0:v:0", "-map", "0:a:0", "-c:v", "copy"]
    if inverted:
        cmd += ["-af", "pan=stereo|c0=c0|c1=c0"]
    cmd += ["-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-ac", "2", "-movflags", "+faststart", str(tmp)]
    subprocess.run(cmd, check=True)
    os.replace(tmp, dst)
    return reenc


def cmd_prepare(a):
    D = src_dir(a.src_dir)
    P, _ = load(D, mixes=False)
    (D / "work").mkdir(exist_ok=True)
    rep_path = D / "work" / "prepare.json"
    report = jload(rep_path) if rep_path.exists() else {}
    for k in keys_of(P, a.keys):
        src, dst = orig_path(P, k), copy_path(D, P, k)
        have_src = bool(src and src.exists())
        if not have_src and not dst.exists():
            raise SystemExit(f"{k}: source not found ({src}) and no copy {dst.name}")
        r = {"file": str(src) if src else None, "copy": dst.name, "issues": []}
        made = False
        if not dst.exists():
            info = probe(src)
            if "sr" not in info:
                raise SystemExit(f"{k}: {src.name} has no audio stream")
            ph = phase(src)
            luma, _ = luma_diff(src)
            gl = black_glitches(luma)
            say(f"[{k}] {src.name}: {info['w']}x{info['h']} {info['fps']} fps, {info['sr']} Hz -> {dst.name}")
            r["reencoded_video"] = make_copy(src, dst, info, bool(ph and ph["inverted"]), gl)
            r.update(source=info, source_phase=ph, black_glitches=gl, patched=bool(gl))
            made = True
        elif have_src:
            r.update(source=probe(src), source_phase=phase(src))
        info = probe(dst)
        ph = phase(dst)
        luma, _ = luma_diff(dst)
        r.update({k2: info.get(k2) for k2 in ("w", "h", "fps", "frames", "duration", "sr", "ch")})
        r.update(phase=ph, status="made" if made else "exists", black_left=black_glitches(luma),
                 black_frames=[[int(i), int(j)] for i, j in runs_of(luma < 8)])
        sp = r.get("source_phase")
        if sp and sp["inverted"]:
            r["issues"].append(f"the original is phase-inverted (channels {sp['l_db']} / {sp['r_db']} dB, mono sum "
                               f"{sp['mono_db']} dB): the copy is dual-mono; tell the user the originals have it")
        if ph and ph["inverted"]:
            r["issues"].append("the COPY is still phase-inverted: remake it (delete nothing: write a new copy name)")
        if r.get("black_glitches"):
            r["issues"].append(f"1-frame black glitch at frames {r['black_glitches']} (bad export): frozen over in the copy")
        if r["black_left"]:
            r["issues"].append(f"black glitch still in the copy at frames {r['black_left']}")
        if (info.get("w"), info.get("h")) != (1080, 1920) or abs(info.get("fps", 0) - F) > 0.02 or info.get("sr") != 48000:
            r["issues"].append(f"the copy is {info.get('w')}x{info.get('h')} {info.get('fps')} fps {info.get('sr')} Hz, "
                               "not 1080x1920 30 fps 48 kHz")
        report[k] = r
        jdump(rep_path, report)
        say(f"[{k}] {r['status']}: {info['frames']} frames, {info['duration']} s, mono sum {ph['mono_db'] if ph else '-'} dB"
            + "".join(f"\n     ! {x}" for x in r["issues"]))
    say(f"report -> {rep_path}")


# ------------------------------------------------------------------ transcribe

def cmd_transcribe(a):
    import wave
    import numpy as np
    D = src_dir(a.src_dir)
    P, _ = load(D, mixes=False)
    (D / "work").mkdir(exist_ok=True)
    todo = [k for k in keys_of(P, a.keys) if a.force or not (D / "work" / f"{k}_words.json").exists()]
    if not todo:
        say("all transcripts exist (--force to redo)")
        return
    import transcribe as T
    prompt = P.get("whisper_prompt") or T.PROMPT
    model = T.load_model()
    for k in todo:
        wav = D / "work" / f"{k}.wav"
        if not wav.exists():
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(copy_path(D, P, k)), "-vn", "-ac", "1", "-ar",
                            "16000", str(wav)], check=True)
        with wave.open(str(wav), "rb") as wf:
            x = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
        segs = T.words_of(model, x, 0.0, prompt)
        jdump(D / "work" / f"{k}_words.json", segs)
        say(f"===== {k}")
        T.show(segs)
        sys.stdout.flush()


def seg_text(D, k, a0, a1):
    """What is said in [a0, a1) of source k, from its transcript (words by their midpoint)."""
    p = D / "work" / f"{k}_words.json"
    if not p.exists():
        return ""
    return " ".join(w["w"] for s in jload(p) for w in s["words"] if a0 <= (w["s"] + w["e"]) / 2 < a1)


# ------------------------------------------------------------------ scan

def silences(path, min_len=SILENCE):
    """20 ms RMS profile and the silences in it. These ads carry music under the voice, so the floor is
    relative: quiet = more than 14 dB under the speech level (90th percentile), never above -30 dBFS."""
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", "48000", "-f", "s16le",
                          "-"], capture_output=True).stdout
    x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    n = 960
    m = len(x) // n
    db = 20 * np.log10(np.sqrt((x[:m * n].reshape(m, n) ** 2).mean(axis=1)) + 1e-9)
    thr = min(-30.0, float(np.percentile(db, 90)) - 14.0)
    out = []
    for i, j in runs_of(db < thr):
        if (j - i + 1) * 0.02 >= min_len - 1e-9:
            q = int(i + np.argmin(db[i:j + 1]))
            out.append({"a": round(i * 0.02, 2), "b": round((j + 1) * 0.02, 2), "dur": round((j - i + 1) * 0.02, 2),
                        "quietest": round(q * 0.02 + 0.01, 2), "db": round(float(db[i:j + 1].mean()), 1)})
    return db, round(thr, 1), out


def cmd_scan(a):
    import numpy as np
    import remix_title_scan as TS
    D = src_dir(a.src_dir)
    P, _ = load(D, mixes=False)
    (D / "work").mkdir(exist_ok=True)
    kinds = P.get("title_kinds") or list(TS.KINDS)
    for k in keys_of(P, a.keys):
        out, curves = D / "work" / f"scan_{k}.json", D / "work" / f"curves_{k}.json"
        if out.exists() and curves.exists() and not a.force:
            say(f"[{k}] scan exists (--force to redo)")
            continue
        path = copy_path(D, P, k)
        luma, diff = luma_diff(path)
        n, med = len(luma), float(np.median(luma))
        bright, cut, black = luma > med + 25, diff > 18, luma < 8
        flashes, cuts = [], []
        for i, j in runs_of(bright | cut, gap=2):
            if bright[i:j + 1].any():
                pk = int(i + np.argmax(luma[i:j + 1]))
                flashes.append({"f0": i, "f1": j, "t0": tt(i), "t1": tt(j + 1), "peak_f": pk,
                                "peak_luma": round(float(luma[pk]), 1), "rise": round(float(luma[pk] - med), 1),
                                "peak_diff": round(float(diff[i:j + 1].max()), 1),
                                "kind": "flash" if j - i < 15 else "bright_section",
                                "white": bool(luma[pk] >= 200), "in_hook_window": bool(i / F <= HOOK_WINDOW)})
            else:
                cuts += [{"f": int(f), "t": tt(int(f)), "diff": round(float(diff[f]), 1)}
                         for f in range(i, j + 1) if cut[f]]
        db, thr, sil = silences(path)
        titles = TS.scan_titles(path, kinds)
        cols = 10
        sheet = D / "work" / f"sheet_{k}.jpg"
        secs = max(1, int(np.ceil(n / F)))
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(path), "-vf",
                        f"fps=1,scale=180:320,tile={cols}x{int(np.ceil(secs / cols))}", "-frames:v", "1", "-q:v", "3",
                        str(sheet)], check=True)
        res = {"key": k, "file": path.name, "fps": F, "frames": n, "duration": tt(n), "median_luma": round(med, 1),
               "hook_window": HOOK_WINDOW,
               "flashes": flashes, "cuts": cuts,
               "black": [{"f0": int(i), "f1": int(j), "t0": tt(i), "t1": tt(j + 1)} for i, j in runs_of(black)],
               "silences": sil, "silence_thr_db": thr, "titles": titles,
               "sheet": {"file": f"work/{sheet.name}", "fps": 1, "cols": cols, "tile": [180, 320], "count": secs},
               "curves": f"work/{curves.name}"}
        jdump(out, res)
        # the per-frame numbers, for a waveform or a closer look at one frame: not for reading whole
        part = curves.with_name(curves.name + ".tmp")
        part.write_text(json.dumps({"fps": F, "luma": [round(float(v), 1) for v in luma],
                                    "diff": [round(float(v), 1) for v in diff],
                                    "rms_db": [round(float(v), 1) for v in db], "rms_hop": 0.02}), encoding="utf-8")
        os.replace(part, curves)
        say(f"===== {k}  frames {n}  median luma {med:.1f}  silence floor {thr} dB")
        hook = [f for f in flashes if f["in_hook_window"] and f["kind"] == "flash"]
        say("  hook-flash candidates (first %.0f s): " % HOOK_WINDOW + (", ".join(
            f"{f['t0']:.3f}s f{f['f0']}-{f['f1']} luma {f['peak_luma']:.0f}{' WHITE' if f['white'] else ''}" for f in hook)
            or "none: look at the cuts and the transcript"))
        for f in flashes:
            if f not in hook:
                say(f"  {f['kind']} {f['t0']:.3f}-{f['t1']:.3f}s f{f['f0']}-{f['f1']} luma {f['peak_luma']:.0f}")
        say("  cuts: " + (" ".join(f"{c['t']:.3f}(f{c['f']})" for c in cuts) or "none"))
        if res["black"]:
            say("  black: " + " ".join(f"f{b['f0']}-{b['f1']}" for b in res["black"]))
        say(f"  silences >= {SILENCE} s: " + " ".join(f"{s['a']:.2f}-{s['b']:.2f}" for s in sil))
        for t in titles:
            say(f"  title {t[6]:6s} {t[0]:6.2f}-{t[1]:6.2f}  x {t[2]}-{t[4]}  y {t[3]}-{t[5]}")
        say(f"  sheet -> {sheet}")


def cmd_frames(a):
    """Look at chosen frames of a source: their luma / frame difference, and one strip picture per range
    (frame number under each tile). For a flash, a hold, a dissolve ghost, a burned-in caption."""
    D = src_dir(a.src_dir)
    P, _ = load(D, mixes=False)
    if a.key not in P["sources"]:
        raise SystemExit(f"not in product.json sources: {a.key}")
    path = copy_path(D, P, a.key)
    cur = D / "work" / f"curves_{a.key}.json"
    c = jload(cur) if cur.exists() else None
    look = D / "work" / "look"
    look.mkdir(parents=True, exist_ok=True)
    crop = ""
    if a.crop:
        if not re.fullmatch(r"\d+:\d+:\d+:\d+", a.crop):
            raise SystemExit(f"--crop wants x:y:w:h in pixels of the 1080x1920 frame, got {a.crop}")
        x, y, w, h = a.crop.split(":")
        crop = f"crop={w}:{h}:{x}:{y},"
    font = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "arial.ttf"
    # the frame number is drawn before select, while n is still the source frame number
    label = (f"drawtext=fontfile='{font.as_posix().replace(':', chr(92) + ':')}':text='%{{n}}':x=8:y=h-th-8:"
             "fontsize=h/14:fontcolor=white:box=1:boxcolor=black@0.65:boxborderw=6," if font.exists() else "")
    for r in a.ranges:
        m = re.fullmatch(r"(\d+)(?:-(\d+))?", r)
        if not m:
            raise SystemExit(f"ranges are frame numbers: 197-204 (or one frame: 199), got {r}")
        f0 = int(m.group(1))
        f1 = int(m.group(2) or f0)
        nums = list(range(f0, f1 + 1, a.every))[:48]
        if c:
            say(f"{a.key} " + " ".join(f"f{i}({i / F:.3f}s):{c['luma'][i]:.0f}/{c['diff'][i]:.0f}" for i in nums
                                      if i < len(c["luma"])) + "   (luma/diff)")
        cols = min(len(nums), 8 if a.width > 300 else 12)
        rows = -(-len(nums) // cols)
        out = look / f"{a.key}_f{f0}-{f1}{'_crop' if a.crop else ''}.jpg"
        sel = "+".join(f"eq(n\\,{i})" for i in nums)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(path), "-vf",
                        f"{crop}{label}select='{sel}',scale={a.width}:-2,tile={cols}x{rows}", "-fps_mode", "passthrough",
                        "-frames:v", "1", "-q:v", "3", str(out)], check=True)
        say(f"  {len(nums)} frames (number in each tile's corner), {cols} per row, from f{nums[0]} -> {out}")


# ------------------------------------------------------------------ cutouts

def manifest(D):
    p = D / "cut" / "manifest.json"
    return jload(p) if p.exists() else {}


def merge(iv, gap=0):
    out = []
    for a, b in sorted(iv):
        if out and a <= out[-1][1] + gap:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def subtract(iv, cov):
    out = []
    for a, b in iv:
        parts = [[a, b]]
        for c0, c1 in cov:
            parts = [q for x, y in parts for q in ([x, min(y, c0)], [max(x, c1), y]) if q[0] < q[1]]
        out += parts
    return merge(out)


def gfx_of(m, P):
    return set(m.get("body") or []) | ({0} if m.get("hook_beats") else set())


def seg_frames(s):
    A0, A1 = fr(s["a0"]), fr(s["a1"])
    V0 = fr(s["v0"]) if s.get("v0") is not None else A0
    V1 = fr(s["v1"]) if s.get("v1") is not None else A1
    return A0, A1, V0, V1


def load_beats(D, P, m):
    """(the mix's source-time beats, whether the file exists yet)."""
    bp = beats_path(D, P, m)
    return (jload(bp), True) if bp.exists() else ({"beats": [], "sfx": []}, False)


def seg_has_beats(src_beats, s):
    """Would map_beats keep a beat in this segment? (0.20 s inside, 0.25 s before its end)"""
    return any(b["src"] == s["src"] and b["in"] >= s["a0"] + 0.20 - 1e-3 and b["out"] <= s["a1"] - 0.25 + 1e-3
               for b in src_beats["beats"])


def plan_cuts(D, P, M, ids=None, exact=False, extra=None, all_gfx=False):
    """Source frame ranges that the mixes' graphic segments need and no cutout covers yet. Once the beats are
    written, only segments that really carry a beat count (a body line with no graphic needs no cutout); before
    that (or with all_gfx: a proposal whose graphics are not written yet), every body segment does. Unless
    `exact`, a range inside a source's body (analysis.json: body_start -> cta_start) grows to that whole body,
    so it is cut once."""
    man = manifest(D)
    need = {}
    for mid in ids_of(M, ids or []):
        m = M[mid]
        src_beats, known = load_beats(D, P, m)
        for i in sorted(gfx_of(m, P)):
            s = m["segs"][i]
            if known and not all_gfx and not seg_has_beats(src_beats, s):
                continue
            _, _, V0, V1 = seg_frames(s)
            need.setdefault(s["src"], []).append([V0, V1])
    for k, f0, f1 in extra or []:
        need.setdefault(k, []).append([f0, f1])
    ana = jload(D / "analysis.json").get("sources", {}) if (D / "analysis.json").exists() else {}
    plan = []
    for k, iv in need.items():
        cov = [[r["f0"], r["f1"]] for r in man.get(k, [])]
        miss = subtract(merge(iv), cov)
        if miss and not exact and ana.get(k, {}).get("body_start") is not None:
            total = frames_of(D, P, k)
            b0 = fr(ana[k]["body_start"])
            b1 = fr(ana[k]["cta_start"]) if ana[k].get("cta_start") is not None else total
            miss = subtract(merge([[b0, b1] if b0 <= x and y <= b1 else [x, y] for x, y in miss]), cov)
        for f0, f1 in merge(miss, gap=2 * F):
            for x, y in subtract([[f0, f1]], cov):
                plan.append({"src": k, "f0": x, "f1": y, "frames": y - x, "seconds": tt(y - x),
                             "eta_s": round((y - x) / CUT_FPS)})
    return plan


def ensure_matte_model():
    home = Path.home()
    src = home / ".rembg" / "models" / "u2net_human_seg" / "u2net_human_seg.onnx"
    dst = home / ".cache" / "hyperframes" / "background-removal" / "models" / "u2net_human_seg.onnx"
    if not dst.exists() and src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def cmd_cut(a):
    D = src_dir(a.src_dir)
    P, M = load(D)
    extra = []
    for r in a.range or []:
        m = re.fullmatch(r"(\w+):(\d+)-(\d+)", r)
        if not m:
            raise SystemExit(f"--range wants <key>:<first frame>-<end frame>, got {r}")
        extra.append((m.group(1), int(m.group(2)), int(m.group(3))))
    plan = plan_cuts(D, P, M, a.ids, a.exact, extra)
    if not a.plan and not a.force:
        # succeeds without cutting, so a pipeline that still runs `cut` before `build` (BluxTech Studio) keeps going
        say("nothing to cut: remixes no longer need a speaker cutout, the assets sit in front of him (Nov 26 2026). "
            "`build` runs without one. --force cuts anyway, --plan shows what it would take.")
        return
    if a.plan:
        say(json.dumps({"fps": CUT_FPS, "ranges": plan, "eta_s": sum(p["eta_s"] for p in plan)}, indent=1))
        return
    if not plan:
        say("every range these mixes need is already cut out")
        return
    cutd = D / "cut"
    cutd.mkdir(exist_ok=True)
    ensure_matte_model()
    hf = hyperframes()
    for p in plan:
        k, f0, f1 = p["src"], p["f0"], p["f1"]
        man = manifest(D)
        stem = k if not (cutd / f"{k}_cutout.webm").exists() else f"{k}_f{f0}"
        body, out = cutd / f"{stem}_body.mp4", cutd / f"{stem}_cutout.webm"
        if out.exists():
            raise SystemExit(f"{out} exists but is not in cut/manifest.json: add it there or move it away")
        if not body.exists():
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(copy_path(D, P, k)), "-vf",
                            f"trim=start_frame={f0}:end_frame={f1},setpts=PTS-STARTPTS", "-an", "-c:v", "libx264",
                            "-preset", "fast", "-crf", "12", "-g", str(F), "-pix_fmt", "yuv420p", str(body)], check=True)
        tmp = cutd / f"{stem}_cutout.part.webm"
        t0 = time.time()
        say(f"[{k}] remove-background frames {f0}-{f1} ({f1 - f0} frames, about {p['eta_s'] // 60} min {p['eta_s'] % 60} s)")
        code = stream([*hf, "remove-background", body, "-o", tmp, "--quality", "best"], cwd=HF,
                      log=cutd / f"{stem}_cutout.log")
        secs = time.time() - t0
        if code != 0 or not tmp.exists():
            raise SystemExit(f"[{k}] remove-background failed (exit {code}); see {cutd / (stem + '_cutout.log')}")
        got = probe(tmp)["frames"]
        if got != f1 - f0:
            raise SystemExit(f"[{k}] the cutout has {got} frames, expected {f1 - f0}: kept as {tmp.name}, not used")
        os.replace(tmp, out)
        man.setdefault(k, []).append({"file": f"cut/{out.name}", "f0": f0, "f1": f1, "secs": round(secs),
                                      "fps": round((f1 - f0) / secs, 2)})
        man[k].sort(key=lambda r: r["f0"])
        jdump(cutd / "manifest.json", man)
        say(f"[{k}] done in {int(secs)} s ({(f1 - f0) / secs:.2f} fps) -> {out.name}")
    say("ALL CUTOUTS DONE")


# ------------------------------------------------------------------ build

def blank(D):
    p = D / "cut" / "blank.webm"
    if not p.exists():
        p.parent.mkdir(exist_ok=True)
        run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
             f"color=c=black@0.0:s=1080x1920:r={F}:d=60,format=yuva420p", "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p",
             "-b:v", "0", "-crf", "40", "-g", str(F), "-auto-alt-ref", "0", "-row-mt", "1", p])
    return p


def cover(ranges, V0, V1):
    """The cutouts that show source frames V0..V1 back to back: [(range, first, end)], or None if there is a hole."""
    pieces, at = [], V0
    while at < V1:
        hit = [r for r in ranges if r["f0"] <= at < r["f1"]]
        if not hit:
            return None
        r = max(hit, key=lambda r: r["f1"])
        end = min(V1, r["f1"])
        pieces.append((r, at, end))
        at = end
    return pieces


def specs(D, P, mid, m, man=None, make_blank=True):
    """(picture + audio join spec, speaker-cutout join spec, warnings) for multi_join.py.
    Graphic segments (body, a lifted hook) take their cutout, shifted to the cutout's own frame 0; the rest is a
    transparent blank, so hooks and CTAs never need cutting out."""
    man = manifest(D) if man is None else man
    src_beats, _ = load_beats(D, P, m)
    used = list(dict.fromkeys(s["src"] for s in m["segs"]))
    main = {"sources": {k: str(copy_path(D, P, k)) for k in used}, "segments": []}
    bl = blank(D) if make_blank else D / "cut" / "blank.webm"
    alpha = {"sources": {"blank": str(bl)}, "segments": []}
    gfx, warns = gfx_of(m, P), []
    for i, s in enumerate(m["segs"]):
        src = s["src"]
        main["segments"].append({"src": src, "a0": s["a0"], "a1": s["a1"], "v0": s.get("v0"), "v1": s.get("v1")})
        A0, A1, V0, V1 = seg_frames(s)
        pieces = cover(man.get(src, []), V0, V1) if (i in gfx or P.get("alpha_all")) else None
        if pieces:
            for n, (r, x, y) in enumerate(pieces):
                first, last = n == 0, n == len(pieces) - 1
                ck = f"{src}c" + ("" if man[src].index(r) == 0 else str(man[src].index(r)))
                alpha["sources"][ck] = str(D / r["file"])
                o = r["f0"]
                alpha["segments"].append({"src": ck, "a0": tt((A0 if first else x) - o), "a1": tt((A1 if last else y) - o),
                                          "v0": tt(x - o) if first and V0 != A0 else None,
                                          "v1": tt(y - o) if last and V1 != A1 else None})
        else:
            left = A1 - A0
            while left > 0:
                n = min(left, 59 * F)
                alpha["segments"].append({"src": "blank", "a0": 0, "a1": tt(n)})
                left -= n
    return main, alpha, warns


def beats_path(D, P, m):
    return D / (m.get("beats_file") or P.get("beats_file") or f"beats_{P['slug']}_src.json")


def mapped_beats(D, P, pid, m, main):
    """beats.json of one mix, before asset_lib place: body beats (map_beats) + the lifted hook's own beats."""
    import map_beats as MB
    src, known = load_beats(D, P, m)
    spec = MB.map_beats(main, src, pid, list(m["body"]), m.get("cta"))
    if P.get("place", True):
        spec["remix"] = True
    if P.get("asset_bottom"):
        spec["asset_bottom"] = P["asset_bottom"]     # the assets' bottom edge, above this product's burned-in captions
    hook = MB.hook_beats(spec, src, m["segs"][0]) if m.get("hook_beats") else []
    return spec, hook, known


def same_json(path, obj):
    try:
        return path.exists() and jload(path) == json.loads(json.dumps(obj))
    except ValueError:
        return False


def fresh(out, deps):
    return out.exists() and out.stat().st_size > 0 and all(Path(d).exists() and Path(d).stat().st_mtime <= out.stat().st_mtime
                                                           for d in deps)


def check_mix(mid, m, P):
    n = len(m.get("segs") or [])
    if not ID_RE.match(mid):
        raise SystemExit(f"{mid}: ids are lowercase letters, digits, - and _")
    if not n or not m.get("body"):
        raise SystemExit(f"{mid}: needs segs and at least one body index")
    bad = [i for i in list(m["body"]) + ([m["cta"]] if m.get("cta") is not None else []) if not 0 <= i < n]
    if bad or 0 in m["body"]:
        raise SystemExit(f"{mid}: body / cta indices {m['body']} / {m.get('cta')} don't fit {n} segments "
                         "(segment 0 is the hook; use hook_beats for a lifted hook)")
    for i, s in enumerate(m["segs"]):
        if s["src"] not in P["sources"]:
            raise SystemExit(f"{mid}: seg {i} uses source {s['src']}, not in product.json")
        A0, A1, V0, V1 = seg_frames(s)
        if not (A0 <= V0 < V1 <= A1):
            raise SystemExit(f"{mid}: seg {i} wants a0 <= v0 < v1 <= a1, got {s}")


def build_mix(D, P, M, mid, as_id=None, force=False, rejoin=False):
    m, pid = M[mid], as_id or mid
    check_mix(pid, m, P)
    proj = HF / pid
    if m.get("locked") and not as_id and not force:
        raise SystemExit(f"{mid} is locked (imported or finished): rebuilding would overwrite its project. "
                         "Build it under a new id, or pass --force for a revision of this ad.")
    if as_id and (proj.exists() or as_id in M):
        raise SystemExit(f"{as_id} already exists: pick an id that was never used")
    j = D / "joins"
    j.mkdir(exist_ok=True)
    # the assets sit in front of the speaker (Nov 26 2026): a remix needs the picture join only, no cutout join
    main, _alpha, warns = specs(D, P, pid, m, make_blank=False)
    for w in warns:
        say(f"  ! {pid} {w}")
    js = j / f"j_{pid}.json"
    jm = j / f"join_{pid}.mp4"
    if rejoin or not (same_json(js, main) and fresh(jm, main["sources"].values())):
        jdump(js, main)
        run([sys.executable, S / "multi_join.py", js, jm])
    else:
        say(f"  = picture join unchanged ({jm.name})")
    if not (proj / "index.html").exists():
        run([sys.executable, S / "new_project.py", jm, pid], quiet=True)
    else:
        shutil.copy2(jm, proj / "assets" / "footage" / "main.mp4")
    for x in P.get("project_assets", []):
        shutil.copy2(D / x["from"], proj / x["to"])
    beats = proj / ".work" / "beats.json"
    spec, hook, has_beats = mapped_beats(D, P, pid, m, main)
    say(f"{pid}: t_body {spec['t_body']}  t_cta {spec.get('t_cta')}  jumps {spec.get('t_jumps', [])}  dur {spec['dur']}  "
        f"beats {len(spec['beats'])}  sfx {len(spec['sfx'])}" + ("" if has_beats else f"  (no {beats_path(D, P, m).name} yet)"))
    for b in spec["beats"]:
        say(f"   {b['in']:6.2f}-{b['out']:6.2f}  {b.get('side', 'C')}  {(b.get('lib') or b['kind']):9s} "
            + ("(hook) " if b in hook else "") + " | ".join(l["html"] for l in b.get("labels", [])))
    jdump(beats, spec)
    place_warn = []
    if P.get("place", True):
        # the user's assets: trimmed PNGs into assets/img, sized and set by the caption (asset_lib.py place)
        cmd = [sys.executable, str(S / "asset_lib.py"), "place", str(beats), "--project", str(proj), "--beats", str(beats)]
        if P.get("asset_lib"):
            cmd += ["--lib", str(D / P["asset_lib"])]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=ENV)
        sys.stdout.write(r.stdout)
        sys.stderr.write(r.stderr)
        if r.returncode != 0:
            raise SystemExit(f"{pid}: asset_lib place failed")
        place_warn = [line.strip() for line in r.stdout.splitlines() if "WARNING" in line]
    run([sys.executable, S / "remix_broll.py", proj, beats])
    done = jload(beats)
    jdump(proj / ".work" / "build.json", {
        "id": pid, "batch": D.name, "mix": mid, "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "dur": done["dur"], "t_body": done["t_body"], "t_cta": done.get("t_cta"), "t_jumps": done.get("t_jumps", []),
        "beats": len(done["beats"]), "place_warnings": place_warn})
    for w in place_warn:
        say(f"  ! {pid} place {w}")
    return proj


def cmd_build(a):
    D = src_dir(a.src_dir)
    P, M = load(D)
    for mid in ids_of(M, a.ids):
        say(f"== {mid}")
        build_mix(D, P, M, mid, force=a.force, rejoin=a.rejoin)


# ------------------------------------------------------------------ cut points and repeats (before building)

def cut_notes(D, P, m):
    """Every cut of a mix against the scan: a cut belongs in a silence of 0.12 s or more, on the editor's own
    cut, or at a flash (remix.md). Returns one note per cut that is in none of them (1 frame of slack)."""
    notes, scans = [], {}
    for i, s in enumerate(m["segs"]):
        k = s["src"]
        if k not in scans:
            p = D / "work" / f"scan_{k}.json"
            scans[k] = jload(p) if p.exists() else None
        sc = scans[k]
        if not sc:
            notes.append(f"seg {i}: {k} is not scanned, its cuts were not checked")
            continue
        for name, t in (("starts", s["a0"]), ("ends", s["a1"])):
            f = fr(t)
            if f <= 1 or f >= sc["frames"] - 1:
                continue
            in_sil = any(x["a"] - 0.035 <= t <= x["b"] + 0.035 for x in sc["silences"])
            on_cut = any(abs(c["f"] - f) <= 1 for c in sc["cuts"])
            at_flash = any(x["f0"] - 1 <= f <= x["f1"] + 2 for x in sc["flashes"])
            if not (in_sil or on_cut or at_flash):
                near = min(sc["silences"], key=lambda x: min(abs(x["a"] - t), abs(x["b"] - t)), default=None)
                notes.append(f"seg {i} {name} at {t} s ({k} f{f}): not in a silence, on an editor's cut or at a flash"
                             + (f"; the nearest silence is {near['a']}-{near['b']} s" if near else ""))
    return notes


def same_segs(a, b, slack=1):
    """Two segment lists that make the same ad: same sources in the same order, every span within a frame."""
    return len(a) == len(b) and all(x["src"] == y["src"] and abs(fr(x["a0"]) - fr(y["a0"])) <= slack
                                    and abs(fr(x["a1"]) - fr(y["a1"])) <= slack for x, y in zip(a, b))


def cmd_cuts(a):
    D = src_dir(a.src_dir)
    P, M = load(D)
    bad = 0
    for mid in ids_of(M, a.ids):
        notes = cut_notes(D, P, M[mid])
        twins = [o for o in M if o != mid and same_segs(M[o]["segs"], M[mid]["segs"])]
        bad += bool(notes)
        say(f"{mid:28s} " + ("every cut sits in a silence, on a cut or at a flash" if not notes else f"{len(notes)} cut(s) to look at")
            + (f"   same segments as {twins}" if twins else ""))
        for n in notes:
            say(f"   ! {n}")
    say(f"{len(ids_of(M, a.ids)) - bad} of {len(ids_of(M, a.ids))} mixes have clean cuts")


# ------------------------------------------------------------------ check (lint + snapshots)

def snap_times(b):
    """Joins (+0.15 s), each beat's key moment, and the CTA (ghaba_src/snap_times.py)."""
    ts = {round(b["t_body"] + 0.15, 2)}
    if b.get("t_cta"):
        ts |= {round(b["t_cta"] + 0.6, 2), round(b["dur"] - 0.6, 2)}
    for x in b["beats"]:
        keys = x.get("keys") or x.get("breathe") or x.get("shake") or [x.get("key") or (x["in"] + 0.9)]
        ts.add(round(min(keys[0] + 0.35, x["out"] - 0.4), 2))
    return sorted(ts)


def check_project(pid):
    """Lint, then snapshots at the joins and every beat's key moment. Look at the sheet before rendering."""
    proj, hf = HF / pid, hyperframes()
    if not (proj / ".work" / "beats.json").exists():
        raise SystemExit(f"{pid} is not built yet")
    say(f"== {pid} lint")
    lint = stream([*hf, "lint"], cwd=proj, log=proj / ".work" / "lint.log")
    ts = snap_times(jload(proj / ".work" / "beats.json"))
    out = proj / ".work" / "snaps"
    out.mkdir(exist_ok=True)
    say(f"== {pid} snapshot at {ts}")
    code = stream([*hf, "snapshot", "--at", ",".join(f"{t:.2f}" for t in ts), "--no-end", "-o", out], cwd=proj,
                  log=proj / ".work" / "snapshot.log")
    res = {"id": pid, "times": ts, "dir": str(out), "lint_exit": lint, "snapshot_exit": code,
           "files": sorted(p.name for p in out.iterdir())}
    jdump(proj / ".work" / "check.json", res)
    return res


def cmd_check(a):
    D = src_dir(a.src_dir)
    P, M = load(D)
    for mid in ids_of(M, a.ids):
        if M[mid].get("locked") and not a.force:
            raise SystemExit(f"{mid} is locked (imported or finished): --force writes new snapshots into its project")
        check_project(mid)


# ------------------------------------------------------------------ render + finalize

def ad_path(P, m):
    """Where this mix's ad is (or goes): the name it was delivered under if the user renamed it (ad_file,
    found by match-ads), else its own file_name."""
    name = m.get("ad_file") or m.get("file_name")
    return Path(P["ads_dir"]) / name if P.get("ads_dir") and name else None


def first_frame(path):
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vf", "scale=135:240,format=gray", "-frames:v", "1",
                          "-f", "rawvideo", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).astype(np.int16) if len(raw) == 135 * 240 else None


def cmd_match_ads(a):
    """Ads the user renamed in the Ads folder: find each one's mix by its length (+-1 frame) and its first frame
    (finalize copies the picture of the raw render untouched), and write the match into mixes.json as ad_file."""
    import numpy as np
    D = src_dir(a.src_dir)
    P, M = load(D)
    ads = Path(P["ads_dir"]) if P.get("ads_dir") else None
    if not ads or not ads.is_dir():
        raise SystemExit(f"no Ads folder for {P.get('name')}: {ads}")
    files = sorted(p for p in ads.iterdir() if p.suffix.lower() in (".mp4", ".mov", ".m4v") and ".part." not in p.name)
    by_name = {m.get("ad_file") or m.get("file_name"): mid for mid, m in M.items()}
    free = [mid for mid, m in M.items() if not (ad_path(P, m) and ad_path(P, m).exists())]
    refs, changed, left = {}, 0, []
    for f in files:
        if f.name in by_name:
            say(f"  {f.name}  = {by_name[f.name]} (its own name)")
            continue
        n, ff = probe(f)["frames"], first_frame(f)
        best = []
        for mid in free:
            if abs(sum(fr(s["a1"]) - fr(s["a0"]) for s in M[mid]["segs"]) - n) > 1:
                continue
            if mid not in refs:
                raw = HF / mid / "renders" / f"{mid}_raw.mp4"
                ref = raw if raw.exists() else HF / mid / "assets" / "footage" / "main.mp4"
                refs[mid] = (first_frame(ref) if ref.exists() else None, "raw render" if raw.exists() else "join")
            rf, kind = refs[mid]
            if rf is not None and ff is not None:
                best.append((float(np.abs(rf - ff).mean()), mid, kind))
        best.sort()
        ok = best and best[0][0] <= (2.0 if best[0][2] == "raw render" else 14.0) and \
            (len(best) == 1 or best[1][0] > best[0][0] + 3.0)
        if not ok:
            left.append(f.name)
            say(f"  {f.name}  ? no mix matches ({n} frames; closest {[(round(d, 1), m) for d, m, _ in best[:2]] or 'none of that length'})")
            continue
        d, mid, kind = best[0]
        M[mid]["ad_file"] = f.name
        M[mid]["ad_match"] = {"frames": n, "first_frame_diff": round(d, 2), "against": kind,
                              "matched_at": time.strftime("%Y-%m-%d")}
        free.remove(mid)
        changed += 1
        say(f"  {f.name}  -> {mid}  ({n} frames, first frame differs by {d:.2f} from its {kind})")
    if changed:
        jdump(D / "mixes.json", M)
    say(f"{changed} renamed ad(s) matched and saved in mixes.json; {len(left)} file(s) unmatched; "
        f"{len(free)} mix(es) with no ad in the folder: {free or '-'}")


def render_mix(D, P, M, mid, replace=False, force=False):
    m, proj = M[mid], HF / mid
    out = ad_path(P, m)
    if not out:
        raise SystemExit(f"{mid}: product.json needs ads_dir and the mix a file_name")
    if m.get("locked") and not force:
        raise SystemExit(f"{mid} is locked (imported or finished); --force re-renders it as a revision")
    if out.exists() and not replace:
        raise SystemExit(f"{out.name} already exists in the Ads folder: --replace re-renders this ad under the same name")
    if not (proj / "index.html").exists():
        raise SystemExit(f"{mid} is not built yet")
    out.parent.mkdir(parents=True, exist_ok=True)
    (proj / "renders").mkdir(exist_ok=True)
    raw = proj / "renders" / f"{mid}_raw.mp4"
    b = jload(proj / ".work" / "beats.json")
    t0 = time.time()
    say(f"[{mid}] render start {time.strftime('%H:%M:%S')}  ({fr(b['dur'])} frames)")
    code = stream([*hyperframes(), "render", "--fps", str(F), "--quality", "delivery", "-o", f"renders/{mid}_raw.mp4"],
                  cwd=proj, log=proj / ".work" / "render.log")
    secs = time.time() - t0
    say(f"[{mid}] render exit {code} in {int(secs)} s")
    if code != 0 or not raw.exists() or raw.stat().st_mtime < t0 - 1:
        raise SystemExit(f"[{mid}] render failed; see {proj / '.work' / 'render.log'}")
    tmp = out.with_name(out.stem + ".part.mp4")
    r = subprocess.run([sys.executable, str(S / "finalize.py"), str(raw), str(tmp), "--sheet",
                        str(proj / ".work" / "final_sheet.jpg")], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=ENV)
    if r.returncode != 0 or "{" not in r.stdout:
        with contextlib.suppress(OSError):
            tmp.unlink()
        raise SystemExit(f"[{mid}] finalize failed: {(r.stderr or r.stdout).strip()[-600:]}")
    rep = json.loads(r.stdout[r.stdout.index("{"):])
    os.replace(tmp, out)                             # the ad appears (or is replaced) only once it is complete
    joins = sorted([b["t_body"]] + b.get("t_jumps", []) + ([b["t_cta"]] if b.get("t_cta") else []))
    total = fr(rep["duration"])
    frames = [min(total - 1, max(0, round((j + o) * F))) for j in joins for o in (-0.5, -0.1, 0.12, 0.6, 2.0)]
    strip = proj / ".work" / "joins_sheet.jpg"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(out), "-vf",
                    "select='" + "+".join(f"eq(n\\,{n})" for n in frames) + f"',scale=180:320,tile=5x{len(joins)}",
                    "-fps_mode", "passthrough", "-frames:v", "1", str(strip)])
    rep.update(id=mid, out=str(out), render_secs=round(secs), render_fps=round(fr(b["dur"]) / secs, 2),
               joins=joins, joins_sheet=str(strip), sheet=str(proj / ".work" / "final_sheet.jpg"),
               finished_at=time.strftime("%Y-%m-%dT%H:%M:%S"))
    jdump(proj / ".work" / "final_report.json", rep)
    say(json.dumps(rep, ensure_ascii=False, indent=1))
    return rep


def cmd_render(a):
    D = src_dir(a.src_dir)
    P, M = load(D)
    for mid in ids_of(M, a.ids):
        render_mix(D, P, M, mid, replace=a.replace, force=a.force)
    say("RENDERS DONE")


# ------------------------------------------------------------------ status

def next_number(D, P, M):
    """The next MixNN: one past every number a mix, a project folder or an ad file of this product ever used."""
    nums = [int(x) for m in M.values() for x in re.findall(r"Mix(\d+)", m.get("name") or "")]
    nums += [int(x) for mid in M for x in re.findall(r"-m(\d+)(?:-|$)", mid)]
    pp = D / "proposals.json"                        # a proposal keeps its number even when it is rejected
    if pp.exists():
        nums += [int(x) for ad in jload(pp).get("ads", []) for x in re.findall(r"-m(\d+)(?:-|$)", ad.get("id") or "")]
    pre = P.get("id_prefix")
    if pre:
        nums += [int(x) for p in HF.glob(f"{pre}-m*") for x in re.findall(rf"^{re.escape(pre)}-m(\d+)(?:-|$)", p.name)]
    ads = Path(P["ads_dir"]) if P.get("ads_dir") else None
    if ads and ads.is_dir() and P.get("name"):
        nums += [int(x) for p in ads.iterdir() if p.name.startswith(P["name"]) for x in re.findall(r"Mix(\d+)", p.name)]
    return max(nums, default=0) + 1


def mix_state(D, P, M, mid):
    m, proj = M[mid], HF / mid
    out = ad_path(P, m)
    return {"id": mid, "name": m.get("name"), "locked": bool(m.get("locked")),
            "duration": tt(sum(fr(s["a1"]) - fr(s["a0"]) for s in m["segs"])),
            "built": (proj / "index.html").exists() and (proj / ".work" / "beats.json").exists(),
            "raw": (proj / "renders" / f"{mid}_raw.mp4").exists(),
            "ad": bool(out and out.exists()), "ad_path": str(out) if out else None}


def cmd_status(a):
    D = src_dir(a.src_dir)
    P, M = load(D)
    man = manifest(D)
    st = {"slug": P.get("slug"), "name": P.get("name"), "dir": str(D),
          "sources": {k: {"copy": copy_path(D, P, k).exists(), "words": (D / "work" / f"{k}_words.json").exists(),
                          "scan": (D / "work" / f"scan_{k}.json").exists(),
                          "cutouts": [[r["f0"], r["f1"]] for r in man.get(k, [])]} for k in P["sources"]},
          "analysis": (D / "analysis.json").exists(), "proposals": (D / "proposals.json").exists(),
          "mixes": [mix_state(D, P, M, mid) for mid in M], "next_mix": next_number(D, P, M)}
    if a.json:
        say(json.dumps(st, ensure_ascii=False, indent=1))
        return
    say(f"{st['name']} ({st['slug']})  {D}")
    for k, s in st["sources"].items():
        say(f"  {k:5s} copy {'y' if s['copy'] else '-'}  words {'y' if s['words'] else '-'}  scan {'y' if s['scan'] else '-'}"
            f"  cutouts {s['cutouts'] or '-'}")
    for x in st["mixes"]:
        say(f"  {x['id']:28s} {x['duration']:6.2f} s  {'built' if x['built'] else '-----'}  "
            f"{'ad' if x['ad'] else '--'}  {'locked' if x['locked'] else ''}")
    say(f"  next mix number: {st['next_mix']}")


# ------------------------------------------------------------------ import a batch made by hand

def sha(p):
    return hashlib.sha1(Path(p).read_bytes()).hexdigest()


def find_assets(D, ids):
    """project_assets by looking: every picture in a built project's assets/img that is byte-identical to a file
    in the batch folder (its own jar, its illustrations) was copied from there."""
    pool = {}
    for p in [*D.glob("*.png"), *(D / "img").glob("*.png")]:
        pool.setdefault(sha(p), p)
    default_jar = sha(SKILL / "assets" / "jar.png")
    found = {}
    for mid in ids:
        img = HF / mid / "assets" / "img"
        if not img.is_dir():
            continue
        for p in img.glob("*.png"):
            h = sha(p)
            if p.name.startswith("lib-") or h == default_jar or h not in pool:
                continue
            found.setdefault(f"assets/img/{p.name}", pool[h].relative_to(D).as_posix())
    return [{"from": v, "to": k} for k, v in sorted(found.items())]


def cutout_ok(D, rel, f0, f1):
    p = D / rel
    return p.exists() and probe(p)["frames"] == f1 - f0


def import_module_batch(D):
    """ghaba_src / tanafous_src: MIXES, CUT and CUT_END from their build_mixes.py."""
    src = (D / "build_mixes.py").read_text(encoding="utf-8")
    spec = importlib.util.spec_from_file_location(f"_bm_{D.name}", D / "build_mixes.py")
    bm = importlib.util.module_from_spec(spec)
    keep, sys.dont_write_bytecode = sys.dont_write_bytecode, True      # leave no __pycache__ in the batch folder
    try:
        spec.loader.exec_module(bm)                  # definitions only: its work is under __main__
    finally:
        sys.dont_write_bytecode = keep
    slug = D.name[:-4] if D.name.endswith("_src") else D.name
    names = jload(D / "mix_names.json") if (D / "mix_names.json").exists() else {}
    files = jload(D / "sources.json") if (D / "sources.json").exists() else {}
    notes = []
    ads_dir = None
    rf = D / "render_finish.ps1"
    if rf.exists():
        t = rf.read_text(encoding="utf-8-sig")
        m = re.search(r'^\$ADS\s*=\s*"([^"]+)"', t, re.M)
        if m:
            ads_dir = Path(m.group(1))
        else:
            m = re.search(r'^\$ADS\s*=\s*Join-Path \(Split-Path -Parent \$HF\) "([^"]+)"', t, re.M)
            if m:
                ads_dir = ROOT / m.group(1)
    product_dir = None
    for c in ([ads_dir.parent] if ads_dir else []) + [p for p in ROOT.iterdir() if p.is_dir()]:
        if files and all((c / f).exists() for f in files.values()):
            product_dir = c
            break
    if not product_dir:
        notes.append("the original source files were not found: set product_dir")
    prompt = None
    ta = D / "transcribe_all.py"
    if ta.exists():
        m = re.search(r'^PROMPT\s*=\s*"([^"]*)"', ta.read_text(encoding="utf-8"), re.M)
        prompt = m.group(1) if m else None
    ids = list(bm.MIXES)
    name = next((m["name"].split(" Mix")[0] for m in bm.MIXES.values() if " Mix" in m.get("name", "")), slug.title())
    name_ar = next((mm.group(1) for f in names.values() for mm in [re.search(r" - ([^-]+)\.mp4$", f)] if mm), None)
    pre = os.path.commonprefix([re.sub(r"-m\d+.*$", "", i) for i in ids]) if ids else slug
    bf = re.search(r'"(beats_\w+\.json)"', src)
    used = sorted({s[0] for m in bm.MIXES.values() for s in m["segs"]})
    sources = {k: {"file": files.get(k), "tag": "finished_ad"} for k in (list(files) or used)}
    for k in used:
        sources.setdefault(k, {"file": None, "tag": "finished_ad"})
    P = {"slug": slug, "name": name, "name_ar": name_ar, "whisper_prompt": prompt,
         "product_dir": str(product_dir) if product_dir else None, "ads_dir": str(ads_dir) if ads_dir else None,
         "name_pattern": "{name} Mix{nn} - {label} - {name_ar}.mp4", "id_prefix": pre, "fps": F,
         "sources": sources, "beats_file": bf.group(1) if bf else None,
         "project_assets": find_assets(D, ids), "place": "asset_lib.py" in src, "gpt_cap": 3,
         "imported_from": "build_mixes.py"}
    M = {}
    for mid, m in bm.MIXES.items():
        M[mid] = {"name": m["name"], "file_name": names.get(mid),
                  "segs": [{"src": s[0], "a0": s[1], "a1": s[2], "v0": s[3], "v1": s[4],
                            "text": seg_text(D, s[0], s[1], s[2])} for s in m["segs"]],
                  "body": list(m["body"]), "cta": m.get("cta"), "hook_beats": bool(m.get("hook_beats")),
                  "locked": True}
        if not names.get(mid):
            notes.append(f"{mid}: no file name in mix_names.json")
    man = {}
    ranges = {k: (bm.CUT[k], bm.CUT_END[k]) for k in bm.CUT}
    ps = D / "cut_bodies.ps1"
    if ps.exists():                                  # ranges that were cut but never used by a mix (a hook's take)
        for k, f0, f1 in re.findall(r'@\{k="(\w+)";\s*f0=(\d+);\s*f1=(\d+)\}', ps.read_text(encoding="utf-8-sig")):
            ranges.setdefault(k, (int(f0), int(f1)))
    for k, (f0, f1) in sorted(ranges.items()):
        rel = f"cut/{k}_cutout.webm"
        if cutout_ok(D, rel, f0, f1):
            man[k] = [{"file": rel, "f0": f0, "f1": f1}]
        else:
            notes.append(f"{rel}: missing, or not {f1 - f0} frames (frames {f0}-{f1}): left out of the manifest")
    return P, M, man, notes


def import_join_specs(D):
    """thyroid_src: no build_mixes.py. Mixes from the j_*.json / ja_*.json join specs, whole-source cutouts,
    and the built project each spec belongs to (found by its joins: t_body, t_jumps, t_cta, duration)."""
    import map_beats as MB
    slug = D.name[:-4] if D.name.endswith("_src") else D.name
    notes = ["no build_mixes.py here: name_ar, product_dir, ads_dir and the ads' file names are unknown: fill them in"]
    js = {p.stem[2:]: jload(p) for p in sorted(D.glob("j_*.json"))}
    built = {}
    for p in HF.iterdir():
        b = p / ".work" / "beats.json"
        if p.is_dir() and b.exists():
            with contextlib.suppress(ValueError, KeyError):
                built[p.name] = jload(b)
    rel = lambda s: Path(s).name
    sources, man, M = {}, {}, {}
    for x, j in js.items():
        for k, f in j["sources"].items():
            sources.setdefault(k, {"file": None, "copy": rel(f), "tag": "finished_ad"})
    ja_all = True
    for x, j in js.items():
        ja = jload(D / f"ja_{x}.json") if (D / f"ja_{x}.json").exists() else None
        if ja:
            for k, f in ja["sources"].items():
                if k in sources and k not in man and (D / rel(f)).exists():
                    man[k] = [{"file": rel(f), "f0": 0, "f1": probe(D / rel(f))["frames"]}]
            ja_all = ja_all and [s["src"] for s in ja["segments"]] == [s["src"] for s in j["segments"]]
        segs, dur = MB.timeline(j)
        offs = [round(s["off"], 4) for s in segs]
        hits = []
        for pid, b in built.items():
            starts = {b["t_body"], *b.get("t_jumps", []), *([b["t_cta"]] if b.get("t_cta") is not None else [])}
            if abs(b["dur"] - dur) < 0.002 and {round(t, 4) for t in starts} == set(offs[1:]):
                hits.append(pid)
        if len(hits) != 1:
            notes.append(f"j_{x}.json: {'no' if not hits else 'more than one'} built project matches its joins {hits}: skipped")
            continue
        pid, b = hits[0], built[hits[0]]
        first = offs.index(round(b["t_body"], 4))
        cta = offs.index(round(b["t_cta"], 4)) if b.get("t_cta") is not None else None
        body = list(range(first, cta if cta is not None else len(segs)))
        if cta is not None and any(z["in"] >= b["t_cta"] for z in b["beats"]):
            body.append(cta)
        sig = lambda bs: sorted((z["kind"], z["side"], z["in"], z["out"]) for z in bs)
        bfile = None
        for bp in sorted(D.glob("beats*_src.json")):
            with contextlib.suppress(Exception):
                if sig(MB.map_beats(j, jload(bp), pid, body, cta)["beats"]) == sig(b["beats"]):
                    bfile = bp.name
                    break
        if not bfile:
            notes.append(f"{pid}: no beats*_src.json maps onto its beats.json exactly (edited by hand?)")
        M[pid] = {"name": pid, "file_name": None,
                  "segs": [{"src": s["src"], "a0": s["a0"], "a1": s["a1"], "v0": s.get("v0"), "v1": s.get("v1"),
                            "text": seg_text(D, s["src"], s["a0"], s["a1"])} for s in j["segments"]],
                  "body": body, "cta": cta, "hook_beats": False, "beats_file": bfile, "join_spec": f"j_{x}.json",
                  "locked": True}
    P = {"slug": slug, "name": slug.title(), "name_ar": None, "whisper_prompt": None, "product_dir": None,
         "ads_dir": None, "name_pattern": "{name} Mix{nn} - {label} - {name_ar}.mp4",
         "id_prefix": os.path.commonprefix([re.sub(r"-[a-z]*\d.*$", "", i) for i in M]) or slug, "fps": F,
         "sources": sources, "beats_file": None, "project_assets": find_assets(D, list(M)), "place": False,
         "alpha_all": ja_all, "gpt_cap": 3, "imported_from": "join specs"}
    return P, M, man, notes


def cmd_import(a):
    D = src_dir(a.src_dir)
    targets = [D / "product.json", D / "mixes.json", D / "cut" / "manifest.json"]
    have = [p for p in targets if p.exists()]
    if have and not a.force:
        raise SystemExit(f"already imported ({', '.join(p.name for p in have)}): --force rewrites them (old ones kept as .bak)")
    P, M, man, notes = import_module_batch(D) if (D / "build_mixes.py").exists() else import_join_specs(D)
    for p, obj in zip(targets, (P, M, man)):
        if p.exists():
            shutil.copy2(p, p.with_name(p.name + time.strftime(".%Y%m%d-%H%M%S.bak")))
        jdump(p, obj)
    say(f"{D.name}: {len(P['sources'])} sources, {len(M)} mixes (locked), cutouts for {sorted(man) or 'none'}")
    say(f"  name {P['name']} / {P['name_ar']}   ads {P['ads_dir']}   beats {P['beats_file']}   place {P['place']}")
    say(f"  project assets: {P['project_assets'] or 'the skill jar only'}")
    for n in notes:
        say(f"  ! {n}")
    say(f"  next mix number: {next_number(D, P, M)}")


# ------------------------------------------------------------------ verify

def spec_frames(spec):
    """A join spec reduced to what multi_join.py does with it: per segment (source file, span frames, picture
    frames). Two specs with the same reduction make the same join."""
    out = []
    for s in spec["segments"]:
        A0, A1, V0, V1 = seg_frames(s)
        name = Path(spec["sources"][s["src"]]).name
        out.append((name, A1 - A0) if name == "blank.webm" else (name, A0, A1, V0, V1))
    return out


PLACE_KEYS = ("img", "w", "h", "x", "mirror", "check")


def beat_core(b):
    """A beat as map_beats wrote it: what asset_lib place adds to a library picture is taken off."""
    o = {k: v for k, v in b.items() if not ("lib" in b and (k in PLACE_KEYS or k == "top"))}
    if "lib" in b:
        o.pop("side", None)                     # place may move a picture to the freer side
    return o


def beats_core(spec):
    o = {k: v for k, v in spec.items() if k not in ("id", "beats", "remix")}
    o["beats"] = sorted((beat_core(b) for b in spec["beats"]), key=lambda b: (b["in"], b["kind"]))
    return o


def old_spec(D, m, mid, alpha=False):
    pre = "ja_" if alpha else "j_"
    c = [D / "joins" / f"{pre}{mid}.json"]
    if m.get("join_spec"):
        c.append(D / (m["join_spec"] if not alpha else "ja_" + m["join_spec"][2:]))
    return next((p for p in c if p.exists()), None)


def verify_light(D, P, M, mid):
    """Nothing runs: batch.py's join specs and beats against what the hand-made batch left on disk."""
    m, res = M[mid], {}
    main, alpha, _ = specs(D, P, mid, m, make_blank=False)
    for key, new, old in (("picture join spec", main, old_spec(D, m, mid)), ("cutout join spec", alpha, old_spec(D, m, mid, True))):
        res[key] = "no old file" if not old else ("same" if spec_frames(new) == spec_frames(jload(old)) else "DIFFERENT")
    old_b = HF / mid / ".work" / "beats.json"
    if old_b.exists():
        new_b, _, _ = mapped_beats(D, P, mid, m, main)
        res["beats"] = "same" if beats_core(new_b) == beats_core(jload(old_b)) else "DIFFERENT"
    else:
        res["beats"] = "no old file"
    return res


def md5_stream(path, kind):
    args = ["ffmpeg", "-v", "error"]
    if str(path).endswith(".webm"):
        args += ["-c:v", "libvpx-vp9"]
    args += ["-i", str(path), "-map", f"0:{kind}:0"]
    if str(path).endswith(".webm"):
        args += ["-pix_fmt", "yuva420p"]
    r = subprocess.run(args + ["-f", "md5", "-"], capture_output=True, text=True)
    return r.stdout.strip().replace("MD5=", "") or None


def psnr(a, b):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(a), "-i", str(b), "-lavfi", "psnr", "-f", "null",
                        "-"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    m = re.search(r"average:(\S+)", r.stderr)
    return m.group(1) if m else None


def cmd_verify(a):
    D = src_dir(a.src_dir)
    P, M = load(D)
    ids = ids_of(M, a.ids)
    if a.rebuild:
        if len(ids) != 1:
            raise SystemExit("--rebuild <new id> rebuilds exactly one mix: name it")
        mid, new = ids[0], a.rebuild
        say(f"== rebuilding {mid} as {new}")
        build_mix(D, P, M, mid, as_id=new)
        rows = []
        # builds since Nov 26 2026 make no cutout join, and their beats / index.html are in the asset style, so
        # only the picture join is expected to match a mix built before that
        for label, old, cur in (("picture join", D / "joins" / f"join_{mid}.mp4", D / "joins" / f"join_{new}.mp4"),):
            if not old.exists():
                rows.append([label, "no original file", "", ""])
                continue
            po, pn = probe(old), probe(cur)
            rows.append([f"{label}: duration", f"{po['duration']:.4f} s", f"{pn['duration']:.4f} s",
                         "same" if abs(po["duration"] - pn["duration"]) < 0.002 else "DIFFERENT"])
            rows.append([f"{label}: frames", po["frames"], pn["frames"], "same" if po["frames"] == pn["frames"] else "DIFFERENT"])
            vo, vn = md5_stream(old, "v"), md5_stream(cur, "v")
            rows.append([f"{label}: decoded picture", vo[:12], vn[:12],
                         "same" if vo == vn else f"differs (PSNR {psnr(old, cur)} dB)"])
            if "sr" in po:
                ao, an = md5_stream(old, "a"), md5_stream(cur, "a")
                rows.append([f"{label}: decoded audio", ao[:12], an[:12], "same" if ao == an else "DIFFERENT"])
        bo, bn = jload(HF / mid / ".work" / "beats.json"), jload(HF / new / ".work" / "beats.json")
        strip = lambda b: {k: v for k, v in b.items() if k != "id"}
        rows.append(["beats.json (all but id)", f"{len(bo['beats'])} beats, {len(bo['sfx'])} sfx",
                     f"{len(bn['beats'])} beats, {len(bn['sfx'])} sfx", "same" if strip(bo) == strip(bn) else "DIFFERENT"])
        ho = (HF / mid / "index.html").read_text(encoding="utf-8-sig").replace(mid, "ID")
        hn = (HF / new / "index.html").read_text(encoding="utf-8-sig").replace(new, "ID")
        rows.append(["index.html (ids aside)", f"{len(ho)} chars", f"{len(hn)} chars", "same" if ho == hn else "DIFFERENT"])
        say(f"\n{'':32s} {'original ' + mid:30s} {'rebuilt ' + new:30s}")
        for r in rows:
            say(f"{r[0]:32s} {str(r[1]):30s} {str(r[2]):30s} {r[3]}")
        jdump(D / "work" / f"verify_{new}.json", {"original": mid, "rebuilt": new, "rows": rows,
                                                  "ok": all("DIFFERENT" not in str(r[3]) for r in rows)})
        return
    bad = 0
    for mid in ids:
        r = verify_light(D, P, M, mid)
        bad += any(v == "DIFFERENT" for v in r.values())
        say(f"{mid:28s} " + "   ".join(f"{k}: {v}" for k, v in r.items()))
    say(f"{len(ids) - bad} of {len(ids)} mixes reproduce exactly" + ("" if not bad else f"  ({bad} differ)"))
    if bad:
        raise SystemExit(1)


# ------------------------------------------------------------------ cli

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    def cmd(name, fn, what="ids"):
        g = sub.add_parser(name)
        g.add_argument("src_dir")
        if what:
            g.add_argument(what, nargs="*")
        g.set_defaults(fn=fn)
        return g

    cmd("prepare", cmd_prepare, "keys")
    cmd("transcribe", cmd_transcribe, "keys").add_argument("--force", action="store_true")
    cmd("scan", cmd_scan, "keys").add_argument("--force", action="store_true")
    g = sub.add_parser("frames")
    g.add_argument("src_dir")
    g.add_argument("key")
    g.add_argument("ranges", nargs="+", help="frame ranges: 197-204 150-165, or single frames")
    g.add_argument("--every", type=int, default=1, help="one frame in N (a longer range)")
    g.add_argument("--width", type=int, default=270, help="tile width in px (540 to read a caption)")
    g.add_argument("--crop", help="x:y:w:h of the 1080x1920 frame, e.g. 0:1000:1080:520 for the caption band")
    g.set_defaults(fn=cmd_frames)
    g = cmd("cut", cmd_cut)
    g.add_argument("--plan", action="store_true", help="only list the ranges still to cut, with their cost")
    g.add_argument("--exact", action="store_true", help="cut only what these mixes show, not each whole body")
    g.add_argument("--force", action="store_true", help="cut anyway (remixes no longer need a speaker cutout)")
    g.add_argument("--range", nargs="*", help="extra ranges <key>:<first frame>-<end frame>")
    g = cmd("build", cmd_build)
    g.add_argument("--force", action="store_true", help="rebuild a locked mix (a revision of that ad)")
    g.add_argument("--rejoin", action="store_true", help="re-encode the joins even if their specs did not change")
    cmd("cuts", cmd_cuts)
    cmd("check", cmd_check).add_argument("--force", action="store_true", help="check a locked mix")
    g = cmd("render", cmd_render)
    g.add_argument("--replace", action="store_true", help="re-render an ad that already exists, same file name")
    g.add_argument("--force", action="store_true", help="render a locked mix")
    cmd("import", cmd_import, None).add_argument("--force", action="store_true")
    cmd("verify", cmd_verify).add_argument("--rebuild", metavar="NEW_ID", help="rebuild one mix under this new id")
    cmd("status", cmd_status, None).add_argument("--json", action="store_true")
    cmd("match-ads", cmd_match_ads, None)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
