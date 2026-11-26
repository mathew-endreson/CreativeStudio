# Style guide: orange health illustrations

The whole family in one sentence: **single-hue orange health/anatomy
illustrations, one subject, isolated on transparency, no text. Each one is
either a glossy translucent "gel" organ seen from the front, or a soft matte
flat silhouette in side profile with debossed cut-aways or thin dark-brown
line details.**

Contents: reference set · palette · mode A (glossy) · mode B (flat) ·
choosing a mode · composition · prompt templates · worked prompts ·
common failure modes

---

## Reference set (`assets/refs/`, downscaled copies)

| file | mode | subject | canvas | what makes it work |
|---|---|---|---|---|
| `glossy-lungs` | A glossy | lungs + trachea, front view | 1254×1254 | translucent orange candy surface; bronchial tree visible *inside* in darker orange; cream specular streaks along the upper rims; darker toward the base |
| `glossy-bronchial-tree` | A glossy | trachea + bronchi on their own | 1254×1254 | ringed trachea with an open top showing the lumen; branches taper into fine curling twigs; a wet highlight runs along every tube |
| `flat-throat-crosssection` | B flat | head in profile facing right, sagittal cut-away | 1536×1024 | the airway (nasal cavity, mouth, pharynx, trachea rings) is *debossed*: recessed into the silhouette in darker burnt orange with a soft inner shadow, as if pressed into clay or paper |
| `flat-person-coughing` | B flat | man's upper body in profile facing right, fist at mouth | 1536×1024 | detail drawn with thin tapered dark-brown strokes (ear, closed eye, jaw/neck, collar line); a thin transparent gap separates the fist from the face; three short orange dashes show the cough |

The originals are in the project's `product img/` folder (`lugs.webp`,
`lungs 2.webp`, `throat 2.webp`, `toughing .webp`). `product pic.jpg` there is
a product photo and is **not** part of this style.

---

## Palette

Measured from every opaque pixel of the four references (median colour per
luminance band). `finish_asset.py` maps every output pixel onto exactly this
ramp, so treat it as the law:

| role | colours |
|---|---|
| line work, deepest recess | `#632302` `#8A2701` |
| recess walls, deep shadow | `#A83301` `#CB4602` |
| shade side | `#DA4F01` `#F16401` |
| **core body (brand orange)** | **`#FB7201`** |
| lit side | `#FC8603` `#FC9A25` |
| gloss | `#FCAE47` `#FBBE68` `#FBD299` |
| specular streaks (glossy only, small) | `#FBE4C6` `#FCF0E1` |

- Hue stays within 14–38° (median 24–28°), saturation ≈ 100%.
- Median luminance of a finished asset is 120–140. Below that it reads
  muddy-brown, above it reads yellow/washed out.
- **No other hues at all**: no red, pink, yellow, green, blue, grey, black
  outlines, white fills. Darks are brown-orange, lights are cream-orange.
- Light comes softly from the top: lighter at the top, darker toward the
  bottom (and bottom-left on flat silhouettes).

---

## Mode A: glossy gel (organs, tubes, internal anatomy)

- **View**: straight front view, centred, symmetric when the anatomy is
  (lungs, bronchi, kidneys pair, heart roughly).
- **Material**: smooth, translucent, wet-looking orange gummy candy or tinted
  glass. Soft inner glow; thicker parts and edges are deeper orange.
- **Internal structure shows through**: vessels, bronchi and folds appear
  inside as darker orange (`#CB4602`–`#DA4F01`) lines that branch and taper.
- **Tubes** (trachea, oesophagus, vessels) carry regular ring ridges, each
  with its own small highlight; open ends show the lumen as a darker ellipse.
- **Highlights**: cream streaks along upper rims plus a few soft spots.
  Never a big white blown-out area.
- **Edges**: no outline stroke. The silhouette reads by a darker rim and a
  thin rim light.
- Semi-realistic but simplified anatomy: no labels, no cross-hatching, no
  blood, no realistic tissue texture.
- Canvas: **square 1254×1254**.

## Mode B: soft-flat silhouette (people, heads, body regions, symptoms)

- **View**: side profile **facing right**.
- **Shape**: one solid orange silhouette with a soft gradient, lighter at the
  top and deeper at the bottom-left, with a smooth matte finish (a very faint
  grain is fine). No gloss, no outline.
- **Interior detail**, one of two techniques:
  - *debossed cut-away*: recessed areas in `#8A2701`–`#CB4602` with a soft
    inner shadow along their upper edge and rounded corners. Use this for
    cross-sections (airways, sinuses, digestive tract inside the body).
  - *line accents*: a few thin, tapered, calligraphic strokes in `#632302`,
    such as an ear "C", closed or squinting eye, brow, jaw/neck line, collar
    line, finger creases. Few strokes; no full facial features.
- **Overlaps** (hand in front of face, arm over chest) are separated by a
  thin gap of empty background, not by a line.
- **Actions** (cough, sneeze, breath, pain, heat) are 2–4 short orange dashes
  or small arcs radiating from the source.
- Crop people at the chest or shoulders, with a flat or gently curved bottom
  edge. Keep the person generic: no hairstyle detail beyond the silhouette, no
  clothing detail.
- Canvas: **wide 1536×1024**.

---

## Choosing a mode

| subject | mode | canvas |
|---|---|---|
| an organ or anatomy part (lungs, heart, stomach, liver, kidney, intestine, brain, sinuses as an organ) | A glossy | square |
| a tube or branching structure (trachea, bronchi, vessels, nerves) | A glossy | square |
| a person or head doing or feeling something (coughing, sneezing, sore throat, blocked nose, breathing deeply, sleeping, tired, strong) | B flat + line accents | wide |
| a cross-section through a body region showing an internal path (airway, swallowing, sinus drainage) | B flat + debossed cut-away | wide |
| an object outside the reference set (honey drop, herb, leaf, shield, germ) | A glossy, unless it is a person/action | square |

