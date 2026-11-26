# Remix mode, remix B-roll and smoother transitions

Copied from `/camel` (Nov 2026) with paths pointed at this skill, then moved to the asset style (Nov 26 2026:
no icon discs or jar packshots; the user's own pictures animate in front of the speaker, by the caption). Read it
when the footage is a set of finished ads (captions and graphics already burned in) or when the user asks for
assets / B-roll on a remix. Planning the assets for a remix is at the end.

## Remix mode: footage that is already edited

Sometimes the footage is a set of finished ads, with captions and graphics already burned into the picture (for example `New Footage/عسل شوك الجمل - V1…V10`), and the user asks for "a new hook with a new body". Camel captions and B-roll on top would double up with what's already there. Remix instead:

0. **Check the audio phase first.** Some finished ads ship with the stereo channels phase-inverted (the thyroid-mix V1/V2, Nov 2026): each channel is about −15 dB, but L+R is about −51 dB. Whisper then hears silence and outputs "شكرا للمشاهدة" or "اشتركوا في القناة", and phone speakers that sum to mono nearly lose the voice. Test it with `ffmpeg -i x.mp4 -af "pan=mono|c0=0.5*c0+0.5*c1,astats" -f null -`. If the mono sum is more than ~20 dB below one channel, fix the source to dual-mono first (`-af "pan=stereo|c0=c0|c1=c0"`) and tell the user the originals have the problem. Scan each source for 1-frame black glitches too (finding one at luma 0 is a sign of a bad export), and patch it with `freezeframes` before joining.
1. **Transcribe every video once**, keeping word times. Find each hook end: these edits put a few-frame flash (frame-difference spike plus brightness) at the end of the hook. Scan the first ~10 s, not just 3–5 s. V3's hook runs to 6.4 s ("…اليوم جبتلكم صديق الكبد"), and the user corrected a cut that ignored this.
   - Everything before a video's own flash is hook. Its body starts right after that flash, on the first word after it.
   - Never let a new hook run through the original hook's flash.
   - Find silences of 0.12 s or more as candidate cut points.
2. **Group the videos by offer and table setup.** In Nov 2026 there were two groups:
   - **Offer A:** 1 kg + 100 g seeds, two jars. Videos V1, V2, V3, V4, V7.
   - **Offer B:** 3 kg + 200 g seeds + 30 ml oil, many jars. Videos V5, V6, V8, V9, V10.
   Only pair a hook with a body from the same group, so the product on the table and the offer stay consistent.
3. **Pick pairings that read as one argument and don't already exist.** Several originals share a body; for example V1, V2 and V7 share one.
   - Start the body on a self-contained sentence such as "اليوم جبتلكم…" or "هذا اللي راه بين يديا…". Avoid a line that answers its original hook, like "إيه؟…" or "ولكن للأسف…".
   - A hook that is only a setup keeps its payoff line, even past 4 s.
4. **Cut points:** end the hook in the silence after its last word. Up to ~3 frames of a warm or orange flash is fine, since the camel flash covers it.
   - If the hook's own flash is near-white, or starts while his last word is still sounding (V8 does both), add a 6th argument to `remix_join.py`: the time just before that flash. The picture then holds that clean frame until the audio cut, hidden under the whip and blur.
   - Start the body after its flash or on a silence, then:
   ```bash
   python .claude/skills/bluxstudio-skill/scripts/remix_join.py "<hook video>" <hook end> "<body video>" <body start> <scratch>/join.mp4
   python .claude/skills/bluxstudio-skill/scripts/new_project.py <scratch>/join.mp4 mixNN-hX-bY
   python .claude/skills/bluxstudio-skill/scripts/remix_comp.py _hyperframes/mixNN-hX-bY <hook end> <whole frames/30> mixNN-hX-bY
   ```
   `remix_comp.py` writes a lean `index.html`. It has only the camel hook → body transition at the join (whip zoom + blur, warm light sweep right → left, flash, whoosh), and nothing else on top.
   **With only 1 source video** (the thyroid S2V4 testimonial ad, Nov 2026, 36 s, no hook flash, just hard camera cuts), every new ad is a reordering of that one take: give each one a different hook (a testimonial line, the benefit line, a second comment, or a setup + payoff jump cut), and drop filler. Cut on the editor's own camera cuts (scene-score spikes with no brightness jump) or on 20 ms-RMS silences, and check the burned caption is blank at each cut. Even when the CTA follows on in the same take, split it into its own segment and pass it as `--cta`, so every ad gets the camel T2 into the CTA and the jump-cut zoom resets to 1.0 before the phone mockup. The mixes (`mixes.json`) and `beats_s2v4_src.json` are in `_hyperframes/thyroid_src/`.
   **With only 2 source videos** you get just 2 cross pairings. A third angle is a hook lifted from inside a body: a testimonial ("البارح برك بعثتلنا وحدة…") makes a strong proof hook. Join that hook + the body with that stretch removed + the CTA using `scripts/multi_join.py <spec.json> <out.mp4>`, which handles any number of frame-exact segments. Each segment has `a0/a1` for its span and optional `v0/v1` for a clean picture range, cloned to fill. Use that clone to hide a flash, a stray caption from a removed sentence, or the hook's own title. Run it with `--alpha` and the per-source cutout webms to build the joined cutout. This lets you cut each source out ONCE (V1 63 s ≈ 18 min, V2 24 s ≈ 7 min) instead of once per remix. Write the beats once in source time and map them per remix with `scripts/map_beats.py` (`--body <segment indices>`, `--cta K`). A jump cut inside the hook becomes `t_jumps`, a 1.0 → 1.06 cut-zoom. A new body → CTA join becomes `t_cta`, the camel T2 (punch + blur, sweep left → right, flash .50, plus a whoosh at T − 0.18 in sfx). `remix_broll.py` reads both.
5. **Render and finalize** as in step 8, saving to the `Ads` folder beside the footage as `MixNN - Hook Vx + Body Vy.mp4`. Then check a 5-frame strip around each join: −0.5, −0.1, +0.12, +0.6 and +2 s.

If the user wants the full camel look on this material, it has to be rebuilt from clean, uncaptioned footage (for these, `New Footage/Timeline 2.1.mov`).

## A batch of remixes: `scripts/batch.py`

Several finished ads of one product turned into several new ads is one folder, `_hyperframes/<slug>_src/`, and one script. `batch.py` does every mechanical step above for any product; the judgment (where a hook ends, which pairings read as one argument, which graphic a line gets) stays with you and goes into three JSON files. Camel Studio (`camel-studio/`) runs these same commands, so a rule changed here changes the app too.

```bash
B=.claude/skills/bluxstudio-skill/scripts/batch.py        # <src> = the folder, or just its slug (ghaba)
python $B prepare <src>              # step 0: 48 kHz copies <k>.mp4, phase check + dual-mono fix, black-glitch patch
python $B transcribe <src> [keys]    # step 1: one Whisper load, work/<k>_words.json, the product's whisper_prompt
python $B scan <src> [keys]          # step 1: hook-flash candidates (first 10 s), the editor's cuts, silences >= 0.12 s,
                                     #         burned-in title boxes, a 1 fps contact sheet -> work/scan_<k>.json, sheet_<k>.jpg
python $B cut <src> [ids] --plan      # NOT NEEDED any more: assets sit in front of him, so no speaker cutout (--force cuts anyway)
python $B build <src> [ids]          # join spec, picture join, the project, map_beats + hook beats, place, remix_broll
python $B check <src> [ids]          # lint + snapshots at every beat's key moment -> <project>/.work/snaps
python $B render <src> [ids]         # render + finalize into the Ads folder, join strips, .work/final_report.json
python $B status <src>               # what exists, and the next mix number
python $B verify <src> [ids]         # batch.py's specs and beats against the files on disk (nothing runs)
```

| file in `<slug>_src/` | what | written by |
|---|---|---|
| `product.json` | `slug`, `name`, `name_ar`, `whisper_prompt`, `product_dir`, `ads_dir`, `id_prefix`, `sources: {k: {file, copy?}}`, `beats_file`, `project_assets: [{from, to}]` (files copied into every project), `place` (run `asset_lib.py place`), `asset_lib` (the upload folder's library.json, e.g. `img/library.json`), `asset_bottom` (px, when this product's burned-in captions sit high), `alpha_all` | you / the app |
| `analysis.json` | per source: `hook_end`, `body_start`, `cta_start`, offer group, set, busy windows, defects; the liftable lines | the judgment step |
| `proposals.json` | candidate ads with their angle, why, risks | the judgment step |
| `mixes.json` | the ads to build: `{id: {name, file_name, segs: [{src, a0, a1, v0, v1, text}], body: [], cta, hook_beats}}` | you / the app |
| `beats_<slug>_src.json` | the B-roll in source time (a mix may name its own with `beats_file`) | you |
| `cut/manifest.json` | `{k: [{file, f0, f1}]}`: cutout frame 0 is source frame `f0` | `cut` |

- **`segs`**: `a0`/`a1` is the span (audio and length), `v0`/`v1` the clean picture range cloned to fill it. `body` lists the segments that carry B-roll and `cta` the CTA segment. When body and CTA are one take, the CTA index is in `body` too (Tanafous `body: [1, 2], cta: 2`). `hook_beats: true` means segment 0 is a hook lifted from a body: it keeps its source beats and its cutout.
- **No cutouts any more.** The assets sit in front of the speaker, so `build` makes only the picture join (no `joinA_*.webm`, no `main_cutout.webm`) and `cut` does nothing without `--force` (it still succeeds, so a pipeline that runs it keeps going). The old cutouts in `cut/` stay as a record.
- **`build`** keeps a join whose spec did not change, so a beats-only fix rebuilds in seconds. It writes `.work/build.json` with the `place` warnings; fix every one before rendering.
- **`render`** never writes over an ad that exists: `--replace` is for a revision of that same ad. The file appears in the Ads folder only once it is complete.
- **Ids are never reused.** `status` prints the next mix number, one past every number a mix, a project folder or an ad file of this product has used. A mix with `locked: true` (imported, or finished) is not rebuilt or re-rendered without `--force`.
- The three batches made by hand (`ghaba_src`, `tanafous_src`, `thyroid_src`) were converted with `batch.py import`; their `build_mixes.py`, `cut_bodies.ps1` and `render_finish.ps1` stay as a record and are no longer the way to add an ad. `verify` shows all 29 of their mixes come out of `batch.py` with the same join specs and beats.

### Remix + animated assets in the body

When the user asks for assets / B-roll ("liver pic or something") on a remix, keep the remix and add the user's own
pictures, animated in front of the speaker in the body only, the way the editor's ads do it
(`references/camel-style.md` §5).

1. **Get the pictures.** Ask the user for the product's pictures if the batch has none: transparent PNG / WebP
   cut-outs of real-looking objects (the herbs, a moon for sleep, a liver, the jar, the offer). Put them in
   `<slug>_src/img/`, then:
   ```bash
   python $S/asset_lib.py index _hyperframes/<slug>_src/img
   ```
   Look at every picture (Read it) and write its keywords in one JSON, linking it to a concept of
   `assets/concepts.json` when one fits (`"concept": "glossy-liver"` gives it the curated Darija triggers), then
   `python $S/asset_lib.py --lib _hyperframes/<slug>_src/img/library.json setmany <scratch>/kw.json`.
   Set `"asset_lib": "img/library.json"` in product.json. A picture listed `NO-ALPHA` needs a proper cut-out
   (`scripts/cutout_product.py`, or ask the user).
2. **Make a 1 fps contact sheet of the remix** (`batch.py scan` does it per source) and note every burned-in element:
   - their top titles;
   - photo cards at chest height;
   - full-screen B-roll (lab footage, anatomy);
   - the phone-mockup CTA;
   - **where the burned-in captions sit in each shot**: they move (Mix35: y ≈ 1525 in the red room, ≈ 1100 in the
     shelf shot), and an asset must never cover one.
   Leave the cards, B-roll and mockup moments alone (`--busy`). The assets go centred above the captions (default
   bottom 1260); a shot with high captions needs that beat's `bottom` lower than its caption's top, or `side: L` / `R`.
   A product whose captions are always high gets `asset_bottom` in product.json.
3. **Write the beats in source time** (`beats_<slug>_src.json`, see "Assets in a remix" below for planning them):
   `{"src": "v3", "kind": "asset", "lib": "<id>", "side": "C", "in": 12.4, "out": 15.1, "keys": [12.8]}`, with
   `breathe` / `shake` instead of `keys` for lungs / a cough. `map_beats.py` shifts every time into remix time, and
   `asset_lib.py place` (run by `batch.py build`) fills `img`, `w`, `h`, `x`, `top`. One asset at a time, on the
   spoken word; clear everything before their CTA mockup.
   - **Percent or number moments** have no picture: the burned-in caption already says them.
   - Beats from before Nov 26 2026 (`oil`, `seeds`, `battery`, `heart`, `people`, `liver`, the jar `pack` …) have no
     picture: `remix_broll.py` drops them with a note. Replace them with assets when an old batch gets new ads.
4. **Generate and check:** `batch.py build`, then `batch.py check` (lint + a snapshot at each asset's key moment).
   Look at every snapshot: the asset must not cover a burned-in caption, a card or his face. Then render and
   finalize. One remix by hand: `python .claude/skills/bluxstudio-skill/scripts/remix_broll.py <project> <beats.json>`
   after `place`. Save the result as `MixNN - … - Brolls.mp4` next to the plain remix.

## Smoother transitions (and why not Tailwind)

In Nov 2026 the user asked to switch to Tailwind CSS "for more smooth transitions". Tailwind doesn't make motion smoother, so explain that and keep plain HTML/CSS + GSAP:
- HyperFrames renders each frame on its own, seeking to its timestamp, so motion must be a function of time. Its docs say Tailwind (the v4 browser runtime from `hyperframes init --tailwind`) is "for static layout and style; timing stays in GSAP".
- Tailwind's `transition-*` / `duration-*` / `ease-*` classes are CSS transitions, which can't be seeked, so in a render they snap instead of animating. Its `animate-*` classes are infinite `@keyframes` loops, and HyperFrames needs finite ones.
- Porting the templates would only change how styles are written; the video would look the same.

When transitions need to feel smoother, use these levers instead. **As of 2026-11-19 they are proposed, not yet tested.** Try them on one short ad, compare with the current render, time the render (motion blur takes ≥ 32 samples per frame), and only then bake the approved values into `assets/remix_broll_template.html`, `assets/reference.html` and `assets/asset_motion.js` and update this section:
1. **Render at 60 fps** (`npx hyperframes render --fps 60 …`). The zoom, sweep and graphics get twice the frames; the footage itself stays 30 fps.
2. **Turn on motion blur:** `data-motion-blur="on"` on `#root` (shutter defaults to 240°, `data-motion-blur-shutter` changes it). Then run `npx hyperframes check` for `motion_blur_*` warnings. Fast moves get a real shutter smear instead of stepping. The whip's flat `filter: blur(7px)` can then be lighter. `render --page-motion-blur off` renders without it, for a comparison.
3. **Soften the timing.** HyperFrames' motion guide says arrivals land on long tails, and entrances that are too snappy read as glitches.
   - Whip into a join: 0.20 → ~0.28 s (`power3.in`).
   - Settle after a join: 0.46 → ~0.6 s (`expo.out`).
   - Asset entrances: `back.out(1.6)` → `back.out(1.2)` or `expo.out`.
   - Exits: 0.30 → ~0.45 s.

   In the remix template these values live in the T1/T2 block; the asset entrances and exits are in `assets/asset_motion.js`.

## Assets in a remix (planning)

The assets are ordinary beats with a library id, so they drop into any remix.

1. Transcribe the remix (or each source once) and plan in that timeline:
   ```bash
   python .claude/skills/bluxstudio-skill/scripts/asset_lib.py --lib _hyperframes/<slug>_src/img/library.json plan <words.json> \
       --t-body <join> --t-cta <cta join> --remix --busy 12.0-15.5 22.7-26.9 --out _hyperframes/<id>/.work/illus_plan.json
   ```
   `--busy` blocks a window while a burned-in card, full-screen B-roll or the CTA mockup is there (from the contact
   sheet / `remix_title_scan.py`). Read every "why" against the sentence, and every MISSING: ask the user for a
   picture of what is worth showing (GPT draws one only if they ask: `fill`).
2. Many sources + `map_beats.py` (`batch.py build` does the per-mix part): plan each source's own transcript in
   source time (`plan <k>_words.json --t-body <its hook end> --t-cta <its CTA> --remix --src <k> --busy <…>`), then
   copy the beats you keep — just `src`, `kind`, `lib`, `side`, `in`, `out`, `keys`/`breathe`/`shake`, any `bottom` —
   into `beats_<slug>_src.json`, shaped so each sits ≥ 0.20 s inside and ≥ 0.25 s before the end of the body segment
   that uses it (`map_beats.py` drops anything else). Per mix, `batch.py build` runs `map_beats.py` →
   `asset_lib.py place <beats.json> --project <mix> --beats <beats.json> --lib <asset_lib>` → `remix_broll.py`.
3. One remix by hand: `python .claude/skills/bluxstudio-skill/scripts/asset_lib.py --lib <lib> place .work/illus_plan.json --project _hyperframes/<id> --beats _hyperframes/<id>/.work/beats.json`
   merges them (re-running replaces earlier asset beats), then `remix_broll.py` as usual.
