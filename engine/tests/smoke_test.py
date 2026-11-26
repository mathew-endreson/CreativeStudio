"""Start the engine on a free port and check what the desktop shell relies on: the READY line, the boot token,
the cookie, and every read endpoint. No job is queued, nothing is written to the workspace.

    .venv\\Scripts\\python tests\\smoke_test.py
"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[1]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


opener = urllib.request.build_opener(NoRedirect)


def call(base, path, token=None, method="GET", body=None):
    req = urllib.request.Request(base + path, method=method, data=json.dumps(body).encode() if body is not None else None)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with opener.open(req, timeout=60) as r:
            raw = r.read()
            try:
                return r.status, json.loads(raw), r.headers
            except ValueError:
                return r.status, raw[:200], r.headers
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw), e.headers
        except ValueError:
            return e.code, raw[:200], e.headers


def main():
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    data = ENGINE / "tests" / ".data"
    p = subprocess.Popen([sys.executable, "-m", "bluxtech_engine", "--port", "0", "--data", str(data)], cwd=str(ENGINE),
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", env=env)
    ready = None
    t0 = time.time()
    while time.time() - t0 < 60:
        line = p.stdout.readline()
        if not line:
            break
        if line.startswith("BLUXTECH_READY "):
            ready = json.loads(line[len("BLUXTECH_READY "):])
            break
        print("engine:", line.rstrip())
    if not ready:
        p.kill()
        sys.exit("no READY line")
    base, token = f"http://127.0.0.1:{ready['port']}", ready["token"]
    print("ready:", {k: v for k, v in ready.items() if k != "token"})
    for _ in range(50):                                 # uvicorn may still be binding
        try:
            opener.open(base + "/api/ping", timeout=2)
            break
        except Exception:
            time.sleep(0.2)
    results = []

    def check(name, cond, info=""):
        results.append((name, bool(cond), info))

    s, b, _ = call(base, "/api/ping")
    check("ping is open", s == 200 and b.get("ok"), s)
    s, b, _ = call(base, "/api/app")
    check("app without token -> 401", s == 401, s)
    s, b, _ = call(base, "/api/app", token)
    check("app with token -> 200", s == 200 and b.get("mode") == ready["mode"], f"{s} {b.get('mode') if isinstance(b, dict) else b}")
    s, b, h = call(base, f"/boot/{token}")
    check("boot sets the cookie and redirects", s == 303 and "bx_session=" in h.get("Set-Cookie", ""), f"{s} {h.get('Set-Cookie', '')[:40]}")
    s, b, _ = call(base, "/boot/wrong")
    check("wrong boot token -> 403", s == 403, s)
    for path in ("/api/products", "/api/environment", "/api/settings", "/api/license", "/api/fresh", "/api/library", "/api/jobs"):
        s, b, _ = call(base, path, token)
        check(f"GET {path}", s == 200, f"{s} {str(b)[:80]}")
    s, b, _ = call(base, "/api/environment", token)
    if s == 200:
        for it in b["items"]:
            print(f"   env {'ok ' if it['ok'] else 'NO '} {it['label']}: {it['detail'][:70]}")
    s, b, _ = call(base, "/api/settings", token, "PUT", {"gpt_cap": 2})
    check("PUT settings", s == 200 and b.get("gpt_cap") == 2, s)
    call(base, "/api/settings", token, "PUT", {"gpt_cap": 3})
    s, b, _ = call(base, "/api/settings/apikey", token, "POST", {"key": "not-a-key"})
    check("bad api key -> 422", s == 422, s)
    s, b, _ = call(base, "/api/settings", token, "PUT", {"nope": 1})
    check("unknown setting -> 400", s == 400, s)
    s, b, _ = call(base, "/api/folder?path=" + urllib.request.quote(str(ENGINE)), token)
    check("folder listing", s == 200 and any(e["name"] == "prompts" for e in b.get("entries", [])), s)
    s, b, _ = call(base, "/api/products/does-not-exist", token)
    check("unknown product -> 404", s == 404, s)
    s, b, _ = call(base, "/api/fresh/nope", token)
    check("unknown fresh -> 404", s == 404, s)
    s, b, _ = call(base, "/api/products", token)
    if s == 200 and b:
        slug = next((x["slug"] for x in b if not x.get("not_imported") and not x.get("error")), None)
        if slug:
            s2, b2, _ = call(base, f"/api/products/{slug}/results", token)
            check(f"results of {slug}", s2 == 200 and "mixes" in b2, f"{s2} {len(b2.get('mixes', [])) if isinstance(b2, dict) else b2} mixes")
            s2, b2, _ = call(base, f"/api/products/{slug}/proposals", token)
            check(f"proposals of {slug}", s2 == 200, s2)
    subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True) if os.name == "nt" else p.kill()
    bad = [r for r in results if not r[1]]
    for name, ok, info in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name}  ({info})")
    print(f"\n{len(results) - len(bad)}/{len(results)} passed")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
