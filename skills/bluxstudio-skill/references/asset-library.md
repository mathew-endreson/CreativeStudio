# Asset library reference

How `scripts/asset_lib.py` turns the pictures the user uploads for a product into animated assets in an ad, and
how the optional GPT side (`scripts/gpt_assets.py`) fits in. Read it when a match looks wrong, a picture lands
badly, or the user wants GPT to draw something.

## Contents
1. Where things live
2. A library entry
3. How words match
4. The plan file
5. Placement
6. The concept lexicon (`assets/concepts.json`)
7. GPT requests (only when the user asks)
8. Fixing things

---

## 1. Where things live

| path | what | written by |
|---|---|---|
| `<upload folder>\*.png / *.webp` | the user's pictures for this product or project: transparent cut-outs of real-looking objects (herbs, moon, organs, the jar, an offer) | the user |
| `<upload folder>\library.json` | that folder's keyword index (one entry per picture); every command takes `--lib` to it | asset_lib (`index`, `setmany`), under `library.json.lock` |
| `<project>\assets\img\lib-<id>[-m].png` | the picture as used in one ad: trimmed to its subject, ≤ 900 px, `-m` mirrored | asset_lib place |
| `<project>\.work\illus_plan.json` | the plan | asset_lib plan |
| `assets/concepts.json` (this skill) | curated health concepts + Darija triggers (+ GPT prompt parts) | by hand |
| `assets/asset_motion.js` (this skill) | how every asset animates, pasted into each project's index.html | by hand |
| `Documents\ChatGPT\asstets tool ebox\...` | the GPT asset studio (its own `library.json`, `generated/`, `style/`): the default library when no `--lib` is given | gpt_assets, only on request |

Where the upload folder is: wherever the user puts the pictures. For a batch, `<slug>_src/img/` is natural (set
`asset_lib` in product.json); for a fresh edit, any folder (`<product>/assets/`, `_hyperframes/<slug>/uploads/`).

## 2. A library entry

```json
{"id": "ashwagandha-root", "file": "Ashwagandha root.png", "look": "photo", "source": "upload",
 "subject": "", "motion": "", "concept": "glossy-ashwagandha-root", "box": [612, 700], "size": [800, 800],
 "opaque": false, "empty": false,
 "keywords": {"darija": ["الاشواغاندا", "اشواغاندا"], "ar": ["الأشواغاندا"], "fr": ["ashwagandha"], "en": ["ashwagandha"]},
 "tagged_by": "claude", "added": "2026-11-26T16:40:00"}
```

- `file` is relative to the folder the library sits in. `box` = the subject's alpha box.
- `id` comes from the file name (lower case, spaces → `-`; Arabic names stay Arabic). `index` seeds the file name
  itself as a first keyword (`en`, or `darija` for an Arabic name); the real keywords are yours (`setmany`).
- `opaque: true` = no transparent background (it would show as a rectangle), `empty: true` = nothing visible:
  such pictures are listed as `NO-ALPHA` and never planned or placed.
- `motion`: `breathe` (lungs, a calm breath, sleep), `shake` (cough, pain), `shine` or empty (everything else: a
  pop + glint on the key word).
- `concept`: links the picture to a concept of `assets/concepts.json`, so it also answers to that concept's curated
  Darija triggers (`الكبد، كبدي، لافوا …`) and the concept stops being MISSING.
- `source`: `upload`, or `gpt` / `ref` for the GPT studio's pictures (those are palette-locked to the house orange
  when placed; uploads keep their colours). `missing: true` = the file is gone (kept, never matched).
- Keywords are merged, never silently dropped: `--replace` on `set` / `setmany` / `tag` overwrites on purpose.

## 3. How words match

Both sides are normalised: no diacritics or tatweel, أ/إ/آ → ا, ى → ي, ة → ه, ؤ → و, ئ → ي, ڨ → ق, Arabic-Indic digits → 0-9, French accents dropped, punctuation splits words.

Per word (spoken `a` against keyword `b`):

