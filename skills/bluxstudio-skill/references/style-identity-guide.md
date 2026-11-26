# Orange Health Illustrations: Visual Identity Guide

> **For the image model making new assets for the product page.** Read this
> whole guide before you generate anything. Every new image must look as if it
> was made in the same session as the four reference illustrations: same
> colour, same material, same light, same framing. If a request conflicts
> with this guide, follow the guide and say what you changed.

---

## 1. The identity in one sentence

**Health and anatomy illustrations in orange only: one subject per image,
isolated on a transparent background, no text. Each one uses one of two
looks: a _glossy, see-through orange gel_ organ seen from the front, or a
_soft matte orange silhouette_ in side profile with pressed-in cut-aways or
a few thin dark-brown lines.**

---

## 2. Reference images

These four images in `product img/` define the style. When in doubt, match
them.

| file | look | subject | size | what makes it work |
|---|---|---|---|---|
| `lugs.webp` | **Glossy** | lungs and trachea, front view | 1254×1254 | the surface looks like see-through orange candy; the branching bronchial tree shows *inside* in darker orange; cream highlight streaks run along the upper edges; the lungs get deeper orange toward the bottom |
| `lungs 2.webp` | **Glossy** | trachea and bronchial tree on their own | 1254×1254 | the trachea has rings and an open top showing the inside; branches taper into fine curling twigs; every tube has a wet-looking highlight |
| `throat 2.webp` | **Flat** | head in profile facing right, cut away down the middle | 1536×1024 | the airway (nose cavity, mouth, throat, trachea rings) is *pressed in*: recessed into the shape in dark burnt orange, with a soft shadow inside, as if pressed into clay |
| `toughing .webp` | **Flat** | man's upper body in profile facing right, coughing into his fist | 1536×1024 | detail comes from a few thin, tapered dark-brown strokes (ear, closed eye, neck, collarbone); a thin empty gap separates the fist from the face; three short orange dashes show the cough |

`product pic.jpg` is a product photo. It is **not** part of this style, so
never imitate it.

**If your tool accepts reference images**, attach one or two references in
the same look as the asset you're making:

- Glossy assets: `lugs.webp` and `lungs 2.webp`
- Flat assets: `throat 2.webp` and `toughing .webp`

Then add this line to the prompt: *"Match the style of the attached images
exactly (colour, material, lighting, level of detail), but draw only the new
subject described here."*

---

## 3. Colour

The whole set uses **one hue: orange.** These colours were measured from
the references, from darkest to lightest:

| role | hex |
|---|---|
| line work, deepest hollows | `#632302` `#8A2701` |
| hollow walls, deep shadow | `#A83301` `#CB4602` |
| shadow side | `#DA4F01` `#F16401` |
| **main body: the brand orange** | **`#FB7201`** |
| lit side | `#FC8603` `#FC9A25` |
| gloss | `#FCAE47` `#FBBE68` `#FBD299` |
| specular highlights (glossy look only, small) | `#FBE4C6` `#FCF0E1` |

Rules:

- Keep every colour between hue 14° and 38° at full saturation.
- **`#FB7201` dominates.** About half of the subject sits between
  `#F16401` and `#FC8603`.
- Darks are **brown-orange**, never black or grey. Lights are
  **cream-orange**, never pure white, except tiny highlight dots.
- No second colour of any kind: no red, pink, yellow, green, blue, purple,
  grey or skin tones, and no gradients that drift into red or yellow.
- The finished image's overall brightness is mid-bright, the same as
  `#FB7201`. It should never look muddy brown or pale yellow.

---

## 4. Light and material (both looks)

- Soft light from the top (upper left on glossy assets): lighter at the top,
  deeper toward the bottom.
- No shadow on the ground, no floor, no glow or halo, no outline stroke
  around the subject.
- The mood is clean, friendly, premium and medical. Never gory, scary or
  photographic.
- Anatomy is simplified but correct: right proportions and right parts
  connected the right way.

---

## 5. Look A: glossy gel

Use it for organs, tubes, internal anatomy and objects.

- **View**: straight from the front, centred, symmetric when the anatomy is
  symmetric.
- **Material**: smooth, see-through, wet-looking orange gummy candy or
  tinted glass, with a soft glow inside. Thick areas and edges are deeper
  orange.
- **Inner structure shows through the surface**: vessels, airways and folds
  appear as darker orange (`#CB4602` to `#DA4F01`) lines that branch and
  taper.
