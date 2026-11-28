import { useCallback, useEffect, useState, type CSSProperties } from "react";
import { api, basename, errText, thumbUrl, type BrandInfo, type Library as LibraryT, type LibraryAsset, type NewPicture, type PictureTag } from "./api";
import { BrandDot } from "./BrandSettings";
import { Icon } from "./icons";
import { ActiveJobs, isActive, useJobs, useOnJobEnd } from "./Jobs";
import { inTauri, pickPictures } from "./tauri";
import { Button, Card, cx, dirOf, Empty, ErrorNote, field, Label, Search, Status, Toolbar } from "./ui";

const TAGS: { id: PictureTag; label: string; hint: string }[] = [
  { id: "illustration", label: "picture", hint: "A herb, an organ, a moon… Copied as it is when it has a transparent background, cut out otherwise." },
  { id: "packshot", label: "jar packshot", hint: "The jar shot straight on a white background: cut out symmetrically." },
  { id: "offer", label: "offer photo", hint: "The offer laid out on a light backdrop: straightened and cut out." },
];
const guessTag = (name: string): PictureTag => (/pack|jar|bocal|produit|product/i.test(name) ? "packshot" : /offer|offre|promo/i.test(name) ? "offer" : "illustration");
const IMAGE = /\.(png|webp|jpe?g|tiff?|heic|rw2)$/i;
const checker: CSSProperties = {
  backgroundImage: "conic-gradient(rgb(128 128 128 / 0.2) 25%, transparent 0 50%, rgb(128 128 128 / 0.2) 0 75%, transparent 0)",
  backgroundSize: "16px 16px",
};

function keywordLine(a: LibraryAsset) {
  const k = a.keywords ?? {};
  return [...(k.darija ?? []).slice(0, 7), ...(k.fr ?? []).slice(0, 3), ...(k.en ?? []).slice(0, 2)].join(" · ");
}

function AssetCard({ a, onRemove }: { a: LibraryAsset; onRemove: (id: string) => void }) {
  const kw = keywordLine(a);
  return (
    <Card className={cx("group relative p-3", (a.problem || a.missing) && "opacity-70")}>
      <div className="grid aspect-square place-items-center overflow-hidden rounded-[14px] bg-well" style={checker}>
        {!a.missing && <img src={`/media/library/${encodeURIComponent(a.id)}`} alt={a.subject || a.id} className="max-h-full max-w-full object-contain drop-shadow-[0_8px_10px_rgb(0_0_0/0.35)]" loading="lazy" />}
      </div>
      <button
        type="button"
        onClick={() => onRemove(a.id)}
        aria-label={`Remove ${a.id}`}
        title="Remove this picture from the library"
        className="glass-pill absolute top-4 right-4 grid h-[32px] w-[32px] place-items-center text-ink-2 opacity-0 transition-opacity group-hover:opacity-100 hover:text-bad focus-visible:opacity-100"
      >
        <Icon name="trash" size={13} />
      </button>
      <div className="mt-2.5 truncate text-[13px] font-medium" title={a.subject || a.id}>
        {a.subject || a.id}
      </div>
      <div className="truncate font-mono text-[11px] text-ink-4" title={a.id}>
        {a.id}
      </div>
      <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-ink-3">
        {a.missing ? (
          <Status tone="bad">file gone</Status>
        ) : a.problem ? (
          <Status tone="bad" title={a.problem}>
            can't be shown
          </Status>
        ) : a.tagged ? (
          <Status tone="ok">keywords</Status>
        ) : (
          <Status tone="warn" title="Claude looks at it and writes its keywords on the next edit">
            no keywords yet
          </Status>
        )}
        {a.look && <span>{a.look}</span>}
        {a.motion && <span title="its key move on the word">{a.motion}</span>}
        {a.label && <span className="font-caption text-ink-2">{a.label.replace(/<[^>]+>/g, "")}</span>}
      </div>
      {a.problem && <div className="mt-1 text-[11.5px] leading-snug text-bad">{a.problem}</div>}
      {kw && a.tagged && (
        <div dir={dirOf(kw)} className="mt-1 line-clamp-2 text-[11.5px] text-ink-4" title={Object.values(a.keywords ?? {}).flat().join(" · ")}>
          {kw}
        </div>
      )}
    </Card>
  );
}

