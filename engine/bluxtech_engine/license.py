"""The license the cloud granted, cached locally. Supabase (Auth + the `license` Edge Function) is the authority;
the engine keeps its last answer and works offline for GRACE_DAYS. Jobs that produce ads need an active license.
If a public key is shipped (license_public_key.pem) the function's RS256 token is verified too, so a hand-written
payload cannot unlock the engine."""
import time
from pathlib import Path

from fastapi import HTTPException
from pydantic import BaseModel, Field

from . import config, settings

GRACE_DAYS = 7
ACTIVE = ("active", "trial")


class LicensePayload(BaseModel):
    uid: str
    email: str = ""
    status: str = Field(description="active | trial | expired | suspended | none")
    plan: str = "free"
    expires_at: float | None = Field(None, description="unix seconds; null = no end")
    max_devices: int = 1
    device_id: str
    device_name: str = ""
    token: str | None = Field(None, description="RS256 JWT from the license Edge Function, when signing is set up")


def _verify(token):
    """Claims from the signed token, or None when no public key is shipped. Raises on a bad token."""
    key = Path(config.LICENSE_KEY)
    if not key.exists():
        return None
    import jwt
    # leeway: the token's iat/exp come from the server's clock; a PC a few minutes behind must not be locked out
    return jwt.decode(token or "", key.read_text(encoding="utf-8"), algorithms=["RS256"], leeway=300,
                      options={"require": ["exp", "sub"]})


def save(p: LicensePayload):
    try:
        claims = _verify(p.token)
    except Exception as e:                                   # expired / forged / wrong key
        raise HTTPException(403, f"license token rejected: {e}")
    rec = p.model_dump()
    if claims:
        rec.update(uid=claims.get("sub", p.uid), status=claims.get("status", p.status), plan=claims.get("plan", p.plan),
                   expires_at=claims.get("license_exp", p.expires_at), signed=True)
        if claims.get("dev") and claims["dev"] != p.device_id:
            raise HTTPException(403, "this license token was issued to another device")
    else:
        rec["signed"] = False
    if p.device_id != settings.device_id():
        raise HTTPException(403, "the device id does not match this installation")
    rec["checked_at"] = time.time()
    settings.set("license", rec)
    return state()


def clear():
    settings.delete("license")


def state():
    """What the UI shows and what require() checks."""
    rec = settings.get("license", default={}) or None
    now = time.time()
    if not config.auth_config():
        return {"ok": True, "reason": "dev" if config.MODE == "dev" else "no-auth-config", "licensing": False,
                "device_id": settings.device_id(), "grace_days": GRACE_DAYS}
    if not rec:
        return {"ok": False, "reason": "not-activated", "licensing": True, "device_id": settings.device_id(),
                "grace_days": GRACE_DAYS}
    ok, reason = True, "active"
    if rec.get("status") not in ACTIVE:
        ok, reason = False, rec.get("status") or "none"
    elif rec.get("expires_at") and rec["expires_at"] < now:
        ok, reason = False, "expired"
    elif now - rec.get("checked_at", 0) > GRACE_DAYS * 86400:
        ok, reason = False, "recheck-needed"
    return {"ok": ok, "reason": reason, "licensing": True, "device_id": settings.device_id(), "grace_days": GRACE_DAYS,
            "uid": rec.get("uid"), "email": rec.get("email"), "plan": rec.get("plan"), "status": rec.get("status"),
            "expires_at": rec.get("expires_at"), "checked_at": rec.get("checked_at"), "signed": rec.get("signed"),
            "offline_until": rec.get("checked_at", 0) + GRACE_DAYS * 86400}


def require():
    st = state()
    if not st["ok"]:
        raise HTTPException(402, f"no active license ({st['reason']}): sign in and activate this device")
    return st
