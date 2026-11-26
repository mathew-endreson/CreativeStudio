Use the bluxstudio-skill: read `.claude/skills/bluxstudio-skill/SKILL.md`, `.claude/skills/bluxstudio-skill/references/remix.md` and `.claude/skills/bluxstudio-skill/references/asset-library.md` first (skip what you already read in this session).

# Stage D: fix `{{id}}` ({{name}})

The app built this mix and found problems. Fix them in the source beats; the app then runs `batch.py build` and `check` again (do not run them yourself).

The mix:
{{mix}}

The problems:
{{problems}}

The last snapshots. Look at them for a picture over a burned-in caption, card or his face, a picture on the wrong word, or a clipped frame edge:
{{snaps}}

The product's pictures, in `{{img}}`, indexed in `{{lib}}`{{bottom_note}}:
{{pictures}}

## Do

- Change only the beats this mix uses in `{{beats}}`. Other mixes share the file: leave their beats alone. Change the mix's `segs` in `{{src}}/mixes.json` only if a cut itself is wrong. Keep the mix id and file name.
- Every beat of this mix is an asset: `{"src", "kind": "asset", "lib", "side", "in", "out", "keys" | "breathe" | "shake", optional "bottom"}`, in source time, using a `lib` of `{{lib}}`. A beat in the old disc / jar style (no `lib`) shows nothing: replace it with a picture that fits his words, or delete it.
- A `place` WARNING means the picture could not be shown (no transparent background, or nothing visible). Use another picture or drop the beat, and say which picture needs a proper cut-out.
- A picture over a burned-in caption: give that beat a `bottom` above the caption's top (the default is {{bottom}} px), or `side: "L"` / `"R"`, or move it to another time inside the same body segment. Over a card or full-screen B-roll: move it out of that window or drop it.
- Lint and snapshot problems: `cd` is not available. Run `npx hyperframes lint` and `npx hyperframes snapshot --at <t,...> --no-end -o .work/snaps` from `{{proj}}`, with the project path given explicitly.
- Times stay frame-exact: a frame number divided by 30, 4 decimals.

## Output

`{{output}}` (UTF-8 JSON), still following the schema below: the mix's beats fixed, everything else as it was.

Then reply in a few lines: what you changed and why, and anything you could not fix.

```json
{{schema}}
```
