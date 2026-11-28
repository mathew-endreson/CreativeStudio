import { useState } from "react";
import { type AppInfo, type LicenseState } from "./api";
import { activate, authError, signOut, type User } from "./auth";
import { BrandMark, TintWall } from "./brand";
import { Button, ErrorNote, Glass, Label, Status } from "./ui";

const when = (s?: number | null) => (s ? new Date(s * 1000).toLocaleDateString() : "no end");

export default function Activate({ info, user, license, onActivated }: { info: AppInfo; user: User; license: LicenseState; onActivated: (l: LicenseState) => void }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const go = async () => {
    setBusy(true);
    setErr(null);
    try {
      onActivated(await activate(info, user));
    } catch (e) {
      setErr(authError(e));
    } finally {
      setBusy(false);
    }
  };
  const reason: Record<string, string> = {
    "not-activated": "This device is not activated yet.",
    "recheck-needed": `The license was last confirmed more than ${license.grace_days} days ago: confirm it again (needs the internet).`,
    expired: "The license has expired.",
    suspended: "The license is suspended.",
    none: "This account has no license yet.",
  };
  return (
    <div className="relative grid min-h-full place-items-center overflow-hidden p-6">
      <TintWall />
      <Glass strong className="relative w-full max-w-[440px] rounded-[32px] p-7">
        <div className="flex flex-col items-center text-center">
          <BrandMark size={56} tile />
          <h1 className="mt-4 text-[20px] font-semibold tracking-tight">Activate this device</h1>
          <p className="mt-1 text-[13px] text-ink-3">{reason[license.reason] ?? license.reason}</p>
        </div>
        <div className="mt-5 grid grid-cols-2 gap-x-4 gap-y-3 rounded-[18px] bg-white/[0.04] p-4 text-[13px]">
          <div className="min-w-0">
            <Label>Account</Label>
            <div className="truncate">{user.email}</div>
          </div>
          <div className="min-w-0">
            <Label>Device</Label>
            <div className="truncate">{info.device_name}</div>
          </div>
          {license.plan && (
            <div>
              <Label>Plan</Label>
              <div className="flex items-center gap-2">
                <span className="capitalize">{license.plan}</span>
                <Status tone={license.ok ? "ok" : "bad"}>{license.status}</Status>
              </div>
            </div>
          )}
          {license.status && (
            <div>
              <Label>Valid until</Label>
              <div className="num">{when(license.expires_at)}</div>
            </div>
          )}
        </div>
        {err && (
          <div className="mt-4">
            <ErrorNote>{err}</ErrorNote>
          </div>
        )}
        <Button variant="primary" onClick={go} disabled={busy} className="mt-5 w-full">
          {busy ? "Checking…" : "Activate"}
        </Button>
        <div className="mt-3 flex items-center justify-between text-[12.5px] text-ink-3">
          <button type="button" className="hover:text-ink" onClick={() => signOut()}>
            Sign out
          </button>
          <span title={`Device id ${info.device_id.slice(0, 8)}`}>Works offline for {license.grace_days} days</span>
        </div>
        <p className="mt-5 text-center text-[11.5px] leading-snug text-ink-4">A new account gets a trial when it is activated the first time. The license is checked online and then works offline for {license.grace_days} days.</p>
      </Glass>
    </div>
  );
}
