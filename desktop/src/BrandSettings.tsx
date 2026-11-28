import { useEffect, useRef, useState, type ReactNode } from "react";
import { api, brandPreviewUrl, errText, type Brand, type BrandInfo, type BrandPreset, type BrandRoles } from "./api";
import { Button, cx, ErrorNote, field, Status } from "./ui";

const HEX = /^#[0-9a-fA-F]{6}$/;

/** A brand's two colours as one dot: the main colour with the line colour as its rim. */
export function BrandDot({ primary, accent, size = 22, className }: { primary: string; accent: string; size?: number; className?: string }) {
  return <span aria-hidden className={cx("inline-block shrink-0 rounded-full", className)} style={{ width: size, height: size, background: primary, boxShadow: `inset 0 0 0 ${Math.max(2, Math.round(size / 7))}px ${accent}` }} />;
}

function BRow({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[240px_1fr] items-start gap-4 border-b border-line px-3 py-3 last:border-b-0">
      <div>
        <div className="text-[13px] font-medium">{label}</div>
        {hint && <div className="mt-0.5 text-[12px] leading-snug text-ink-3">{hint}</div>}
      </div>
      <div className="min-w-0">{children}</div>
    </div>
  );
}

function ColorField({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  const [text, setText] = useState(value);
  useEffect(() => setText(value), [value]);
  const ok = HEX.test(text.trim());
  return (
    <div className="flex items-center gap-2 text-[12.5px]">
      <span className="w-[120px] text-ink-3">{label}</span>
      <input
        type="color"
        value={HEX.test(value) ? value : "#000000"}
        onChange={(e) => onChange(e.target.value.toUpperCase())}
        aria-label={`${label}: pick`}
        className="h-[32px] w-[44px] cursor-pointer rounded-[8px] border border-line bg-transparent p-0.5"
      />
      <input
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          if (HEX.test(e.target.value.trim())) onChange(e.target.value.trim().toUpperCase());
        }}
        className={cx(field, "w-[108px] font-mono uppercase", !ok && "border-bad")}
        aria-label={`${label}: hex value`}
        aria-invalid={!ok}
        spellCheck={false}
      />
      {!ok && <span className="text-[12px] text-bad">#RRGGBB</span>}
    </div>
  );
}

function Ramp({ roles }: { roles: BrandRoles }) {
  const stops: [string, string][] = [
    ...roles.deep.map((h): [string, string] => [h, "line work, deepest hollows"]),
    ...roles.shadow.map((h): [string, string] => [h, "hollow walls, deep shadow"]),
    ...roles.shade.map((h): [string, string] => [h, "shadow side"]),
    [roles.main, "main body"],
    ...roles.lit.map((h): [string, string] => [h, "lit side"]),
    ...roles.gloss.map((h): [string, string] => [h, "gloss"]),
    ...roles.highlight.map((h): [string, string] => [h, "specular highlights"]),
  ];
  return (
    <div className="flex h-[22px] overflow-hidden rounded-[8px] border border-line" role="img" aria-label={`Palette from ${roles.deep[0]} to ${roles.highlight[1]}`}>
      {stops.map(([h, what], i) => (
        <span key={i} title={`${h} · ${what}`} className="flex-1" style={{ background: h }} />
      ))}
    </div>
  );
}

const sameBrand = (a: Brand, b: Brand) => a.name === b.name && a.primary === b.primary && a.accent === b.accent && (a.hue || "") === (b.hue || "") && a.notes === b.notes;

/** Settings → Brand: the colours GPT draws this PC's pictures in. Pick a preset or your own colours; the drawing
 *  rules, the reference pictures and the colour lock are rendered from it into the library folder. */
