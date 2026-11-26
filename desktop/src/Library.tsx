import { useEffect, useState } from "react";
import { api, errText, type Library as LibraryT } from "./api";
import { Button, Card, Chip, Empty, ErrorNote, Label, PageHeader } from "./ui";

/** The GPT asset library: every orange illustration with the words that pull it into an ad. */
export default function Library() {
  const [lib, setLib] = useState<LibraryT | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [found, setFound] = useState<string | null>(null);
  const [status, setStatus] = useState<Record<string, any> | null>(null);
  const [filter, setFilter] = useState("");
  useEffect(() => {
    api.library().then(setLib).catch((e) => setErr(errText(e)));
  }, []);
  const search = () => api.librarySearch(q).then((r) => setFound(r.output || "(no match)")).catch((e) => setErr(errText(e)));
  const assets = (lib?.assets ?? []).filter((a) => {
    if (!filter.trim()) return true;
    const f = filter.trim().toLowerCase();
    const kw = Object.values(a.keywords ?? {}).flat().join(" ").toLowerCase();
    return a.id.includes(f) || (a.subject ?? "").toLowerCase().includes(f) || kw.includes(f) || (a.label ?? "").includes(filter.trim());
  });
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <PageHeader
          icon="images"
          title="Asset library"
          sub={
            <>
              {lib ? `${lib.assets.length} pictures` : "…"} in <code>{lib?.dir}</code>. Pictures the ChatGPT / Codex app draws land here; <code>asset_lib.py sync</code> and <code>tag</code> file them with their keywords.
            </>
          }
        />
        <div className="mb-3 flex items-center gap-2">
          <Button small onClick={() => api.gptStatus().then(setStatus).catch((e) => setErr(errText(e)))}>
            GPT status
          </Button>
          <input placeholder="filter…" value={filter} onChange={(e) => setFilter(e.target.value)} className="h-[28px] rounded-[5px] border border-line bg-well shadow-[inset_0_1px_2px_rgb(0_0_0/0.25)] focus:border-accent focus:outline-none px-2 text-[13px]" dir="auto" />
        </div>
      </div>
      {err && <ErrorNote>{err}</ErrorNote>}
      {status && (
        <Card className="p-3 text-[12.5px]">
          <Label>GPT (Codex app) status</Label>
          <pre className="mt-1 whitespace-pre-wrap">{JSON.stringify(status, null, 1)}</pre>
        </Card>
      )}
      <Card className="p-3">
        <Label>Which picture does a spoken word pull?</Label>
        <div className="mt-1 flex gap-2">
          <input dir="auto" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && search()} placeholder="الكحة" className="h-[28px] w-[320px] rounded-[5px] border border-line bg-well shadow-[inset_0_1px_2px_rgb(0_0_0/0.25)] focus:border-accent focus:outline-none px-2 text-[14px]" />
          <Button small onClick={search} disabled={!q.trim()}>
            Search
          </Button>
        </div>
        {found && <pre dir="auto" className="mt-2 max-h-[200px] overflow-auto rounded-[6px] bg-surface-2 p-2 text-[12px] whitespace-pre-wrap">{found}</pre>}
      </Card>
      {lib && !lib.exists && <Empty title="No library.json">The GPT asset tool has not been set up on this PC. Ads still get discs and the jar.</Empty>}
      <div className="grid grid-cols-[repeat(auto-fill,minmax(210px,1fr))] gap-3">
        {assets.map((a) => (
          <Card key={a.id} className="p-2 ring-2 ring-transparent transition-shadow hover:ring-sel">
            <img src={`/media/library/${a.id}`} alt={a.subject} className="aspect-square w-full rounded-[5px] bg-well object-contain" loading="lazy" />
            <div className="mt-2 truncate font-mono text-[12px]" title={a.id}>
              {a.id}
            </div>
            <div className="line-clamp-2 text-[12.5px] text-ink-2" title={a.subject}>
              {a.subject}
            </div>
            <div className="mt-1 flex flex-wrap gap-1">
              <Chip>{a.look}</Chip>
              {a.motion && <Chip tone="accent">{a.motion}</Chip>}
              {a.label && (
                <Chip tone="ok" className="font-caption">
                  {a.label}
                </Chip>
              )}
            </div>
            {a.keywords && (
              <div dir="auto" className="mt-1 line-clamp-2 text-[11.5px] text-ink-3" title={Object.values(a.keywords).flat().join(" · ")}>
                {[...(a.keywords.darija ?? []), ...(a.keywords.fr ?? [])].slice(0, 8).join(" · ")}
              </div>
            )}
          </Card>
        ))}
      </div>
    </div>
  );
}
