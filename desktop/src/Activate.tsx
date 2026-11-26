import { useState } from "react";
import { type AppInfo, type LicenseState } from "./api";
import { activate, authError, signOut, type User } from "./auth";
import { Button, Card, Chip, ErrorNote, Label } from "./ui";

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
    <div className="grid min-h-full place-items-center p-6">
      <Card className="w-[460px] p-6 shadow-hud">
        <div className="text-[17px] font-semibold tracking-tight">Activate this device</div>
        <p className="mt-1 text-ink-2">{reason[license.reason] ?? license.reason}</p>
        <div className="mt-4 grid grid-cols-2 gap-3 text-[13px]">
          <div>
            <Label>Account</Label>
            <div className="truncate">{user.email}</div>
          </div>
          <div>
            <Label>Device</Label>
            <div className="truncate">{info.device_name}</div>
          </div>
          {license.plan && (
            <div>
              <Label>Plan</Label>
              <div className="flex items-center gap-2">
                {license.plan} <Chip tone={license.ok ? "ok" : "bad"}>{license.status}</Chip>
              </div>
            </div>
          )}
          {license.status && (
            <div>
              <Label>Valid until</Label>
              <div>{when(license.expires_at)}</div>
            </div>
          )}
        </div>
        {err && (
          <div className="mt-4">
            <ErrorNote>{err}</ErrorNote>
          </div>
        )}
        <div className="mt-5 flex items-center gap-2">
          <Button variant="primary" onClick={go} disabled={busy}>
            {busy ? "Checking…" : "Activate"}
          </Button>
          <Button variant="ghost" onClick={() => signOut()}>
            Sign out
          </Button>
        </div>
        <p className="mt-4 text-[12px] leading-snug text-ink-3">
          A new account gets a trial when it is activated the first time. The license is checked online and then works offline for {license.grace_days} days.
          Device id <code>{info.device_id.slice(0, 8)}</code>.
        </p>
      </Card>
    </div>
  );
}