- **Tubes** (trachea, oesophagus, blood vessels): the trachea has evenly
  spaced rings, each with its own small highlight. Smooth tubes have one
  long highlight stripe. Open ends show the inside as a darker ellipse.
- **Highlights**: cream streaks along the upper edges, a couple of soft
  glossy spots and at most one tiny sharp dot. Never a large blown-out white
  area.
- **Edges**: no outline. The edge shows through a darker rim plus a thin rim
  of light.
- **Never**: labels, cross-hatching, realistic tissue texture, blood, veins
  in other colours.
- **Size**: square, generated at 1024×1024 (finished at 1254×1254).

## 6. Look B: soft flat

Use it for people, heads, body regions, symptoms and actions.

- **View**: side profile, **always facing right**.
- **Shape**: one solid orange silhouette with a soft gradient, lighter orange
  at the top and deeper orange (`#E85A01`) at the bottom left. Smooth matte
  finish; a very faint grain is fine. No gloss and no outline.
- **Inner detail**, using one of two techniques:
  - **Pressed-in cut-away**, for cross-sections such as airways, sinuses or
    swallowing: recessed shapes in `#8A2701` to `#CB4602`, with a soft dark
    shadow along their top edge, a faint light edge along their bottom edge
    and rounded corners, like shapes pressed into clay or thick paper.
  - **Line accents**, for people doing or feeling something: a *few* thin,
    tapered strokes in `#632302`, such as an ear "C", a closed or squinting
    eye, a brow, the jaw or neck line, the collarbone, finger creases. Draw
    no other facial features.
- **Overlaps** (a hand in front of the face, an arm across the body) are
  separated by a **thin gap of empty background**, never by a drawn line.
- **Actions** (cough, sneeze, breath, pain, heat) are shown with 2–4 short
  orange dashes, dots or small arcs coming out of the source.
- **Crop**: people are cut off at the chest or shoulders, with a flat or
  gently curved bottom edge.
- **People** are generic: no detailed hairstyle beyond the silhouette, no
  clothing details, no age or ethnicity cues beyond the silhouette.
- **Size**: wide, 1536×1024.

---

## 7. Which look to use

| subject | look | size |
|---|---|---|
| an organ or body part (lungs, heart, stomach, liver, kidney, intestine, brain) | **Glossy** | 1024×1024 |
| a tube or branching structure (trachea, bronchi, blood vessels, nerves) | **Glossy** | 1024×1024 |
| a person or head doing or feeling something (coughing, sneezing, sore throat, blocked nose, deep breath, sleeping, tired, strong) | **Flat**, line accents | 1536×1024 |
| a cut-away through the body showing an inner path (airway, sinuses, swallowing) | **Flat**, pressed-in cut-away | 1536×1024 |
| an object (honey drop, herb, leaf, shield, germ) | **Glossy**, unless it's a person or an action | 1024×1024 |

Objects aren't in the reference set, so they extend the family. Keep them
just as simple and centred, in the same gel material.

### Short requests (one word or a few words)

When the request is only a subject, such as "Human", "heart" or
"sneezing", **don't ask questions. Fill in the rest yourself:**

1. Pick the look and size from the table above.
2. Use neutral defaults for anything not given:
   - **A person** ("human", "man", "woman") without an action is a generic
     adult in the **flat** look: upper body in calm profile facing right,
     cropped at the chest, with line accents for the ear, closed eye and
     neck line, and no action marks.
   - **An organ** is the **glossy** look: the whole organ, front view, with
     its main inner structure showing through.
   - **A symptom or action** ("cough", "fever", "tired") is a person in the
     **flat** look doing it, with action marks.
3. Fill in the template for that look from section 10, keeping every fixed
   word, and attach that look's reference images (section 2).
4. Name the file `<look>-<subject>` (for example `flat-human.webp`) and
   check it against section 13.

If a word could mean either look (for example "throat" as an organ or a
person), pick the one closest to an existing reference ("throat" becomes a
flat cut-away like `throat 2.webp`) and say which one you chose.

**Example: the request "Human"** becomes this prompt (1536×1024):
```
Minimal flat health icon illustration: side-profile silhouette of an adult
person's upper body standing calmly, facing right, cropped at the chest. One
solid vivid orange (#FB7201) shape with a soft gradient from lighter orange
at the top to deeper orange (#E85A01) at the bottom left, smooth matte
finish, no outline. A few thin tapered dark brown (#632302) strokes mark the
ear, the closed eye and the neck line. Isolated on a transparent background,
no shadow, no text, no other colors.
```

---

## 8. Composition and output

