"""Map source-time B-roll beats onto one remix's timeline and write its beats.json.

    python map_beats.py <join spec.json> <beats_src.json> <id> <out beats.json> --body 1 [2 3] [--cta K] [--jumps-from-hook]

--body: segment indices that may carry B-roll (never the hook). A beat is kept only when it sits wholly inside one
of them, at least 0.20 s after its start and 0.25 s before its end (nothing straddles a cut).
--cta K: segment K starts at a new body -> CTA join: sets t_cta and adds the camel whoosh.
Every other segment start (inside the hook or the body) becomes a jump cut (t_jumps).

Also importable (batch.py uses it): map_beats(spec, src, id, body, cta) returns the beats.json dict, and
hook_beats(out, src, seg) adds the beats of a hook that was lifted from a body (segment 0, remix time = source - a0).
"""
import json, sys

F = 30
snap = lambda t: round(t * F) / F
IN_PAD, OUT_PAD = 0.20, 0.25          # a beat sits this far inside its segment / before its end


def shift(b, mv):
    """One source beat with every time moved by mv (its src key dropped)."""
    o = {k: v for k, v in b.items() if k != "src"}
    for k in ("in", "out", "key", "fill", "ghosts"):
        if k in o:
            o[k] = mv(o[k])
    for k in ("keys", "pops", "breathe", "shake"):
        if k in o:
            o[k] = [mv(x) for x in o[k]]
    o["labels"] = [{**l, "t": mv(l["t"]), **({"countAt": mv(l["countAt"])} if "countAt" in l else {})}
                   for l in o.get("labels", [])]
    if "badge" in o:
        o["badge"] = {**o["badge"], "t": mv(o["badge"]["t"])}
    return o


def timeline(spec):
    """[{src, a0, a1, off}] with frame-snapped times and each segment's start in the remix, plus the total."""
    segs, t = [], 0.0
    for s in spec["segments"]:
        a0, a1 = snap(s["a0"]), snap(s["a1"])
        segs.append({"src": s["src"], "a0": a0, "a1": a1, "off": t})
        t += a1 - a0
    return segs, round(t, 3)


def map_beats(spec, src, ID, body, cta=None):
    segs, dur = timeline(spec)
    t_body = round(segs[min(body)]["off"], 4)
    # every other segment start is a jump cut (hook or body or CTA), masked by the template's alternating cut-zoom
    t_jumps = [round(s["off"], 4) for k, s in enumerate(segs) if k > 0 and k != min(body) and k != cta]

    def where(source, a, b):
        for k in body:
            s = segs[k]
            if s["src"] == source and a >= s["a0"] + IN_PAD - 1e-6 and b <= s["a1"] - OUT_PAD + 1e-6:
                return s
        return None

    def mv(x, s):
        return round(x - s["a0"] + s["off"], 3)

    beats = []
    for b in src["beats"]:
        s = where(b["src"], b["in"], b["out"])
        if s:
            beats.append(shift(b, lambda x, s=s: mv(x, s)))
    sfx = []
    for x in src.get("sfx", []):
        s = where(x["src"], x["t"], x["t"])
        if s:
            sfx.append({"src": x["file"], "t": mv(x["t"], s), "vol": x["vol"]})
    out = {"id": ID, "t_body": t_body, "dur": dur, "sfx": sfx, "beats": beats}
    if cta is not None:
        out["t_cta"] = round(segs[cta]["off"], 4)
        sfx.append({"src": "whoosh.mp3", "t": round(out["t_cta"] - 0.18, 3), "vol": 0.32})
    if t_jumps:
        out["t_jumps"] = t_jumps
    return out


def hook_beats(out, src, seg):
    """Source beats wholly inside the hook segment (0.20 s in, 0.25 s before its end), shifted to remix time
    (the hook starts at 0). map_beats only maps body segments, so this is the hook's own pass: a hook lifted
    from a body has no burned-in title, so its picture can open the ad. Returns the beats it added."""
    source, a0, a1 = seg["src"], seg["a0"], seg["a1"]
    mv = lambda t: round(t - a0, 3)
    added = []
    for b in src["beats"]:
        if b["src"] != source or b["in"] < a0 + IN_PAD - 1e-6 or b["out"] > a1 - OUT_PAD + 1e-6:
            continue
        added.append(shift(b, mv))
    out["beats"] += added
    for x in src.get("sfx", []):
        if x["src"] == source and a0 + IN_PAD <= x["t"] <= a1 - OUT_PAD:
            out["sfx"].append({"src": x["file"], "t": mv(x["t"]), "vol": x["vol"]})
    return added


def main():
    spec = json.load(open(sys.argv[1], encoding="utf-8-sig"))
    src = json.load(open(sys.argv[2], encoding="utf-8-sig"))
    ID, OUT = sys.argv[3], sys.argv[4]
    args = sys.argv[5:]
    body = []
    i = args.index("--body") + 1
    while i < len(args) and not args[i].startswith("--"):
        body.append(int(args[i])); i += 1
    cta = int(args[args.index("--cta") + 1]) if "--cta" in args else None
    out = map_beats(spec, src, ID, body, cta)
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{ID}: t_body {out['t_body']}  t_cta {out.get('t_cta')}  jumps {out.get('t_jumps', [])}  dur {out['dur']}  "
          f"beats {len(out['beats'])}  sfx {len(out['sfx'])}")
    for b in out["beats"]:
        print(f"   {b['in']:6.2f}-{b['out']:6.2f}  {b.get('side', 'C')}  {(b.get('lib') or b['kind']):9s} "
              + " | ".join(l["html"] for l in b.get("labels", [])))


if __name__ == "__main__":
    main()
