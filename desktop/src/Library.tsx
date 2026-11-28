import { useEffect, useState } from "react";
import { api, errText, type Library as LibraryT } from "./api";
import { Button, Card, Empty, ErrorNote, field, Label, Search, Status, Toolbar } from "./ui";

/** The picture library: every illustration drawn for the ads, with its keywords. The ads use each product's own
 *  pictures (its Pictures tab); new drawings are made only when the user asks. */
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
    <div>
      <Toolbar title="Library" sub={lib ? `${lib.assets.length} pictures · the ads themselves use each project's own pictures` : "…"}>
        <Search value={filter} onChange={setFilter} placeholder="Filter pictures" />
        <Button onClick={() => api.gptStatus().then(setStatus).catch((e) => setErr(errText(e)))}>Drawing status</Button>
      </Toolbar>
      {err && <ErrorNote>{err}</ErrorNote>}
      {status && (
        <Card className="mb-[10px] p-4 text-[12.5px]">
          <Label>Drawing tool status</Label>
          <pre className="mt-1 whitespace-pre-wrap text-ink-2">{JSON.stringify(status, null, 1)}</pre>
        </Card>
      )}
      <Card className="mb-[10px] p-4">
        <Label>Which picture does a spoken word pull?</Label>
        <div className="mt-2 flex gap-2">
          <input dir="auto" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && search()} placeholder="الكحة" className={`${field} w-[320px] text-[14px]`} aria-label="A spoken word" />
          <Button onClick={search} disabled={!q.trim()}>
            Search
          </Button>
        </div>
        {found && <pre dir="auto" className="mt-3 max-h-[200px] overflow-auto rounded-[14px] bg-well p-3 text-[12px] whitespace-pre-wrap text-ink-2">{found}</pre>}
      </Card>
      {lib && !lib.exists && <Empty title="No library yet">The drawing tool has not been set up on this PC. The ads use each project's own pictures, so nothing is missing.</Empty>}
      <div className="grid grid-cols-[repeat(auto-fill,minmax(210px,1fr))] gap-[10px]">
        {assets.map((a) => (
          <Card key={a.id} className="press overflow-hidden p-3 hover:border-line-strong">
            <img src={`/media/library/${a.id}`} alt={a.subject} className="aspect-square w-full rounded-[14px] bg-well object-contain" loading="lazy" />
            <div className="mt-2.5 truncate text-[13px] font-medium" title={a.subject}>
              {a.subject || a.id}
            </div>
            <div className="truncate font-mono text-[11px] text-ink-4" title={a.id}>
              {a.id}
            </div>
            <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-[12px] text-ink-3">
              <span>{a.look}</span>
              {a.motion && <span>{a.motion}</span>}
              {a.label && (
                <Status tone="ok" className="font-caption">
                  {a.label.replace(/<[^>]+>/g, "")}
                </Status>
              )}
            </div>
            {a.keywords && (
              <div dir="auto" className="mt-1 line-clamp-2 text-[11.5px] text-ink-4" title={Object.values(a.keywords).flat().join(" · ")}>
                {[...(a.keywords.darija ?? []), ...(a.keywords.fr ?? [])].slice(0, 8).join(" · ")}
              </div>
            )}
          </Card>
        ))}
      </div>
    </div>
  );
}
