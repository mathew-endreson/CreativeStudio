# EBOX DZ asset studio

This folder is the GPT side of the EBOX DZ asset pipeline. Claude sends image
requests here through the local `gpt-assets` tool, and the user may also type
requests directly. Every request is for an illustration in one fixed style.

## Rules for every image request

1. Follow `style/style-identity-guide.md`. It is the only allowed style:
   monochrome orange health/anatomy illustrations, either glossy see-through
   gel organs (square) or soft matte silhouettes facing right (wide); one
   subject; transparent background; no text.
2. Generate with the built-in `image_gen` tool. Do not use the image CLI
   fallback, an API key, or drawing with SVG/HTML/Python.
3. Use the matching images in `style/refs/` as style references (glossy:
   `glossy-*.png`, flat: `flat-*.png`). Match their colour, material and
   lighting, and draw only the requested subject.
4. Ask for a transparent background and keep the alpha channel.
5. If the request is only a word or two ("Human", "heart"), use section 7
   "Short requests" of the guide instead of asking questions.
6. If a request contains a ready-written prompt, use it exactly as written.
7. Save each final image as PNG in `generated/`, named `<look>-<subject>.png`
   (for example `generated/glossy-heart.png`). Never overwrite a file; add
   `-2`, `-3` instead.
8. Reply with the saved path(s) and the prompt you used.

`.gpt-assets/` holds request logs written by the tool. Leave it alone.
