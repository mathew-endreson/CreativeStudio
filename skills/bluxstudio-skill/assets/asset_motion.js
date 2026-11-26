/* Animated assets for bluxstudio-skill ads. One file for both templates: new_project.py pastes it into a fresh edit's
   index.html (reference.html) and remix_broll.py into a remix's (remix_broll_template.html), where the page says
   / *ASSET-MOTION* /. Tune the motion here, nowhere else.

   The style is the editor's own ads (9wa source ads, Nov 2026): a picture the user uploaded for this product grows
   out of the caption, in FRONT of the speaker at chest height, on the word that names it; it floats while he talks
   about it, then shrinks away. No disc, ring, badge or label: the caption is the label.

   A beat (asset_lib.py place fills img / w / h / x / top):
     {img, w, h, x, top, in, out, breathe?: [t], shake?: [t], keys?: [t]}
     breathe = a slow swell (lungs, a calm breath), shake = a short shudder (cough, pain),
     keys    = a pop with a light glint across the picture (he names it again, the benefit lands).
   in = when it starts growing (about 0.25 s before the word), out = when it is gone. */
(function () {
  const CSS = `
    #assets { position: absolute; inset: 0; pointer-events: none; direction: ltr; }
    .asset { position: absolute; opacity: 0; visibility: hidden; transform-origin: 50% 88%; }
    .asset .afloat, .asset .apic { position: absolute; inset: 0; }
    .asset .apic { transform-origin: 50% 62%; }
    .asset img { display: block; width: 100%; height: 100%; object-fit: contain;
      filter: drop-shadow(0 20px 24px rgba(0,0,0,0.34)) drop-shadow(0 3px 6px rgba(0,0,0,0.22)); }
    .asset .aglint { position: absolute; inset: 0; overflow: hidden; pointer-events: none; mix-blend-mode: screen;
      -webkit-mask-size: 100% 100%; mask-size: 100% 100%; -webkit-mask-repeat: no-repeat; mask-repeat: no-repeat; }
    .asset .aglint i { position: absolute; top: -15%; left: 0; width: 36%; height: 130%;
      background: linear-gradient(90deg, rgba(255,255,255,0), rgba(255,255,255,0.55), rgba(255,255,255,0)); }`;
  const style = document.createElement("style");
  style.textContent = CSS;
  document.head.appendChild(style);

  const BOX = 420, BOTTOM = 1330;   // fallbacks only: asset_lib.py place writes w / h / x / top

  function mount(layer, beats) {
    return beats.map((b) => {
      const W = b.w || BOX, H = b.h || BOX;
      const x = b.x != null ? b.x : Math.round(540 - W / 2);
      const top = b.top != null ? b.top : (b.bottom || BOTTOM) - H;
      const n = document.createElement("div");
      n.className = "asset";
      n.style.cssText = `left:${x}px; top:${top}px; width:${W}px; height:${H}px;`;
      n.innerHTML = `<div class="afloat"><div class="apic"><img src="${b.img}" alt="">`
        + `<div class="aglint" style="-webkit-mask-image:url('${b.img}'); mask-image:url('${b.img}')"><i></i></div>`
        + `</div></div>`;
      layer.appendChild(n);
      return n;
    });
  }

  function glint(tl, el, t) {
    tl.fromTo(el, { xPercent: -170 }, { xPercent: 340, duration: 0.8, ease: "power2.inOut", immediateRender: false }, t);
  }

  function animate(tl, beats, nodes) {
    beats.forEach((b, i) => {
      const n = nodes[i];
      const fl = n.querySelector(".afloat"), pic = n.querySelector(".apic"), gl = n.querySelector(".aglint i");
      const tIn = b.in, tOut = b.out - 0.30;
      tl.set(gl, { xPercent: -170, rotation: 14 }, 0);
      // in: grows out of the caption, rising and sharpening (the editor's ~0.4 s scale-up, with a soft overshoot)
      tl.fromTo(n, { autoAlpha: 0, scale: 0.32, y: 80, rotation: -7, filter: "blur(10px)" },
        { autoAlpha: 1, scale: 1, y: 0, rotation: 0, filter: "blur(0px)", duration: 0.52, ease: "back.out(1.6)" }, tIn);
      // hold: a gentle float, so it is never a still sticker
      const hold = tOut - (tIn + 0.5), period = 1.5;
      if (hold > 0.6) {
        const reps = Math.max(0, Math.floor(hold / period) - 1);
        tl.fromTo(fl, { y: 0, rotation: 0 },
          { y: -12, rotation: 1.8, duration: Math.min(period, hold), ease: "sine.inOut", yoyo: true, repeat: reps,
            immediateRender: false }, tIn + 0.5);
      }
      const keys = b.keys || [], breathe = b.breathe || [], shake = b.shake || [];
      if (!keys.length) glint(tl, gl, tIn + 0.42);       // one light pass as it lands
      keys.forEach((k) => {
        tl.fromTo(pic, { scale: 1 }, { scale: 1.08, duration: 0.14, ease: "power2.out", yoyo: true, repeat: 1,
          immediateRender: false }, k);
        glint(tl, gl, k);
      });
      breathe.forEach((t) => {
        tl.fromTo(pic, { scale: 1 }, { scale: 1.07, duration: 0.6, ease: "sine.inOut", yoyo: true, repeat: 1,
          immediateRender: false }, t);
      });
      shake.forEach((t) => {
        tl.fromTo(pic, { x: 0 }, { x: 8, duration: 0.05, ease: "sine.inOut", yoyo: true, repeat: 5,
          immediateRender: false }, t);
        tl.fromTo(pic, { rotation: 0 }, { rotation: -3, duration: 0.15, ease: "power2.out", yoyo: true, repeat: 1,
          immediateRender: false }, t);
      });
      // out: shrinks back toward the caption and fades
      tl.to(n, { autoAlpha: 0, scale: 0.6, y: 36, filter: "blur(8px)", duration: 0.30, ease: "power2.in" }, tOut);
    });
  }

  window.CamelAssets = { mount, animate };
})();
