# The bluxstudio-skill look — exact spec

Every number here comes from `assets/reference.html` (Timeline 1, approved by the user on 2026-11-16, reworked
on 2026-11-26: the icon discs and jar packshots are gone, the user's own assets animate by the caption, captions
are Liquid Glass) and `assets/asset_motion.js`. When in doubt, open those and copy the block.

## Contents
1. Layer stack
2. Captions (Liquid Glass)
3. Camera
4. Section transitions
5. The user's assets
6. Product shots
7. CTA block
8. Ambient particles
9. Sound
10. What each part of the reference does
11. Placement & framing
12. Gotchas already hit once

---

## 1. Layer stack (z-index)

| z | layer | why |
|---|---|---|
| 1 | `#camA` footage (keeps audio, `data-has-audio="true"`) | |
| 2 | `#mg` gold particles + delivery route | behind the speaker |
| 3 | `#camB` speaker cutout WebM (`muted`, `data-layout-allow-occlusion`) | hides the particles and the route where his head and hands pass |
| 4 | `#assets` the user's pictures | **in front of the speaker**, by the caption, like the editor's own ads |
| 4 | `#shade` vignette + `#grain` 4.5 % (after `#assets` in the page) | the grade sits over the assets too, so they belong to the picture |
| 5 | `#fg` CTA button + arrows | in front, it must be tappable-looking |
| 6 | `#captions` | always readable, over the asset's lower edge |
| 20 | `#fx` flash + light sweeps | transitions over everything |

`#camA` and `#camB` are always animated together (`const cams = ["#camA", "#camB"]`), so the cutout stays glued to
the footage through every zoom and blur. The assets don't zoom with the camera.

## 2. Captions (Liquid Glass)

- One glass pill per 2–4 spoken words (6 max), Thmanyah Sans 900, **52 px**, white; auto-shrinks to fit 900 px (min 38 px).
- Pill: `top: 1262px` (chest height), padding `10px 34px 16px`, gap 15 px, radius 999 px.
- **Liquid Glass, not frosted glass**: a light `backdrop-filter: blur(9px) saturate(210%) brightness(1.12)`, so the
  picture behind stays readable and its colour is boosted; a faint white gradient tint; a 1 px white border.
  - Specular rims as inset shadows: bright top rim (.90), softer bottom rim (.40), side rims, a lens glow under the
    top edge and a refraction band along the bottom.
  - `::before` is the edge refraction: a 1.6 px gradient rim, bright top-left and bottom-right and clear between
    (mask-composite).
  - `::after` is the caustic: a soft light band across the upper half.
  - Words sit at `z-index: 1`, above both.
- Entry: the pill blooms like a drop settling, `scaleX .76 / scaleY .58 / y +24 → 1` in 0.62 s
  `elastic.out(1, 0.7)`, opacity in 0.14 s, a sheen glides across.
  Exit: 0.12 s, it widens and flattens (`scaleX 1.05, scaleY .86, y −12`) as it fades.
- Words sit at opacity .46 and light up on the exact spoken time: opacity 1, scale 1.12, y −5 for 0.11 s, then
  settle with `back.out(2.4)`.
- Key words (numbers, product, the benefit, the action) are gold `#ffc93c`. Usually 1–2 per pill.
- Timing per pill: `in = first word − 0.10`; `out = next pill's first word − 0.10` if the pause is ≤ 0.9 s, else `speech end + 0.40`; last pill holds to the end.
- Text = what he says, in Algerian Darija spelling, digits for quantities ("3 كيلو", "200 غرام", "30 مل"). Brand: **إي بوكس** (label reads EBOX DZ). Honey: **شوك الإبل** (as spoken; the jar label says شوك الجمل). Known Whisper fixes: مع صورة للبارد → معصور على البارد · بوذور → بذور · قرام → غرام · قنبولة → قنبلة · ينعط لكم → ينعطالكم · ونزيد لكم → ونزيدولكم · ويتلقاه → وين تلقاه.

