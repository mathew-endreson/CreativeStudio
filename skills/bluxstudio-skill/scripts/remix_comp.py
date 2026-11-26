"""Write a lean /camel composition for already-edited footage: the camel hook->body
transition (whip zoom + blur, warm light sweep right->left, flash, whoosh) at T, nothing
else on top (captions and graphics are already burned into the footage).

    python nf_comp.py <project dir> <join T> <duration> <id>
"""
import pathlib, sys

proj, T, DUR, ID = pathlib.Path(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
html = f"""<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=1080, height=1920">
<!-- /camel remix: new hook + new body from already-edited ads, camel transition at the join. -->
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
  html, body {{ margin: 0; padding: 0; background: #000; }}
  #root {{ position: relative; width: 1080px; height: 1920px; overflow: hidden; background: #000; }}
  .camwrap {{ position: absolute; inset: 0; transform-origin: 50% 32%; }}
  .camwrap video {{ position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }}
  #fx {{ position: absolute; inset: 0; z-index: 20; pointer-events: none; overflow: hidden; }}
  #flash {{
    position: absolute; inset: 0; opacity: 0; mix-blend-mode: screen;
    background: radial-gradient(85% 60% at 50% 38%, rgb(255, 240, 205) 0%, rgb(255, 205, 120) 75%);
  }}
  .sweep {{
    position: absolute; top: -20%; left: 0; width: 520px; height: 140%; opacity: 0; mix-blend-mode: screen;
    background: linear-gradient(90deg, rgba(255,214,120,0) 0%, rgba(255,226,160,0.85) 45%, rgba(255,255,240,0.95) 52%, rgba(255,214,120,0) 100%);
    filter: blur(18px);
  }}
</style>
</head>
<body>
<div id="root" data-composition-id="{ID}" data-start="0" data-duration="{DUR}" data-width="1080" data-height="1920" data-fps="30">
  <div id="camA" class="camwrap">
    <video id="v0" class="clip" src="assets/footage/main.mp4" data-start="0" data-duration="{DUR}" data-media-start="0"
      data-track-index="0" data-has-audio="true" playsinline></video>
  </div>
  <div id="fx">
    <div id="flash"></div>
    <div class="sweep" id="sweep1"></div>
  </div>
  <audio id="s1" class="clip" src="assets/sfx/whoosh-short.mp3" data-start="{T - 0.20:.2f}" data-duration="0.57" data-track-index="3" data-volume="0.32"></audio>
</div>
<script>
  const ID = "{ID}";
  const DUR = {DUR};
  const T_BODY = {T};   // new hook -> new body
  const tl = gsap.timeline({{ paused: true }});
  const cam = "#camA", sw = "#sweep1", flash = "#flash";
  tl.set(cam, {{ scale: 1.0, filter: "blur(0px)", transformOrigin: "50% 32%" }}, 0);
  // camel T1: whip in on the last 0.2 s of the hook, snap out on the body
  tl.to(cam, {{ scale: 1.09, filter: "blur(7px)", duration: 0.20, ease: "power2.in" }}, T_BODY - 0.20);
  tl.fromTo(cam, {{ scale: 1.09 }}, {{ scale: 1.0, filter: "blur(0px)", duration: 0.46, ease: "expo.out", immediateRender: false }}, T_BODY);
  // warm light sweep right -> left + flash
  tl.set(sw, {{ rotation: 16 }}, 0);
  tl.fromTo(sw, {{ x: 1250, opacity: 0 }}, {{ x: -760, opacity: 1, duration: 0.55, ease: "power2.inOut" }}, T_BODY - 0.26);
  tl.to(sw, {{ opacity: 0, duration: 0.10, ease: "none" }}, T_BODY + 0.29);
  tl.fromTo(flash, {{ opacity: 0 }}, {{ opacity: 0.42, duration: 0.06, ease: "none", immediateRender: false }}, T_BODY - 0.04);
  tl.to(flash, {{ opacity: 0, duration: 0.30, ease: "power2.out" }}, T_BODY + 0.02);
  tl.set({{}}, {{}}, DUR);
  window.__timelines = window.__timelines || {{}};
  window.__timelines[ID] = tl;
</script>
</body>
</html>
"""
(proj / "index.html").write_text(html, encoding="utf-8")
print("wrote", proj / "index.html")

