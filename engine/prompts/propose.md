Use the camel-gpt skill: read `.claude/skills/camel-gpt/SKILL.md` and `.claude/skills/camel-gpt/references/remix.md` first (skip this if you already read them in this session).

# Stage B: propose {{count}} new ads for {{name}} ({{name_ar}})

This is steps 3 and 4 of remix mode: pick pairings that read as one argument and do not exist yet, and set their cuts. Nothing is built here. The user reads each proposal as a card, ticks the ones to build, and edits or rejects the others, so a proposal has to be an ad you would build exactly as written.

## Input

- `{{src}}/analysis.json`: per source its `hook_end`, `hook_hold`, `body_start`, `cta_start`, offer group, shoot, busy windows, defects and `lines` (the ad split at its clean cut points, with `said` and `can_open_body`); for the product its `duplicates` and `liftable` hooks. The user has checked it, and the fields in a source's `edited` were set by hand. Use its times. If one looks wrong to you, say so in `notes`; do not quietly cut somewhere else.
- `{{src}}/work/<k>_words.json` and `scan_<k>.json` (silences, editor's cuts, flashes), when you need a cut the lines do not give.
- `python .claude/skills/camel-gpt/scripts/batch.py frames {{src}} <k> <first>-<last>` writes a strip of those frames to `{{look}}/` (frame number in each tile). Use it on every cut whose role changes.
- The B-roll already written for this product, in source time: `{{beats}}`.
- The GPT library: `python .claude/skills/camel-gpt/scripts/asset_lib.py search "<spoken word>"` shows which picture a word pulls; `asset_lib.py list` shows them all.

Ads that already exist (their segments as `source start-end`, holds as `v0` / `v1`). Never propose one of these again, nor the same ad a frame or two apart:
{{existing}}

Each source's own hook + body + CTA is the original ad and exists too, and so does any pairing that `duplicates` in `analysis.json` makes identical to one of the above.

Earlier proposals from the app:
{{earlier}}

A rejected proposal stays rejected. Its reason tells you what the user does not want: apply it to the new ones.

The Ads folder now holds:
{{ads_listing}}

What the user asked for this round:
{{note}}

## The rules (remix.md)

> Only pair a hook with a body from the same group, so the product on the table and the offer stay consistent.

The CTA comes from the same shoot and offer as the body.

> Pick pairings that read as one argument and don't already exist. Several originals share a body.

> Start the body on a self-contained sentence such as "اليوم جبتلكم…" or "هذا اللي راه بين يديا…". Avoid a line that answers its original hook, like "إيه؟…" or "ولكن للأسف…".
> A hook that is only a setup keeps its payoff line, even past 4 s.

> Never let a new hook run through the original hook's flash.

> Cut points: end the hook in the silence after its last word. Up to ~3 frames of a warm or orange flash is fine, since the camel flash covers it.
> If the hook's own flash is near-white, or starts while his last word is still sounding, the picture holds [the last] clean frame until the audio cut, hidden under the whip and blur.

> With only 1 source video, every new ad is a reordering of that one take: give each one a different hook (a testimonial line, the benefit line, a second comment, or a setup + payoff jump cut), and drop filler. Cut on the editor's own camera cuts or on 20 ms-RMS silences, and check the burned caption is blank at each cut. Even when the CTA follows on in the same take, split it into its own segment, so every ad gets the camel T2 into the CTA.

> With only 2 source videos you get just 2 cross pairings. A third angle is a hook lifted from inside a body: a testimonial makes a strong proof hook. Join that hook + the body with that stretch removed + the CTA.

> Re-check every `v0`/`v1` hold when a cut changes role. A hold that the camel T1 flash covered shows plainly once the same cut becomes a jump inside a longer hook: hold the last frame before any colour shift, not the spike. UGC dissolves leave a faint ghost ~5 frames after they look finished, so check the first hook frame at full size. A body that opens on the tail of the previous shot gets `v0` = its first clean shot.

And from the user: no contradiction between the parts of one ad (one source calling it "معجزة" against another saying "ماشي معجزة"), and every ad reads as one argument a viewer can follow from the first word to the order line.

## How an ad is written

An ad is a list of segments `{src, a0, a1, v0, v1}`, in playing order. `a0`/`a1` is the span (its audio and its length); `v0`/`v1` is the clean picture inside it, cloned to fill the span. Times are frame-exact (a frame number divided by 30, 4 decimals).

- **Segment 0 is the hook.** A source's own hook runs from its start to its `hook_end`, with `v1` = its `hook_hold` when there is one. A hook lifted from a body takes the liftable's `a0`/`a1`/`v0`/`v1` and sets `hook_beats: true`: it keeps its source beats and its cutout, so its picture can open the ad. A hook made of two cuts (a setup and its payoff from elsewhere) is two segments: the second is still hook, and it is not in `body`.
- **The body** follows, one segment per unbroken stretch of the source: merge consecutive lines into one segment, and start a new one only where you jump. A body that starts at the top of a source's body has `a0` = that source's `hook_end` and `v0` = its `body_start`. Elsewhere use the lines' own `a0`/`a1`/`v0`/`v1`. When the hook was lifted out of this body, leave that stretch out.
- **The CTA is its own last segment**, and `cta` is its index.
- **`body`** lists the indices of the segments that carry B-roll: the body segments, never segment 0. The CTA's index goes in `body` only when body and CTA are one unbroken take.
- A cut that is not in a silence of 0.12 s or more, on an editor's cut or at a flash will be flagged to the user. If you make one on purpose, say why in the segment's `note`.
- Look at the first and last frames of every segment whose neighbours are new (`batch.py frames`): a tint, a ghost or a stray caption there needs a `v0`/`v1`, or another cut.
- Stay away from a source's defects (a caption typo, a missing caption, a collision) when a clean copy of the same line exists in another source.

For each ad also give:

- **`label`**: the name after "MixNN - ", in the style of the existing ones (`Hook Analyse V7 + Body V5`), and **`key`**, a short slug for the project id (`analyse7-b5`). The app adds the mix number.
- **`angle`**: the ad's angle in one line.
- **`why`**: why hook, body and CTA read as one argument: what the hook promises, how the body pays it, why the order line follows.
- **`risks`**: what could still go wrong on screen or in the argument. An empty list if nothing.
- **`graphics`**: the one graphic each body line (and a lifted hook) would get, in order: a beat already written in the beats file (`existing: true`), a disc from remix.md's list, the jar or the offer photo, a library picture (give its id), or `missing` for a picture GPT would have to draw (at most {{gpt_cap}} per ad). Only what he says, where nothing is burned in (`busy`), nothing in the CTA.

## Output

Write `{{output}}` (UTF-8 JSON, no comments) with the new ads only. Change nothing else: not `mixes.json`, not `proposals.json`, no project, no cutout; only your pictures in `{{look}}/`. Do not build and do not render.

Then reply with a short summary: for each ad its label, its segments, and one line on why it works; then what you were not sure of.

The file must follow this JSON schema:

```json
{{schema}}
```
