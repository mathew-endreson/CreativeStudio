Use the camel-gpt skill: read `.claude/skills/camel-gpt/SKILL.md` and `.claude/skills/camel-gpt/references/remix.md` first (skip what you already read in this session).

# Stage E: revise `{{id}}` ({{name}})

The user watched the finished ad (`{{ad}}`) and asks for this change:

{{feedback}}

The mix:
{{mix}}

## Do

- Apply the feedback to the source beats of this mix in `{{beats}}` (schema at the end) and, when the feedback is about a cut, to the mix's `segs` / `body` / `cta` in `{{src}}/mixes.json`. Keep the mix id and its `file_name`: the app rebuilds, checks and re-renders it under the same name (`batch.py build --force`, `check --force`, `render --replace --force`). Do not run those yourself.
- Other mixes share the beats file: change only what this mix uses, or copy a shared beat under a new time if the change must not reach the others.
- If the feedback asks for something the footage does not have (words he does not say, a picture of an organ he does not name), do what the footage supports and say so in `notes`.
- Need to see a frame? `python .claude/skills/camel-gpt/scripts/batch.py frames {{src}} <k> <first>-<last>` writes a strip to `{{src}}/work/look/`. The mix's own timeline is in `{{proj}}/.work/beats.json` (read it, do not edit it: build rewrites it).
- Times stay frame-exact (a frame number divided by 30, 4 decimals).

## Output

`{{output}}` (UTF-8 JSON): `{"changed": ["one line per change, for the user"], "notes": "what you could not do, or were unsure of"}`.

Then reply in a few lines.

```json
{{schema}}
```

The beats file keeps this shape:

```json
{{beats_schema}}
```