- **One subject** per image, centred.
- The subject fills **about 88%** of the image's height (or width, if that
  runs out first). That leaves an even margin of about 6% around it.
- On the wide 1536×1024 images, the empty space goes left and right. Don't
  stretch the subject to fill it.
- **Background: transparent.** If the tool supports it, request a
  transparent background and PNG or WebP output. If it doesn't, use a
  **plain pure white** background (`#FFFFFF`) with nothing else on it, so it
  can be removed cleanly afterwards.
- **File names**: English kebab-case starting with the look, for example
  `glossy-heart.webp` or `flat-person-sneezing.webp`.

---

## 9. Never

- Text, letters, numbers, labels, arrows, logos, watermarks or signatures.
- More than one subject, scenery, a background shape, a circle or badge
  behind the subject, a frame or a border.
- Shadows on the ground, glows or halos, outline strokes.
- Any colour outside the orange range in section 3, including black and
  pure white fills.
- A photo-real look, skin texture, blood or gore.
- In the flat look: facing left, full faces, detailed clothing or hair, or
  gloss.
- In the glossy look: matte or flat shading, side views of symmetric organs,
  or cartoon faces on organs.

---

## 10. Prompt templates

In each template, replace `{…}` with your text and keep every other word.
The fixed wording is what keeps results on style.

### Look A: glossy

```
Semi-realistic 3D medical illustration of {SUBJECT}, straight front view,
centered, a single isolated object. Entirely monochrome vivid orange
(#FB7201): a glossy, translucent orange gel / gummy-candy surface with a soft
inner glow, {INNER DETAIL} visible inside the surface in darker burnt orange
(#CB4602), small cream-white specular highlight streaks along the upper rims,
deeper orange toward the bottom edges. {TUBE DETAIL} No outline strokes.
Isolated on a transparent background, no shadow, no text, no labels, no
other colors.
```

### Look B: flat

```
Minimal flat health icon illustration: side-profile silhouette of {SUBJECT},
facing right, cropped at the {CROP}. One solid vivid orange (#FB7201) shape
with a soft gradient from lighter orange at the top to deeper orange
(#E85A01) at the bottom left, smooth matte finish, no outline. {DETAIL}
{ACTION} Overlapping parts are separated by a thin gap of empty background.
Isolated on a transparent background, no shadow, no text, no other colors.
```

