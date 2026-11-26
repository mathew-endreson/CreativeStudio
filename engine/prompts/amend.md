Use the bluxstudio-skill: read `.claude/skills/bluxstudio-skill/SKILL.md` and `.claude/skills/bluxstudio-skill/references/remix.md` first (skip this if you already read them in this session).

# Change the analysis of {{name}} ({{name_ar}})

The user read `{{output}}` in the app and asks for this change:

{{feedback}}

Apply it to `{{output}}` in place, with Edit where the change is local.

- Change what was asked and what follows from it. Everything else stays as it is, including the fields listed in a source's `edited` (the user set them by hand) and the `edited` lists themselves.
- If the change needs a fact from the footage, look before you write it: the transcripts and scans are in `{{src}}/work/`, and `python .claude/skills/bluxstudio-skill/scripts/batch.py frames {{src}} <k> <first>-<last>` writes a strip of frames to `{{look}}/`.
- If the request contradicts what the footage shows, do what the footage supports and say so in your reply.
- Times stay frame-exact (a frame number divided by 30, 4 decimals).

## Output

`{{output}}` (UTF-8 JSON, no comments), still following the schema below. No other file changes except your pictures in `{{look}}/`. Do not render.

Then reply in a few lines: what you changed, and anything you were not sure of.

```json
{{schema}}
```