| score | when |
|---|---|
| 1.00 | identical after normalising |
| 0.93 | same stem of 4+ letters: the spoken word loses و/ف, a preposition + article (بال، وال، لل، ال، ب، ل، ك …) and a pronoun/plural ending (ي، ك، ه، ها، نا، كم، هم، ين، ات، ون، ا); a possessed ـت gets its ة back (ركبتي → ركبه ~ الركبة). The keyword only loses its prefixes. |
| 0.90 | same length ≥ 5 letters, one look-alike letter different (س/ص, ت/ط, د/ذ/ض/ظ/ز, ق/ك/غ, ح/ه): Whisper slips |
| 0.86 | same 3-letter stem, and the spoken word is inflected (4+ letters): صدرك ~ الصدر, بالكحة ~ الكحة |

Deliberately NOT matched: bare 3-letter spoken words against a longer keyword (تعب, شوف, قرح are everyday words or Whisper garble); verb prefixes (يقولون must not reach القولون); keyword endings (الدوال ≠ الدوالي, تتنفس ≠ التنفسي — list verb forms as keywords instead).

A phrase matches when every word scores ≥ 0.80 and the average ≥ 0.85; one filler (تاع، نتاع، ديال، في، de, la …) may sit between its words. Ranking adds a little for keywords early in their list (most specific first) and for multi-word phrases, and takes a little off English. Single-word keywords in the stoplist (`STOP` in asset_lib.py: وجع، مرض، عسل، خلطة، نفسي، قريب، الظهر، النيف، قلبي … and their French) never pull a picture.

Writing keywords for an upload (look at the picture first): 6–15 Darija words or short phrases as Whisper spells
them (definite and bare forms, possessives, verbs: النوم، تنوم مليح، ترقد), a few Arabic and French, most specific
first, never a generic word alone.

## 4. The plan file

`plan` writes `{words, t_body, t_cta, dur, remix, hook, asset_bottom, beats, skipped, missing, hits}`.

- **Sections**: body = `t_body + 0.30` → `t_cta − 0.25` (or the end); the hook too with `--hook` (never with `--remix`); never the CTA. A word must come ≥ 1 s before its section ends.
- **Clusters**: hits on the same or touching words compete; the best picture wins (ties → the one shown longest ago).
- **One idea = one picture**: if the picture for these words is already up (or left < 2 s ago), it stays up longer (≤ 6 s total) and gets another key instead of a new picture. The same picture comes back only ≥ 6 s after it left.
- **One at a time**: every asset sits by the caption, so they share one lane: ≥ 0.3 s between one leaving and the next arriving. `--busy 12.0-15.5` blocks a window (a burned-in card at chest height, full-screen B-roll, the CTA mockup; the old `L:12.0-15.5` form still works, the side is ignored).
- **Timing**: in = first word − 0.25; out = last word + 1.3 (at least 2.4 s, at most 4 s); nothing straddles a cut.
- **Beat fields**: `kind: "asset"`, `lib`, `side` (`C`), `in`, `out`, one of `keys` / `breathe` / `shake` (times), optional `bottom`, `x`, `size`, `side: L|R`, `mirror`, `src` (multi-source remixes), and info only: `why`. Edit freely; `place` reads it again.
- **missing**: concepts from the lexicon he names that no picture covers, with count and first time: ask the user to upload a picture for each one worth showing (or, only if they ask, `fill` has GPT draw it).

## 5. Placement

