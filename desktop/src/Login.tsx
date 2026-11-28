import { useState, type FormEvent } from "react";
import { authError, confirmSignup, createAccount, errorCode, resendSignup, resetWithCode, sendResetCode, signIn } from "./auth";
import { BrandMark, PRODUCT_NAME, TintWall } from "./brand";
import { Button, ErrorNote, field, Glass, Segmented } from "./ui";

type Mode = "in" | "new" | "confirm" | "reset" | "code";

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
          go("confirm", "Your email is not confirmed yet: we sent you a new email. Enter its code here, or open its link and then sign in.");
        }
      } else if (mode === "new") {
        if ((await createAccount(mail, pw)) === "confirm") go("confirm", `We sent an email to ${mail}. Enter its code here; if it holds a link instead, open the link, then sign in.`);
      } else if (mode === "confirm") await confirmSignup(mail, code.trim());
      else if (mode === "reset") {
        await sendResetCode(mail);
        go("code", `We sent an email to ${mail}. Enter its code here. If it only holds a link, ask support to reset the password.`);
      } else await resetWithCode(mail, code.trim(), pw);
    });
  };

  const resend = () =>
    run(async () => {
      if (mode === "confirm") await resendSignup(email.trim());
      else await sendResetCode(email.trim());
      setNote("A new email is on its way.");
    });

  const title = { in: "Continue", new: "Create the account", confirm: "Confirm the email", reset: "Send a reset code", code: "Set the new password" }[mode];
  const heading = { in: "Welcome back", new: "Create an account", confirm: "Confirm the email", reset: "Reset the password", code: "Set the new password" }[mode];
  const needsPw = mode === "in" || mode === "new" || mode === "code";
  const needsCode = mode === "confirm" || mode === "code";
  const tabbed = mode === "in" || mode === "new";

  return (
    <div className="relative grid min-h-full place-items-center overflow-hidden p-6">
      <TintWall />
      <Glass strong className="relative w-full max-w-[400px] rounded-[32px] p-7">
        <div className="flex flex-col items-center text-center">
          <BrandMark size={64} tile />
          <h1 className="mt-4 text-[20px] font-semibold tracking-tight">{PRODUCT_NAME}</h1>
          <div className="mt-1 text-[13px] text-ink-3">{heading}</div>
        </div>
        {tabbed && (
          <div className="mt-5 flex justify-center">
            <Segmented
              value={mode}
              onChange={(m) => go(m)}
              options={[
                { id: "in", label: "Sign in" },
                { id: "new", label: "Create account" },
              ]}
            />
          </div>
        )}
        <form onSubmit={submit} className="mt-5 space-y-3">
          <label className="block">
            <span className="mb-1 block text-[12px] font-medium text-ink-3">Email</span>
            <input type="email" required autoFocus={!needsCode} readOnly={needsCode} value={email} onChange={(e) => setEmail(e.target.value)} className={`${field} h-[40px] w-full ${needsCode ? "text-ink-3" : ""}`} autoComplete="email" aria-label="Email" />
          </label>
          {needsCode && (
            <label className="block">
              <span className="mb-1 block text-[12px] font-medium text-ink-3">Code from the email</span>
              <input inputMode="numeric" autoComplete="one-time-code" required autoFocus pattern="[0-9]{6,10}" value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} className={`${field} num h-[40px] w-full tracking-[0.3em]`} aria-label="Code from the email" />
            </label>
          )}
          {needsPw && (
            <label className="block">
              <span className="mb-1 block text-[12px] font-medium text-ink-3">{mode === "code" ? "New password" : "Password"}</span>
              <input type="password" required minLength={6} autoComplete={mode === "in" ? "current-password" : "new-password"} value={pw} onChange={(e) => setPw(e.target.value)} className={`${field} h-[40px] w-full`} aria-label={mode === "code" ? "New password" : "Password"} />
            </label>
          )}
          {err && <ErrorNote>{err}</ErrorNote>}
          {note && <div className="rounded-[14px] border border-ok/30 bg-ok/10 px-3 py-2 text-[12.5px] text-ok">{note}</div>}
          <Button type="submit" variant="primary" disabled={busy} className="mt-1 w-full">
            {busy ? "…" : title}
          </Button>
        </form>
        <div className="mt-4 flex items-center justify-between text-[12.5px] text-ink-3">
          {tabbed ? (
            <>
              <button type="button" className="hover:text-ink" onClick={() => go("reset")}>
                Forgot password
              </button>
              <span title="Once activated, the app works without a connection for a week at a time">Works offline</span>
            </>
          ) : (
            <>
              <button type="button" className="hover:text-ink" onClick={() => go("in")}>
                Back to sign in
              </button>
              {needsCode && (
                <button type="button" className="hover:text-ink disabled:opacity-50" disabled={busy} onClick={resend}>
                  Send the email again
                </button>
              )}
            </>
          )}
        </div>
        <p className="mt-5 text-center text-[11.5px] leading-snug text-ink-4">
          v{version} · Your account and license live in the cloud. Footage, transcripts, projects and renders stay on this PC.
        </p>
      </Glass>
    </div>
  );
}
