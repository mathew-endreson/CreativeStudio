"""Start the engine.

    python -m bluxtech_engine                       dev: workspace = the SH-101126 project root, http://127.0.0.1:8766
    python -m bluxtech_engine --open                ... and open the UI (through its boot link) in the browser
    python -m bluxtech_engine --resources <dir> --workspace <dir> --port 0
                                                    installed: what the desktop shell runs; it reads the first stdout
                                                    line, `BLUXTECH_READY {json}`, for the port and the boot token
"""
import argparse
import json
import socket
import webbrowser


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    ap = argparse.ArgumentParser(prog="bluxtech_engine", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workspace", help="folder with .claude/skills/bluxstudio-skill and _hyperframes (default: the project root in dev)")
    ap.add_argument("--resources", help="the desktop app's resources folder (switches to installed mode)")
    ap.add_argument("--data", help="where the engine keeps its database (default: %%LOCALAPPDATA%%\\BluxTech Studio)")
    ap.add_argument("--port", type=int, default=None, help="0 = any free port (default 8766)")
    ap.add_argument("--no-auth", action="store_true", help="dev only: no boot token on /api and /media")
    ap.add_argument("--open", action="store_true", help="open the UI in the default browser")
    a = ap.parse_args()

    from . import config
    config.init(workspace=a.workspace, resources=a.resources, port=a.port, auth=not a.no_auth, data=a.data)
    from . import environment
    environment.init_workspace()
    environment.link_root_node_modules()     # both modes: npx hyperframes resolves to the bundled version
    if config.PORT == 0:
        config.PORT = free_port()
    from . import security
    from .app import app
    import uvicorn

    print("BLUXTECH_READY " + json.dumps({"port": config.PORT, "token": security.TOKEN, "mode": config.MODE,
                                          "workspace": str(config.ROOT), "version": config.VERSION}), flush=True)
    if a.open:
        webbrowser.open(security.boot_url())
    uvicorn.run(app, host=config.HOST, port=config.PORT, log_level="warning")


if __name__ == "__main__":
    main()