## 3. Camera (`transformOrigin: 50% 32%`, never below scale 1.0)

| moment | move |
|---|---|
| 0 → 0.8 s | 1.16 → 1.08 `expo.out` (settle-in) |
| hook | 1.08 → 1.10 `sine.inOut` |
| x − 0.20 → x | whip 1.10 → 1.17 + `blur(7px)` `power2.in` |
| x → x + 0.46 | snap to 1.00, blur 0, `expo.out` (wide body framing) |
| body | slow push 1.00 → 1.045 |
| strongest body word | punch +0.035 in 0.18 s `power3.out`, ease back over ~1.9 s |
| z − 0.20 → z | punch 1.05 → 1.14 + `blur(7px)` |
| z → z + 0.50 | settle 1.08, blur 0 |
| CTA | slow push 1.08 → 1.11 to the end |

## 4. Section transitions

At **x** (hook → body) and **z** (body → CTA):
- Light sweep: a 520 px warm gold-white band, `blur(18px)`, rotated 16°, `mix-blend-mode: screen`, crosses the frame in 0.55 s starting at cut − 0.26. Hook → body travels right → left (reading direction); body → CTA travels left → right.
- Warm radial flash: peaks .42 (x) / .50 (z) over 0.06 s at cut − 0.04, fades 0.30–0.34 s.
- Camera whip as above. Sound: `whoosh-short` at x − 0.20, `whoosh` at z − 0.18, both volume .32.
- No asset straddles a cut: `asset_lib.py plan` ends each one ≥ 0.25 s before its section ends.

## 5. The user's assets (`asset_motion.js`)

The style of the editor's own ads (the 9wa source ads, Nov 2026): a picture the user uploaded for this product — a
real-looking object on a transparent background (ashwagandha sprig, moon, the jar, a liver) — grows out of the
caption in front of the speaker on the word that names it, floats while he talks about it, and shrinks away.
**No disc, ring, badge, glow, sparkles or label**: the caption is the label.

- **Size and place**: fits in 420 × 420 (remix 380), centred (`side: C`, x 540; `L` 330 / `R` 750 when his hands or
  the product are in the way), bottom edge at **1330** so the caption pill (top 1262) covers its lower edge.
  Remixes: bottom 1260, above the burned-in captions (§11). `asset_lib.py place` writes `w/h/x/top`.
- **In** (from `in`, about 0.25 s before the word): scale .32 → 1, y +80 → 0, rotation −7° → 0, blur 10 → 0, opacity
  0 → 1 in 0.52 s `back.out(1.6)`, transform origin 50% 88% (it rises out of the caption). One light glint crosses
  it as it lands.
