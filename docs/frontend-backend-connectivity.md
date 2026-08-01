# Frontend-to-backend connectivity in separate Databricks Apps

This is the most important part of the split deployment. The short answer is:

> Let the browser call only the frontend App. Let a small server inside the frontend App call the backend App.

That small server is called a **proxy**, **backend-for-frontend**, or **BFF**. The implementation is [proxy.py](../scenarios/split/frontend/proxy.py).

## The problem in plain language

After deployment, the two Apps have different URLs:

```text
Frontend: https://once-upon-a-runtime-web-123.region.databricksapps.com
Backend:  https://once-upon-a-runtime-api-456.region.databricksapps.com
```

Even though both belong to Databricks, the browser considers these two different **origins** because their hostnames differ.

An origin is the combination of:

```text
protocol + hostname + port
```

Therefore this is same-origin:

```text
https://frontend.databricksapps.com/       -> /api/hello
```

But this is cross-origin:

```text
https://frontend.databricksapps.com/       -> https://backend.databricksapps.com/api/hello
```

Browsers restrict cross-origin JavaScript calls. This browser protection is what produces most “CORS errors.”

## Why a direct browser call is difficult

Imagine React contains this code:

```ts
fetch("https://backend-app-id.region.databricksapps.com/api/hello");
```

Several independent problems can occur:

1. The browser sees a different origin and may send an `OPTIONS` preflight request.
2. The backend must return exactly the required CORS response headers.
3. The backend Databricks App has its own SSO and `CAN USE` boundary.
4. An unauthenticated API request can receive an OAuth login redirect instead of JSON.
5. The login page does not necessarily allow the frontend origin through CORS, so the browser reports “blocked by CORS.” The underlying problem may actually be missing authentication.
6. Cookies for the frontend hostname are not automatically credentials for the backend hostname.
7. Putting an OAuth token in React, local storage, or a `VITE_*` variable exposes a sensitive bearer credential to the browser.

CORS only answers: **“May JavaScript on origin A read a response from origin B?”** It does not log the user in, grant `CAN USE`, issue an OAuth token, or grant access to Unity Catalog.

## Recommended request path

```mermaid
sequenceDiagram
  actor Browser
  participant FG as Frontend Databricks gateway
  participant BFF as Frontend BFF proxy
  participant BG as Backend Databricks gateway
  participant API as FastAPI backend

  Browser->>FG: GET /api/hello (relative URL)
  Note over Browser,FG: Same frontend origin; no CORS
  FG->>BFF: Request after SSO and CAN USE check
  BFF->>BG: GET backend-url/api/hello + OAuth Bearer token
  Note over BFF,BG: Server-to-server; browser CORS does not apply
  BG->>API: Request after backend CAN USE check
  API-->>BFF: JSON response
  BFF-->>Browser: JSON from frontend origin
```

The React code stays simple:

```ts
fetch("/api/hello", { credentials: "same-origin" })
  .then((response) => {
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  });
```

The browser thinks it is talking only to the frontend hostname. There is no browser cross-origin request, so CORS middleware is unnecessary for this path.

## How the proxy knows the backend address

Do not hardcode the generated backend URL. The Bundle attaches the backend as a Databricks **App Resource**:

```yaml
# databricks.yml
split_frontend:
  resources:
    - name: backend-app
      app:
        name: ${resources.apps.split_backend.name}
        permission: CAN_USE
```

This does two things:

1. Grants the frontend App’s service principal `CAN USE` on the backend App.
2. Makes the backend App name available to `app.yaml` through `valueFrom`.

```yaml
# scenarios/split/frontend/app.yaml
env:
  - name: BACKEND_APP_NAME
    valueFrom: backend-app
```

At runtime, the proxy resolves the generated URL:

```python
from databricks.sdk import WorkspaceClient

name = os.environ["BACKEND_APP_NAME"]
backend = WorkspaceClient().apps.get(name=name)
url = backend.url
```

This remains portable across development and production workspaces.

## How the second hop authenticates

The proxy-to-backend request still needs authentication. There are two models.

Select the model through the frontend App’s `PROXY_AUTH_MODE` environment variable:

```yaml
env:
  - name: PROXY_AUTH_MODE
    value: app  # change to user only after configuring user authorization
```

### Model A: app authorization — recommended default

The frontend App calls the backend as the frontend App’s service principal:

```python
client = WorkspaceClient()
headers = client.config.authenticate()

response = await httpx_client.get(
    f"{backend_url}/api/hello",
    headers=headers,
)
```

