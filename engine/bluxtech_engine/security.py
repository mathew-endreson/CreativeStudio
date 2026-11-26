"""One secret per launch. The desktop shell reads it from the engine's first stdout line and opens the window on
/boot/<token>, which sets an HttpOnly cookie; every /api and /media request needs that cookie (or the token as a
bearer header / `token` query, for scripts). The UI's static files are public on localhost, the data is not."""
import os
import secrets

from fastapi.responses import JSONResponse, RedirectResponse

from . import config

TOKEN = os.environ.get("BLUXTECH_TOKEN") or secrets.token_urlsafe(32)
COOKIE = "bx_session"


def boot_url():
    return f"http://{config.HOST}:{config.PORT}/boot/{TOKEN}"


def presented(request):
    c = request.cookies.get(COOKIE)
    if c:
        return c
    h = request.headers.get("authorization", "")
    if h.lower().startswith("bearer "):
        return h[7:].strip()
    return request.query_params.get("token")


def allowed(request):
    p = request.url.path
    if not config.AUTH or p == "/api/ping":
        return True
    if not (p.startswith("/api/") or p.startswith("/media/")):
        return True
    return secrets.compare_digest(presented(request) or "", TOKEN)


async def middleware(request, call_next):
    if not allowed(request):
        return JSONResponse({"detail": "not authorized: open BluxTech Studio through the app (or its boot link)"},
                            status_code=401)
    return await call_next(request)


def boot_response(token):
    if not secrets.compare_digest(token or "", TOKEN):
        return JSONResponse({"detail": "wrong boot token: start the app again"}, status_code=403)
    r = RedirectResponse("/", status_code=303)
    r.set_cookie(COOKIE, TOKEN, httponly=True, samesite="lax", path="/")
    return r
