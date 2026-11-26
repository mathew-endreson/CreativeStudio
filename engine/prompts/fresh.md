Use the bluxstudio-skill: read `.claude/skills/bluxstudio-skill/SKILL.md`, `.claude/skills/bluxstudio-skill/references/camel-style.md` and `.claude/skills/bluxstudio-skill/references/asset-library.md` first (skip what you already read in this session).

# Fresh edit: `{{slug}}`

One clean talking-head footage becomes one ad in the camel style: SKILL.md steps 3 to 10. The app already did:

- step 1: project `{{proj}}`, footage `{{proj}}/assets/footage/{{main}}`, {{duration}} s at {{fps}} fps, `.work/audio.wav`, `.work/sheet.jpg`;
- step 2: {{cutout_state}};
- the Whisper pass of step 3: `{{proj}}/.work/words.json`{{prompt_note}}.

The user set the sections on the timeline:

- hook: 0 → **{{hook_end}}** s (transition 1 lands exactly there)
- body: **{{body_start}}** → **{{cta_start}}** s
- CTA: **{{cta_start}}** s → the end{{product_note}}

The pictures the user gave for this ad (their asset folder) are in `{{assets}}`: {{assets_state}}

`S` below is `.claude/skills/bluxstudio-skill/scripts`. Run commands from the project root with explicit paths (no `cd`, one command per shell call). Every `asset_lib.py` command takes `--lib "{{lib}}"`.

## Do

3. Run `python S/measure_windows.py {{proj}}/assets/footage/{{main}} 0 {{duration}} --thr -34 --gap 0.12`. Anchor the captions to the speech windows: Whisper pulls the first word after a pause early. Write them as spoken Algerian Darija (camel-style.md §2: digits for quantities, "إي بوكس", "شوك الإبل"). Re-run unclear stretches with `transcribe.py --slices`.
4. Index the assets: `python S/asset_lib.py index "{{assets}}"`. Then Read every picture that has no keywords yet and write its keywords into one JSON in `{{proj}}/.work/` (SKILL.md step 4, asset-library.md §3: Darija as Whisper spells it, most specific first, never a generic word alone; `motion` `breathe` / `shake` where it fits; `concept` when one in `assets/concepts.json` fits). Run `python S/asset_lib.py --lib "{{lib}}" setmany <that file>`. A NO-ALPHA picture is never used: name it in `unsure` (the user needs to give a PNG / WebP cut-out).
5. Run `python S/asset_lib.py --lib "{{lib}}" plan {{proj}}/.work/words.json --t-body {{hook_end}} --t-cta {{cta_start}} --out {{proj}}/.work/illus_plan.json` (add `--hook` only when the hook itself names the symptom). Read every "why" against the sentence before you keep a beat. Check symptom vs relief, and drop figurative words and false hits. Edit the plan by hand where needed: delete a beat, change `lib`, `in` / `out` or `keys`, or set `side: L|R`, `bottom` or `size`. MISSING are the ideas he names that no picture shows. {{draw_rule}}
6. Look at `{{proj}}/.work/sheet.jpg`. The assets sit centred at chest height, with their bottom edge at 1330 and the caption pill over it. Check they land on his chest, not his chin. Where he holds the product in the middle, put that beat on `side: L` or `R`.
7. Plan all the beats (SKILL.md step 7: hook, body, CTA; one asset at a time, on the word that names it; nothing in the CTA). Write them into `{{proj}}/.work/beats.md` as time · asset · trigger word.
8. Edit `{{proj}}/index.html` in place (SKILL.md step 8). Set `T_BODY = {{hook_end}}` and `T_CTA = {{cta_start}}`, and fill the `CH` caption array and the punch word. Set the route and CTA timings, changing the HTML and the timeline blocks together. Add the `<audio>` accents: a pop .12–.16 on an asset's entry, at most 3 in the body, never on a key word. There are no disc, jar or label blocks any more. Then run `python S/asset_lib.py --lib "{{lib}}" place {{proj}}/.work/illus_plan.json --project {{proj}}`. It writes the `ILLUS` slot; leave that slot to it. Fix every WARNING and run `place` again.
9. From `{{proj}}`, run `npx hyperframes lint`, then `npx hyperframes snapshot --at <every asset's in + 0.6 and its key time, both transitions, the CTA> --no-end -o {{proj}}/.work/snaps`. Look at the sheets:
   - captions read right-to-left, in order, inside 900 px;
   - each asset appears on its word, sits on his chest (not his chin or face) with the caption over its lower edge, and is gone before the next one;
   - nothing touches the frame edge;
   - the transitions land on {{hook_end}} and {{cta_start}}.
10. From `{{proj}}`, run `npx hyperframes render --fps {{fps}} --quality delivery -o renders/{{slug}}_raw.mp4`. Then run `python S/finalize.py {{proj}}/renders/{{slug}}_raw.mp4 "{{out}}" --sheet {{proj}}/.work/final_sheet.jpg`. finalize.py prints a JSON report (duration, loudness, peak, size, black frames): copy its numbers into the result file.

Rules: SKILL.md "Keep in mind". Keep it light and premium, one asset at a time, each on the word that names it. The particles and the delivery route stay behind the speaker; the assets, captions and CTA button are in front. Never claim what he does not say. The ad keeps the footage's length. An ad with no pictures is fine: it gets captions, the route and the CTA.

## Output

The finished ad goes to `{{out}}`: make its folder if needed, and never overwrite another file. Then write `{{output}}` (UTF-8 JSON) following the schema below. It holds:

- the output path and finalize's numbers;
- the caption count;
- every asset of the ILLUS slot (time → side → library id → the words it lands on);
- the library pictures used;
- the MISSING ideas worth a picture;
- any picture GPT drew (path + prompt);
- the wording you were not sure of.

Then reply in a few lines with the same.

```json
{{schema}}
```
