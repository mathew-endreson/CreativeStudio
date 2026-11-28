import { useCallback, useEffect, useState } from "react";
import { api, errText, type ProductDetail } from "./api";
import Analysis from "./Analysis";
import { tintFor } from "./brand";
import Build from "./Build";
import Pictures from "./Pictures";
import Proposals from "./Proposals";
import { Button, ErrorNote, Loading, Segmented, Status, Toolbar } from "./ui";

const TABS = [
  { id: "analysis", label: "Analysis" },
  { id: "possible", label: "Ideas" },
  { id: "pictures", label: "Pictures" },
  { id: "build", label: "Results" },
];

export default function Product({ slug, tab, openJob }: { slug: string; tab: string; openJob: (id: number) => void }) {
  const [p, setP] = useState<ProductDetail | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const reload = useCallback(() => {
    api.product(slug).then(setP).catch((e) => setErr(errText(e)));
  }, [slug]);
  useEffect(() => {
    setP(null);
    setErr(null);
    reload();
  }, [reload]);

  if (err) return <ErrorNote>{err}</ErrorNote>;
  if (!p) return <Loading />;
  const P = p.product;
  const rendered = p.mixes.filter((m) => m.ad).length;
  const tint = tintFor(slug);

  return (
    <div>
      <Toolbar back="#/">
        <div className="mr-auto flex min-w-0 items-center gap-3">
          <span className="h-[28px] w-[28px] shrink-0 rounded-[8px]" style={{ background: tint.bg, boxShadow: `inset 0 0 0 1px ${tint.frame}` }} aria-hidden="true" />
          <div className="min-w-0">
            <h1 className="flex items-baseline gap-3 text-[17px] leading-tight font-semibold tracking-tight">
              <span className="truncate">{P.name}</span>
              {P.name_ar && (
                <span dir="auto" className="font-caption truncate text-[15px] font-black text-ink-2">
                  {P.name_ar}
                </span>
              )}
            </h1>
            <div className="num mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[12px] text-ink-3">
              <Status tone={rendered ? "ok" : "neutral"}>
                {rendered} of {p.mixes.length} rendered
              </Status>
              <span>
                Claude {p.usage.claude_runs} run{p.usage.claude_runs === 1 ? "" : "s"}
                {p.usage.claude_runs > 0 && ` · $${p.usage.cost_usd.toFixed(2)}`}
              </span>
              {p.usage.gpt_drawings > 0 && <span>{p.usage.gpt_drawings} GPT drawings</span>}
              {p.todo.map((t) => (
                <Status key={t} tone="warn">
                  missing: {t}
                </Status>
              ))}
            </div>
          </div>
        </div>
        <Segmented value={tab} options={TABS} onChange={(id) => (location.hash = `#/p/${slug}/${id}`)} />
        {P.ads_dir && (
          <Button icon="folder" onClick={() => api.reveal(P.ads_dir)} title={P.ads_dir}>
            Ads folder
          </Button>
        )}
      </Toolbar>

      {tab === "build" ? (
        <Build p={p} reload={reload} openJob={openJob} />
      ) : tab === "possible" ? (
        <Proposals p={p} reload={reload} openJob={openJob} />
      ) : tab === "pictures" ? (
        <Pictures p={p} reload={reload} openJob={openJob} />
      ) : (
        <Analysis p={p} reload={reload} openJob={openJob} />
      )}
    </div>
  );
}
