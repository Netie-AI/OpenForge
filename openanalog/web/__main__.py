"""Launch OpenForge web UI: python -m openanalog.web [--port 8080]"""

from __future__ import annotations

import sys

import uvicorn


def main() -> None:
    port = 8080
    host = "127.0.0.1"
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a in ("--port", "-p") and i + 1 < len(args):
            port = int(args[i + 1])
        elif a in ("--host", "-h") and i + 1 < len(args):
            host = args[i + 1]
    uvicorn.run("openanalog.web.app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
