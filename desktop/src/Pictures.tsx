import { useCallback, useEffect, useState, type CSSProperties } from "react";
import { api, basename, errText, pictureUrl, thumbUrl, type Folder, type NewPicture, type Picture, type PictureTag, type ProductDetail, type ProductPictures } from "./api";
import { Icon } from "./icons";
import { ActiveJobs, isActive, useJobs, useOnJobEnd } from "./Jobs";
import { inTauri, pickPictures } from "./tauri";
import { Button, Card, Chip, cx, dirOf, Empty, ErrorNote, field, Label, Loading } from "./ui";

const TAGS: { id: PictureTag; label: string; hint: string }[] = [
  { id: "illustration", label: "picture", hint: "A herb, an organ, a moon… Copied as it is when it has a transparent background, cut out otherwise." },
  { id: "packshot", label: "jar packshot", hint: "The jar shot straight on a white background: cut out symmetrically." },
  { id: "offer", label: "offer photo", hint: "The offer laid out on a light backdrop: straightened and cut out." },
];
const guessTag = (name: string): PictureTag => (/pack|jar|bocal|produit|product/i.test(name) ? "packshot" : /offer|offre|promo/i.test(name) ? "offer" : "illustration");
const IMAGE = /\.(png|webp|jpe?g|tiff?|heic|rw2)$/i;
/** A checkerboard behind each picture, so its transparent background shows. */
const checker: CSSProperties = {
  backgroundImage: "conic-gradient(rgb(128 128 128 / 0.2) 25%, transparent 0 50%, rgb(128 128 128 / 0.2) 0 75%, transparent 0)",
  backgroundSize: "16px 16px",
};
const input = field;

function keywordLine(p: Picture) {
  const k = p.keywords ?? {};
  return [...(k.darija ?? []).slice(0, 7), ...(k.fr ?? []).slice(0, 3), ...(k.en ?? []).slice(0, 2)].join(" · ");
}

function PictureCard({ slug, pics, p, onRemove }: { slug: string; pics: ProductPictures; p: Picture; onRemove?: (id: string) => void }) {
  const kw = keywordLine(p);
  return (
    <Card className={cx("group relative p-3", (p.problem || p.missing) && "opacity-70")}>
      <div className="grid aspect-square place-items-center overflow-hidden rounded-[14px] bg-well" style={checker}>
        {!p.missing && <img src={pictureUrl(slug, pics, p)} alt={p.id} className="max-h-full max-w-full object-contain drop-shadow-[0_8px_10px_rgb(0_0_0/0.35)]" loading="lazy" />}
      </div>
      {onRemove && (
        <button
          onClick={() => onRemove(p.id)}
          aria-label={`Remove ${p.id}`}
          title="Remove this picture from the project"
          className="glass-pill absolute top-4 right-4 grid h-[32px] w-[32px] place-items-center text-ink-2 opacity-0 transition-opacity group-hover:opacity-100 hover:text-bad focus-visible:opacity-100"
        >
          <Icon name="trash" size={13} />
        </button>
      )}
      <div className="mt-2.5 truncate font-mono text-[12px]" title={p.id}>
        {p.id}
      </div>
      <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1">
        {p.missing ? (
          <Chip tone="bad">file gone</Chip>
        ) : p.problem ? (
          <Chip tone="bad" title={p.problem}>
            can't be shown
          </Chip>
        ) : p.tagged ? (
          <Chip tone="ok">keywords</Chip>
        ) : (
          <Chip tone="warn" title="Claude looks at it and writes its keywords in the next asset run">
            no keywords yet
          </Chip>
        )}
        {p.motion && (
          <Chip tone="accent" title="its key move on the word: breathe = slow swell, shake = shudder, shine = pop + glint">
            {p.motion}
          </Chip>
        )}
        {p.concept && <Chip title="It also answers to this concept's Darija words">{p.concept}</Chip>}
      </div>
      {p.problem && <div className="mt-1 text-[11.5px] leading-snug text-bad">{p.problem}</div>}
      {kw && p.tagged && (
        <div dir={dirOf(kw)} className="mt-1 line-clamp-2 text-[11.5px] text-ink-3" title={Object.values(p.keywords ?? {}).flat().join(" · ")}>
          {kw}
        </div>
      )}
    </Card>
  );
}

