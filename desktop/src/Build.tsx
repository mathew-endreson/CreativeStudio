import { useCallback, useEffect, useState } from "react";
import { api, basename, clock, errText, fmt, type Job, type ProductDetail, type Proposal, type ResultMix, type Results, type Settings } from "./api";
import { Icon } from "./icons";
import { isActive, JobTiming, useJobs, useOnJobEnd } from "./Jobs";
import { Button, Card, cx, dirOf, Empty, ErrorNote, field, Label, Status } from "./ui";

function Stat({ label, value, tone }: { label: string; value: string; tone?: "ok" | "warn" | "bad" }) {
  return (
    <div className="rounded-[14px] bg-well px-3 py-2">
      <div className="text-[11px] text-ink-4">{label}</div>
      <div className={cx("num text-[13.5px] font-semibold", tone === "ok" && "text-ok", tone === "warn" && "text-warn", tone === "bad" && "text-bad")}>{value}</div>
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
      <div className="flex flex-wrap items-center gap-3 px-5 py-3">
        <Status tone={m.ad ? "ok" : m.built ? "info" : "neutral"} pulse={busy}>
          {state}
        </Status>
        <div className="min-w-0 flex-1">
          <div className="truncate text-[14px] font-semibold">{m.name}</div>
          <div className="num truncate text-[12px] text-ink-3">
            <span className="font-mono">{m.id}</span> · {fmt(m.duration, 1)} s {m.angle && <span dir={dirOf(m.angle)}>· {m.angle}</span>}
          </div>
        </div>
        {busy && (
          <button type="button" className="text-[12.5px] text-accent-text underline" onClick={() => openJob(mine[0].id)}>
            {mine[0].title} · <JobTiming job={mine[0]} />
          </button>
        )}
        {m.built && !m.ad && !busy && (
          <Button small icon="share" onClick={() => onAction(api.render(slug, [m.id]))}>
            Render
          </Button>
        )}
        {m.ad && m.ad_path && (
          <Button small variant="ghost" icon="folder" onClick={() => api.reveal(m.ad_path!)}>
            Show in Explorer
          </Button>
        )}
      </div>
      <div className="border-t border-line p-5">
        {m.warnings.length > 0 && (
          <div className="mb-4 rounded-[14px] bg-well p-3 text-[12.5px]">
            <div className="flex flex-wrap items-center gap-3">
              <Status tone="warn">
                {m.warnings.length} placement warning{m.warnings.length > 1 ? "s" : ""}
              </Status>
              <Button small onClick={() => onAction(api.fix(slug, m.id))} disabled={busy}>
                Fix placement
              </Button>
            </div>
            <ul className="mt-2 list-disc pl-5 text-ink-2">
              {m.warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          </div>
        )}

        <div className="grid gap-4 lg:grid-cols-[220px_1fr]">
          <div className="viewer overflow-hidden rounded-[18px]">
            {m.ad ? (
              <video src={`/media/${slug}/ad/${m.id}?v=${m.report?.finished_at ?? ""}`} controls playsInline preload="metadata" className="aspect-[9/16] w-full bg-black" />
            ) : m.sheets.includes("final_sheet.jpg") ? (
              <img src={`/media/${slug}/sheet/${m.id}/final_sheet.jpg`} alt="final sheet" className="w-full bg-black" />
            ) : (
              <div className="grid aspect-[9/16] place-items-center text-[12px] text-white/45">
                <div className="text-center">
                  <Icon name="film" size={24} className="mx-auto mb-1" strokeWidth={1.3} />
                  {m.built ? "not rendered yet" : "not built yet"}
                </div>
              </div>
            )}
          </div>
          <div className="min-w-0 space-y-4">
            {m.report && (
              <div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
                <Stat label="Length" value={`${fmt(m.report.duration, 1)} s`} />
                <Stat label="Loudness" value={`${fmt(m.report.loudness_after, 1)} LUFS`} tone={m.report.loudness_after != null ? (Math.abs(m.report.loudness_after + 15) < 1 ? "ok" : "warn") : undefined} />
                <Stat label="Peak" value={`${fmt(m.report.peak_dbfs, 1)} dB`} />
                <Stat label="Size" value={`${fmt(m.report.size_mb, 1)} MB`} />
                <Stat label="Black frames" value={String(m.report.black_frames?.length ?? 0)} tone={m.report.black_frames?.length ? "bad" : "ok"} />
                <Stat label="Render" value={clock(m.report.render_secs)} />
              </div>
            )}
            {m.snaps.length > 0 && (
              <div>
                <Label>Snapshots at every key moment</Label>
                <div className="mt-1.5 flex gap-2 overflow-x-auto pb-1">
                  {m.snaps.map((f) => (
                    <img key={f} src={`/media/${slug}/snap/${m.id}/${f}?v=${m.check?.times.length}`} alt={f} title={f} onClick={() => setBig(f)} className="press h-[150px] w-[84px] shrink-0 cursor-zoom-in rounded-[8px] bg-black object-cover" loading="lazy" />
                  ))}
                </div>
                {big && (
                  <div className="fixed inset-0 z-50 grid place-items-center bg-black/80 backdrop-blur-sm" onClick={() => setBig(null)}>
                    <img src={`/media/${slug}/snap/${m.id}/${big}`} alt={big} className="max-h-[92vh] rounded-[14px] shadow-glass" />
                  </div>
                )}
              </div>
            )}
            {m.beats.length > 0 && (
              <div>
                <Label>Pictures (time · picture · his words)</Label>
                <table className="mt-1 w-full text-[12.5px]">
                  <tbody>
                    {m.beats.map((b, i) => (
                      <tr key={i} className="border-b border-line last:border-b-0">
                        <td className="num w-[110px] py-1.5 text-ink-3">
                          {fmt(b.in)}–{fmt(b.out)}
                        </td>
                        <td className="w-[44px] py-1.5 text-ink-4">{b.side}</td>
                        <td className="py-1.5 pr-3 font-medium">{b.graphic}</td>
                        <td dir="auto" className="py-1.5 pr-4 text-ink-2">
                          {b.label}
                        </td>
                        {b.check && <td className={cx("py-1.5 pl-2 text-[12px]", /WARN|dropped/.test(b.check) ? "text-warn" : "text-ink-3")}>{b.check}</td>}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {(m.gpt_drawings.length > 0 || m.unsure.length > 0 || m.revision || (m.missing?.length ?? 0) > 0) && (
              <div className="grid gap-3 text-[12.5px] sm:grid-cols-2">
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
                    <a href={`#/p/${slug}/pictures`} className="text-[12px] text-accent-text underline">
                      Add their pictures
                    </a>
                  </div>
                )}
                {m.gpt_drawings.length > 0 && (
                  <div>
                    <Label>Drawn for this batch</Label>
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
                    <Label>Last change</Label>
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
                <textarea dir="auto" value={feedback} onChange={(e) => setFeedback(e.target.value)} placeholder="Request changes: the ad is revised and rendered again under the same file name" className={cx(field, "h-[72px] flex-1")} aria-label="Changes to request" />
                <Button disabled={!feedback.trim() || busy} onClick={() => onAction(api.revise(slug, m.id, feedback)).then(() => setFeedback(""))}>
                  Request changes
                </Button>
              </div>
            )}
          </div>
        </div>
      </div>
    </Card>
  );
}

/** The build queue and the results: picked ideas in, finished MP4s out. */
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
    <div className="space-y-[10px]">
      {err && <ErrorNote>{err}</ErrorNote>}
      <Card className="p-5">
        <div className="flex flex-wrap items-center gap-4">
          <div className="min-w-[280px] flex-1">
            <div className="text-[14px] font-semibold">Picked ideas</div>
            <div className="mt-0.5 text-[12.5px] text-ink-3">
              {picked.length === 0 ? (
                <>
                  Pick ideas in{" "}
                  <a href={`#/p/${slug}/possible`} className="text-accent-text underline">
                    Ideas
                  </a>{" "}
                  first.
                </>
              ) : (
                <>
                  Each goes through: the project's{" "}
                  <a href={`#/p/${slug}/pictures`} className="text-accent-text underline">
                    pictures
                  </a>{" "}
                  indexed → pictures placed → build → check and snapshots{doRender ? " → render" : ""}.
                </>
              )}
            </div>
          </div>
          <label className="flex items-center gap-2 text-[13px]">
            <input type="checkbox" checked={doRender} onChange={(e) => setRender(e.target.checked)} /> Render right after the check
          </label>
          <label className="flex items-center gap-2 text-[13px]" title={`Off: ideas with no picture are listed for you to upload. On: the drawing tool makes up to ${settings?.gpt_cap ?? 3} of them this run.`}>
            <input type="checkbox" checked={draw} onChange={(e) => setDraw(e.target.checked)} /> Draw missing pictures
          </label>
          <Button variant="primary" disabled={picked.length === 0} onClick={() => act(api.build(slug, picked.map((a) => a.id), doRender, draw))}>
            Build {picked.length || ""} ad{picked.length === 1 ? "" : "s"}
          </Button>
        </div>
        {picked.length > 0 && (
          <ul className="mt-3 grid gap-1.5 text-[13px] sm:grid-cols-2">
            {picked.map((a) => (
              <li key={a.id} className="flex items-center gap-3 rounded-[12px] bg-well px-3 py-1.5">
                <span className="truncate font-medium">{a.name}</span>
                <span className="num ml-auto text-ink-3">{fmt(a.duration, 1)} s</span>
                {a.graphics.filter((g) => g.kind === "missing").length > 0 && (
                  <Status tone="warn" title="Ideas with no picture yet">
                    {a.graphics.filter((g) => g.kind === "missing").length} without a picture
                  </Status>
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
        <div className="px-1 text-[12.5px] text-ink-3">
          Ads folder: <span dir="auto">{res.ads_dir}</span>{" "}
          <button type="button" className="text-accent-text underline" onClick={() => api.reveal(res.ads_dir!)}>
            open
          </button>
        </div>
      )}
    </div>
  );
}
