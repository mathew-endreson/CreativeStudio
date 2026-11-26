import { useState, type FormEvent } from "react";
import { authError, confirmSignup, createAccount, errorCode, resendSignup, resetWithCode, sendResetCode, signIn } from "./auth";
import { BrandMark } from "./icons";
import { Button, Card, ErrorNote, Label } from "./ui";

type Mode = "in" | "new" | "confirm" | "reset" | "code";

const field =
  "mt-1 h-[30px] w-full rounded-[5px] border border-line bg-well shadow-[inset_0_1px_2px_rgb(0_0_0/0.25)] focus:border-accent focus:outline-none px-3";

export default function Login({ version }: { version: string }) {
  const [mode, setMode] = useState<Mode>("in");
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  const go = (m: Mode, n: string | null = null) => {
    setMode(m);
    setErr(null);
    setNote(n);
    setCode("");
  };

  const run = async (fn: () => Promise<void>) => {
    setErr(null);
    setNote(null);
    setBusy(true);
    try {
      await fn();
    } catch (x) {
      setErr(authError(x));
    } finally {
      setBusy(false);
    }
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const mail = email.trim();
    run(async () => {
      if (mode === "in") {
        try {
          await signIn(mail, pw);
        } catch (x) {
          if (errorCode(x) !== "email_not_confirmed") throw x;
          await resendSignup(mail);
          go("confirm", "Your email is not confirmed yet: we sent you a new code.");
        }
      } else if (mode === "new") {
        if ((await createAccount(mail, pw)) === "confirm") go("confirm", `We sent a code to ${mail}.`);
      } else if (mode === "confirm") await confirmSignup(mail, code.trim());
      else if (mode === "reset") {
        await sendResetCode(mail);
        go("code", `We sent a code to ${mail}.`);
      } else await resetWithCode(mail, code.trim(), pw);
    });
  };

  const resend = () =>
    run(async () => {
      if (mode === "confirm") await resendSignup(email.trim());
      else await sendResetCode(email.trim());
      setNote("A new code is on its way.");
    });

  const title = { in: "Sign in", new: "Create the account", confirm: "Confirm the email", reset: "Send a reset code", code: "Set the new password" }[mode];
  const needsPw = mode === "in" || mode === "new" || mode === "code";
  const needsCode = mode === "confirm" || mode === "code";

  return (
    <div className="grid min-h-full place-items-center bg-bg p-6">
      <Card className="w-[400px] p-6 shadow-hud">
        <div className="mb-5 flex items-center gap-3">
          <BrandMark size={40} />
          <div>
            <div className="text-[17px] font-semibold tracking-tight">BluxTech Studio</div>
            <div className="text-[12px] text-ink-3">v{version}</div>
          </div>
        </div>
        <form onSubmit={submit} className="space-y-3">
          <div>
            <Label>Email</Label>
            <input type="email" required autoFocus={!needsCode} readOnly={needsCode} value={email} onChange={(e) => setEmail(e.target.value)} className={`${field} ${needsCode ? "text-ink-3" : ""}`} />
          </div>
          {needsCode && (
            <div>
              <Label>Code from the email</Label>
              <input
                inputMode="numeric"
                autoComplete="one-time-code"
                required
                autoFocus
                pattern="[0-9]{6,10}"
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                className={`${field} tracking-[0.3em]`}
              />
            </div>
          )}
          {needsPw && (
            <div>
              <Label>{mode === "code" ? "New password" : "Password"}</Label>
              <input type="password" required minLength={6} autoComplete={mode === "in" ? "current-password" : "new-password"} value={pw} onChange={(e) => setPw(e.target.value)} className={field} />
            </div>
          )}
          {err && <ErrorNote>{err}</ErrorNote>}
          {note && <div className="rounded-[6px] border border-ok/40 bg-ok/10 px-3 py-2 text-[13px] text-ok">{note}</div>}
          <Button type="submit" variant="primary" disabled={busy} className="w-full">
            {busy ? "…" : title}
          </Button>
        </form>
        <div className="mt-4 flex justify-between text-[12.5px] text-ink-2">
          {mode === "in" ? (
            <>
              <button className="hover:text-ink" onClick={() => go("new")}>Create an account</button>
              <button className="hover:text-ink" onClick={() => go("reset")}>Forgot the password?</button>
            </>
          ) : (
            <>
              <button className="hover:text-ink" onClick={() => go("in")}>Back to sign in</button>
              {needsCode && (
                <button className="hover:text-ink disabled:opacity-50" disabled={busy} onClick={resend}>
                  Send the code again
                </button>
              )}
            </>
          )}
        </div>
        <p className="mt-5 text-[12px] leading-snug text-ink-3">
          Your account and license live in the cloud. Footage, transcripts, projects and renders stay on this PC; only the Claude model calls leave it.
        </p>
      </Card>
    </div>
  );
}