- `{DETAIL}`, line-accent version: *"A few thin tapered dark brown
  (#632302) strokes mark the {ear, closed eye, neck line, …}."*
- `{DETAIL}`, cut-away version: *"A cut-away cross-section shows {the inner
  path} as recessed, debossed channels in dark burnt orange (#A83301) with a
  soft inner shadow, like shapes pressed into clay."*
- `{ACTION}`: for example *"Three short orange dashes radiate from the
  mouth."* Leave it out if nothing is happening.

If transparency isn't available, replace *"Isolated on a transparent
background"* with *"Isolated on a plain pure white background"*.

**Negative prompt** (if supported): `text, letters, labels, watermark, logo,
multiple objects, scene, background, frame, badge, drop shadow, glow, halo,
outline, red, pink, yellow, green, blue, purple, grey, black, white fill,
photo, realistic skin, blood`

---

## 11. Calibration prompts (rebuilding the references)

Use these to check the setup: the results should look nearly identical to
the reference images.

**`glossy-lungs`** (1024×1024)
```
Semi-realistic 3D medical illustration of a pair of human lungs with the
trachea, straight front view, centered, a single isolated object. Entirely
monochrome vivid orange (#FB7201): a glossy, translucent orange gel /
gummy-candy surface with a soft inner glow, a branching bronchial tree
visible inside the surface in darker burnt orange (#CB4602), small
cream-white specular highlight streaks along the upper rims, deeper orange
toward the bottom edges. The trachea is a ribbed tube with evenly spaced
ring ridges. No outline strokes. Isolated on a transparent background, no
shadow, no text, no labels, no other colors.
```

**`glossy-bronchial-tree`** (1024×1024)
```
Semi-realistic 3D medical illustration of the trachea and bronchial tree on
its own, without lung tissue, branches spreading left and right and tapering
into fine curling twigs, straight front view, centered, a single isolated
object. Entirely monochrome vivid orange (#FB7201): a glossy, translucent
orange gel / gummy-candy surface with a soft inner glow, wet highlights
running along every tube, small cream-white specular highlight streaks,
deeper orange toward the bottom. The trachea is a ribbed tube with evenly
spaced ring ridges and an open top showing the inside. No outline strokes.
Isolated on a transparent background, no shadow, no text, no labels, no
other colors.
```

**`flat-throat-crosssection`** (1536×1024)
```
Minimal flat health icon illustration: side-profile silhouette of a human
head and neck, facing right, cropped at the base of the neck. One solid
vivid orange (#FB7201) shape with a soft gradient from lighter orange at the
top to deeper orange (#E85A01) at the bottom left, smooth matte finish, no
outline. A cut-away cross-section shows the nasal cavity, the mouth, the
throat (pharynx) and the ringed trachea as recessed, debossed channels in
dark burnt orange (#A83301) with a soft inner shadow, like shapes pressed
into clay. Isolated on a transparent background, no shadow, no text, no
other colors.
```

**`flat-person-coughing`** (1536×1024)
```
Minimal flat health icon illustration: side-profile silhouette of a man's
upper body coughing into his raised fist, facing right, cropped at the
chest. One solid vivid orange (#FB7201) shape with a soft gradient from
lighter orange at the top to deeper orange (#E85A01) at the bottom left,
smooth matte finish, no outline. A few thin tapered dark brown (#632302)
strokes mark the ear, the squinting closed eye, the neck line, the
collarbone line and the finger creases on the fist. Three short orange
dashes radiate from the mouth. Overlapping parts are separated by a thin gap
of empty background. Isolated on a transparent background, no shadow, no
text, no other colors.
```

---

## 12. Asset list: ready-to-run batch

Each entry is a complete job. The first four already exist. The rest are
**suggestions**: edit, remove or add entries to match what the page needs,
using the templates in section 10.

```yaml
existing:   # done, use them as references only
  - glossy-lungs              # product img/lugs.webp
  - glossy-bronchial-tree     # product img/lungs 2.webp
  - flat-throat-crosssection  # product img/throat 2.webp
  - flat-person-coughing      # product img/toughing .webp

to_generate:
  - name: flat-person-sore-throat
    look: flat
    size: 1536x1024
    background: transparent
    references: [throat 2.webp, toughing .webp]
    prompt: >
      Minimal flat health icon illustration: side-profile silhouette of a
      woman's head and shoulders gently holding the front of her neck with
      one hand, eyes closed and brow tense in discomfort, facing right,
      cropped at the shoulders. One solid vivid orange (#FB7201) shape with a
      soft gradient from lighter orange at the top to deeper orange (#E85A01)
      at the bottom left, smooth matte finish, no outline. A few thin tapered
      dark brown (#632302) strokes mark the ear, the closed eye, the brow and
      the finger creases. Three small orange arcs pulse outward from the
      throat. Overlapping parts are separated by a thin gap of empty
      background. Isolated on a transparent background, no shadow, no text,
      no other colors.

  - name: flat-person-sneezing
    look: flat
    size: 1536x1024
    background: transparent
    references: [toughing .webp, throat 2.webp]
    prompt: >
      Minimal flat health icon illustration: side-profile silhouette of a
      man's upper body sneezing, head tilted forward, eyes squeezed shut, one
      hand raised near the nose, facing right, cropped at the chest. One
      solid vivid orange (#FB7201) shape with a soft gradient from lighter
      orange at the top to deeper orange (#E85A01) at the bottom left, smooth
      matte finish, no outline. A few thin tapered dark brown (#632302)
      strokes mark the ear, the squeezed eye, the neck line and the finger
      creases. A small burst of short orange dashes and dots sprays forward
      from the nose and mouth. Overlapping parts are separated by a thin gap
      of empty background. Isolated on a transparent background, no shadow,
      no text, no other colors.

  - name: flat-person-breathing-deeply
    look: flat
    size: 1536x1024
    background: transparent
    references: [toughing .webp, throat 2.webp]
    prompt: >
      Minimal flat health icon illustration: side-profile silhouette of a
      woman's upper body breathing in deeply and calmly, chin slightly
      raised, eyes closed, chest open, facing right, cropped at the chest.
      One solid vivid orange (#FB7201) shape with a soft gradient from
      lighter orange at the top to deeper orange (#E85A01) at the bottom
      left, smooth matte finish, no outline. A few thin tapered dark brown
      (#632302) strokes mark the ear, the closed eye and the neck line. Three
      soft curved orange airflow lines flow toward the nose. Isolated on a
      transparent background, no shadow, no text, no other colors.

  - name: flat-sinus-crosssection
    look: flat
    size: 1536x1024
    background: transparent
    references: [throat 2.webp]
    prompt: >
      Minimal flat health icon illustration: side-profile silhouette of a
      human head and neck, facing right, cropped at the base of the neck. One
      solid vivid orange (#FB7201) shape with a soft gradient from lighter
      orange at the top to deeper orange (#E85A01) at the bottom left, smooth
      matte finish, no outline. A cut-away cross-section shows the frontal
      sinus above the eye, the maxillary sinus beside the nose and the nasal
      passage leading back to the throat as recessed, debossed channels in
      dark burnt orange (#A83301) with a soft inner shadow, like shapes
      pressed into clay. Isolated on a transparent background, no shadow, no
      text, no other colors.

  - name: glossy-stomach
    look: glossy
    size: 1024x1024
    background: transparent
    references: [lugs.webp, lungs 2.webp]
    prompt: >
      Semi-realistic 3D medical illustration of a human stomach with the
      oesophagus entering at the top and the duodenum leaving at the lower
      right, straight front view, centered, a single isolated object.
      Entirely monochrome vivid orange (#FB7201): a glossy, translucent
      orange gel / gummy-candy surface with a soft inner glow, soft wavy
      inner folds visible inside the surface in darker burnt orange
      (#CB4602), small cream-white specular highlight streaks along the upper
      rims, deeper orange toward the bottom edges. The oesophagus is a smooth
      tube with an open top showing the inside. No outline strokes. Isolated
      on a transparent background, no shadow, no text, no labels, no other
      colors.

  - name: glossy-heart
    look: glossy
    size: 1024x1024
    background: transparent
    references: [lugs.webp, lungs 2.webp]
    prompt: >
      Semi-realistic 3D medical illustration of a simplified anatomical human
      heart with the aorta and main vessels on top, straight front view,
      centered, a single isolated object. Entirely monochrome vivid orange
      (#FB7201): a glossy, translucent orange gel / gummy-candy surface with a
      soft inner glow, branching coronary vessels visible on and inside the
      surface in darker burnt orange (#CB4602), small cream-white specular
      highlight streaks along the upper rims, deeper orange toward the
      bottom. The vessels on top are smooth tubes with open ends showing the
      inside. No outline strokes. Isolated on a transparent background, no
      shadow, no text, no labels, no other colors.

  - name: glossy-honey-drop        # object: extends the family
    look: glossy
    size: 1024x1024
    background: transparent
    references: [lugs.webp, lungs 2.webp]
    prompt: >
      Semi-realistic 3D illustration of a single plump drop of honey, front
      view, centered, a single isolated object. Entirely monochrome vivid
      orange (#FB7201): a glossy, translucent orange gel surface with a soft
      inner glow, deeper burnt orange (#CB4602) toward the thick base, small
      cream-white specular highlight streaks along the upper left rim and one
      tiny bright highlight dot. No outline strokes. Isolated on a
      transparent background, no shadow, no text, no labels, no other colors.
```

---

## 13. Quality check: accept or regenerate

Check every result on **both a white and a dark background** before
accepting it.

- [ ] One subject, centred, filling about 88% of the image.
- [ ] Only orange colours from section 3: no red, yellow, grey, black or
      white areas.
- [ ] It follows its look's rules: **glossy** means front view, see-through
      gel, highlights and visible inner structure; **flat** means a matte
      silhouette **facing right**, a few dark-brown lines or pressed-in
      cut-aways, and gaps instead of lines between overlapping parts.
- [ ] No text, labels, shadow, glow, outline, frame or background shape.
- [ ] Transparent background with clean edges: no white fringe on dark, no
      holes.
- [ ] Anatomy is plausible, and hands have sensible fingers or a clean fist.
- [ ] Placed next to the four references, it looks like a fifth member of the
      same set.

If any item fails, **regenerate with a corrected prompt** instead of
patching the image. Typical fixes: add *"entirely monochrome orange"* if a
second colour appears; add *"facing right"* if the subject faces left;
remove extra nouns if a second object appears.

---

## 14. Optional finishing step (recommended)

This project has a finishing script that removes a white background, snaps
every pixel to the exact palette in section 3, centres the subject at the
reference size and checks the result:

```powershell
python ".claude/skills/orange-health-assets/scripts/finish_asset.py" "product img/_raw/<name>.png" "product img/<name>.webp" --canvas square
```

Use `--canvas square` for glossy assets and `--canvas wide` for flat ones.
A good result reports a median hue of 24–28°, at least 97% of pixels on the
palette, a median luminance of 120–140 and at most 3% semi-transparent
pixels.