/** This PC's picture library: what every ad may show in front of the speaker. Add pictures here; each is cut out
 *  when it needs it, indexed, and given its keywords by Claude on the next edit. */
export default function Library() {
  const [lib, setLib] = useState<LibraryT | null>(null);
  const [brand, setBrand] = useState<BrandInfo | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [found, setFound] = useState<string | null>(null);
  const [status, setStatus] = useState<Record<string, any> | null>(null);
  const [filter, setFilter] = useState("");
  const [staged, setStaged] = useState<NewPicture[]>([]);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const jobs = useJobs("library");
  const active = jobs.filter(isActive);
  const load = useCallback(() => api.library().then(setLib).catch((e) => setErr(errText(e))), []);
  useEffect(() => {
    load();
    api.brand().then(setBrand).catch(() => {});
  }, [load]);
  useOnJobEnd(jobs, load);

  const search = () => api.librarySearch(q).then((r) => setFound(r.output || "(no match)")).catch((e) => setErr(errText(e)));
  const stage = (paths: string[]) =>
    setStaged((s) => [
      ...s,
      ...paths
        .filter((x) => x.trim() && !s.some((y) => y.file === x.trim()))
        .map((x) => ({ file: x.trim(), tag: guessTag(basename(x)), label: basename(x).replace(/\.[^.]+$/, ""), note: "" })),
    ]);
  const change = (i: number, patch: Partial<NewPicture>) => setStaged((s) => s.map((x, j) => (j === i ? { ...x, ...patch } : x)));
  const send = (body: { files?: NewPicture[]; reindex?: boolean }, after?: () => void) => {
    setBusy(true);
    setErr(null);
    return api
      .addLibraryPictures(body)
      .then((r) => {
        setLib(r.library);
        after?.();
      })
      .catch((e) => setErr(errText(e)))
      .finally(() => setBusy(false));
  };
  const remove = (id: string) => {
    if (!confirm(`Remove the picture "${id}" from the library? Ads built later will not use it.`)) return;
    setErr(null);
    api
      .removeLibraryPicture(id)
      .then(setLib)
      .catch((e) => setErr(errText(e)));
  };

  const assets = (lib?.assets ?? []).filter((a) => {
    if (!filter.trim()) return true;
    const f = filter.trim().toLowerCase();
    const kw = Object.values(a.keywords ?? {}).flat().join(" ").toLowerCase();
    return a.id.includes(f) || (a.subject ?? "").toLowerCase().includes(f) || kw.includes(f) || (a.label ?? "").includes(filter.trim());
  });
  const n = lib?.counts;

  return (
    <div>
      <Toolbar
        title="Library"
        sub={
          <>
            {lib ? (n?.pictures ? `${n.pictures} picture${n.pictures === 1 ? "" : "s"}${n.untagged ? ` · ${n.untagged} without keywords yet` : ""} · every ad may use them` : "No pictures yet · every ad may use what you add here") : "…"}
            {brand && (
              <>
                {" · GPT draws in "}
                <BrandDot primary={brand.brand.primary} accent={brand.brand.accent} size={10} className="mr-1 align-[-1px]" />
                {brand.brand.name}
                {brand.managed && (
                  <>
                    {" ("}
                    <a href="#/settings" className="underline hover:text-ink">
                      change
                    </a>
                    {")"}
                  </>
                )}
              </>
            )}
          </>
        }
      >
        <Search value={filter} onChange={setFilter} placeholder="Filter pictures" />
        {lib?.studio && <Button onClick={() => api.gptStatus().then(setStatus).catch((e) => setErr(errText(e)))}>Drawing status</Button>}
        {inTauri() && (
          <Button variant={staged.length ? "default" : "primary"} icon="plus" onClick={() => pickPictures().then(stage)}>
            Add pictures…
          </Button>
        )}
      </Toolbar>
      {err && <ErrorNote>{err}</ErrorNote>}
      <ActiveJobs jobs={active} openJob={(id) => (location.hash = `#/jobs/${id}`)} />
      {status && (
        <Card className="my-[10px] p-4 text-[12.5px]">
          <Label>Drawing tool status</Label>
          <pre className="mt-1 whitespace-pre-wrap text-ink-2">{JSON.stringify(status, null, 1)}</pre>
        </Card>
      )}

      <Card className="my-[10px] p-5">
        <div className="flex flex-wrap items-center gap-2">
          <div className="min-w-[260px] flex-1">
            <div className="text-[14px] font-semibold">Add pictures</div>
            <div className="mt-0.5 text-[12.5px] text-ink-3">Transparent PNG or WebP cut-outs of what the speaker talks about: herbs, the jar, a moon, an organ. A picture with a background is cut out when you add it. Claude writes each one's keywords on the next edit.</div>
          </div>
          <Button small variant="ghost" icon="refresh" disabled={busy || active.length > 0} onClick={() => send({ reindex: true })} title="Index the folder again, after you dropped pictures into it in Explorer">
            Re-index
          </Button>
        </div>
        <form
          className="mt-3 flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            stage([typed]);
            setTyped("");
          }}
        >
          <input className={cx(field, "min-w-0 flex-1")} placeholder="C:\…\moon.png" value={typed} onChange={(e) => setTyped(e.target.value)} aria-label="Path of a picture" />
          <Button type="submit" disabled={!IMAGE.test(typed.trim())}>
            Add to the list
          </Button>
        </form>
        {staged.length > 0 && (
          <div className="mt-3 overflow-hidden rounded-[14px] border border-line">
            {staged.map((s, i) => (
              <div key={s.file} className="flex flex-wrap items-center gap-2 border-b border-line px-3 py-2 last:border-b-0">
                <img src={thumbUrl(s.file, 96)} alt="" className="h-[44px] w-[44px] rounded-[6px] bg-well object-contain" loading="lazy" />
                <div dir="auto" className="min-w-[140px] flex-1 truncate text-[12.5px]" title={s.file}>
                  {basename(s.file)}
                </div>
                <select className={cx(field, "w-[150px]")} value={s.tag} onChange={(e) => change(i, { tag: e.target.value as PictureTag })} title={TAGS.find((t) => t.id === s.tag)?.hint} aria-label="What this picture is">
                  {TAGS.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.label}
                    </option>
                  ))}
                </select>
                <input className={cx(field, "w-[180px]")} value={s.label} onChange={(e) => change(i, { label: e.target.value })} placeholder="name in the library" title="Its file name in the library (Latin letters; the first keyword)" aria-label="Name" />
                <button type="button" className="grid h-[32px] w-[32px] place-items-center rounded-full text-ink-3 hover:bg-hover hover:text-ink" onClick={() => setStaged((x) => x.filter((_, j) => j !== i))} aria-label={`Take ${basename(s.file)} out of the list`}>
                  <Icon name="x" size={13} />
                </button>
              </div>
            ))}
          </div>
        )}
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <Button variant="primary" icon="plus" disabled={staged.length === 0 || busy} onClick={() => send({ files: staged }, () => setStaged([]))}>
            Add {staged.length || ""} picture{staged.length === 1 ? "" : "s"}
          </Button>
          {lib && <span className="truncate text-[12px] text-ink-4">Kept in {lib.dir}</span>}
        </div>
      </Card>

      <Card className="mb-[10px] p-5">
        <Label>Which picture does a spoken word pull?</Label>
        <div className="mt-2 flex gap-2">
          <input dir="auto" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && search()} placeholder="الكحة" className={`${field} w-[320px] text-[14px]`} aria-label="A spoken word" />
          <Button onClick={search} disabled={!q.trim()}>
            Search
          </Button>
        </div>
        {found && <pre dir="auto" className="mt-3 max-h-[200px] overflow-auto rounded-[14px] bg-well p-3 text-[12px] whitespace-pre-wrap text-ink-2">{found}</pre>}
      </Card>

      {lib && lib.assets.filter((a) => !a.missing).length === 0 && (
        <Empty title="No pictures yet" icon="images">
          Add transparent cut-outs of what the speaker names. Until then the ads use only each project's own pictures, and every idea with no picture is listed after a build.
        </Empty>
      )}
      <div className="grid grid-cols-[repeat(auto-fill,minmax(210px,1fr))] gap-[10px]">
        {assets.map((a) => (
          <AssetCard key={a.id} a={a} onRemove={remove} />
        ))}
      </div>
    </div>
  );
}
