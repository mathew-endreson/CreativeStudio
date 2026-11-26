import { useCallback, useEffect, useState } from "react";
import { api, basename, clock, errText, fmt, type Job, type ProductDetail, type Proposal, type ResultMix, type Results, type Settings } from "./api";
import { isActive, JobTiming, useJobs, useOnJobEnd } from "./Jobs";
import { Icon } from "./icons";
import { Button, Card, Chip, cx, dirOf, Dot, Empty, ErrorNote, field, Label } from "./ui";

function Stat({ label, value, tone }: { label: string; value: string; tone?: "ok" | "warn" | "bad" }) {
  return (
    <div className="rounded-[6px] bg-well px-2.5 py-1.5 shadow-[inset_0_1px_2px_rgb(0_0_0/0.25)]">
      <div className="text-[10px] font-semibold tracking-[0.06em] text-ink-3 uppercase">{label}</div>
      <div className={cx("tc text-[13px] font-semibold", tone === "ok" && "text-ok", tone === "warn" && "text-warn", tone === "bad" && "text-bad")}>{value}</div>
    </div>
  );
}

function MixCard({ slug, m, jobs, onAction, openJob }: { slug: string; m: ResultMix; jobs: Job[]; onAction: (p: Promise<{ jobs: Job[] }>) => Promise<unknown>; openJob: (id: number) => void }) {
  const [feedback, setFeedback] = useState("");
  const [big, setBig] = useState<string | null>(null);
  const mine = jobs.filter((j) => isActive(j) && j.title.includes(m.id));
  const busy = mine.length > 0;
  const state = m.ad ? "rendered" : m.raw ? "finalizing" : m.built ? (m.check ? "checked" : "built") : "queued";
  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center gap-2 border-b border-line bg-surface-2/60 px-3 py-2">
        <Dot tone={m.ad ? "ok" : m.built ? "accent" : "neutral"} pulse={busy} />
        <Chip tone={m.ad ? "ok" : m.built ? "accent" : "neutral"}>{state}</Chip>
        <div className="min-w-0 flex-1">
          <div className="truncate text-[13.5px] font-semibold">{m.name}</div>
          <div className="truncate text-[11.5px] text-ink-3">
            <span className="font-mono">{m.id}</span> · {fmt(m.duration, 1)} s {m.angle && <span dir={dirOf(m.angle)}>· {m.angle}</span>}
          </div>
        </div>
        {busy && (
          <button className="text-[12.5px] text-accent underline" onClick={() => openJob(mine[0].id)}>
            {mine[0].title} · <JobTiming job={mine[0]} />
          </button>
        )}
        {m.built && !m.ad && !busy && (
          <Button small variant="primary" icon="share" onClick={() => onAction(api.render(slug, [m.id]))}>
            Render
          </Button>
        )}
        {m.ad && m.ad_path && (
          <Button small variant="ghost" icon="folder" onClick={() => api.reveal(m.ad_path!)}>
            Show in Explorer
          </Button>
        )}
      </div>
      <div className="p-3">

      {m.warnings.length > 0 && (
        <div className="mb-3 rounded-[6px] border border-warn/40 bg-warn/10 p-2 text-[12.5px]">
          <div className="flex items-center gap-2">
            <Icon name="alert" size={14} className="text-warn" />
            <b className="text-warn">{m.warnings.length} placement warning{m.warnings.length > 1 ? "s" : ""}</b>
            <Button small icon="sparkles" onClick={() => onAction(api.fix(slug, m.id))} disabled={busy}>
              Fix with Claude
            </Button>
          </div>
          <ul className="mt-1 list-disc pl-5 text-ink-2">
            {m.warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="grid gap-3 lg:grid-cols-[220px_1fr]">
        <div className="viewer overflow-hidden rounded-[6px] p-1">
          {m.ad ? (
            <video src={`/media/${slug}/ad/${m.id}?v=${m.report?.finished_at ?? ""}`} controls playsInline preload="metadata" className="aspect-[9/16] w-full rounded-[3px] bg-black" />
          ) : m.sheets.includes("final_sheet.jpg") ? (
            <img src={`/media/${slug}/sheet/${m.id}/final_sheet.jpg`} alt="final sheet" className="w-full rounded-[3px] bg-black" />
          ) : (
            <div className="grid aspect-[9/16] place-items-center text-[12px] text-white/45">
              <div className="text-center">
                <Icon name="film" size={24} className="mx-auto mb-1" strokeWidth={1.3} />
                {m.built ? "not rendered yet" : "not built yet"}
              </div>
            </div>
          )}
        </div>
        <div className="min-w-0 space-y-3">
          {m.report && (
            <div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
              <Stat label="length" value={`${fmt(m.report.duration, 1)} s`} />
              <Stat label="loudness" value={`${fmt(m.report.loudness_after, 1)} LUFS`} tone={m.report.loudness_after != null ? (Math.abs(m.report.loudness_after + 15) < 1 ? "ok" : "warn") : undefined} />
              <Stat label="peak" value={`${fmt(m.report.peak_dbfs, 1)} dB`} />
              <Stat label="size" value={`${fmt(m.report.size_mb, 1)} MB`} />
              <Stat label="black frames" value={String(m.report.black_frames?.length ?? 0)} tone={m.report.black_frames?.length ? "bad" : "ok"} />
              <Stat label="render" value={clock(m.report.render_secs)} />
            </div>
          )}
          {m.snaps.length > 0 && (
            <div>
              <Label>Snapshots at every key moment</Label>
              <div className="mt-1 flex gap-1.5 overflow-x-auto pb-1">
                {m.snaps.map((f) => (
                  <img key={f} src={`/media/${slug}/snap/${m.id}/${f}?v=${m.check?.times.length}`} alt={f} title={f} onClick={() => setBig(f)} className="h-[150px] w-[84px] shrink-0 cursor-zoom-in rounded-[3px] bg-black object-cover ring-2 ring-transparent hover:ring-sel" loading="lazy" />
                ))}
              </div>
              {big && (
                <div className="fixed inset-0 z-50 grid place-items-center bg-black/80 backdrop-blur-sm" onClick={() => setBig(null)}>
                  <img src={`/media/${slug}/snap/${m.id}/${big}`} alt={big} className="max-h-[92vh] rounded-[6px] shadow-hud" />
                </div>
              )}
            </div>
          )}
          {m.beats.length > 0 && (
            <div>
              <Label>Assets (time · picture · his words)</Label>
              <table className="mt-1 w-full text-[12.5px]">
                <tbody>
                  {m.beats.map((b, i) => (
                    <tr key={i} className="border-b border-line last:border-b-0">
                      <td className="num w-[110px] py-1 text-ink-3">
                        {fmt(b.in)}–{fmt(b.out)}
                      </td>
                      <td className="w-[36px] py-1">
                        <Chip>{b.side}</Chip>
                      </td>
                      <td className="py-1 font-medium">{b.graphic}</td>
                      <td dir="auto" className="py-1 text-ink-2">
                        {b.label}
                      </td>
                      {b.check && <td className={cx("py-1 text-[12px]", /WARN|dropped/.test(b.check) ? "text-warn" : "text-ink-3")}>{b.check}</td>}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {(m.gpt_drawings.length > 0 || m.unsure.length > 0 || m.revision || (m.missing?.length ?? 0) > 0) && (
            <div className="grid gap-2 text-[12.5px] sm:grid-cols-2">
              {m.missing && m.missing.length > 0 && (
                <div>
                  <Label>Ideas with no picture</Label>
                  <ul className="mt-1 list-disc pl-4">
                    {m.missing.map((x, i) => (
                      <li key={i}>
                        <span className="font-medium">{x.concept}</span>
                        {x.words && (
                          <span className="text-ink-3">
                            {" · "}
                            <bdi>{x.words}</bdi>
                          </span>
                        )}
                      </li>
                    ))}
                  </ul>
                  <a href={`#/p/${slug}/pictures`} className="text-[12px] text-accent underline">
                    Add their pictures
                  </a>
                </div>
              )}
              {m.gpt_drawings.length > 0 && (
                <div>
                  <Label>GPT drew for this batch</Label>
                  <ul className="mt-1 space-y-1">
                    {m.gpt_drawings.map((g, i) => (
                      <li key={i} title={g.prompt}>
                        <code>{basename(g.path)}</code>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {m.unsure.length > 0 && (
                <div>
                  <Label>Claude was unsure of</Label>
                  <ul className="mt-1 list-disc pl-4">
                    {m.unsure.map((u, i) => (
                      <li key={i} dir={dirOf(u)}>
                        {u}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {m.revision && (
                <div className="sm:col-span-2">
                  <Label>Last revision</Label>
                  <ul className="mt-1 list-disc pl-4">
                    {m.revision.changed.map((c, i) => (
                      <li key={i} dir={dirOf(c)}>
                        {c}
                      </li>
                    ))}
                  </ul>
                  {m.revision.notes && <div className="text-ink-3">{m.revision.notes}</div>}
                </div>
              )}
            </div>
          )}
          {m.built && (
            <div className="flex gap-2">
              <textarea dir="auto" value={feedback} onChange={(e) => setFeedback(e.target.value)} placeholder="Request changes: Claude revises this ad and renders it again under the same file name" className={cx(field, "h-16 flex-1 py-1.5")} />
              <Button variant="primary" icon="sparkles" disabled={!feedback.trim() || busy} onClick={() => onAction(api.revise(slug, m.id, feedback)).then(() => setFeedback(""))}>
                Revise
              </Button>
            </div>
          )}
        </div>
      </div>
      </div>
    </Card>
  );
}

/** The build queue and the results: ticked proposals in, finished MP4s out. */
export default function Build({ p, reload, openJob }: { p: ProductDetail; reload: () => void; openJob: (id: number) => void }) {
  const slug = p.slug;
  const [props, setProps] = useState<Proposal[]>([]);
  const [res, setRes] = useState<Results | null>(null);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [render, setRender] = useState<boolean | null>(null);
  const [draw, setDraw] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const jobs = useJobs(slug);
  const load = useCallback(() => {
    api.proposals(slug).then((x) => setProps(x.ads)).catch((e) => setErr(errText(e)));
    api.results(slug).then(setRes).catch((e) => setErr(errText(e)));
  }, [slug]);
  useEffect(() => {
    load();
    api.settings().then(setSettings).catch(() => {});
  }, [load]);
  useOnJobEnd(jobs, () => {
    load();
    reload();
  });
  const picked = props.filter((a) => a.picked && a.status === "proposed");
  const doRender = render ?? settings?.auto_render ?? false;
  const act = (pr: Promise<{ jobs: Job[] }>) =>
    pr
      .then((r) => {
        if (r.jobs[0]) openJob(r.jobs[0].id);
        load();
        return r;
      })
      .catch((e) => {
        setErr(errText(e));
        return { jobs: [] as Job[] };
      });

  return (
    <div className="space-y-3">
      {err && <ErrorNote>{err}</ErrorNote>}
      <Card className="p-3">
        <div className="flex flex-wrap items-center gap-3">
          <span className="clip grid h-8 w-8 shrink-0 place-items-center rounded-[6px] bg-surface-3 text-ink-2">
            <Icon name="share" size={15} />
          </span>
          <div className="min-w-[280px] flex-1">
            <div className="font-semibold">Ticked proposals</div>
            <div className="text-[12.5px] text-ink-2">
              {picked.length === 0 ? (
                <>Tick ads in <a href={`#/p/${slug}/possible`} className="text-accent underline">Possible ads</a> first.</>
              ) : (
                <>
                  Each goes through: the product's <a href={`#/p/${slug}/pictures`} className="text-accent underline">pictures</a> indexed → assets (Claude) → build → lint and snapshots{doRender ? " → render" : ""}. No speaker cutout: the pictures sit in front of him.
                </>
              )}
            </div>
          </div>
          <label className="flex items-center gap-1.5 text-[13px]">
            <input type="checkbox" checked={doRender} onChange={(e) => setRender(e.target.checked)} /> render right after the check
          </label>
          <label
            className="flex items-center gap-1.5 text-[13px]"
            title={`Off: ideas he names that no picture shows are listed for you to upload. On: GPT draws up to ${settings?.gpt_cap ?? 3} of them this run (your ChatGPT image allowance).`}
          >
            <input type="checkbox" checked={draw} onChange={(e) => setDraw(e.target.checked)} /> let GPT draw missing pictures
          </label>
          <Button variant="primary" icon="share" disabled={picked.length === 0} onClick={() => act(api.build(slug, picked.map((a) => a.id), doRender, draw))}>
            Build {picked.length || ""} ad{picked.length === 1 ? "" : "s"}
          </Button>
        </div>
        {picked.length > 0 && (
          <ul className="mt-2 grid gap-1 text-[13px] sm:grid-cols-2">
            {picked.map((a) => (
              <li key={a.id} className="flex items-center gap-2 rounded-[5px] border-l-[3px] border-sel bg-surface-2 px-2 py-1">
                <span className="truncate font-medium">{a.name}</span>
                <span className="num ml-auto text-ink-3">{fmt(a.duration, 1)} s</span>
                {a.graphics.filter((g) => g.kind === "missing").length > 0 && (
                  <Chip tone="warn" title="Ideas he names that no picture shows yet">
                    {a.graphics.filter((g) => g.kind === "missing").length} without a picture
                  </Chip>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>

      {res && res.mixes.length === 0 && <Empty title="No ad built yet">The ads you build appear here with their snapshots, report and player.</Empty>}
      {res?.mixes
        .slice()
        .reverse()
        .map((m) => <MixCard key={m.id} slug={slug} m={m} jobs={jobs} onAction={act} openJob={openJob} />)}
      {res?.ads_dir && (
        <div className="text-[12.5px] text-ink-3">
          Ads folder: <span dir="auto">{res.ads_dir}</span>{" "}
          <button className="text-accent underline" onClick={() => api.reveal(res.ads_dir!)}>
            open
          </button>
        </div>
      )}
    </div>
  );
}
