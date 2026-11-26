Use the camel-gpt skill: read `.claude/skills/camel-gpt/SKILL.md`, `.claude/skills/camel-gpt/references/remix.md` ("Remix + animated B-roll in the body" and "GPT library pictures in a remix") and `references/asset-library.md` first (skip what you already read in this session).

# Stage C: the graphics of {{name}} ({{name_ar}}) — mixes {{ids}}

The user ticked these proposals. The app added them to `{{src}}/mixes.json` and is cutting out the speaker. Your part is the B-roll: every body line of these mixes gets its graphic, in SOURCE time, in `{{output}}` (the shape of `_hyperframes/ghaba_src/beats_ghaba_src.json`: `{"_note", "beats": [...], "sfx": [...]}`). `batch.py build` then maps them into each mix with `map_beats.py`, places the library pictures against that mix's own cutout (`asset_lib.py place`) and writes the project with `remix_broll.py`. Nothing is built or rendered here.

## Input

The mixes (segment index: source span [role] transcript):
{{mixes}}

The sources, from `{{src}}/analysis.json` (its `lines` carry the clean wording `said` and the cut points):
{{sources}}

- {{beats_state}}. Keep every beat that is already there (other mixes use them) unless it is wrong; add what these mixes need. A beat another mix already uses on the same source range is reused as it is: do not write a second one for the same words.
- Project assets available as `pack` pictures (`img`): {{assets}}.
- Library pictures: `python .claude/skills/camel-gpt/scripts/asset_lib.py plan {{src}}/work/<k>_words.json --t-body <hook_end> --t-cta <cta_start> --remix --src <k> --matte none --busy <side:a-b ...> --out {{src}}/work/illus_<k>.json` per source these mixes use; read every "why" against the sentence (symptom vs relief, figurative words, false hits) before keeping a beat. `asset_lib.py fill {{src}}/work/illus_<k>.json --max {{gpt_cap}}` draws the MISSING concepts with GPT: at most {{gpt_cap}} drawings for this round, only concepts these ads really show, and look at every new picture (the result lists its path) before using it. If GPT is unavailable, say so and carry on with discs and the jar.
- `python .claude/skills/camel-gpt/scripts/batch.py frames {{src}} <k> <first>-<last>` writes a strip of frames to `{{look}}/` when you need to see what is on screen.

## Rules (remix.md)

- One graphic per idea; alternate sides; at least 0.3 s between an exit and the next entry on the same side; nothing on a side during a burned-in title / card / full-screen B-roll there (`busy`); nothing in a hook segment unless the mix has `hook_beats`; nothing in the CTA.
- Each beat sits at least 0.20 s after the start and ends at least 0.25 s before the end of the body segment that uses it: `map_beats.py` drops anything else, so a beat that straddles a cut never shows.
- A body part, organ or symptom he names is a library picture (`kind: "pack"`, `lib: <id>`, `side`, `in`, `out`, `keys` / `breathe` / `shake`, `labels`; no `img`/`w`/`h`: place resolves them). Quantities, gifts, delivery, lab, origin stay discs (`lab`, `shield`, `people`, `honey`, `truck`, `gift`, `plant`, `research`, `seeds`, `oil`, `combo` ...). A honey quantity or the order line is the jar (`pack` with no `lib`; `ghosts` for a count). An offer photo is `pack` with its `img`.
- Labels follow his words at that moment, in caption spelling (`camel-style.md` §2: digits, "إي بوكس"); `<em>` is the gold word; a counter only for a number he says (`<em class="cnt">0</em>` with `count`, `countAt`, `countDur`); percent labels wrapped as remix.md shows. Never claim what he does not say: no ratings, wilaya counts or organs he did not name.
- `key` / `keys` / `pops` / `fill` land on the key word. `badge` (`check`, `gem`, `ice`, `shield`) only where it fits the claim.
- `sfx`: a `pop.mp3` at .12–.16 on a picture's entry, at most 3 per body, never on a key word. The join whooshes are added by the template.

## Output

1. `{{output}}` (UTF-8 JSON, no comments), following the schema below.
2. `{{notes_out}}` for the app's cards: `{"beats": [{"mix", "t", "side", "graphic", "words"}], "gpt_drawings": [{"path", "prompt"}], "unsure": ["..."]}` — one line per beat and mix, with the words it lands on.

Do not run `batch.py build`, `check` or `render`: the app queues them when this file is valid.

Then reply in a few lines: per mix its beats (time → graphic → words), the library pictures used, the pictures GPT drew for this round, and the wording you were not sure of.

```json
{{schema}}
```