export default function BrandEditor() {
  const [info, setInfo] = useState<BrandInfo | null>(null);
  const [draft, setDraft] = useState<Brand | null>(null);
  const [roles, setRoles] = useState<BrandRoles | null>(null);
  const [hueWord, setHueWord] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const timer = useRef<number | undefined>(undefined);

  const take = (i: BrandInfo) => {
    setInfo(i);
    setDraft(i.brand);
    setRoles(i.roles);
    setHueWord(i.words.hue);
  };
  useEffect(() => {
    api.brand().then(take).catch((e) => setErr(errText(e)));
  }, []);
  // the palette of what is being picked, a moment after the last change
  useEffect(() => {
    if (!draft) return;
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      api
        .deriveBrand(draft.primary, draft.accent)
        .then((d) => {
          setRoles(d.roles);
          setHueWord(draft.hue || d.words.hue);
        })
        .catch(() => {});
    }, 250);
    return () => window.clearTimeout(timer.current);
  }, [draft?.primary, draft?.accent, draft?.hue]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!info || !draft) return err ? <ErrorNote>{err}</ErrorNote> : <div className="px-3 py-3 text-[12.5px] text-ink-3">Loading…</div>;

  if (!info.managed) {
    return (
      <BRow label="Drawing colours" hint="This PC draws in the GPT asset studio's own style. The brand guide is for the app's own library on a customer's PC.">
        <div className="flex items-center gap-2 text-[13px]">
          <BrandDot primary={info.brand.primary} accent={info.brand.accent} />
          <span>{info.brand.name}</span>
          <span className="text-ink-4">· {info.dir}</span>
        </div>
      </BRow>
    );
  }

  const dirty = !sameBrand(draft, info.brand);
  const isPresetName = (n: string) => !n.trim() || info.presets.some((p) => p.name === n);
  const pick = (p: BrandPreset) => setDraft({ ...draft, preset: p.id, primary: p.primary, accent: p.accent, hue: "", name: isPresetName(draft.name) ? p.name : draft.name });
  const setColour = (patch: Pick<Brand, "primary"> | Pick<Brand, "accent">) => {
    const next = { ...draft, ...patch };
    const match = info.presets.find((p) => p.primary === next.primary && p.accent === next.accent);
    setDraft({ ...next, preset: match ? match.id : "custom" });
  };
  const save = (b: Brand) => {
    setBusy(true);
    setErr(null);
    api
      .saveBrand({ name: b.name, preset: b.preset, primary: b.primary, accent: b.accent, hue: b.hue || null, notes: b.notes })
      .then((i) => {
        take(i);
        setSaved(true);
        window.setTimeout(() => setSaved(false), 2500);
      })
      .catch((e) => setErr(errText(e)))
      .finally(() => setBusy(false));
  };
  const house = info.presets[0];
  const previewKey = `${draft.primary}|${draft.accent}`;

  return (
    <>
      {err && (
        <div className="px-3 pt-2">
          <ErrorNote>{err}</ErrorNote>
        </div>
      )}
      <BRow label="Preset" hint="A starting point. Your own colours below override it.">
        <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Brand presets">
          {info.presets.map((p) => {
            const on = draft.preset === p.id;
            return (
              <button
                key={p.id}
                type="button"
                role="radio"
                aria-checked={on}
                onClick={() => pick(p)}
                className={cx("press flex h-[36px] items-center gap-2 rounded-full border px-3 pr-3.5 text-[12.5px] transition-colors", on ? "border-accent-text/60 bg-accent/20 text-ink" : "border-line text-ink-2 hover:bg-hover hover:text-ink")}
              >
                <BrandDot primary={p.primary} accent={p.accent} size={16} />
                {p.name}
              </button>
            );
          })}
        </div>
      </BRow>
      <BRow label="Colours" hint="The main colour is the body of every picture. The line colour draws the thin strokes and the deepest hollows; it has to be darker than the main colour.">
        <div className="space-y-2">
          <ColorField label="Main colour" value={draft.primary} onChange={(v) => setColour({ primary: v })} />
          <ColorField label="Lines and hollows" value={draft.accent} onChange={(v) => setColour({ accent: v })} />
          <div className="flex items-center gap-2 text-[12.5px]">
            <span className="w-[120px] text-ink-3">Colour word</span>
            <input value={draft.hue} onChange={(e) => setDraft({ ...draft, hue: e.target.value.toLowerCase().replace(/[^a-z -]/g, "").slice(0, 20) })} placeholder={hueWord} className={cx(field, "w-[160px]")} aria-label="Colour word used in the prompts" />
            <span className="text-[12px] text-ink-4">the word the prompts use, e.g. “{hueWord || "blue"}”</span>
          </div>
          {roles && <Ramp roles={roles} />}
        </div>
      </BRow>
      <BRow label="Preview" hint="Two of the reference pictures GPT is shown, in these colours. New drawings follow them.">
        <div className="flex flex-wrap gap-3">
          {(["flat", "glossy"] as const).map((look) => (
            <div key={look} className="overflow-hidden rounded-[14px] border border-line bg-well p-2">
              <img key={previewKey + look} src={brandPreviewUrl(draft.primary, draft.accent, look, 300)} alt={`${look} reference picture in ${draft.name || "these colours"}`} className={cx("object-contain", look === "flat" ? "h-[132px] w-[198px]" : "h-[132px] w-[132px]")} />
            </div>
          ))}
        </div>
      </BRow>
      <BRow label="Brand name" hint="Shown in the Library and written into the drawing rules.">
        <input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value.slice(0, 60) })} className={cx(field, "w-[320px]")} aria-label="Brand name" placeholder={house.name} />
      </BRow>
      <BRow label="Notes for GPT" hint="Anything every picture must keep, in your words: a motif, a shape rule, what to avoid. Added to the drawing rules as written.">
        <textarea value={draft.notes} onChange={(e) => setDraft({ ...draft, notes: e.target.value.slice(0, 1500) })} rows={3} className={cx(field, "w-full max-w-[560px] resize-y leading-snug")} aria-label="Notes for GPT" placeholder="Rounded shapes, no hard corners. A small leaf where it fits." />
      </BRow>
      <BRow label="" hint="">
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="primary" disabled={!dirty || busy || !HEX.test(draft.primary) || !HEX.test(draft.accent)} onClick={() => save(draft)}>
            {busy ? "Saving…" : "Save brand"}
          </Button>
          {!info.house && (
            <Button variant="ghost" disabled={busy} onClick={() => save({ ...draft, preset: house.id, primary: house.primary, accent: house.accent, hue: "", name: house.name })}>
              Back to {house.name}
            </Button>
          )}
          {saved && <Status tone="ok">Saved</Status>}
          {!saved && info.applied && !dirty && <span className="text-[12px] text-ink-4">In use for new drawings · kept with the library in {info.dir}</span>}
          {dirty && !saved && <span className="text-[12px] text-ink-3">Not saved yet</span>}
        </div>
      </BRow>
    </>
  );
}
