Use the camel-gpt skill: read `.claude/skills/camel-gpt/SKILL.md` and `.claude/skills/camel-gpt/references/remix.md` first (skip what you already read in this session).

# Stage D: fix `{{id}}` ({{name}})

The app built this mix and found problems. Fix them in the source beats, then the app runs `batch.py build` and `check` again (do not run them yourself).

The mix:
{{mix}}

The problems:
{{problems}}

The last snapshots (look at them: a label behind his head, a picture over a burned-in title, a clipped frame edge):
{{snaps}}

## Do

- Change only the beats this mix uses in `{{beats}}` (other mixes share the file: leave their beats alone), and the mix's `segs` in `{{src}}/mixes.json` only if a cut itself is wrong. Keep the mix id and file name.
- A `place` WARNING means the picture is hidden by the speaker or clashes with a burned-in element: move it to the other side, another time inside the same body segment, or drop it. A `no cutout` warning means that segment's range was never cut out: say so in your reply, the app cuts on the next build.
- Lint and snapshot problems: `cd` is not available; run `npx hyperframes lint` and `npx hyperframes snapshot --at <t,...> --no-end -o .work/snaps` with the project path given explicitly, from `{{proj}}`.
- Times stay frame-exact (a frame number divided by 30, 4 decimals).

## Output

`{{output}}` (UTF-8 JSON), still following the schema below; the mix's beats fixed, everything else as it was.

Then reply in a few lines: what you changed and why, and anything you could not fix.

```json
{{schema}}
```
