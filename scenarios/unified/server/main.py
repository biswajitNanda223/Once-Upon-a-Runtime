from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Once Upon a Runtime unified API", version="1.0.0")
STATIC = Path(__file__).resolve().parents[1] / "static"


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/hello")
def hello(request: Request) -> dict[str, str]:
    # Databricks strips client spoofing and injects these after SSO.
    email = request.headers.get("x-forwarded-email", "local.user@example.com")
    return {"message": "Hello from FastAPI", "email": email, "pattern": "unified"}


@app.get("/api/items/{item_id}")
def item(item_id: int) -> dict[str, int | str]:
    return {"id": item_id, "name": f"Runtime item {item_id}"}


if STATIC.exists():
    app.mount("/assets", StaticFiles(directory=STATIC / "assets"), name="assets")


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str) -> FileResponse:
    candidate = (STATIC / path).resolve()
    if path and candidate.is_relative_to(STATIC.resolve()) and candidate.is_file():
        return FileResponse(candidate)
    return FileResponse(STATIC / "index.html")
