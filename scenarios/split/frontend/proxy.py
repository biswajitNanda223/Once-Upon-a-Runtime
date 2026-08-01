import os
from functools import lru_cache
from pathlib import Path

import httpx
from databricks.sdk import WorkspaceClient
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Once Upon a Runtime frontend BFF")
STATIC = Path(__file__).parent / "static"


@lru_cache(maxsize=1)
def backend_url() -> str:
    if local := os.getenv("BACKEND_BASE_URL"):
        return local.rstrip("/")
    name = os.environ["BACKEND_APP_NAME"]
    url = WorkspaceClient().apps.get(name=name).url
    if not url:
        raise RuntimeError(f"Backend App {name!r} does not have a deployed URL")
    return url.rstrip("/")


def auth_headers(request: Request) -> dict[str, str]:
    """Keep OAuth credentials server-side. Never return them to the SPA."""
    if os.getenv("PROXY_AUTH_MODE", "app") == "user":
        token = request.headers.get("x-forwarded-access-token")
        if not token and not os.getenv("BACKEND_BASE_URL"):
            raise HTTPException(401, "User authorization token unavailable")
        return {"Authorization": f"Bearer {token}"} if token else {}
    # App authorization uses the frontend app's injected service-principal identity.
    return WorkspaceClient().config.authenticate()


@app.api_route(
    "/api/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
)
async def proxy(path: str, request: Request) -> Response:
    headers = auth_headers(request)
    headers["x-request-id"] = request.headers.get("x-request-id", "local")
    for name in ("content-type", "accept"):
        if value := request.headers.get(name):
            headers[name] = value
    # Forward identity display headers for app-auth calls only as context, never as authorization.
    for name in ("x-forwarded-user", "x-forwarded-email", "x-forwarded-preferred-username"):
        if value := request.headers.get(name):
            headers[name] = value
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0)) as client:
            upstream = await client.request(
                request.method,
                f"{backend_url()}/api/{path}",
                params=request.query_params,
                content=await request.body(),
                headers=headers,
            )
    except httpx.TimeoutException as exc:
        raise HTTPException(504, "Backend request timed out") from exc
    except httpx.RequestError as exc:
        raise HTTPException(502, "Backend is unavailable") from exc
    safe = {k: v for k, v in upstream.headers.items() if k.lower() in {"content-type", "cache-control"}}
    return Response(upstream.content, status_code=upstream.status_code, headers=safe)


if STATIC.exists():
    app.mount("/assets", StaticFiles(directory=STATIC / "assets"), name="assets")


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str) -> FileResponse:
    candidate = (STATIC / path).resolve()
    if path and candidate.is_relative_to(STATIC.resolve()) and candidate.is_file():
        return FileResponse(candidate)
    return FileResponse(STATIC / "index.html")
