---
name: bluxstudio-skill
description: Edit a talking-head EBOX DZ ad in the "camel" house style (Liquid Glass captions in Algerian Darija, hook / body / CTA with light-sweep zoom transitions, rendered with HyperFrames at -15 LUFS) and animate the pictures the user uploads for the product (herbs, organs, a moon, the jar, the offer) in front of the speaker, by the caption, on the word that names them, the way the editor's own ads do. Matches what the speaker says (Algerian Darija, Arabic, French) to each picture's keywords. Also remixes finished ads (new hook + body) with the same animated assets, and, only when asked, has the user's ChatGPT/Codex app draw a missing picture. Use it whenever the user types /bluxstudio-skill, asks for a camel edit, a remix, "animate the assets", B-roll pictures on an ad, or wants pictures matched to what the speaker says. It contains everything /camel does (fresh edits and remixes).
argument-hint: <footage> the hook end at x · body y to z · CTA z to the end · <assets folder>
---

# /bluxstudio-skill — camel ad edit + the user's animated assets

One skill, two halves that talk to each other locally:

- **camel**: the house edit. HyperFrames composition, Liquid Glass Darija captions, hook → body → CTA transitions,
  gold particles and the delivery route behind the speaker, the CTA button. Every number is in
  `references/camel-style.md`; the template is `assets/reference.html`.
- **assets**: the pictures the user uploads for this product (transparent cut-outs of real-looking objects). Each
  one gets keywords; `scripts/asset_lib.py` finds them in the word-timed transcript and places them **in front of
  the speaker, by the caption**, where `assets/asset_motion.js` animates them: grow out of the caption, float, a pop
  or swell on the key word, shrink away. No discs, rings, badges or labels: that motion-graphic style is gone
  (Nov 26 2026). The caption is the label.

The link is the upload folder's **`library.json`**: every picture with the words a speaker would say for it
(`darija`, `ar`, `fr`, `en`) and a motion (`breathe`, `shake`, `shine`):

```
uploads/*.png ─► asset_lib index ─► library.json ◄─ asset_lib setmany (keywords you write after looking)
                                         │
words.json ─────────────────────► asset_lib plan ─► illus_plan.json ─► asset_lib place ─► index.html ILLUS (fresh edit)
                                         │ MISSING: ask the user for that picture          or .work/beats.json (remix)
```

Details of matching, plan fields and placement: `references/asset-library.md`. Run commands from the project root
(`SH-101126 EBOX YASSINE`); `S=.claude/skills/bluxstudio-skill/scripts` below. Every `asset_lib.py` command takes
`--lib <upload folder>/library.json`.

## Input

```
/bluxstudio-skill @"CHaouk el Djamal/Ready to edit Footage/Footage 05.mov"
the hook end at 2.80s
body 2.80s to 21.40s
CTA 21.40s to the end
assets: CHaouk el Djamal/assets
```

- **x** is where the hook ends: transition 1 (hook → body) lands exactly on it.
- **y → z** is the body. y is normally x; if later, the gap is part of the transition.
- **z** is where the CTA starts: transition 2 lands on it, the CTA runs to the end.
- **assets**: the folder of pictures for this product. Missing → ask for it (an ad with no assets is fine if the
  user says so: captions, route and CTA only).
- Footage or any time missing → ask before doing anything. Footage that is already edited (burned-in captions) → remix mode, `references/remix.md`.

## Workflow

### 1. Set up the project

```bash
python $S/new_project.py "<footage path>" <slug>
```

Short slug from the footage name (`footage-05`). It creates `_hyperframes/<slug>/` (must be inside `_hyperframes/` so `npx hyperframes` finds its install), normalises the footage to 1080×1920 with ≤ 1 s keyframes, writes `index.html` from this skill's reference (with `asset_motion.js` pasted in and an empty `ILLUS` slot for the assets), the 16 kHz wav and a contact sheet in `.work/`, and puts the local matte model in the HyperFrames cache.

### 2. Start the speaker cutout (background, ~5 min per 30 s on CPU)

From `_hyperframes/<slug>/`:

```bash
npx hyperframes remove-background assets/footage/main.mov -o assets/footage/main_cutout.webm --quality best
```

