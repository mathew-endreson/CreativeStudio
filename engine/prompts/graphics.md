Use the bluxstudio-skill: read `.claude/skills/bluxstudio-skill/SKILL.md`, `.claude/skills/bluxstudio-skill/references/remix.md` ("Remix + animated assets in the body" and "Assets in a remix (planning)") and `.claude/skills/bluxstudio-skill/references/asset-library.md` first (skip what you already read in this session).

# Stage C: the assets of {{name}} ({{name_ar}}) — mixes {{ids}}

The user ticked these proposals and the app added them to `{{src}}/mixes.json`. Your part is the animated assets: the product's own pictures, each one in the body on the word that names it, in front of the speaker by the caption (`camel-style.md` §5). Write them in SOURCE time in `{{output}}` (`{"_note", "beats": [...], "sfx": [...]}`). `batch.py build` then maps them into each mix (`map_beats.py`), places the pictures (`asset_lib.py place --lib {{lib}}`: trimmed PNG, size, `x`, `top`) and writes the project (`remix_broll.py`). A remix needs no speaker cutout. Nothing is built or rendered here.

## Input

The mixes (segment index: source span [role] transcript):
{{mixes}}

The sources, from `{{src}}/analysis.json` (its `lines` carry the clean wording `said` and the cut points):
{{sources}}

The product's pictures, in `{{img}}`, indexed in `{{lib}}` (the app ran `asset_lib.py index` just before this step){{bottom_note}}:
{{pictures}}

- {{beats_state}}.
- `S` below is `.claude/skills/bluxstudio-skill/scripts`. Every `asset_lib.py` command takes `--lib {{lib}}`. Run commands from the project root with explicit paths (no `cd`).

## Do

1. **Keywords first.** Read every picture marked NO KEYWORDS YET and write its keywords into one JSON in `{{src}}/work/` (asset-library.md §3: 6–15 Darija words or short phrases as Whisper spells them, most specific first, never a generic word alone; a few `ar` / `fr`; `motion` `breathe` for lungs / breathing / sleep, `shake` for cough / pain, else none; `concept` when one in `assets/concepts.json` fits). Then run `python S/asset_lib.py --lib {{lib}} setmany <that file>`. Fix a keyword that pulls the wrong picture the same way. A NOT USABLE picture is never planned: name it in `unsure` so the user can replace it with a PNG / WebP cut-out.
2. **Plan each source these mixes use**, in its own time: `python S/asset_lib.py --lib {{lib}} plan {{src}}/work/<k>_words.json --t-body <hook_end> --t-cta <cta_start> --remix --src <k> --busy <a-b ...> --out {{src}}/work/illus_<k>.json`. `--busy` takes each window of the source's busy list where a burned-in photo card at chest height, full-screen B-roll or the phone-mockup CTA is on screen. A title at the top of the frame does not block an asset. Read every "why" against the sentence before you keep a beat. Check symptom vs relief ("يحبس السعال وتولي تتنفس" is breathing lungs, not the cough), and drop figurative words and false hits.
3. **Copy the beats you keep** into `{{output}}` with only these fields: `src`, `kind: "asset"`, `lib`, `side`, `in`, `out`, `keys` / `breathe` / `shake`, and `bottom` when needed. Leave out `img`, `w`, `h`, `x` and `top`: place fills them. Write no labels, discs, jar packs, ghosts, counters or badges. That style is gone, and `remix_broll.py` drops any beat without a picture.
4. **Keep it off the burned-in captions.** They move between shots, so check each beat on the contact sheet or with `python S/batch.py frames {{src}} <k> <first>-<last>` (a strip in `{{look}}/`). The picture's bottom edge sits at {{bottom}} px. Where that shot's caption sits higher, give the beat a `bottom` above the caption's top. Use `side: "L"` / `"R"` when his hands or the product are in the way. It never covers a caption, a card or his face.
5. **MISSING** are the ideas he names that no picture shows. {{draw_rule}}

## Rules (remix.md, camel-style.md §5)

- One asset at a time: at least 0.3 s between one leaving (`out`) and the next arriving (`in`) in the same source. Each stays 2.4–4 s, or up to 6 s with another key when he stays on the topic. The same picture comes back only 6 s or more after it left.
- `in` is about 0.25 s before the first word that names it. The key move (`keys` pop, `breathe` swell, `shake` shudder, from the picture's `motion`) lands on the key word while the picture is on screen.
- Each beat starts at least 0.20 s after the start of the body segment that uses it and ends at least 0.25 s before that segment's end. `map_beats.py` drops anything else. Nothing goes in a hook segment unless the mix has `hook_beats`, and nothing in the CTA: clear everything before the CTA mockup.
- Show only what he says, at the moment he says it. Percent, number, price and gift moments get no picture: the burned-in caption already says them.
- Keep every asset beat already in the file (other mixes use them) unless it is wrong. Reuse a beat another mix already has on the same source range as it is. Older beats (discs, the jar `pack`, labels: no `lib`, or not `kind: "asset"`) show nothing any more. Replace the ones inside these mixes' body segments with asset beats where a picture fits, or delete them. A `lib` that is not in `{{lib}}` stops the build: fix or delete every such beat. To keep a GPT studio picture an older beat used, copy its file into `{{img}}` and `index` again; it keeps its id.
- `sfx`: at most 3 `pop.mp3` per body, each at volume .12–.16 on an asset's entry and never on a key word. The template adds the join whooshes.

## Output

1. `{{output}}` (UTF-8 JSON, no comments), following the schema below.
2. `{{notes_out}}` for the app's cards: `{"beats": [{"mix", "t", "side", "graphic", "words"}], "missing": [{"concept", "words", "src", "t"}], "gpt_drawings": [{"path", "prompt"}], "unsure": ["..."]}`. Write one `beats` line per asset and mix: `t` in the mix's own time, `graphic` = the picture's library id, `words` = what he says on it. List every MISSING idea worth a picture, and the wording or matches you were not sure of.

Do not run `batch.py build`, `check` or `render`: the app queues them once this file is valid.

Then reply in a few lines. Give, per mix, its assets (time → picture → words), the pictures you wrote keywords for, the ideas that have no picture (MISSING) for the user to upload, any picture GPT drew, and what you were not sure of.

```json
{{schema}}
```
