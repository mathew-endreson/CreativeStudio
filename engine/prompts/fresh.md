Use the camel-gpt skill: read `.claude/skills/camel-gpt/SKILL.md`, `.claude/skills/camel-gpt/references/camel-style.md` and `.claude/skills/camel-gpt/references/asset-library.md` first (skip what you already read in this session).

# Fresh edit: `{{slug}}`

One clean talking-head footage becomes one ad in the camel style: SKILL.md steps 3 to 10. The app did step 1 (project `{{proj}}`, footage `{{proj}}/assets/footage/{{main}}`, {{duration}} s at {{fps}} fps, `.work/audio.wav`, `.work/sheet.jpg`), step 2 ({{cutout_state}}) and the Whisper pass of step 3 (`{{proj}}/.work/words.json`{{prompt_note}}).

The user set the sections on the timeline:

- hook: 0 → **{{hook_end}}** s (transition 1 lands exactly there)
- body: **{{body_start}}** → **{{cta_start}}** s
- CTA: **{{cta_start}}** s → the end{{product_note}}

`S` below is `.claude/skills/camel-gpt/scripts`. Run commands from the project root with explicit paths (no `cd`, one command per shell call).

## Do

3. `python S/measure_windows.py {{proj}}/assets/footage/{{main}} 0 {{duration}} --thr -34 --gap 0.12`. Anchor the captions to the speech windows (Whisper pulls the first word after a pause early) and write them as spoken Algerian Darija (camel-style.md §2: digits for quantities, "إي بوكس", "شوك الإبل"). Re-run unclear stretches with `transcribe.py --slices`.
4. `python S/asset_lib.py sync`, then `python S/asset_lib.py plan {{proj}}/.work/words.json --t-body {{hook_end}} --t-cta {{cta_start}} --out {{proj}}/.work/illus_plan.json`. Read every "why" against the sentence (symptom vs relief, figurative words); edit the plan by hand where needed.
5. `python S/asset_lib.py fill {{proj}}/.work/illus_plan.json --max {{gpt_cap}}` for the MISSING concepts this ad really shows (at most {{gpt_cap}} drawings), then `plan` again. Look at each new picture. If GPT fails: `python S/gpt_assets.py status`, carry on with discs and the jar, and say so. A cap of 0 means this PC has no drawing tool: skip this step and use the library as it is.
6. Look at `{{proj}}/.work/sheet.jpg` and build the alpha sheet of the cutout (SKILL.md step 6) to check the default slots against his head and hands.
7. Plan all the beats (SKILL.md step 7) into `{{proj}}/.work/beats.md` and the disc / jar beats into `{{proj}}/.work/discs.json`.
8. Edit `{{proj}}/index.html` in place (`T_BODY = {{hook_end}}`, `T_CTA = {{cta_start}}`, the `CH` caption array, the punch word, the disc / jar blocks, the audio accents), then `python S/asset_lib.py place {{proj}}/.work/illus_plan.json --project {{proj}} --avoid {{proj}}/.work/discs.json`. Fix every WARNING and run `place` again.
9. From `{{proj}}`: `npx hyperframes lint`, then `npx hyperframes snapshot --at <every key moment, both transitions, the CTA> --no-end -o {{proj}}/.work/snaps`. Look at the sheets: captions right-to-left inside 900 px, graphics behind head and hands, labels visible, transitions on {{hook_end}} and {{cta_start}}.
10. `npx hyperframes render --fps {{fps}} --quality delivery -o renders/{{slug}}_raw.mp4` (from `{{proj}}`), then `python S/finalize.py {{proj}}/renders/{{slug}}_raw.mp4 "{{out}}" --sheet {{proj}}/.work/final_sheet.jpg`. finalize.py prints a JSON report (duration, loudness, peak, size, black frames): copy its numbers into the result file.

Rules: SKILL.md "Keep in mind". One graphic per idea, light and premium, everything behind the speaker except captions and the CTA button. Never claim what he does not say. The ad keeps the footage's length.

## Output

The finished ad at `{{out}}` (make its folder if needed; never overwrite another file), and `{{output}}` (UTF-8 JSON) following the schema below: the output path, finalize's numbers, the caption count, every beat (time → side → graphic → the words it lands on), the library pictures used, the pictures GPT drew (path + prompt) and the wording you were not sure of.

Then reply in a few lines with the same.

```json
{{schema}}
```
