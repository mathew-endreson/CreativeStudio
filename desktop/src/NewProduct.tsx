import { useEffect, useState } from "react";
import { api, basename, clock, errText, thumbUrl, type Folder, type FolderEntry, type NewSource } from "./api";
import { pickFolder } from "./tauri";
import { Button, Card, Chip, ErrorNote, Label, PageHeader } from "./ui";

type Tag = NewSource["tag"];
const TAGS: { id: Tag; label: string }[] = [
  { id: "finished_ad", label: "finished ad" },
  { id: "source", label: "raw footage" },
  { id: "packshot", label: "packshot" },
  { id: "offer", label: "offer photo" },
  { id: "illustration", label: "illustration" },
  { id: "ignore", label: "ignore" },
];
const input = "h-[28px] w-full rounded-[5px] border border-line bg-well shadow-[inset_0_1px_2px_rgb(0_0_0/0.25)] focus:border-accent focus:outline-none px-2 text-[13px]";

/** A product from a folder: its finished ads (or raw footage), its pictures, the words Whisper should know. */
export default function NewProduct({ openJob }: { openJob: (id: number) => void }) {
  const [path, setPath] = useState("");
  const [folder, setFolder] = useState<Folder | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [tags, setTags] = useState<Record<string, Tag>>({});
  const [labels, setLabels] = useState<Record<string, string>>({});
  const [name, setName] = useState("");
  const [nameAr, setNameAr] = useState("");
  const [prompt, setPrompt] = useState("");
  const [adsDir, setAdsDir] = useState("");
  const [gpt, setGpt] = useState(3);
  const [offers, setOffers] = useState("");
  const [dups, setDups] = useState("");
  const [busy, setBusy] = useState(false);

  const list = (p: string) =>
    api
      .folder(p)
      .then((f) => {
        setFolder(f);
        setErr(null);
        const t: Record<string, Tag> = {};
        const l: Record<string, string> = {};
        let n = 0;
        for (const e of f.entries) {
          if (e.kind === "video") {
            n += 1;
            t[e.path] = "finished_ad";
            l[e.path] = `V${n}`;
          } else if (e.kind === "image") t[e.path] = /pack|jar|produit|product/i.test(e.name) ? "packshot" : /offer|offre|promo/i.test(e.name) ? "offer" : "illustration";
        }
        setTags(t);
        setLabels(l);
        if (!name) setName(basename(f.path));
        if (!adsDir) setAdsDir(`${f.path}\\Ads`);
      })
      .catch((e) => setErr(errText(e)));

  useEffect(() => {
    if (folder && adsDir === "") setAdsDir(`${folder.path}\\Ads`);
  }, [folder, adsDir]);

  const videos = folder?.entries.filter((e) => e.kind === "video") ?? [];
  const images = folder?.entries.filter((e) => e.kind === "image") ?? [];
  const nAds = Object.values(tags).filter((t) => t === "finished_ad" || t === "source").length;

  const create = () => {
    if (!folder) return;
    setBusy(true);
    const sources: NewSource[] = [...videos, ...images]
      .filter((e) => tags[e.path] && tags[e.path] !== "ignore")
      .map((e) => ({ file: e.path, tag: tags[e.path], label: labels[e.path] ?? "", note: "" }));
    api
      .createProduct({
        name: name.trim(),
        name_ar: nameAr.trim(),
        whisper_prompt: prompt.trim(),
        product_dir: folder.path,
        ads_dir: adsDir.trim(),
        sources,
        offers: offers
          .split("\n")
          .map((x) => x.trim())
          .filter(Boolean)
          .map((x) => ({ label: x, photo: "", note: "" })),
        duplicates: dups.split("\n").map((x) => x.trim()).filter(Boolean),
        gpt_cap: gpt,
      })
      .then((r) => {
        if (r.jobs[0]) openJob(r.jobs[0].id);
        location.hash = `#/p/${r.slug}/analysis`;
      })
      .catch((e) => setErr(errText(e)))
      .finally(() => setBusy(false));
  };

  const FileRow = ({ e }: { e: FolderEntry }) => (
    <div className="flex items-center gap-3 border-b border-line px-3 py-2 last:border-b-0">
      <img src={thumbUrl(e.path, 96)} alt="" className={e.kind === "video" ? "h-[64px] w-[36px] rounded bg-black object-cover" : "h-[64px] w-[64px] rounded bg-surface-2 object-contain"} loading="lazy" />
      <div className="min-w-0 flex-1">
        <div dir="auto" className="truncate font-medium">
          {e.name}
        </div>
        <div className="num truncate text-[12px] text-ink-3">
          {e.kind === "video" ? `${e.duration ? clock(e.duration) : "?"} · ${e.w}×${e.h} · ${e.fps} fps · ${e.audio_rate ? `${(e.audio_rate / 1000).toFixed(1)} kHz` : "no audio"}` : `${((e.size ?? 0) / 1e6).toFixed(1)} MB`}
        </div>
      </div>
      {(tags[e.path] === "finished_ad" || tags[e.path] === "source") && (
        <input className={`${input} w-[70px]`} value={labels[e.path] ?? ""} onChange={(x) => setLabels({ ...labels, [e.path]: x.target.value })} title="short label used in ad names" />
      )}
      <select className="h-[28px] rounded-[5px] border border-line bg-well shadow-[inset_0_1px_2px_rgb(0_0_0/0.25)] focus:border-accent focus:outline-none px-2 text-[13px]" value={tags[e.path] ?? "ignore"} onChange={(x) => setTags({ ...tags, [e.path]: x.target.value as Tag })}>
        {TAGS.filter((t) => (e.kind === "video" ? ["finished_ad", "source", "ignore"] : ["packshot", "offer", "illustration", "ignore"]).includes(t.id)).map((t) => (
          <option key={t.id} value={t.id}>
            {t.label}
          </option>
        ))}
      </select>
    </div>
  );

  return (
    <div className="mx-auto max-w-[1100px]">
      <PageHeader icon="plus" title="New project" sub="A product is a folder of finished ads (or raw footage) and its pictures. The app analyses the ads, proposes new ones, and renders the ones you tick into the Ads folder." />
      {err && <ErrorNote>{err}</ErrorNote>}
      <Card className="p-4">
        <Label>Product folder</Label>
        <div className="mt-1 flex gap-2">
          <input className={input} placeholder="C:\…\Product" value={path} onChange={(e) => setPath(e.target.value)} onKeyDown={(e) => e.key === "Enter" && list(path)} />
          <Button onClick={() => list(path)} disabled={!path.trim()}>
            List
          </Button>
          <Button
            onClick={() =>
              pickFolder().then((p) => {
                if (p) {
                  setPath(p);
                  list(p);
                }
              })
            }
          >
            Browse…
          </Button>
        </div>
        {folder && (
          <div className="mt-3 grid gap-3 xl:grid-cols-2">
            <div>
              <Label>Videos ({videos.length})</Label>
              <div className="mt-1 rounded-[6px] border border-line">{videos.map((e) => <FileRow key={e.path} e={e} />)}{videos.length === 0 && <div className="p-3 text-ink-3">No video in this folder.</div>}</div>
            </div>
            <div>
              <Label>Pictures ({images.length})</Label>
              <div className="mt-1 rounded-[6px] border border-line">{images.map((e) => <FileRow key={e.path} e={e} />)}{images.length === 0 && <div className="p-3 text-ink-3">No picture: the default EBOX jar is used.</div>}</div>
              {folder.entries.some((e) => e.kind === "folder") && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {folder.entries
                    .filter((e) => e.kind === "folder")
                    .map((e) => (
                      <button key={e.path} className="rounded-full border border-line px-2 py-px text-[12px] hover:border-accent" onClick={() => (setPath(e.path), list(e.path))}>
                        {e.name}/
                      </button>
                    ))}
                </div>
              )}
            </div>
          </div>
        )}
      </Card>
      {folder && (
        <Card className="mt-3 grid gap-3 p-4 md:grid-cols-2">
          <div>
            <Label>Name (Latin, for file names)</Label>
            <input className={`${input} mt-1`} value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div>
            <Label>Arabic name</Label>
            <input dir="auto" className={`${input} mt-1 font-caption text-[15px]`} value={nameAr} onChange={(e) => setNameAr(e.target.value)} />
          </div>
          <div className="md:col-span-2">
            <Label>Key words for Whisper (Darija, Arabic, French; the product, the organ, the symptoms, the brand)</Label>
            <textarea dir="auto" className="mt-1 h-16 w-full rounded-[5px] border border-line bg-well shadow-[inset_0_1px_2px_rgb(0_0_0/0.25)] focus:border-accent focus:outline-none p-2 text-[14px]" value={prompt} onChange={(e) => setPrompt(e.target.value)} />
          </div>
          <div>
            <Label>Ads folder (output)</Label>
            <input className={`${input} mt-1`} value={adsDir} onChange={(e) => setAdsDir(e.target.value)} />
          </div>
          <div>
            <Label>GPT drawings per ad</Label>
            <input type="number" min={0} max={10} className={`${input} mt-1 w-[90px]`} value={gpt} onChange={(e) => setGpt(Number(e.target.value))} />
          </div>
          <div>
            <Label>Offers (one per line, as he says them)</Label>
            <textarea dir="auto" className="mt-1 h-16 w-full rounded-[5px] border border-line bg-well shadow-[inset_0_1px_2px_rgb(0_0_0/0.25)] focus:border-accent focus:outline-none p-2 text-[13px]" value={offers} onChange={(e) => setOffers(e.target.value)} placeholder={"1 kg + 100 g seeds\n3 kg"} />
          </div>
          <div>
            <Label>Known duplicates (one per line)</Label>
            <textarea className="mt-1 h-16 w-full rounded-[5px] border border-line bg-well shadow-[inset_0_1px_2px_rgb(0_0_0/0.25)] focus:border-accent focus:outline-none p-2 text-[13px]" value={dups} onChange={(e) => setDups(e.target.value)} placeholder="V7 = V5 hook + V6 body" />
          </div>
          <div className="flex items-center gap-3 md:col-span-2">
            <Button variant="primary" onClick={create} disabled={busy || !name.trim() || nAds === 0}>
              {busy ? "Creating…" : "Create the project"}
            </Button>
            <Chip>{nAds} video{nAds === 1 ? "" : "s"} to analyse</Chip>
            {images.some((e) => tags[e.path] && tags[e.path] !== "ignore") && <Chip tone="accent">pictures are cut out after creation (a job)</Chip>}
          </div>
        </Card>
      )}
    </div>
  );
}
