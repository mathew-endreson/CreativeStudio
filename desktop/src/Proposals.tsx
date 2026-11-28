import { useCallback, useEffect, useState } from "react";
import { api, errText, fmt, frameOf, type Graphic, type Job, type ProductDetail, type Proposal, type ProposalList } from "./api";
import { Icon } from "./icons";
import { ActiveJobs, isActive, useJobs, useOnJobEnd } from "./Jobs";
import { Preview, roleOf, SegEditor, thumb } from "./SegEditor";
import { Button, Card, cx, dirOf, Empty, ErrorNote, field, Glass, Label, Loading, Status, type Tone } from "./ui";

// library = one of the product's pictures, missing = an idea no picture shows yet; disc / pack / offer come from
// proposals made before Nov 26 2026, when the ads still had icon discs and jar packshots
const graphicTone = (g: Graphic): Tone => (g.kind === "missing" ? "warn" : g.kind === "library" ? "ok" : "neutral");
const graphicName = (g: Graphic) =>
  g.kind === "missing" ? `no picture: ${g.what}` : g.kind === "library" ? g.what : g.kind === "disc" ? `old style: ${g.what} disc` : g.kind === "pack" ? "old style: jar" : "old style: offer photo";

function Segments({ slug, ad, labels }: { slug: string; ad: Proposal; labels: Record<string, string> }) {
  return (
    <div className="space-y-2">
      {ad.segs.map((s, i) => {
        const role = roleOf(ad, i);
        const first = frameOf(s.v0 ?? s.a0),
          last = frameOf(s.v1 ?? s.a1) - 1;
        return (
          <div key={i} className="flex gap-3 rounded-[14px] bg-well p-2">
            <div className="flex shrink-0 gap-1">
              <img src={thumb(slug, s.src, first)} alt={`first frame of segment ${i + 1}`} title={`first frame shown: f${first}`} className="h-[80px] w-[45px] rounded-[6px] bg-black object-cover" loading="lazy" />
              <img src={thumb(slug, s.src, last)} alt={`last frame of segment ${i + 1}`} title={`last frame shown: f${last}`} className="h-[80px] w-[45px] rounded-[6px] bg-black object-cover" loading="lazy" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px]">
                <Status tone={role}>{role === "hook" ? (i === 0 && ad.hook_beats ? "hook, lifted" : "hook") : role === "cta" ? "CTA" : "body"}</Status>
                <span className="font-semibold text-ink">{labels[s.src] ?? s.src}</span>
                <span className="tc text-ink-3">
                  {fmt(s.a0)}–{fmt(s.a1)} s ({fmt((frameOf(s.a1) - frameOf(s.a0)) / 30, 1)} s)
                </span>
                {s.v0 != null && (
                  <span className="text-ink-4" title="The picture starts on this clean frame and is held back to the cut">
                    picture from {fmt(s.v0, 3)}
                  </span>
                )}
                {s.v1 != null && (
                  <span className="text-ink-4" title="The picture is held on this clean frame until the cut">
                    picture until {fmt(s.v1, 3)}
                  </span>
                )}
                {role !== "hook" && !ad.body.includes(i) && role !== "cta" && <span className="text-ink-4">no pictures on this segment</span>}
              </div>
              <div dir="auto" className="mt-0.5 text-[14.5px] leading-snug" title={s.text ? `Whisper wrote: ${s.text}` : undefined}>
                {s.said || s.text}
              </div>
              {s.note && (
                <div dir={dirOf(s.note)} className="text-[12px] text-ink-3">
                  {s.note}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/** The storyboard strip: the first frame of every segment, sized by its length. Click to preview. */
function Storyboard({ slug, ad, labels, onPlay }: { slug: string; ad: Proposal; labels: Record<string, string>; onPlay: () => void }) {
  const total = ad.segs.reduce((n, s) => n + Math.max(0.05, s.a1 - s.a0), 0);
  return (
    <button type="button" onClick={onPlay} aria-label="Rough preview of this ad" className="press flex h-[104px] w-full gap-[3px] overflow-hidden rounded-[14px] bg-black">
      {ad.segs.map((s, i) => {
        const role = roleOf(ad, i);
        return (
          <span key={i} className="relative min-w-[18px] overflow-hidden" style={{ flex: Math.max(0.05, s.a1 - s.a0) / total }} title={`${role} · ${labels[s.src] ?? s.src} ${fmt(s.a0)}–${fmt(s.a1)} s`}>
            <img src={thumb(slug, s.src, frameOf(s.v0 ?? s.a0))} alt="" className="h-full w-full object-cover" loading="lazy" />
            <span className={cx("absolute inset-x-0 bottom-0 h-[3px]", role === "hook" ? "bg-hook" : role === "cta" ? "bg-cta" : "bg-body")} />
          </span>
        );
      })}
    </button>
  );
}

function AdCard({ slug, ad, labels, onChange }: { slug: string; ad: Proposal; labels: Record<string, string>; onChange: (p: Proposal) => void }) {
  const [editing, setEditing] = useState(false);
  const [preview, setPreview] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const [open, setOpen] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const patch = (p: Record<string, unknown>) => api.patchProposal(slug, ad.id, p).then(onChange).catch((e) => setErr(errText(e)));
  const missing = ad.graphics.filter((g) => g.kind === "missing");
  const rejected = ad.status === "rejected";
  const hookSeg = ad.segs.find((_, i) => roleOf(ad, i) === "hook") ?? ad.segs[0];
  const hook = hookSeg?.said || hookSeg?.text || ad.name;

  return (
    <Card className={cx("relative flex flex-col p-4 transition-[border-color,opacity]", ad.picked ? "border-2 border-accent" : "border border-line", rejected && "opacity-60")}>
      {!rejected && (
        <button
          type="button"
          aria-pressed={ad.picked}
          aria-label={ad.picked ? "Picked to build: click to unpick" : "Pick this ad to build"}
          title={ad.exists ? `An ad with these segments already exists: ${ad.exists.name}` : ad.picked ? "Picked to build" : "Pick to build"}
          disabled={!!ad.exists}
          onClick={() => patch({ picked: !ad.picked })}
          className={cx("press absolute top-3 right-3 z-10 grid h-[32px] w-[32px] place-items-center rounded-full disabled:opacity-40", ad.picked ? "pill-accent text-white" : "glass-pill text-ink-2 hover:text-ink")}
        >
          <Icon name="check" size={15} />
        </button>
      )}
      <Storyboard slug={slug} ad={ad} labels={labels} onPlay={() => setPreview(true)} />
      <div className="mt-3 flex items-center gap-2 text-[12px] text-ink-3">
        <span dir={dirOf(ad.angle)} className="truncate">
          {ad.angle}
        </span>
        <span>·</span>
        <span className="num shrink-0">{fmt(ad.duration, 1)} s</span>
      </div>
      <h3 dir="auto" className="mt-1 line-clamp-3 text-[17px] leading-snug font-semibold" title={ad.file_name}>
        {hook}
      </h3>
      <div dir={dirOf(ad.why)} className="mt-1.5 line-clamp-2 text-[12.5px] text-ink-2" title={ad.why}>
        {ad.why}
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1">
        {ad.exists && (
          <Status tone="bad" title="An ad with these segments already exists">
            already exists: {ad.exists.name}
          </Status>
        )}
        {ad.built && <Status tone="ok">built</Status>}
        {ad.edited && (
          <Status tone="info" title="You changed its segments">
            edited by you
          </Status>
        )}
        {rejected && <Status tone="bad">rejected</Status>}
        {missing.length > 0 && !rejected && (
          <Status tone="warn">
            {missing.length} idea{missing.length > 1 ? "s" : ""} without a picture
          </Status>
        )}
      </div>

      {open && (
        <div className="mt-3 space-y-3 border-t border-line pt-3">
          <div>
            <Label>Segments</Label>
            <div className="mt-1.5">
              <Segments slug={slug} ad={ad} labels={labels} />
            </div>
          </div>
          <div>
            <Label>Risks</Label>
            {ad.risks.length === 0 ? (
              <div className="mt-1 text-[13px] text-ink-3">None named.</div>
            ) : (
              <ul className="mt-1 list-disc space-y-0.5 pl-4 text-[13px]">
                {ad.risks.map((r, i) => (
                  <li key={i} dir={dirOf(r)}>
                    {r}
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div>
            <Label>Planned pictures</Label>
            <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1">
              {ad.graphics.length === 0 && <span className="text-[13px] text-ink-3">None planned.</span>}
              {ad.graphics.map((g, i) => (
                <Status key={i} tone={graphicTone(g)} title={`on «${g.on}»${g.label ? ` · label ${g.label}` : ""}${g.existing ? " · already written in the beats file" : " · new"}`}>
                  {graphicName(g)}
                </Status>
              ))}
            </div>
            {missing.length > 0 && (
              <div className="mt-1 text-[12.5px] text-ink-3">
                <a href={`#/p/${slug}/pictures`} className="text-accent-text underline">
                  Add {missing.length > 1 ? "their" : "its"} picture{missing.length > 1 ? "s" : ""}
                </a>{" "}
                to the project, or let the drawing tool make {missing.length > 1 ? "them" : "it"} when you build.
              </div>
            )}
          </div>
          <div>
            <Label>Cut check</Label>
            {ad.checks.length === 0 ? (
              <div className="mt-1 text-[13px] text-ink-3">Every cut sits in a silence, on an editor's cut or at a flash.</div>
            ) : (
              <ul className="mt-1 list-disc space-y-0.5 pl-4 text-[12.5px] text-warn">
                {ad.checks.map((c, i) => (
                  <li key={i}>{c}</li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}

      {err && (
        <div className="mt-2">
          <ErrorNote>{err}</ErrorNote>
        </div>
      )}
      {rejected && ad.reject_reason && (
        <div dir={dirOf(ad.reject_reason)} className="mt-2 text-[13px] text-ink-2">
          Your reason: {ad.reject_reason}
        </div>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-line pt-3">
        <Button small variant="ghost" icon={open ? "chevronDown" : "chevronRight"} onClick={() => setOpen(!open)}>
          Details
        </Button>
        {!rejected && (
          <Button small variant="ghost" icon="scissors" onClick={() => setEditing(true)}>
            Edit segments
          </Button>
        )}
        <div className="flex-1" />
        {rejected ? (
          <Button small onClick={() => patch({ status: "proposed" })}>
            Take it back
          </Button>
        ) : rejecting ? (
          <form
            className="flex flex-1 items-center gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              void patch({ status: "rejected", reject_reason: reason });
              setRejecting(false);
            }}
          >
            <input autoFocus value={reason} onChange={(e) => setReason(e.target.value)} dir="auto" placeholder="Why? Claude reads this before proposing more" className={cx(field, "min-h-[32px] min-w-0 flex-1")} aria-label="Reason for rejecting" />
            <Button small variant="danger" type="submit">
              Reject
            </Button>
            <Button small variant="ghost" type="button" onClick={() => setRejecting(false)}>
              Cancel
            </Button>
          </form>
        ) : (
          <Button small variant="ghost" onClick={() => setRejecting(true)}>
            Reject…
          </Button>
        )}
      </div>

      {editing && <SegEditor slug={slug} ad={ad} labels={labels} onClose={() => setEditing(false)} onSaved={onChange} />}
      {preview && <Preview slug={slug} ad={ad} labels={labels} onClose={() => setPreview(false)} />}
    </Card>
  );
}

export default function Proposals({ p, reload, openJob }: { p: ProductDetail; reload: () => void; openJob: (id: number) => void }) {
  const slug = p.slug;
  const [list, setList] = useState<ProposalList | null>(null);
  const [labels, setLabels] = useState<Record<string, string>>({});
  const [err, setErr] = useState<string | null>(null);
  const [count, setCount] = useState(3);
  const [note, setNote] = useState("");
  const [showRejected, setShowRejected] = useState(false);
  const [building, setBuilding] = useState(false);
  const jobs = useJobs(slug);
  const active = jobs.filter(isActive);
  const proposing = active.some((j) => j.kind === "propose");

  const load = useCallback(() => {
    api.proposals(slug).then(setList).catch((e) => setErr(errText(e)));
    api.analysis(slug).then((a) => setLabels(Object.fromEntries(Object.entries(a?.sources ?? {}).map(([k, s]) => [k, s.label || k])))).catch(() => {});
  }, [slug]);
  useEffect(load, [load]);
  useOnJobEnd(jobs, () => {
    reload();
    load();
  });

  const propose = async () => {
    setErr(null);
    try {
      const r = await api.propose(slug, count, note);
      setNote("");
      openJob(r.jobs[0].id);
    } catch (e) {
      setErr(errText(e));
    }
  };
  const onChange = (ad: Proposal) => setList((l) => (l ? { ...l, ads: l.ads.map((x) => (x.id === ad.id ? ad : x)) } : l));

  if (!list) return err ? <ErrorNote>{err}</ErrorNote> : <Loading />;
  const open = list.ads.filter((a) => a.status !== "rejected");
  const rejected = list.ads.filter((a) => a.status === "rejected");
  const picked = open.filter((a) => a.picked);
  const failed = jobs.find((j) => j.kind === "propose");

  // the quick build from the floating bar: the same call as the Results tab, with the saved render preference
  const build = async () => {
    setBuilding(true);
    setErr(null);
    try {
      const s = await api.settings().catch(() => null);
      const r: { jobs: Job[] } = await api.build(
        slug,
        picked.map((a) => a.id),
        s?.auto_render ?? false,
        false,
      );
      if (r.jobs[0]) openJob(r.jobs[0].id);
      location.hash = `#/p/${slug}/build`;
    } catch (e) {
      setErr(errText(e));
    } finally {
      setBuilding(false);
    }
  };

  return (
    <div className="relative space-y-[10px] pb-[72px]">
      <Glass className="flex flex-wrap items-center gap-3 rounded-[24px] px-4 py-2.5">
        <div className="num text-[12.5px] text-ink-2">
          {open.length} idea{open.length === 1 ? "" : "s"}
          {rejected.length > 0 && ` · ${rejected.length} rejected`}
          <span className="text-ink-4"> · next mix number {list.next_mix}</span>
        </div>
        <div className="flex-1" />
        <label className="flex items-center gap-2 text-[12px] text-ink-3">
          How many
          <input type="number" min={1} max={12} value={count} onChange={(e) => setCount(Math.max(1, Math.min(12, parseInt(e.target.value) || 1)))} className={cx(field, "num w-16")} />
        </label>
        <input value={note} onChange={(e) => setNote(e.target.value)} dir="auto" placeholder="Anything to steer this round (optional)" className={cx(field, "min-w-[260px] flex-[2]")} aria-label="Guidance for the next ideas" />
        <Button variant={picked.length ? "default" : "primary"} disabled={proposing || !p.analysis} onClick={propose} title={p.analysis ? "" : "Analyze the sources first"}>
          {proposing ? "Thinking…" : "More ideas"}
        </Button>
      </Glass>

      {err && <ErrorNote>{err}</ErrorNote>}
      {!proposing && failed?.status === "failed" && (
        <ErrorNote>
          The last ideas run failed: {failed.error}{" "}
          <button type="button" className="underline" onClick={() => openJob(failed.id)}>
            Open its log
          </button>
        </ErrorNote>
      )}
      <ActiveJobs jobs={active} openJob={openJob} />

      {!p.analysis && <Empty title="Analyze the sources first">Ideas are made from the analysis: the hook ends, the lines and the liftable hooks.</Empty>}
      {p.analysis && list.ads.length === 0 && !proposing && <Empty title="No idea yet">Ask for a few. Claude pairs hooks and bodies that read as one argument and skips everything already made.</Empty>}

      <div className="grid grid-cols-[repeat(auto-fill,minmax(340px,1fr))] gap-[10px]">
        {open.map((ad) => (
          <AdCard key={ad.id} slug={slug} ad={ad} labels={labels} onChange={onChange} />
        ))}
      </div>

      {rejected.length > 0 && (
        <div>
          <button type="button" className="flex items-center gap-1 text-[12.5px] font-medium text-ink-2 hover:text-ink" onClick={() => setShowRejected(!showRejected)}>
            <Icon name={showRejected ? "chevronDown" : "chevronRight"} size={13} /> Rejected ({rejected.length})
          </button>
          {showRejected && (
            <div className="mt-2 grid grid-cols-[repeat(auto-fill,minmax(340px,1fr))] gap-[10px]">
              {rejected.map((ad) => (
                <AdCard key={ad.id} slug={slug} ad={ad} labels={labels} onChange={onChange} />
              ))}
            </div>
          )}
        </div>
      )}

      {picked.length > 0 && (
        <div className="pointer-events-none sticky bottom-[10px] z-20 flex justify-center">
          <Glass className="pointer-events-auto flex items-center gap-4 rounded-full py-2 pr-2 pl-5">
            <span className="num text-[13px] font-medium">
              {picked.length} picked
            </span>
            <Button variant="primary" disabled={building} onClick={build}>
              {building ? "Starting…" : `Build ${picked.length} ad${picked.length === 1 ? "" : "s"}`}
            </Button>
          </Glass>
        </div>
      )}
    </div>
  );
}
