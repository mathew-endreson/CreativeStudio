Use the darijadz skill (Algerian Darija). Invoke it with the Skill tool if it is listed; otherwise read `{{skill}}/SKILL.md`, `{{skill}}/references/writing-system.md` and `{{skill}}/references/code-switching.md`. When you are unsure of a spelling, Grep `{{skill}}/references/lexicon.md` and `{{skill}}/references/verbs.md` for the word instead of reading those big files whole.

# Correct the Darija of Whisper's transcripts: {{name}}

Whisper (local, large-v3-turbo) has listened to these recordings. You never hear the audio: you correct Whisper's text, you do not invent it.

{{files}}

Each draft has `segments` with `id`, `start`, `end`, `raw` (Whisper's text), `doubtful` (the words Whisper itself was least sure of) and `lint` (darija_lint findings on Whisper's text). Product and key words that may be said: {{hints}}.

## For every segment, write what the speaker actually said, spelled the way Algerians write Darija

- Keep the speaker's words and their order. Fix spelling and clear mishearings only. Never paraphrase, translate, summarise, add words or "improve" the grammar.
- Change a فصحى-looking word only when it is clearly Whisper's spelling of a Darija word (Whisper writing هذه where Algerians say and write هادي is a spelling fix; الآن and دروك are different words, so الآن stays الآن). If the speaker really said the فصحى word, keep it.
- French or English words go in Latin letters, except the loanwords the darijadz guide writes in Arabic letters (كوموند، نورمال، ديجا…). Brand and product names as the product writes them (إي بوكس).
- A number the speaker says goes in digits (3 علب، 2000 دج، 100 غرام). Never add a number nobody said: "كيلو" alone stays "كيلو".
- Keep Whisper's punctuation light: a comma or a full stop where the speaker pauses, nothing more.
- Use the neighbouring segments as context: it is one recording.
- If you can't tell what a word was, keep Whisper's version and list it in `unsure`.
- If a segment is only noise, music or a typical Whisper hallucination ("اشترك في القناة", subtitle credits nobody said), set `text` to "" and say why in `note`.
- `note` is a short English remark, or "".

## Output

Write `{{output}}` (UTF-8 JSON, no comments) with one entry per transcript key above and every segment id of each draft, even when Whisper was right (then copy its text):

```json
{"transcripts": {"<key>": {"segments": [{"id": 0, "text": "...", "unsure": [], "note": ""}]}}}
```

For a long transcript, write the file in parts with Edit rather than one giant Write.

Then check it with darija_lint:

```
python {{skill}}/scripts/darija_lint.py "{{output}}"
```

For each HIGH finding decide: Whisper's spelling → fix it in the file; what the speaker really said → keep it and say so in that segment's `note`. Run the lint once more after your fixes. Do not touch any other file: the app merges your file, re-times the words onto Whisper's and writes the .txt, .srt and .json itself.

Reply in a few lines: how many segments you changed, the words you were unsure of, and anything odd in the recordings.

Schema of `{{output}}`:

```json
{{schema}}
```