Use the footage's real extension (the setup script prints it; `main.mp4` when re-encoded). Do steps 3–5 meanwhile. The cutout keeps the gold particles and the delivery route behind his head and hands; the assets are in front and don't need it.

### 3. Transcribe and time every word

```bash
python $S/transcribe.py _hyperframes/<slug>/.work/audio.wav --out _hyperframes/<slug>/.work/words.json
python $S/measure_windows.py _hyperframes/<slug>/assets/footage/main.mov 0 <duration> --thr -34 --gap 0.12
```

Whisper pulls the first word after a pause up to ~0.4 s early: anchor captions to the speech windows. Re-run unclear stretches with `--slices a-b c-d`. Write captions as spoken Algerian Darija (`references/camel-style.md` §2): digits for quantities, "إي بوكس", "شوك الإبل". For a non-honey product pass `--prompt` with its key words (the Tanafous run used "خلطة الجهاز التنفسي، الكحة، الربو، الحساسية، الرئتين، البلغم").

### 4. Index the user's assets

```bash
python $S/asset_lib.py index "<assets folder>"
```

It writes `<assets folder>/library.json`, one entry per picture, and lists the ones with no keywords and any
`NO-ALPHA` picture (no transparent background: it would show as a rectangle, so it is never used; ask the user for a
PNG/WebP cut-out, or cut it with `cutout_product.py`). Then **look at every picture** (Read it) and write one JSON:

```json
{"moon": {"keywords": {"darija": ["في الليل", "الليل", "تنوم مليح", "النوم", "ترقد"], "ar": ["الليل", "النوم"],
          "fr": ["la nuit", "sommeil"], "en": ["night", "moon"]}, "motion": "breathe"},
 "ashwagandha-root": {"keywords": {"darija": ["الاشواغاندا", "اشواغاندا"], "fr": ["ashwagandha"]},
                      "concept": "glossy-ashwagandha-root"}}
```

```bash
python $S/asset_lib.py --lib "<assets folder>/library.json" setmany <scratch>/kw.json
```

Darija as Whisper spells it, most specific first, never a generic word alone (`references/asset-library.md` §3).
`concept` links a picture to `assets/concepts.json`, so it also answers to that concept's curated triggers.
`motion`: `breathe` for lungs / breathing / sleep, `shake` for cough / pain, else leave it (a pop + glint).
`asset_lib.py --lib … tag` has GPT write the keywords instead (~1 min for 8) if the user prefers.

### 5. Ask the library what he talks about

```bash
python $S/asset_lib.py --lib "<assets folder>/library.json" plan _hyperframes/<slug>/.work/words.json --t-body <x> --t-cta <z> --out _hyperframes/<slug>/.work/illus_plan.json
```

The plan prints one line per asset beat — time, picture, motion key, and **why** (the words heard, the keyword they matched, score) — then `skipped` and `MISSING` concepts (things he names that no picture shows). Body only by default; `--hook` also allows the hook when the hook itself names the symptom.

Read every "why" against the sentence before keeping a beat — the matcher knows words, not meaning:
- **Symptom vs relief.** "يحبس السعال وتولي تتنفس" is the cure: show breathing lungs, not the coughing figure.
- **Figurative or wrong words**: drop the beat. A recurring false hit goes into the stoplist or out of the keywords (`references/asset-library.md`).
- **MISSING**: tell the user which ideas have no picture; they upload one (then `index` + `setmany` + `plan` again) or skip it. Only if they ask, `asset_lib.py fill` has GPT draw it in the house orange style ("The GPT side" below).

Edit `illus_plan.json` by hand when needed (delete a beat, change `lib`, `in`/`out`, `keys`; `side: L|R`, `bottom`, `size` to move one).

### 6. Look at the framing

Open `.work/sheet.jpg`. The assets sit centred at chest height (bottom 1330, the caption pill over their lower edge). Check that this lands on his chest, not his chin; where he holds the product in the middle, plan that asset on `side: L` or `R`. Once the cutout exists you can build an alpha sheet for the route and particles:

```bash
ffmpeg -y -c:v libvpx-vp9 -i assets/footage/main_cutout.webm -vf "select='not(mod(n\,120))',alphaextract,scale=216:384,tile=6x1" -fps_mode passthrough -frames:v 1 .work/alpha.png
```

