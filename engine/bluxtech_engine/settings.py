"""Settings, secrets and the device id, in SQLite under %LOCALAPPDATA%\\BluxTech Studio\\engine.db.
Secrets (the Anthropic API key) are sealed with Windows DPAPI for the current user; elsewhere they are only
base64 (dev machines)."""
import base64
import json
import os
import sqlite3
import threading
import uuid

from . import config

_lock = threading.RLock()
_db = None

DEFAULTS = {
    "runner": None,                 # None = "cli" in dev, "sdk" when installed (see runner())
    "model": None,                  # None = the CLI's / SDK's default
    "effort": None,
    "max_budget_usd": 10.0,          # per headless run (sdk runner)
    "max_turns": 120,
    "limits": {"heavy": 1, "claude": 2, "light": 3},
    "gpt_cap": 3,
    "auto_render": False,
}
HIDDEN = ("license", "device_id")


def db():
    global _db
    with _lock:
        if _db is None:
            config.DATA.mkdir(parents=True, exist_ok=True)
            _db = sqlite3.connect(str(config.DATA / "engine.db"), check_same_thread=False)
            _db.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT)")
            _db.execute("PRAGMA journal_mode=WAL")
            _db.commit()
        return _db


def get(key, default=None):
    with _lock:
        row = db().execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    if row is None:
        return DEFAULTS.get(key) if default is None else default
    return json.loads(row[0])


def set(key, value):
    with _lock:
        db().execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)",
                     (key, json.dumps(value, ensure_ascii=False)))
        db().commit()


def delete(key):
    with _lock:
        db().execute("DELETE FROM settings WHERE key=?", (key,))
        db().commit()


def public():
    """What the UI may see: every default, the stored values, never a secret."""
    out = dict(DEFAULTS)
    with _lock:
        rows = db().execute("SELECT key,value FROM settings WHERE key NOT LIKE 'secret:%'").fetchall()
    for k, v in rows:
        if k not in HIDDEN:
            out[k] = json.loads(v)
    out["runner"] = runner()
    out["has_api_key"] = bool(api_key())
    out["api_key_source"] = "settings" if get_secret("anthropic_api_key") else ("env" if os.environ.get("ANTHROPIC_API_KEY") else None)
    return out


def runner():
    r = get("runner")
    return r or ("cli" if config.MODE == "dev" else "sdk")


def device_id():
    d = get("device_id")
    if not d:
        d = str(uuid.uuid4())
        set("device_id", d)
    return d


# ------------------------------------------------------------------ secrets (DPAPI on Windows)

def _dpapi(data: bytes, encrypt: bool) -> bytes:
    import ctypes
    import ctypes.wintypes as wt

    class BLOB(ctypes.Structure):
        _fields_ = [("cbData", wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    buf = ctypes.create_string_buffer(data, len(data))
    inp = BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    out = BLOB()
    fn = ctypes.windll.crypt32.CryptProtectData if encrypt else ctypes.windll.crypt32.CryptUnprotectData
    if not fn(ctypes.byref(inp), None, None, None, None, 1, ctypes.byref(out)):      # 1 = CRYPTPROTECT_UI_FORBIDDEN
        raise OSError(f"DPAPI failed ({ctypes.GetLastError()})")
    res = ctypes.string_at(out.pbData, out.cbData)
    ctypes.windll.kernel32.LocalFree(out.pbData)
    return res


def set_secret(name, plaintext):
    if not plaintext:
        delete(f"secret:{name}")
        return
    raw = plaintext.encode("utf-8")
    sealed = _dpapi(raw, True) if os.name == "nt" else raw
    set(f"secret:{name}", {"dpapi": os.name == "nt", "b64": base64.b64encode(sealed).decode("ascii")})


def get_secret(name):
    rec = get(f"secret:{name}", default={})
    if not rec:
        return None
    raw = base64.b64decode(rec["b64"])
    try:
        return (_dpapi(raw, False) if rec.get("dpapi") else raw).decode("utf-8")
    except OSError:
        return None


def api_key():
    """The Anthropic key the sdk runner uses: stored by the user in Settings, else the environment."""
    return get_secret("anthropic_api_key") or os.environ.get("ANTHROPIC_API_KEY")
