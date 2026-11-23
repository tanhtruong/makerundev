from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

NOT_BUILT = """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>makerundev</title></head>
<body>
<p>UI not built: run <code>make build-web</code>, then restart the server.</p>
<p>The JSON API under <a href="/api/activities">/api</a> works without it.</p>
</body>
</html>
"""


def serve(app: FastAPI, web_dir: Path) -> None:
    if (web_dir / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=web_dir / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False, response_model=None)
    def single_page_app(request: Request, path: str) -> Response:
        if path.endswith("/"):
            query = f"?{request.url.query}" if request.url.query else ""
            return RedirectResponse(f"/{path.rstrip('/')}{query}", status_code=307)
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404, detail="not found")
        index = web_dir / "index.html"
        if not index.is_file():
            return HTMLResponse(NOT_BUILT, status_code=503)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
