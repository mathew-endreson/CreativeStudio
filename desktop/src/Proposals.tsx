import { useCallback, useEffect, useState } from "react";
import { api, fmt, frameOf, type Graphic, type ProductDetail, type Proposal, type ProposalList } from "./api";
import { Icon } from "./icons";
import { ActiveJobs, isActive, useJobs, useOnJobEnd } from "./Jobs";
import { Preview, roleOf, SegEditor, thumb } from "./SegEditor";
import { Button, Card, Chip, cx, dirOf, Empty, ErrorNote, field, Label, Loading } from "./ui";

// library = one of the product's pictures, missing = an idea no picture shows yet; disc / pack / offer come from
// proposals made before Nov 26 2026, when the ads still had icon discs and jar packshots
const graphicTone = (g: Graphic) => (g.kind === "missing" ? "warn" : g.kind === "library" ? "ok" : "neutral");
const graphicName = (g: Graphic) =>
  g.kind === "missing" ? `no picture: ${g.what}` : g.kind === "library" ? g.what : g.kind === "disc" ? `old style: ${g.what} disc` : g.kind === "pack" ? "old style: jar" : "old style: offer photo";

function Segments({ slug, ad, labels }: { slug: string; ad: Proposal; labels: Record<string, string> }) {
  return (
    <div className="space-y-1.5">
      {ad.segs.map((s, i) => {
        const role = roleOf(ad, i);
        const first = frameOf(s.v0 ?? s.a0), last = frameOf(s.v1 ?? s.a1) - 1;
        return (
          <div key={i} className={cx("flex gap-2.5 rounded-[6px] border-l-[3px] bg-surface-2 p-1.5", role === "hook" ? "border-hook" : role === "cta" ? "border-cta" : "border-body")}>
            <div className="flex shrink-0 gap-1">
              <img src={thumb(slug, s.src, first)} alt={`first frame of segment ${i + 1}`} title={`first frame shown: f${first}`} className="h-[80px] w-[45px] rounded-[3px] bg-black object-cover" loading="lazy" />
              <img src={thumb(slug, s.src, last)} alt={`last frame of segment ${i + 1}`} title={`last frame shown: f${last}`} className="h-[80px] w-[45px] rounded-[3px] bg-black object-cover" loading="lazy" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-1.5">
                <Chip tone={role}>{role === "hook" ? (i === 0 && ad.hook_beats ? "hook, lifted" : "hook") : role === "cta" ? "CTA" : "body"}</Chip>
                <span className="font-semibold">{labels[s.src] ?? s.src}</span>
                <span className="tc text-[11.5px] text-ink-2">
                  {fmt(s.a0)}–{fmt(s.a1)} s <span className="text-ink-3">({fmt((frameOf(s.a1) - frameOf(s.a0)) / 30, 1)} s)</span>
                </span>
                {s.v0 != null && <Chip title="The picture starts on this clean frame and is held back to the cut">picture from {fmt(s.v0, 3)}</Chip>}
                {s.v1 != null && <Chip title="The picture is held on this clean frame until the cut">picture until {fmt(s.v1, 3)}</Chip>}
                {role !== "hook" && !ad.body.includes(i) && role !== "cta" && <Chip title="No pictures on this segment">no assets</Chip>}
              </div>
              <div dir="auto" className="mt-0.5 text-[15px] leading-snug" title={s.text ? `Whisper wrote: ${s.text}` : undefined}>
                {s.said || s.text}
              </div>
              {s.note && <div dir={dirOf(s.note)} className="text-[12px] text-ink-3">{s.note}</div>}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/** The ad as Final Cut draws a project: its segments as clips on one storyline, sized by length. Click one to preview. */
function Storyline({ ad, labels, onPlay }: { ad: Proposal; labels: Record<string, string>; onPlay: () => void }) {
  const total = ad.segs.reduce((n, s) => n + Math.max(0.05, s.a1 - s.a0), 0);
  return (
    <div className="flex h-[30px] gap-[2px] rounded-[6px] bg-well p-[3px]">
      {ad.segs.map((s, i) => {
        const role = roleOf(ad, i);
        return (
          <button
            key={i}
            onClick={onPlay}
            title={`${role} · ${labels[s.src] ?? s.src} ${fmt(s.a0)}–${fmt(s.a1)} s`}
            className={cx(
              "clip flex min-w-0 items-center overflow-hidden rounded-[4px] border border-black/30 px-1.5 text-[10.5px] font-semibold whitespace-nowrap hover:brightness-110",
              role === "hook" ? "bg-hook text-black/80" : role === "cta" ? "bg-cta text-white" : "bg-body text-white",
            )}
            style={{ flex: Math.max(0.05, s.a1 - s.a0) / total }}
          >
            <span className="truncate">{labels[s.src] ?? s.src}</span>
          </button>
        );
      })}
    </div>
  );
}

function AdCard({ slug, ad, labels, onChange }: { slug: string; ad: Proposal; labels: Record<string, string>; onChange: (p: Proposal) => void }) {
  const [editing, setEditing] = useState(false);
  const [preview, setPreview] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const patch = (p: Record<string, unknown>) => api.patchProposal(slug, ad.id, p).then(onChange).catch((e) => setErr(String(e.message || e)));
  const missing = ad.graphics.filter((g) => g.kind === "missing");
  const rejected = ad.status === "rejected";

  return (
    <Card className={cx("p-3 ring-2", ad.picked ? "ring-sel" : "ring-transparent", rejected && "opacity-60")}>
      <div className="flex flex-wrap items-center gap-2">
        {!rejected && (
          <label className="flex h-[26px] cursor-pointer items-center gap-2 glass-2 rounded-[8px] px-2 text-[12.5px] font-medium has-[:checked]:border-sel has-[:checked]:bg-sel/15 has-[:checked]:text-sel" title="Tick to build this ad">
            <input type="checkbox" className="h-3.5 w-3.5" checked={ad.picked} disabled={!!ad.exists} onChange={(e) => patch({ picked: e.target.checked })} />
            Build
          </label>
        )}
        <h3 className="min-w-0 flex-1 truncate text-[14.5px] font-semibold" title={ad.file_name}>{ad.name}</h3>
        <Chip title="Length of the ad">{fmt(ad.duration, 1)} s</Chip>
        {ad.exists && <Chip tone="bad" title="An ad with these segments already exists">already exists: {ad.exists.name}</Chip>}
        {ad.built && <Chip tone="ok">built</Chip>}
        {ad.edited && <Chip tone="accent" title="You changed its segments">edited by you</Chip>}
        {rejected && <Chip tone="bad">rejected</Chip>}
      </div>
      <div dir={dirOf(ad.angle)} className="mt-1 text-[13.5px] text-ink-2">{ad.angle}</div>
      <div className="mt-2.5">
        <Storyline ad={ad} labels={labels} onPlay={() => setPreview(true)} />
      </div>

      <div className="mt-3 grid gap-4 lg:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
        <div>
          <Label>Segments</Label>
          <div className="mt-1.5"><Segments slug={slug} ad={ad} labels={labels} /></div>
        </div>
        <div className="space-y-3 rounded-[6px] bg-surface-2/50 p-2.5">
          <div>
            <Label>Why it reads as one argument</Label>
            <div dir={dirOf(ad.why)} className="mt-1 text-[13.5px]">{ad.why}</div>
          </div>
          <div>
            <Label>Risks</Label>
            {ad.risks.length === 0 ? <div className="mt-1 text-[13.5px] text-ink-3">None named.</div> : (
              <ul className="mt-1 list-disc space-y-0.5 pl-4 text-[13.5px]">
                {ad.risks.map((r, i) => <li key={i} dir={dirOf(r)}>{r}</li>)}
              </ul>
            )}
          </div>
          <div>
            <Label>Planned assets</Label>
            <div className="mt-1.5 flex flex-wrap gap-1">
              {ad.graphics.length === 0 && <span className="text-[13.5px] text-ink-3">None planned.</span>}
              {ad.graphics.map((g, i) => (
                <Chip key={i} tone={graphicTone(g)} title={`on «${g.on}»${g.label ? ` · label ${g.label}` : ""}${g.existing ? " · already written in the beats file" : " · new"}`}>
                  {graphicName(g)}
                </Chip>
              ))}
            </div>
            <div className={cx("mt-1 text-[12.5px]", missing.length ? "text-warn" : "text-ink-3")}>
              {missing.length === 0 ? (
                "Every idea it shows has a picture."
              ) : (
                <>
                  {missing.length} idea{missing.length > 1 ? "s have" : " has"} no picture yet:{" "}
                  <a href={`#/p/${slug}/pictures`} className="underline">
                    add {missing.length > 1 ? "them" : "it"} to the product's pictures
                  </a>
                  , or let GPT draw when you build.
                </>
              )}
            </div>
          </div>
          <div>
            <Label>Cut check</Label>
            {ad.checks.length === 0 ? <div className="mt-1 text-[13.5px] text-ink-3">Every cut sits in a silence, on an editor's cut or at a flash.</div> : (
              <ul className="mt-1 list-disc space-y-0.5 pl-4 text-[13px] text-warn">
                {ad.checks.map((c, i) => <li key={i}>{c}</li>)}
              </ul>
            )}
          </div>
        </div>
      </div>

      {err && <div className="mt-2"><ErrorNote>{err}</ErrorNote></div>}
      {rejected && ad.reject_reason && <div dir={dirOf(ad.reject_reason)} className="mt-2 text-[13.5px] text-ink-2">Your reason: {ad.reject_reason}</div>}

      <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-line pt-2.5">
        <Button small icon="play" onClick={() => setPreview(true)}>Rough preview</Button>
        {!rejected && <Button small icon="scissors" onClick={() => setEditing(true)}>Edit the segments</Button>}
        <div className="flex-1" />
        {rejected ? (
          <Button small onClick={() => patch({ status: "proposed" })}>Take it back</Button>
        ) : rejecting ? (
          <form className="flex flex-1 items-center gap-2" onSubmit={(e) => { e.preventDefault(); void patch({ status: "rejected", reject_reason: reason }); setRejecting(false); }}>
            <input autoFocus value={reason} onChange={(e) => setReason(e.target.value)} dir="auto" placeholder="Why? Claude reads this before proposing more"
              className={cx(field, "h-[24px] min-w-0 flex-1")} aria-label="Reason for rejecting" />
            <Button small variant="danger" type="submit">Reject</Button>
            <Button small variant="ghost" type="button" onClick={() => setRejecting(false)}>Cancel</Button>
          </form>
        ) : (
          <Button small variant="danger" onClick={() => setRejecting(true)}>Reject…</Button>
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
  const jobs = useJobs(slug);
  const active = jobs.filter(isActive);
  const proposing = active.some((j) => j.kind === "propose");

  const load = useCallback(() => {
    api.proposals(slug).then(setList).catch((e) => setErr(String(e.message || e)));
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
    } catch (e: any) {
      setErr(String(e.message || e));
    }
  };
  const onChange = (ad: Proposal) => setList((l) => (l ? { ...l, ads: l.ads.map((x) => (x.id === ad.id ? ad : x)) } : l));

  if (!list) return err ? <ErrorNote>{err}</ErrorNote> : <Loading />;
  const open = list.ads.filter((a) => a.status !== "rejected");
  const rejected = list.ads.filter((a) => a.status === "rejected");
  const picked = open.filter((a) => a.picked);
  const failed = jobs.find((j) => j.kind === "propose");

  return (
    <div className="space-y-3">
      <Card className="flex flex-wrap items-end gap-3 px-3 py-2">
        <div className="flex flex-wrap items-center gap-2 self-center">
          <Chip tone={open.length ? "ok" : "neutral"}>{open.length} possible ad{open.length === 1 ? "" : "s"}</Chip>
          <Chip tone={picked.length ? "accent" : "neutral"}>{picked.length} ticked</Chip>
          {rejected.length > 0 && <Chip>{rejected.length} rejected</Chip>}
          <span className="text-[11.5px] text-ink-3">next mix number {list.next_mix}</span>
        </div>
        <div className="flex-1" />
        <label className="text-[11px] text-ink-3">
          How many
          <input type="number" min={1} max={12} value={count} onChange={(e) => setCount(Math.max(1, Math.min(12, parseInt(e.target.value) || 1)))}
            className={cx(field, "num mt-0.5 block h-[28px] w-16")} />
        </label>
        <label className="min-w-[280px] flex-[2] text-[11px] text-ink-3">
          Anything to steer this round (optional)
          <input value={note} onChange={(e) => setNote(e.target.value)} dir="auto" placeholder="e.g. use V7 for the new hooks; nothing longer than 30 s"
            className={cx(field, "mt-0.5 block h-[28px] w-full")} />
        </label>
        <Button variant="primary" icon="sparkles" disabled={proposing || !p.analysis} onClick={propose} title={p.analysis ? "" : "Analyze the sources first"}>
          {proposing ? "Proposing…" : open.length || rejected.length ? "Propose more" : "Propose ads"}
        </Button>
      </Card>

      {err && <ErrorNote>{err}</ErrorNote>}
      {!proposing && failed?.status === "failed" && (
        <ErrorNote>
          The last proposal run failed: {failed.error}{" "}
          <button className="underline" onClick={() => openJob(failed.id)}>Open its log</button>
        </ErrorNote>
      )}
      <ActiveJobs jobs={active} openJob={openJob} />

      {picked.length > 0 && (
        <div className="flex flex-wrap items-center gap-3 rounded-[8px] border border-sel/40 bg-sel/10 px-3 py-2">
          <div className="min-w-0 flex-1 text-[13.5px]">
            <b>{picked.length} ticked</b> to build: {picked.map((a) => a.name.replace(/^.*?(Mix\d+).*$/, "$1")).join(", ")}.
          </div>
          <Button icon="share" onClick={() => (location.hash = `#/p/${slug}/build`)}>
            Go to Build & results
          </Button>
        </div>
      )}

      {!p.analysis && <Empty title="Analyze the sources first">Proposals are made from analysis.json: the hook ends, the lines and the liftable hooks.</Empty>}
      {p.analysis && list.ads.length === 0 && !proposing && (
        <Empty title="No possible ad yet">
          Ask for a few. Claude pairs hooks and bodies that read as one argument and skips everything in "Ads so far".
        </Empty>
      )}

      {open.map((ad) => <AdCard key={ad.id} slug={slug} ad={ad} labels={labels} onChange={onChange} />)}

      {rejected.length > 0 && (
        <div>
          <button className="flex items-center gap-1 text-[12.5px] font-medium text-ink-2 hover:text-ink" onClick={() => setShowRejected(!showRejected)}>
            <Icon name={showRejected ? "chevronDown" : "chevronRight"} size={13} /> Rejected ({rejected.length})
          </button>
          {showRejected && <div className="mt-2 space-y-3">{rejected.map((ad) => <AdCard key={ad.id} slug={slug} ad={ad} labels={labels} onChange={onChange} />)}</div>}
        </div>
      )}
    </div>
  );
}