Databricks injects the frontend App’s credentials at runtime. No secret is stored in Git. The App Resource grants this principal `CAN USE` on the backend.

Use this when the backend performs the same service operation for every signed-in frontend user. If the backend receives `X-Forwarded-Email` as informational context, it must not treat that text header as proof that the user is authorized to access data. The authenticated identity for the second hop is the frontend App.

### Model B: user authorization — advanced

With Databricks user authorization enabled, the frontend gateway supplies `X-Forwarded-Access-Token` to the BFF. The BFF can keep it server-side and use it as the backend bearer token:

```python
token = request.headers.get("x-forwarded-access-token")
headers = {"Authorization": f"Bearer {token}"}
```

This can preserve the user identity for Unity Catalog enforcement, but it has more requirements:

- User authorization must be enabled by the workspace administrator.
- Required OAuth scopes must be configured.
- The user must have `CAN USE` on the backend App as well as suitable downstream permissions.
- The target App’s required scopes must be covered by the token.
- User authorization is currently a preview capability, so validate cross-App behavior in the target workspace before choosing it as the production design.

Never return this token to React, log it, put it in a cookie you manage, or save it in browser storage.

## Complete proxy behavior

The included proxy accepts `/api/{path}` on the frontend and creates a new request to the backend:

```python
@app.api_route(
    "/api/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
)
async def proxy(path: str, request: Request) -> Response:
    async with httpx.AsyncClient(timeout=30.0) as client:
        upstream = await client.request(
            request.method,
            f"{backend_url()}/api/{path}",
            params=request.query_params,
            content=await request.body(),
            headers=auth_headers(request),
        )
    return Response(
        upstream.content,
        status_code=upstream.status_code,
        headers={"content-type": upstream.headers.get("content-type", "application/json")},
    )
```

Production proxy rules:

- Use an allowlisted `/api` path, not an arbitrary destination URL. Otherwise the proxy can become an SSRF/open-proxy vulnerability.
- Do not blindly copy all request or response headers. Remove `Host`, cookies, hop-by-hop headers and internal authentication headers.
- Set connection and response timeouts.
- Limit request and response sizes.
- Retry only idempotent operations and only for transient failures.
- Propagate a request ID for tracing.
- Return a controlled `502` or `504` response when the backend is unavailable.

## Dynamic routes: the two separate cases

### Case 1: dynamic backend API paths

A proxy written only for `/api/hello` will not automatically handle paths such as:

```text
/api/items/42
/api/customers/india/orders/2026
```

The frontend proxy therefore uses a FastAPI catch-all parameter:

```python
@app.api_route(
    "/api/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
)
async def proxy(path: str, request: Request):
    target = f"{backend_url()}/api/{path}"
```

For `/api/items/42`, `path` becomes `items/42`; the proxy sends the request to the backend as `/api/items/42`. It also preserves the query string, request method and body.

The backend declares its normal dynamic FastAPI route:

```python
@app.get("/api/items/{item_id}")
def item(item_id: int):
    return {"id": item_id, "name": f"Split backend item {item_id}"}
```

React must use a leading slash so the URL is rooted at the frontend App:

```ts
const itemId = 42;
fetch(`/api/items/${encodeURIComponent(String(itemId))}`);
```

Avoid `fetch("api/items/42")` without the leading slash. From a page such as `/projects/7`, the browser can interpret that as `/projects/api/items/42`.

Also keep backend endpoints under `/api/`. Databricks documents token-authenticated App API access for `/api/*` routes, and the prefix prevents API requests from colliding with React routes.

### Case 2: React dynamic pages and refresh/deep links

Suppose React has a client-side page `/projects/42`. Navigation inside the SPA works because React handles it. But pressing refresh sends this request to the server:

```text
GET /projects/42
```

There is no physical `projects/42` file. Without a fallback, FastAPI returns 404 and React never starts.

The frontend server must return `static/index.html` for every non-API path that is not a real static file:

```python
# Register API/proxy and /assets routes before this catch-all.
@app.get("/{path:path}", include_in_schema=False)
def spa(path: str) -> FileResponse:
    candidate = (STATIC / path).resolve()
    if path and candidate.is_relative_to(STATIC.resolve()) and candidate.is_file():
        return FileResponse(candidate)
    return FileResponse(STATIC / "index.html")
```

Route order and prefixes are important:

```text
1. /api/{path:path}     -> backend proxy
2. /assets/...          -> JavaScript/CSS files
3. /{path:path}         -> React index.html fallback
```

