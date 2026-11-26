import { useCallback, useEffect, useState } from "react";
import { api, errText, type ProductDetail } from "./api";
import Analysis from "./Analysis";
import Build from "./Build";
import { Icon } from "./icons";
import Pictures from "./Pictures";
import Proposals from "./Proposals";
import { Button, Chip, ErrorNote, Loading, Segmented } from "./ui";

const TABS = [
  { id: "analysis", label: "Analysis", icon: "eye" as const },
  { id: "possible", label: "Possible ads", icon: "scissors" as const },
  { id: "pictures", label: "Pictures", icon: "images" as const },
  { id: "build", label: "Build & results", icon: "share" as const },
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

  return (
    <div>
      <div className="glass mb-[6px] rounded-[12px] px-3 py-2.5">
        <div className="flex flex-wrap items-center gap-3">
          <span className="clip grid h-9 w-9 shrink-0 place-items-center rounded-[8px] bg-surface-3 text-sel">
            <Icon name="star" size={17} />
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="flex items-baseline gap-3 text-[17px] leading-tight font-semibold tracking-tight">
              <span className="truncate">{P.name}</span>
              {P.name_ar && (
                <span dir="auto" className="font-caption text-[16px] font-black text-ink-2">
                  {P.name_ar}
                </span>
              )}
            </h1>
            <div className="mt-0.5 flex min-w-0 items-center gap-2 text-[11.5px] text-ink-3">
              <code className="truncate">{p.dir}</code>
              <span>·</span>
              <span className="shrink-0">Ads folder:</span>
              <span dir="auto" className="truncate">{P.ads_dir || "not set"}</span>
              {P.ads_dir && (
                <Button small variant="ghost" icon="folder" onClick={() => api.reveal(P.ads_dir)}>
                  Open
                </Button>
              )}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            {p.todo.map((t) => (
              <Chip key={t} tone="warn">
                missing: {t}
              </Chip>
            ))}
            <Chip title="Claude runs for this project">
              Claude: {p.usage.claude_runs} run{p.usage.claude_runs === 1 ? "" : "s"}
              {p.usage.claude_runs > 0 && ` · ${(p.usage.output_tokens / 1000).toFixed(1)}k out · $${p.usage.cost_usd.toFixed(2)}`}
            </Chip>
            <Chip>GPT drawings: {p.usage.gpt_drawings}</Chip>
            <Chip tone={rendered ? "ok" : "neutral"}>
              {rendered} / {p.mixes.length} rendered
            </Chip>
          </div>
        </div>
        <div className="mt-2.5 flex justify-center">
          <Segmented value={tab} options={TABS} onChange={(id) => (location.hash = `#/p/${slug}/${id}`)} />
        </div>
      </div>

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