### 7. Plan all the beats

Map the transcript onto the three sections:
- **Hook (0 → x):** the promise in the captions; the product as an asset on the brand or first product word if the user gave its cut-out. A symptom-led hook ("عندك الكحة؟") may open on that picture (`--hook`).
- **Body (x → z):** each thing he names that has a picture gets it ~0.25 s before its first word, one at a time; the key move (pop, swell, shudder) lands on the key word. Quantities, gifts and prices with no picture stay in the captions as gold key words. One punch word gets a camera punch.
- **CTA (z → end):** the delivery route, the button tap + arrows. No assets.
- Never claim what he doesn't say: no ratings, percentages, wilaya or jar counts, no organ he didn't name.

Write the plan (time · asset · trigger word) in `.work/beats.md`.

### 8. Build `index.html`

Edit the copied reference in place: `T_BODY = x`, `T_CTA = z`, the `CH` caption array, the punch word, the route and CTA timings (HTML and timeline blocks together), the `<audio>` accents (a pop .12–.16 on an asset's entry is fine, ≤ 3 in the body, never on a key word). Then write the assets:

```bash
python $S/asset_lib.py --lib "<assets folder>/library.json" place _hyperframes/<slug>/.work/illus_plan.json --project _hyperframes/<slug>
```

It trims each picture into `assets/img/lib-<id>.png`, sizes it (≤ 420 × 420), centres it by the caption and writes the `ILLUS` array. Any **WARNING** (a picture left out) needs a fix before rendering. Re-running replaces the previous assets; nothing else in `index.html` is touched.

Shortcut when nothing needs a human eye in between: `python $S/asset_lib.py --lib <lib> auto _hyperframes/<slug>/.work/words.json --project _hyperframes/<slug> --t-body <x> --t-cta <z>` = plan → place. Still read its plan lines.

### 9. Check before rendering

From the project folder:
- `npx hyperframes lint` — "file too large" and "duplicate img" warnings are expected; `missing_local_asset` for `main_cutout.webm` means step 2 hasn't finished.
- `npx hyperframes snapshot --at <every asset's in + 0.6 and key time, both transitions, CTA> --no-end -o <scratch dir>` and look at the contact sheets.

Verify: captions read right-to-left in order and stay inside 900 px; each asset appears on its word, sits on his chest (not his chin or face) with the caption over its lower edge, and is gone before the next one; nothing at the frame edge; the transitions land on x and z. Zoom one caption (`--zoom "x,y,w,h"`) to check the glass.

### 10. Render, finish and deliver

```bash
npx hyperframes render --fps <fps> --quality delivery -o renders/<slug>_raw.mp4
python ../../.claude/skills/bluxstudio-skill/scripts/finalize.py renders/<slug>_raw.mp4 "<output>" --sheet .work/final_sheet.jpg
```

`<output>` is the `Edited Ads` folder beside the footage's folder, `<footage name> - Edited.mp4` (`CHaouk el Djamal/Ready to edit Footage/Footage 05.mov` → `CHaouk el Djamal/Edited Ads/Footage 05 - Edited.mp4`); if that name holds a different earlier edit, add ` v2`. `finalize.py` matches −15 LUFS behind a −1 dBFS limiter, reports size/codec/loudness/peak/black frames and writes a 4-frame sheet — look at it. Send the video; in the reply list the beats (time → asset → words), the ideas that had no picture (MISSING), and wording you weren't sure of.

## Remix mode

Finished ads with burned-in captions ("a new hook with a new body", Tanafous, thyroid mixes): follow `references/remix.md` — phase check, hook-flash scan, offer groups, `remix_join.py` / `multi_join.py`, `remix_comp.py`, and for assets `remix_broll.py`. The assets go in with `plan --remix --busy <a-b for cards / B-roll>` and `place --beats <project>/.work/beats.json`. Burned-in captions move from shot to shot: an asset must never cover one (move that beat's `bottom`, or `side`).

A product with several finished ads is a batch, `_hyperframes/<slug>_src/`, and `scripts/batch.py` runs every mechanical step of it for any product:

```bash
python $S/batch.py prepare|transcribe|scan <src>      # copies + phase fix, transcripts, flashes / cuts / silences / titles / sheets
python $S/batch.py build|check|render <src> [ids]     # the mix projects (no speaker cutout needed), lint + snapshots, the ads
python $S/batch.py status|verify <src>                # what exists and the next mix number; specs and beats against disk
python $S/batch.py cuts|frames|match-ads|import <src> # cut points vs the scan; a close look at frames; renamed ads; hand-made batches
```

You write the judgment into `analysis.json` (hook end, body start, CTA start per source), `mixes.json` (the ads: segments, `body`, `cta`, `hook_beats`) and `beats_<slug>_src.json` (the assets in source time); the product's pictures go in `<slug>_src/img/` with `"asset_lib": "img/library.json"` in product.json. The formats and rules are in `references/remix.md`, "A batch of remixes". Do not write a new `build_mixes.py` per product. Camel Studio (`camel-studio/`) drives the same commands. Beats in the old disc / jar style are dropped by `remix_broll.py` with a note.

## The GPT side (only when the user asks)

The pictures normally come from the user. When they ask GPT to draw one (a MISSING concept, or "make me a liver
picture"), the user's ChatGPT/Codex desktop app draws it in the house monochrome-orange illustration style
(glossy gel organs, flat silhouettes facing right; a customer's own brand colours when the folder carries a
`brand.json`, see Brand below) in `C:\Users\EL ASSLI\Documents\ChatGPT\asstets tool ebox`. No API key: `scripts/gpt_assets.py` drives the app's `codex exec` with its built-in `image_gen`.

- **Folder**: `AGENTS.md` and `style/` (guide + `refs/`) keep GPT on style; `generated/` holds GPT's PNGs; `.gpt-assets/` the request logs; `library.json` its keyword index (the default library when no `--lib` is given). The 9owa `orange-health-assets` tool shares this folder: never delete or rename what's in it.
- **Brand**: a library folder with a `brand.json` (CreativeStudio's Library on a customer PC, Settings → Brand) is drawn in that brand instead of orange. `scripts/brand_guide.py apply <folder>` renders its `AGENTS.md`, `style/style-identity-guide.md`, re-coloured `style/refs/` and `style/brand-ramp.json` (the palette lock's ramp); `gpt_assets.py` applies it before every drawing and `asset_lib.py` (`fill` prompts, `place` palette lock) follows it by itself. Write prompts from THAT folder's guide then, never from `references/`. The owner's GPT asset studio folder has no `brand.json` and stays orange, word for word.
- **Draw what's missing**: `python $S/asset_lib.py fill <plan.json> --max 3` (prompts from `assets/concepts.json`, ≤ 3 in parallel, 1–4 min each, uses the user's ChatGPT image allowance), then plan against the GPT library (no `--lib`) or copy the PNG into the upload folder and `index` it. Look at each new picture before using it.
- **One picture**: `python $S/gpt_assets.py generate --name <look>-<subject> --look glossy|flat --prompt-file p.txt` (or `--subject "..."`); prompts from `references/style-identity-guide.md` §10.
- **Connection**: `python $S/gpt_assets.py status`. If GPT fails (logged out, allowance used up, Codex app moved): quote the error, carry on without that picture, tell the user. Never fall back to an API key.
- `scripts/contact_sheet.py` and `scripts/finish_asset.py` check or fix an orange-style picture made elsewhere. Optional MCP server: `gpt_assets.py serve`.

## Keep in mind

- Light and premium: small captions, one asset at a time, each on the word that names it. A busy stretch loses an asset; assets don't shrink to fit two.
- The speech is the ad. Sound accents stay quiet (`camel-style.md` §9) and never sit on a key word.
- Assets illustrate what he says, at the moment he says it. The library only finds words: the meaning check in step 5 is yours.
- An asset never covers his face or a caption (fresh: the pill sits over its lower edge on purpose; remix: above the burned-in caption).
- Re-render, don't patch: changes go into `index.html` / `illus_plan.json`, then steps 8–10 run again.
- All motion lives in the GSAP timeline; asset motion in `assets/asset_motion.js` only (both templates paste it in); no Tailwind or CSS transitions (why: `references/remix.md`, "Smoother transitions").
- Improve this skill rather than `/camel` or `orange-health-assets`: it is the combined, self-contained copy.