/** The product's pictures: the asset folder its ads animate in front of the speaker, with each picture's keywords. */
export default function Pictures({ p, reload, openJob }: { p: ProductDetail; reload: () => void; openJob: (id: number) => void }) {
  const slug = p.slug;
  const [pics, setPics] = useState<ProductPictures | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [staged, setStaged] = useState<NewPicture[]>([]);
  const [typed, setTyped] = useState("");
  const [browse, setBrowse] = useState<Folder | null>(null);
  const [bottom, setBottom] = useState("");
  const [busy, setBusy] = useState(false);
  const jobs = useJobs(slug);
  const active = jobs.filter((j) => isActive(j) && j.kind === "pictures");
  const load = useCallback(() => api.pictures(slug).then(setPics).catch((e) => setErr(errText(e))), [slug]);
  useEffect(() => {
    load();
  }, [load]);
  useEffect(() => setBottom(pics?.asset_bottom ? String(pics.asset_bottom) : ""), [pics?.asset_bottom]);
  useOnJobEnd(jobs, () => {
    load();
    reload();
  });

  const stage = (paths: string[]) =>
    setStaged((s) => [
      ...s,
      ...paths
        .filter((x) => x.trim() && !s.some((y) => y.file === x.trim()))
        .map((x) => ({ file: x.trim(), tag: guessTag(basename(x)), label: basename(x).replace(/\.[^.]+$/, ""), note: "" })),
    ]);
  const change = (i: number, patch: Partial<NewPicture>) => setStaged((s) => s.map((x, j) => (j === i ? { ...x, ...patch } : x)));
  const openFolder = (path: string) => api.folder(path).then(setBrowse).catch((e) => setErr(errText(e)));
  const remove = (id: string) => {
    if (!confirm(`Remove the picture "${id}" from this project? Ads built later will not use it.`)) return;
    setErr(null);
    api
      .removePicture(slug, id)
      .then((r) => {
        setPics(r);
        reload();
      })
      .catch((e) => setErr(errText(e)));
  };
  const send = (body: Parameters<typeof api.addPictures>[1], after?: () => void) => {
    setBusy(true);
    setErr(null);
    return api
      .addPictures(slug, body)
      .then((r) => {
        setPics(r.pictures);
        if (r.jobs[0]) openJob(r.jobs[0].id);
        after?.();
      })
      .catch((e) => setErr(errText(e)))
      .finally(() => setBusy(false));
  };

  if (!pics) return err ? <ErrorNote>{err}</ErrorNote> : <Loading />;
  const live = pics.assets.filter((a) => !a.missing);
  const bottomN = Number(bottom);
  const bottomOk = bottom.trim() === "" || (Number.isInteger(bottomN) && bottomN >= 600 && bottomN <= 1800);

  return (
    <div className="space-y-[10px]">
      {err && <ErrorNote>{err}</ErrorNote>}
      <Card className="p-5">
        <div className="flex flex-wrap items-start gap-4">
          <div className="min-w-[260px] flex-1">
            <div className="text-[14px] font-semibold">The product's pictures</div>
            <p className="mt-0.5 max-w-[760px] text-[12.5px] text-ink-3">
              Transparent PNG / WebP cut-outs of what he talks about: the herbs, the jar, a moon for sleep, a liver. When an ad is built, Claude looks at each new picture and writes the words that name it. Each one then grows out of the caption in front of him on that word. A picture with a background is cut out when you add it.
            </p>
            {pics.own_library && pics.dir && (
              <div className="mt-1 flex min-w-0 items-center gap-2 text-[11.5px] text-ink-3">
                <span>Kept with the project, so an update never touches them.</span>
                <Button small variant="ghost" icon="folder" onClick={() => api.reveal(pics.dir!)}>
                  Open the folder
                </Button>
              </div>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-3">
            {pics.own_library && (
              <>
                <Chip tone={pics.counts.usable ? "ok" : "neutral"}>
                  {pics.counts.usable} usable picture{pics.counts.usable === 1 ? "" : "s"}
                </Chip>
                {pics.counts.untagged > 0 && (
                  <Chip tone="warn" title="Claude writes their keywords in the next asset run">
                    {pics.counts.untagged} without keywords
                  </Chip>
                )}
                {pics.counts.pictures > pics.counts.usable && <Chip tone="bad">{pics.counts.pictures - pics.counts.usable} can't be shown</Chip>}
              </>
            )}
            <Button small icon="refresh" disabled={busy || active.length > 0} onClick={() => send({ reindex: true })} title="Index the folder again, after you dropped pictures into it in Explorer">
              Re-index
            </Button>
          </div>
        </div>
      </Card>

      <ActiveJobs jobs={active} openJob={openJob} />

      {!pics.own_library && (
        <div className="flex gap-2 rounded-[14px] bg-well px-4 py-3 text-[12.5px] text-ink-2">
          <Icon name="alert" size={15} className="mt-px shrink-0 text-warn" />
          <div>
            This product has no picture folder of its own yet: its earlier ads drew from the{" "}
            <a href="#/library" className="text-accent-text underline">
              library
            </a>
            . Add its pictures below or press Re-index: the product then gets a picture folder of its own, and new ads use only the pictures in it.
          </div>
        </div>
      )}

      <Card className="p-5">
        <div className="flex flex-wrap items-center gap-2">
          <Label>Add pictures</Label>
          <div className="flex-1" />
          {inTauri() && (
            <Button small icon="images" onClick={() => pickPictures().then(stage)}>
              Choose files…
            </Button>
          )}
          <Button small icon="folder" disabled={!p.product.product_dir} onClick={() => (browse ? setBrowse(null) : openFolder(p.product.product_dir))}>
            {browse ? "Close the folder" : "From the product folder"}
          </Button>
        </div>
        <form
          className="mt-2 flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            stage([typed]);
            setTyped("");
          }}
        >
          <input className={cx(input, "min-w-0 flex-1")} placeholder="C:\…\moon.png" value={typed} onChange={(e) => setTyped(e.target.value)} aria-label="Path of a picture" />
          <Button small type="submit" disabled={!IMAGE.test(typed.trim())}>
            Add to the list
          </Button>
        </form>

        {browse && (
          <div className="mt-3 rounded-[14px] border border-line p-3">
            <div className="mb-1.5 flex min-w-0 items-center gap-2 text-[11.5px] text-ink-3">
              <code className="min-w-0 flex-1 truncate">{browse.path}</code>
              {browse.parent && (
                <Button small variant="ghost" icon="up" onClick={() => openFolder(browse.parent!)}>
                  Up
                </Button>
              )}
            </div>
            {browse.entries.some((e) => e.kind === "folder") && (
              <div className="mb-2 flex flex-wrap gap-1">
                {browse.entries
                  .filter((e) => e.kind === "folder")
                  .map((e) => (
                    <button key={e.path} type="button" className="press glass-pill h-[30px] px-3 text-[12px] hover:bg-white/[0.1]" onClick={() => openFolder(e.path)}>
                      {e.name}/
                    </button>
                  ))}
              </div>
            )}
            <div className="grid grid-cols-[repeat(auto-fill,minmax(96px,1fr))] gap-2">
              {browse.entries
                .filter((e) => e.kind === "image")
                .map((e) => {
                  const on = staged.some((s) => s.file === e.path);
                  return (
                    <button
                      key={e.path}
                      onClick={() => (on ? setStaged((s) => s.filter((x) => x.file !== e.path)) : stage([e.path]))}
                      type="button"
                      className={cx("press rounded-[12px] p-1 text-left ring-2 transition-shadow", on ? "bg-accent-soft ring-accent" : "ring-transparent hover:ring-line-strong")}
                      title={on ? "In the list: click to take it out" : "Click to add it to the list"}
                    >
                      <img src={thumbUrl(e.path, 160)} alt="" className="aspect-square w-full rounded-[5px] bg-well object-contain" loading="lazy" />
                      <div dir="auto" className="mt-1 truncate text-[11.5px]">
                        {e.name}
                      </div>
                    </button>
                  );
                })}
              {!browse.entries.some((e) => e.kind === "image") && <div className="col-span-full p-2 text-[12.5px] text-ink-3">No picture in this folder.</div>}
            </div>
          </div>
        )}

        {staged.length > 0 && (
          <div className="mt-3 overflow-hidden rounded-[14px] border border-line">
            {staged.map((s, i) => (
              <div key={s.file} className="flex flex-wrap items-center gap-2 border-b border-line px-2 py-1.5 last:border-b-0">
                <img src={thumbUrl(s.file, 96)} alt="" className="h-[44px] w-[44px] rounded-[4px] bg-well object-contain" loading="lazy" />
                <div dir="auto" className="min-w-[140px] flex-1 truncate text-[12.5px]" title={s.file}>
                  {basename(s.file)}
                </div>
                <select className={cx(input, "w-[130px]")} value={s.tag} onChange={(e) => change(i, { tag: e.target.value as PictureTag })} title={TAGS.find((t) => t.id === s.tag)?.hint} aria-label="What this picture is">
                  {TAGS.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.label}
                    </option>
                  ))}
                </select>
                <input className={cx(input, "w-[160px]")} value={s.label} onChange={(e) => change(i, { label: e.target.value })} placeholder="file name in the folder" title="Its file name in the folder (Latin letters; the first keyword)" aria-label="Name" />
                <button type="button" className="grid h-[32px] w-[32px] place-items-center rounded-full text-ink-3 hover:bg-hover hover:text-ink" onClick={() => setStaged((x) => x.filter((_, j) => j !== i))} aria-label={`Take ${basename(s.file)} out of the list`}>
                  <Icon name="x" size={13} />
                </button>
              </div>
            ))}
          </div>
        )}
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <Button variant="primary" icon="plus" disabled={staged.length === 0 || busy} onClick={() => send({ files: staged }, () => (setStaged([]), setBrowse(null)))}>
            Add {staged.length || ""} picture{staged.length === 1 ? "" : "s"}
          </Button>
          <span className="text-[12px] text-ink-3">They are prepared and indexed by a job; Claude writes their keywords in the next asset run.</span>
        </div>
        {pics.pending.length > 0 && (
          <div className="mt-2 text-[12px] text-ink-3">
            Waiting to be prepared: {pics.pending.map((x) => basename(x.file)).join(", ")}
          </div>
        )}
      </Card>

      <Card className="p-5">
        <div className="flex flex-wrap items-center gap-3">
          <div className="min-w-[260px] flex-1">
            <Label>Height in remixes</Label>
            <div className="mt-0.5 text-[12.5px] text-ink-2">
              The pictures' bottom edge, in pixels from the top of the 1920 px frame. Default 1260: just above the burned-in captions. Set a smaller number when this product's captions sit higher; a single shot can still be moved in its own beat.
            </div>
          </div>
          <input type="number" min={600} max={1800} step={10} className={cx(input, "num w-[90px]", !bottomOk && "ring-2 ring-bad/60")} value={bottom} placeholder="1260" onChange={(e) => setBottom(e.target.value)} aria-label="Bottom edge in pixels" />
          <Button small disabled={busy || !bottomOk || bottom.trim() === (pics.asset_bottom ? String(pics.asset_bottom) : "")} onClick={() => send(bottom.trim() ? { asset_bottom: bottomN } : { clear_asset_bottom: true })}>
            Save
          </Button>
        </div>
      </Card>

      {pics.own_library && live.length === 0 && (
        <Empty title="No picture yet" icon="images">
          Without pictures the ads keep their captions and transitions, and every idea he names is listed as missing after a build. Add the product's pictures above.
        </Empty>
      )}
      {pics.own_library && live.length > 0 && (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(180px,1fr))] gap-[10px]">
          {pics.assets.map((a) => (
            <PictureCard key={a.id} slug={slug} pics={pics} p={a} onRemove={pics.own_library ? remove : undefined} />
          ))}
        </div>
      )}
    </div>
  );
}