- **Hold**: a gentle float, y −12 / rotation 1.8° `sine.inOut` yoyo every 1.5 s. Never a still sticker.
- **Key moves** on the spoken word (from the picture's `motion`):
  - `keys` (shine): a pop to 1.08 and back in 0.28 s plus the glint;
  - `breathe`: a slow swell to 1.07 and back in 1.2 s (lungs, a calm breath, sleep);
  - `shake`: a 0.3 s shudder ±8 px with a −3° tilt (cough, pain).
- **Out** (`out − 0.30`): scale .6, y +36, blur 8, opacity 0 in 0.30 s `power2.in`.
- Soft drop shadow (`0 20px 24px .34` + `0 3px 6px .22`) so it sits on the frame.
- One asset at a time, ≥ 0.3 s between one leaving and the next arriving; 2.4–4 s each (≤ 6 s when he stays on
  the topic, with another key).

## 6. Product shots

The floating jar packshot with ghost copies is gone (Nov 26 2026). When the product itself is the point (the brand
name in the hook, "3 كيلو", the order line), show it the same way as any other asset: the user's own cut-out of the
jar or the offer, uploaded with the other pictures. Never print a jar count.

## 7. CTA block (front layer)

- Gold pill button "اطلب الآن" with a cart icon, `top: 1530px`, enters on "ما عليك غير / تضغط" (−0.35 s) with `back.out(1.8)`.
- Tap on the word "تضغط": button squash .92 → 1, white ripple ring ×2, `click-soft` at volume .40.
- Three white chevrons under it (`top: 1660px`) cascade 4 times from "أسفل الفيديو" to the end.
- If the CTA wording is different (e.g. WhatsApp, comments), keep the same button but change the label/icon to match what he says.

## 8. Ambient particles

18 seeded gold bokeh dots (10–32 px) in the background zones, opacity .25–.60, drifting up 70–180 px over the whole video and breathing. They live behind the speaker; never use `Math.random()` (seeded `rnd()` only).

## 9. Sound

Speech is the mix. Accents only, all from `assets/sfx` (Pixabay licence, no attribution needed):

| sound | volume | when |
|---|---|---|
| whoosh-short | .32 | hook → body transition |
| whoosh | .32 | body → CTA transition |
| pop | .12–.16 | an asset's entry (≤ 3 in the body), never on a key word |
| sparkle | .20 | a "rare / premium / original" asset |
| ping | .13 | the punch word |
| click-soft | .40 | CTA button tap |

Final mix: −15 LUFS integrated, −1 dBFS peak (`scripts/finalize.py`).

## 10. What each part of the reference does

| block | what | Timeline 1 words |
|---|---|---|
| `ILLUS` (filled by `asset_lib.py place`) | the user's assets, animated by `asset_motion.js` | each body part, ingredient or product he names |
| `#route` + `#routeLbl` | dotted route + truck + pins across the top, behind him | التوصيل لجميع الولايات |
| `#order` + `#chev` | button tap + arrows | تضغط في الزر أسفل الفيديو |
| camera punch + `s5` ping | the punch word | قنبلة |

Every other idea gets an uploaded picture or nothing: there are no drawn icons any more. A quantity, a gift or a
delivery promise with no picture stays in the caption (gold key word).

## 11. Placement & framing (1080 × 1920)

- Fresh edit: the asset is centred at chest height, bottom 1330, top ≈ 910 for a square picture. That fits a
  centred talking head (head ≈ x 300–780, y 285–840). In a closer or lower framing where it would reach his chin,
  pass `--bottom` (or a beat's `bottom`) lower, or `size` smaller; where his hands hold the product in the middle,
  move it to `side: L` or `R`.
- Remix: the burned-in captions move from shot to shot (Mix35: y ≈ 1525 in the red room, ≈ 1100 in the shelf shot).
  The default bottom 1260 clears the low ones only. Look at every asset's snapshot and give a beat that covers a
  caption its own `bottom` above that caption, or `side: L` / `R`; a product whose captions always sit high gets
  `asset_bottom` in product.json.
- The asset may cover his hands or chest (that is the editor's look), never his face or a caption.

## 12. Gotchas already hit once

- Whisper's first word after a pause starts up to ~0.4 s early; snap captions to the speech windows from `measure_windows.py`.
- `fromTo` renders its from-state immediately: anything that must stay invisible until later (ripples, tap rings) gets `tl.set(el, {opacity: 0}, 0)` and `immediateRender: false`.
- A CSS `transform` on an element GSAP animates gets folded into GSAP's values; put rotations in the tween (`rotation: 14`) instead of CSS.
- No `backdrop-filter` inside anything that fades or blurs (Chrome makes the parent a backdrop root and the glass goes flat). The caption pill fades itself; its parent `.cap` only scales and moves.
- An uploaded picture without a transparent background shows as a rectangle: `asset_lib.py` flags it (`NO-ALPHA`) and never plans or places it. Ask the user for a PNG/WebP cut-out (or cut it with `cutout_product.py`).
