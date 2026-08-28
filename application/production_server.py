"""Official single-worker DexSato production launcher."""

from __future__ import annotations

import os


def main() -> None:
    os.environ.setdefault("DEXSATO_ENV", "production")
    os.environ.setdefault("DEXSATO_WEB_WORKERS", "1")

    import uvicorn

    from application.production_security import application_host, application_port

    uvicorn.run(
        "app.main:app",
        host=application_host(),
        port=application_port(),
        workers=1,
        access_log=False,
    )


if __name__ == "__main__":
    main()