Objects outside the reference set extend the family, so tell the user you
picked a mode for it and why.

---

## Composition

- One subject, centred. It fills about 88% of the limiting side
  (`finish_asset.py --fill 0.88`; the references sit at 81–93%).
- Transparent background. No ground or drop shadow, no glow, no frame,
  badge, circle backdrop, text, labels or watermark.
- On wide canvases the empty space is left and right; don't stretch the
  subject to fill it.

---

## Prompt templates

Image generators rarely output real transparency, so always ask for a **plain
pure white background**. The finisher removes it cleanly. Hex codes in prompts
help most generators stay on palette; the finisher corrects whatever drift
remains.

### Mode A template

```
Semi-realistic 3D medical illustration of {SUBJECT}, straight front view,
centered, a single isolated object. Entirely monochrome vivid orange
(#FB7201): a glossy, translucent orange gel / gummy-candy surface with a soft
inner glow, {INTERNAL DETAIL} visible inside the surface in darker burnt
orange (#CB4602), small cream-white specular highlight streaks along the
upper rims, deeper orange toward the bottom edges. {TUBE DETAIL}
No outline strokes. Plain pure white background, no shadow, no text, no
labels, no other colors.
```

- `{INTERNAL DETAIL}`: e.g. "a branching bronchial tree", "branching blood
  vessels", "soft wavy inner folds".
- `{TUBE DETAIL}`: e.g. "The trachea is a ribbed tube with evenly spaced
  ring ridges and an open top." Leave it out if there is no tube.

### Mode B template

```
Minimal flat health icon illustration: side-profile silhouette of {SUBJECT},
facing right, cropped at the {CROP}. One solid vivid orange (#FB7201) shape
with a soft gradient from lighter orange at the top to deeper orange
(#E85A01) at the bottom left, smooth matte finish, no outline. {DETAIL}
{ACTION} Overlapping parts are separated by a thin gap of empty background.
Plain pure white background, no shadow, no text, no other colors.
```

- `{CROP}`: "shoulders" or "chest".
- `{DETAIL}`, line-accent version: "A few thin tapered dark brown (#632302)
  strokes mark the ear, the closed eyes and the neck line."
- `{DETAIL}`, cut-away version: "A cut-away cross-section shows {PATHS} as
  recessed, debossed channels in dark burnt orange (#A83301) with a soft
  inner shadow, like shapes pressed into clay."
- `{ACTION}`: e.g. "Three short orange dashes radiate from the mouth." Leave
  it out if nothing happens.

Avoid list (add as a negative prompt if the generator supports one):
`text, labels, watermark, multiple objects, scene, background, drop shadow,
glow, red, pink, yellow, blue, green, grey, black outline, photo, realistic
skin, blood`.

---

## Worked prompts

These four rebuild the references. Use them as calibration for new subjects.

**glossy-lungs**: Mode A with SUBJECT "a pair of human lungs with the
trachea", INTERNAL DETAIL "a branching bronchial tree", TUBE DETAIL "The
trachea is a ribbed tube with evenly spaced ring ridges."

**glossy-bronchial-tree**: Mode A with SUBJECT "the trachea and bronchial
tree on its own, without lung tissue, branches spreading left and right and
tapering into fine curling twigs", no internal detail clause, TUBE DETAIL "The
trachea is a ribbed tube with an open top showing the inside."

**flat-throat-crosssection**: Mode B with SUBJECT "a human head and neck",
CROP "base of the neck", DETAIL (cut-away) "the nasal cavity, mouth, throat
(pharynx) and the ringed trachea".

**flat-person-coughing**: Mode B with SUBJECT "a man's upper body coughing
into his raised fist", CROP "chest", DETAIL (line accents) "ear, squinting
closed eye, neck line and collarbone line, finger creases on the fist",
ACTION "Three short orange dashes radiate from the mouth."

New-subject examples:

- *stomach*: Mode A, SUBJECT "a human stomach with the oesophagus entering
  at the top and the duodenum leaving at the lower right", INTERNAL DETAIL
  "soft wavy inner folds (rugae)", TUBE DETAIL "The oesophagus is a smooth
  tube with an open top."
- *sore throat*: Mode B, SUBJECT "a woman's head and shoulders holding her
  throat with one hand, eyes closed in discomfort", CROP "shoulders", DETAIL
  line accents "ear, closed eye, brow, fingers", ACTION "Three small orange
  arcs pulse outward from the throat."
- *sinuses*: Mode B, SUBJECT "a human head", CROP "neck", DETAIL cut-away
  "the frontal and maxillary sinuses and the nasal passage".

---

## Common failure modes

| you see | fix |
|---|---|
| reddish or yellowish result | the finisher normalises hue; if it still looks off, the generator added a second hue (e.g. pink tissue). Re-prompt with "entirely monochrome orange". |
| muddy/brown, median luminance < 115 | `--match-brightness`, or re-prompt with "vivid bright orange" |
| washed out, median luminance > 145 | `--match-brightness`, or re-prompt with "deep saturated orange" |
| highlight at the very edge turned see-through | the white-background cut-out can't tell edge highlights from background: rerun with `--method rembg` (downloads a ~170 MB model on first use, so ask the user first) or re-prompt for "a darker orange rim" |
| text, labels, a backdrop circle or a second object | re-prompt; the finisher can't remove these |
| person facing left | re-prompt with "facing right", or mirror the raw image before finishing |
| glossy look on a person / flat look on an organ | wrong mode in the prompt; check the "choosing a mode" table |
