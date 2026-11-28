import { useEffect, useState } from "react";
import { api, errText, type Job, type ProductCard } from "./api";
import { FrameTiles } from "./brand";
import { Icon } from "./icons";
import { ActivityPanel, isActive, useOnJobEnd } from "./Jobs";
import { thumb } from "./SegEditor";
import { Button, cx, Empty, ErrorNote, Loading, Search, Segmented, Status, Toolbar, type Tone } from "./ui";

type Filter = "all" | "progress" | "ready";

/** The four stages a project goes through, lit as far as it got. */
function StageBar({ p }: { p: ProductCard }) {
  const stages = [
    { label: "Analyze", done: !!p.analysis },
    { label: "Propose", done: (p.proposals ?? 0) > 0 },
    { label: "Build", done: (p.mixes ?? 0) > 0 },
    { label: "Render", done: (p.ads ?? 0) > 0 },
  ];
  return (
    <div className="flex gap-1" title={stages.map((s) => `${s.label}: ${s.done ? "done" : "not yet"}`).join(" · ")} aria-label="Stages">
      {stages.map((s) => (
        <span key={s.label} className={cx("h-[4px] flex-1 rounded-full", s.done ? "bg-ink/80" : "bg-white/[0.12]")} />
      ))}
    </div>
  );
}

function statusOf(p: ProductCard, busy: boolean): { tone: Tone; text: string } {
  if (busy) return { tone: "info", text: "Working" };
  if ((p.ads ?? 0) > 0) return { tone: "ok", text: "Ready" };
  if (p.analysis) return { tone: "warn", text: "In progress" };
  return { tone: "neutral", text: "Not analysed" };
}

export default function Products({ jobs, openJob }: { jobs: Job[]; openJob: (id: number) => void }) {
  const [list, setList] = useState<ProductCard[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  // real frames from the engine for the cards of analysed products: the first three sources that have a copy
  const [thumbs, setThumbs] = useState<Record<string, string[]>>({});
  const load = () =>
    api
      .products()
      .then((l) => {
        setList(l);
        for (const p of l.filter((x) => x.analysis && !x.not_imported && !x.error).slice(0, 24)) {
          api
            .product(p.slug)
            .then((d) => {
              const t = d.sources.filter((s) => s.copy).slice(0, 3).map((s) => thumb(p.slug, s.key, 45, 240));
              if (t.length) setThumbs((m) => ({ ...m, [p.slug]: t }));
            })
            .catch(() => {});
        }
      })
      .catch((e) => setErr(errText(e)));
  useEffect(() => {
    load();
  }, []);
  useOnJobEnd(jobs, load);

  if (err) return <ErrorNote>Could not load the projects: {err}</ErrorNote>;
  if (!list) return <Loading />;
  const busy = new Set(jobs.filter(isActive).map((j) => j.slug));
  const shown = list.filter((p) => {
    if (q.trim() && !`${p.name} ${p.name_ar ?? ""} ${p.slug}`.toLowerCase().includes(q.trim().toLowerCase())) return false;
    if (filter === "ready") return (p.ads ?? 0) > 0;
    if (filter === "progress") return busy.has(p.slug) || (!!p.analysis && !(p.ads ?? 0));
    return true;
  });

  return (
    <div className="flex h-full min-h-0 flex-col">
      <Toolbar title="Projects" sub={`${list.length} project${list.length === 1 ? "" : "s"}`}>
        <Segmented
          small
          value={filter}
          onChange={setFilter}
          options={[
            { id: "all", label: "All" },
            { id: "progress", label: "In progress" },
            { id: "ready", label: "Ready" },
          ]}
        />
        <Search value={q} onChange={setQ} />
        <Button variant="primary" icon="plus" onClick={() => (location.hash = "#/new")}>
          New
        </Button>
      </Toolbar>
      <div className="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)_300px] gap-[10px]">
        <div className="min-h-0 overflow-auto">
          {list.length === 0 && <Empty title="No project yet">Create one from a folder of finished ads, or start a fresh edit from one footage.</Empty>}
          {list.length > 0 && shown.length === 0 && <Empty title="Nothing matches">Try another filter or search.</Empty>}
          <div className="grid grid-cols-[repeat(auto-fill,minmax(290px,1fr))] gap-[10px]">
            {shown.map((p) => {
              if (p.not_imported || p.error) {
                return (
                  <div key={p.slug} className="flex h-[290px] flex-col justify-end rounded-[22px] border border-line bg-surface p-4">
                    <div className="flex items-center gap-2 font-semibold">
                      <Icon name="folder" size={14} className="text-ink-3" />
                      {p.slug}
                    </div>
                    <div className="mt-1 text-[12px] text-ink-3">{p.error ?? "This batch folder has no product.json yet."}</div>
                  </div>
                );
              }
              const s = statusOf(p, busy.has(p.slug));
              return (
                <a
                  key={p.slug}
                  href={`#/p/${p.slug}/analysis`}
                  className="press group relative block h-[290px] overflow-hidden rounded-[22px] border border-line focus-visible:outline-2 focus-visible:outline-focus"
                >
                  <FrameTiles seed={p.slug} height={290} thumbs={thumbs[p.slug]} />
                  <div className="glass-img absolute inset-x-0 bottom-0 rounded-none border-x-0 border-b-0 px-4 py-3">
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <div className="truncate text-[14px] font-semibold">{p.name || p.slug}</div>
                        {p.name_ar && (
                          <div dir="auto" className="truncate text-[12px] text-ink-3">
                            {p.name_ar}
                          </div>
                        )}
                      </div>
                      <span className="num shrink-0 text-[12px] text-ink-2">
                        {p.ads ?? 0} ad{p.ads === 1 ? "" : "s"}
                      </span>
                    </div>
                    <div className="mt-2 flex items-center justify-between gap-3">
                      <Status tone={s.tone} pulse={s.tone === "info"}>
                        {s.text}
                      </Status>
                      {!!p.todo?.length && <span className="truncate text-[11.5px] text-ink-4">missing: {p.todo.join(", ")}</span>}
                    </div>
                    <div className="mt-2.5">
                      <StageBar p={p} />
                    </div>
                  </div>
                </a>
              );
            })}
          </div>
        </div>
        <ActivityPanel jobs={jobs} openJob={openJob} className="max-h-full self-start" />
      </div>
    </div>
  );
}
