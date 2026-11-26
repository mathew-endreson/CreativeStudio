import { useEffect, useState } from "react";
import { api, errText, type ProductCard } from "./api";
import { Icon } from "./icons";
import { Button, Chip, cx, Empty, ErrorNote, Loading, PageHeader } from "./ui";

function Count({ n, label }: { n: number | undefined; label: string }) {
  return (
    <div className="min-w-0">
      <div className="num text-[15px] leading-none font-semibold">{n ?? 0}</div>
      <div className="mt-1 truncate text-[10.5px] text-ink-3">{label}</div>
    </div>
  );
}

/** A decorative storyline: the project drawn as hook / body / CTA clips, the way Final Cut draws a project thumbnail. */
function Storyline({ seed, done }: { seed: string; done: boolean }) {
  let h = 0;
  for (const c of seed) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  const w = [14 + (h % 9), 46 + ((h >> 4) % 18), 18 + ((h >> 9) % 8)];
  return (
    <div className={cx("flex h-[18px] gap-[2px]", !done && "opacity-50")}>
      <div className="clip rounded-[3px] bg-hook" style={{ flex: w[0] }} />
      <div className="clip rounded-[3px] bg-body" style={{ flex: w[1] }} />
      <div className="clip rounded-[3px] bg-cta" style={{ flex: w[2] }} />
    </div>
  );
}

export default function Products() {
  const [list, setList] = useState<ProductCard[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [q, setQ] = useState("");
  useEffect(() => {
    api.products().then(setList).catch((e) => setErr(errText(e)));
  }, []);

  if (err) return <ErrorNote>Could not load the projects: {err}</ErrorNote>;
  if (!list) return <Loading />;
  const shown = list.filter((p) => !q.trim() || `${p.name} ${p.name_ar ?? ""} ${p.slug}`.toLowerCase().includes(q.trim().toLowerCase()));

  return (
    <div>
      <PageHeader
        icon="film"
        title="Projects"
        sub="A project is one product: its finished ads, the analysis, the ads proposed from them, and the ones rendered into its Ads folder."
        actions={
          <>
            <label className="relative">
              <Icon name="search" size={13} className="pointer-events-none absolute top-1/2 left-2 -translate-y-1/2 text-ink-3" />
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Search"
                dir="auto"
                className="h-[28px] w-[200px] rounded-[6px] border border-line bg-well pr-2 pl-7 text-[12.5px] placeholder:text-ink-3 focus:border-accent focus:outline-none"
              />
            </label>
            <Button icon="wand" onClick={() => (location.hash = "#/fresh")}>
              Fresh edit
            </Button>
            <Button variant="primary" icon="plus" onClick={() => (location.hash = "#/new")}>
              New project
            </Button>
          </>
        }
      />
      {list.length === 0 && <Empty title="No project yet">Create one from a folder of finished ads, or start a fresh edit from one footage.</Empty>}
      <div className="grid grid-cols-[repeat(auto-fill,minmax(290px,1fr))] gap-3">
        {shown.map((p) =>
          p.not_imported || p.error ? (
            <div key={p.slug} className="rounded-[12px] border border-dashed border-line-strong bg-surface/40 p-3 backdrop-blur-md">
              <div className="flex items-center gap-2 font-semibold">
                <Icon name="folder" size={14} className="text-ink-3" />
                {p.slug}
              </div>
              <div className="mt-1 text-[12px] text-ink-2">{p.error ?? "This batch folder has no product.json yet."}</div>
            </div>
          ) : (
            <a
              key={p.slug}
              href={`#/p/${p.slug}/analysis`}
              className="glass group block overflow-hidden rounded-[12px] ring-2 ring-transparent transition-[box-shadow,transform] duration-150 hover:-translate-y-px hover:ring-sel focus-visible:ring-sel"
            >
              <div className="viewer relative flex h-[112px] flex-col justify-between p-3">
                <div className="flex items-start justify-between gap-2">
                  <Icon name="star" size={15} className={p.analysis ? "text-sel" : "text-white/30"} />
                  <Chip tone={p.analysis ? "ok" : "neutral"}>{p.analysis ? "analysed" : "not analysed"}</Chip>
                </div>
                <div dir="auto" className="font-caption truncate text-[22px] leading-tight font-black text-white/90">
                  {p.name_ar || p.name}
                </div>
                <Storyline seed={p.slug} done={!!p.analysis} />
              </div>
              <div className="border-t border-line px-3 py-2.5">
                <div className="truncate text-[13.5px] font-semibold">{p.name}</div>
                <div className="mt-2.5 grid grid-cols-4 gap-2">
                  <Count n={p.sources} label="sources" />
                  <Count n={p.proposals} label="proposals" />
                  <Count n={p.mixes} label="mixes" />
                  <Count n={p.ads} label="ads" />
                </div>
                {!!p.todo?.length && (
                  <div className="mt-2.5 flex flex-wrap gap-1">
                    {p.todo.map((t) => (
                      <Chip key={t} tone="warn">
                        missing: {t}
                      </Chip>
                    ))}
                  </div>
                )}
              </div>
            </a>
          ),
        )}
      </div>
    </div>
  );
}