`place` (and `auto`) prepare `lib-<id>.png` (trimmed to the subject; GPT studio pictures also palette-locked), then
size each picture to fit 420 × 420 (remix 380 × 380, or the beat's `size`) and set it by the caption:

- x: centred on 540 (`side: L` → 330, `R` → 750, or the beat's own `x`), ≥ 24 px from the frame edge;
- bottom edge: the beat's `bottom`, else `--bottom` / the plan's `asset_bottom` (product.json for a batch), else
  **1330** in a fresh edit (the caption pill, top 1262, covers its lower edge) or **1260** in a remix (above the
  burned-in captions, which move from shot to shot: check every snapshot).

The assets are in front of the speaker, so nothing is checked against his cutout: a remix needs no cutout at all.
`place` leaves out a picture with no transparent background or nothing visible and prints a **WARNING** for it.

Both templates render the beats with `assets/asset_motion.js`: grow out of the caption (scale .32 → 1, rising,
sharpening, 0.52 s `back.out`), a glint as it lands, a gentle float, `keys` pop + glint, `breathe` swell, `shake`
shudder, shrink away at `out − 0.30`. The fresh-edit template takes them in its `ILLUS` slot; remixes in beats.json
(`remix_broll.py`).

## 6. The concept lexicon (`assets/concepts.json`)

```json
{"id": "glossy-kidneys", "look": "glossy", "assets": [],
 "subject": "a pair of human kidneys with the ureters running down from them",
 "inner": "the branching renal pelvis and calyces", "tube": "The ureters are smooth tubes ...",
 "triggers": {"darija": ["الكلاوي", "كلاوي", "الحصى", ...], "ar": [...], "fr": ["reins", ...]}}
```

- The triggers are a curated Darija lexicon: a picture gets them by its id, the concept's `assets` list, or its own
  `concept` (setmany). Link an upload to a concept whenever one fits.
- When he names a concept no picture covers, `plan` reports it as MISSING.
- `subject` / `inner` / `tube` (glossy) and `crop` / `marks` / `cutaway` / `action` (flat), or a full `prompt`, are for
  the GPT studio only; a concept without them (immunity, energy, thyroid, hormones) can only be an upload.
- Triggers must be specific. A bare word that has an everyday meaning in a honey ad (البرد cold weather, الضغط press, الحرارة heat, كيلو kilo, الدم, نفسي myself, قريب near, الظهر noon, النيف pride) makes false hits: use a phrase (ضربني البرد, ضغط الدم).
- To add a concept: copy an entry, write 6–12 Darija triggers as Whisper spells them, check with `asset_lib.py search "<word>"`.

## 7. GPT requests (only when the user asks)

The pictures normally come from the user. GPT draws (in the monochrome-orange house illustration style, see
`references/style-identity-guide.md`) only when the user asks for it. All requests run `codex exec` in the GPT
folder (sandboxed, reasoning effort low), the request on stdin, a strict JSON schema for the answer:

- **generate** (`gpt_assets.py generate`, `asset_lib.py fill`): one `image_gen` call per image with the look's two reference images attached, saved to the GPT folder's `generated/` and filed in its library. ~1.5 min each, ≤ 3 in parallel, 15 min timeout. Uses the ChatGPT image allowance.
- **tag** (`asset_lib.py [--lib <lib>] tag [ids] [--all] [--replace]`): no image generation; up to 8 pictures attached per call, GPT looks at them and writes keywords (~1 min for 8). Works on an upload library too. Read-only sandbox.
- Keyword rules sent to GPT: `KEYWORD_RULES` in gpt_assets.py.
- `gpt_assets.py status`: Codex path, version, login, image flag, folder trusted, library counts.

## 8. Fixing things

| symptom | fix |
|---|---|
| an asset on the wrong word | `asset_lib.py --lib <lib> search "<spoken word>"` shows which keyword pulled it; remove that keyword (`set <id> file.json --replace`) or add the word to `STOP` |
| a word he says pulls nothing | `search` it; add the keyword with `set` / `setmany` (merges), or link the picture to a concept |
| `NO-ALPHA` / "no transparent background" | ask the user for a PNG/WebP cut-out of it (or cut it with `scripts/cutout_product.py`), put it in the folder, `index` again |
| the asset covers his chin | lower it: the beat's `bottom`, or `--bottom`; or a smaller `size` |
| the asset covers a burned-in caption (remix) | that beat's `bottom` above the caption, or `side: L` / `R`; or `--busy` that window |
| his hands or the product are right where it lands | `side: L` or `R` for that beat |
| `MISSING` for something that should not be shown | remove the trigger from concepts.json |
| new pictures in the folder aren't used | `asset_lib.py index <folder>` (or `--lib <lib> sync`), then `setmany` |
| "library is locked" | another asset_lib/gpt_assets is writing; a lock older than 2 min is cleared automatically |
| JSON error with a BOM | all asset_lib readers accept UTF-8 with or without BOM; keep writing plain UTF-8 |