If the SPA catch-all is registered first or implemented as an overly broad middleware rewrite, it can return HTML for `/api/items/42`. React then reports errors such as `Unexpected token '<'` while parsing JSON.

For React Router, routes can then be declared normally:

```tsx
<Routes>
  <Route path="/" element={<Home />} />
  <Route path="/projects/:projectId" element={<Project />} />
  <Route path="*" element={<NotFound />} />
</Routes>
```

The server fallback gets React loaded; React Router decides which page component to render.

### Dynamic-route diagnostic table

| Symptom | Likely cause | Fix |
|---|---|---|
| `/projects/42` works through a link but fails on refresh | Missing SPA fallback | Return `index.html` for non-API paths |
| API returns HTML instead of JSON | SPA catch-all swallowed `/api` | Register API routes first and reserve `/api` |
| `/api/items/42` becomes `/projects/api/items/42` | Relative fetch URL lacks leading `/` | Use `/api/items/42` |
| Fixed API works but nested API is 404 | Proxy handles one fixed route or loses subpath | Use `/api/{path:path}` and append the captured path |
| Query filters disappear | Proxy did not forward query parameters | Pass `params=request.query_params` |
| Dynamic request reaches backend but is 401/403 | Path is correct; authentication/permission failed | Debug OAuth and `CAN USE`, not routing |

## When CORS middleware is actually needed

CORS is required only if browser JavaScript intentionally calls the backend App URL directly. FastAPI configuration would look like this:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://exact-frontend-app.region.databricksapps.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)
```

Do not use this insecure configuration:

```python
allow_origins=["*"]
allow_credentials=True
```

Even correctly configured CORS does not solve the separate backend SSO/token problem. For Databricks Apps, the BFF proxy is usually the cleaner architecture.

## Local development

Locally there is no Databricks App Resource. Start the backend on port 8001 and give the frontend proxy a local override:

```powershell
$env:BACKEND_BASE_URL = "http://localhost:8001"
uvicorn proxy:app --reload --port 8000
```

The proxy skips Databricks authentication for this local URL. React still calls `/api/hello`, so frontend code is identical locally and in Databricks.

An alternative during frontend-only development is a Vite development proxy:

```ts
// vite.config.ts — local development only
export default defineConfig({
  server: {
    proxy: {
      "/api": "http://localhost:8001",
    },
  },
});
```

The Vite proxy is not the production Databricks proxy: Vite runs only during development/build, while the FastAPI BFF runs after deployment.

## Debugging checklist

### Browser says “CORS policy blocked”

Check the browser Network panel. If React called the backend hostname directly, change it to the relative `/api/...` URL. If the response is a `302` or an HTML login page, the real problem is authentication, not merely missing CORS headers.

### Frontend proxy returns 401

- In app mode, confirm the request includes a token generated from `WorkspaceClient().config.authenticate()`.
- In user mode, confirm `X-Forwarded-Access-Token` reaches the BFF and user authorization is enabled.
- Never expect the frontend browser cookie alone to authenticate a server-to-server request.

### Backend returns 403

- Confirm the authenticated caller has `CAN USE` on the backend.
- For app mode, verify the `backend-app` resource is attached to the frontend.
- For user mode, verify the user’s backend permission and OAuth scopes.
- Check downstream Unity Catalog/resource privileges separately from App permissions.

### Proxy returns 502 or cannot resolve the backend

- Verify `BACKEND_APP_NAME` exists in the frontend App environment.
- Verify `valueFrom: backend-app` exactly matches the Bundle resource key.
- Deploy and start the backend before the frontend.
- Confirm the backend is running and `/api/health` responds.
- Check serverless egress/network policies and Private Link DNS.

### It works in Postman but fails in React

Postman is not a browser and does not enforce browser CORS. This almost always means the browser is making a direct cross-origin request or its credentials/preflight behavior differs. Test the recommended relative frontend URL instead:

```text
https://frontend-app...databricksapps.com/api/health
```

## Final rule of thumb

```text
Browser -> frontend App /api -> authenticated server-side proxy -> backend App
```

Use direct browser-to-backend calls only when there is a deliberate reason to own CORS, token acquisition, backend `CAN USE`, OAuth scopes and two independent App authentication boundaries.

Primary references: [App-to-app resources](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/apps-resource), [API App token authentication](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/connect-local), [App authorization](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/auth), [HTTP identity headers](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/http-headers), and [Apps networking](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/networking).
