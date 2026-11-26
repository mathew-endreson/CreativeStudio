Use the camel-gpt skill: read `.claude/skills/camel-gpt/SKILL.md` and `.claude/skills/camel-gpt/references/remix.md` first.

# Stage A: analyze the finished ads of {{name}} ({{name_ar}})

This is steps 0 to 2 of remix mode in `remix.md`, for the batch folder `{{src}}`. The mechanical work is already done (48 kHz copies, transcripts, scans, contact sheets). Your part is the judgment: for every source, where its hook ends, where its body and its CTA start, which offer and shoot it belongs to, what is burned into its picture, what is wrong with it, and which of its lines could open another ad.

The next stage pairs hooks and bodies from what you write here and the cuts go into real ads, so a hook end that is 0.3 s off, or a flash you did not see, ends up on screen. Look at the frames before you decide.

## Input

- Product: `{{src}}/product.json`. Prepare report (phase, black frames): `{{prepare}}`.
- Sources:
{{sources}}

What the user told the app about this product:
{{known}}

Values the user set by hand in the app. They win over what you would choose:
{{keep}}

Each `scan_<k>.json` has:
- `flashes`: brightness jumps. The hook-flash candidates are the ones with `in_hook_window` (first 10 s) and `kind: "flash"`; `white` means near-white.
- `cuts`: the editor's own cuts (a frame-difference spike with no brightness jump).
- `black`: black frames. `silences`: every silence of 0.12 s or more, with its `quietest` spot.
- `titles`: burned-in boxes found by colour, `[t0, t1, x0, y0, x1, y1, kind]` in 1080×1920 pixels. They are candidates: the scanner misses pale titles and reads warm backgrounds as orange.
- `sheet`: the contact sheet, one frame per second, 10 per row.

To look at frames (the contact sheet is too small to judge a flash or read a caption):

```
python .claude/skills/camel-gpt/scripts/batch.py frames {{src}} <k> 196-203
python .claude/skills/camel-gpt/scripts/batch.py frames {{src}} <k> 300-420 --every 30 --width 540 --crop 0:1000:1080:520
```

It prints each frame's luma and frame difference and writes a strip to `{{look}}/` with the frame number in each tile's corner. Read the picture it names. `--crop x:y:w:h` with `--width 540` is for reading a burned-in caption or title; move the crop to where this edit puts them.

## What to find for every source

The rules are remix.md's. The ones that decide this stage:

> Find each hook end: these edits put a few-frame flash (frame-difference spike plus brightness) at the end of the hook. Scan the first ~10 s, not just 3–5 s. V3's hook runs to 6.4 s, and the user corrected a cut that ignored this.
> Everything before a video's own flash is hook. Its body starts right after that flash, on the first word after it.
> Never let a new hook run through the original hook's flash.

> If the hook's own flash is near-white, or starts while his last word is still sounding, [use] the time just before that flash. The picture then holds that clean frame until the audio cut.

> V1's tint starts 2 frames before the luma spike, so hold the last frame before any colour shift, not the spike. UGC dissolves leave a faint ghost ~5 frames after they look finished. A body that opens on the tail of the previous shot gets `v0` = its first clean shot.

> With only 1 source video (no hook flash, just hard camera cuts): cut on the editor's own camera cuts or on 20 ms-RMS silences, and check the burned caption is blank at each cut.

> Group the videos by offer and table setup. Only pair a hook with a body from the same group, so the product on the table and the offer stay consistent.

> Start the body on a self-contained sentence. Avoid a line that answers its original hook, like "إيه؟…" or "ولكن للأسف…". A hook that is only a setup keeps its payoff line, even past 4 s.

For each source, in this order:

1. **Hook end** (`hook_end`, `hook_flash`, `hook_hold`). Take the flash candidates in the first 10 s and check them against the transcript: the last hook word ends before the flash and a new idea starts after it. Then look at the frames from 3 before the flash to 4 after it. `hook_end` is the audio cut, in the silence after the hook's last word, at the flash. If the flash is near-white, or the tint starts while he is still speaking, set `hook_hold` to the last clean frame's time. No flash at all: the hook ends on the editor's cut or the silence where the opening idea ends; say so in `notes`.
2. **Body start** (`body_start`): the first clean frame after the flash, where the tint and the previous shot's caption are gone. It is on the first word after the flash.
3. **CTA start** (`cta_start`): the cut before the order line ("وإذا حبيت تدير طلبية", "أطلب الآن", the phone mockup), in the silence before its first word.
4. **Hook kind**: a claim, a question, a setup that needs its payoff (`hook_needs_payoff`), a testimonial, a symptom.
5. **Lines** (`lines`): the whole ad split at its clean cut points, in order, from 0 to the end. A cut point is a silence of 0.12 s or more (use its quietest spot), an editor's cut, or the frame after a flash. Give each line its role, and `v0` / `v1` when its first or last frames are not clean. Mark `can_open_body` on the body lines a body could start on under another hook. Each line carries its words twice:
   - `text`: the transcript exactly as Whisper wrote it, slips included («يأتي من مغصن تعشاجها»). It is kept for keyword matching: do not correct it.
   - `said`: what he actually says, in clean spoken Algerian Darija, the way a caption would write it (`camel-style.md` §2: digits for quantities, "إي بوكس") («يأتي من غصن الأشجار»). Fix Whisper's slips from the burned-in caption and the sense. Keep his words and his Darija: nothing added, nothing turned into standard Arabic. This is what the user reads in the app.
6. **Busy windows** (`busy`): every moment a graphic behind the speaker would clash with something burned in: top titles (a two-line title fills both sides), photo cards, full-screen B-roll, the phone-mockup CTA. Start from `titles`, then check each on the contact sheet and by eye; add what the scanner missed, drop what is only a warm background.
7. **Defects** (`defects`): what the prepare report and the scan flag (phase-inverted original, black frames, a fade-in at the start with the first clean time), and what you see: a typo in a burned-in caption (quote it; read the captions of a few lines per source at `--width 540`), a stray caption or a dissolve ghost at a cut point.
8. **Offer group and shoot**: what is on the table and what he says the offer is; the place, the clothes, the set. Two sources share a group only if both match.

Then, for the product:

- **`offer_groups`** and **`duplicates`**: sources that share a hook or a body (same words at the same times) are duplicates of each other; say which part they share.
- **`liftable`**: the lines that could open another ad. Testimonials, and self-contained claims that work as a hook (in earlier batches: the anemia line, the price and rarity line, the fake honey found by the lab). Each needs source times at clean cut points, its `text` and `said` (as for a line), a one- or two-word Latin label for the ad name, and why it works.

Times are frame-exact: a frame number divided by 30, with 4 decimals (199 / 30 = `6.6333`).

## Output

Write `{{output}}` (UTF-8 JSON, no comments). Nothing else may change: no other file in the batch folder except your pictures in `{{look}}/`, no project, no render. Do not render.

Then reply with a short summary: per source its hook end, body start and CTA start with one line of reasoning each, the liftable lines, and what you were not sure of.

The file must follow this JSON schema (the descriptions say what each field means):

```json
{{schema}}
```
