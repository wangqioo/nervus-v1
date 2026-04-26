import os
from pathlib import Path

from fastapi.responses import HTMLResponse

from nervus_sdk import NervusApp

nervus = NervusApp("model-manager")

_HTML = (Path(__file__).parent / "index.html").read_text(encoding="utf-8")


@nervus._api.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(_HTML)


@nervus.state
async def get_state():
    return {"status": "ok"}


if __name__ == "__main__":
    nervus.run(port=int(os.getenv("APP_PORT", "8016")))
