# SSO, authentication and authorization

## Three separate controls

1. **Authentication**: Databricks Apps performs OAuth/SSO before app code runs.
2. **App permission**: `CAN USE` decides who or which service principal can invoke the app; `CAN MANAGE` controls administration.
3. **Data authorization**: either the app’s dedicated service principal or the signed-in user accesses downstream resources.

Apps cannot be anonymous or public, and custom code cannot bypass the Databricks login. External collaborators must be account identities, commonly synchronized or JIT-provisioned through the organization IdP.

## Custom React frontend

React needs no MSAL or custom callback route for normal Databricks App access. Use relative requests:

```ts
fetch("/api/hello", { credentials: "same-origin" })
```

The Databricks gateway owns browser session cookies. Do not read `X-Forwarded-Access-Token` into the SPA, place a Databricks access token in local/session storage, or embed a client secret in a Vite environment variable.

## Trusted headers in FastAPI

Databricks forwards `X-Forwarded-User`, `X-Forwarded-Preferred-Username`, `X-Forwarded-Email`, `X-Real-Ip`, and `X-Request-Id`. When user authorization is enabled it also forwards `X-Forwarded-Access-Token`.

```python
email = request.headers.get("x-forwarded-email")
token = request.headers.get("x-forwarded-access-token")
```

Only trust these when running behind the Databricks gateway. Local tests may inject them, so never treat a dev server exposed directly to the internet as protected. Identity headers are display/audit context; the OAuth bearer token is the actual credential for app-to-app or downstream API authorization.

## User authorization (on behalf of user)

As of this guide’s review date, user authorization is Public Preview. A workspace admin must enable it. In the App UI, add the minimum scopes, for example `sql` for SQL and `files` for file APIs. Defaults only cover basic identity reads. Users consent on first use, and Unity Catalog row filters and column masks apply using their identity.

For split mode, optional `user` proxy mode keeps the forwarded token server-side and sends it to the backend’s `/api/*` endpoint. The user still needs `CAN USE` on the backend, and token scopes must cover those configured by the target app. Validate cross-App user delegation in your workspace because this feature is preview. An Entra token cannot be sent directly to an App endpoint without the Databricks token-exchange flow.

## App authorization

Each App has a unique, non-reusable service principal. Databricks injects its OAuth configuration so `WorkspaceClient()` uses unified authentication without a committed secret. Bind resources to the App and grant least privilege. In split mode the `backend-app` App Resource both exposes the backend’s name through `valueFrom` and grants the frontend app principal `CAN USE`.

Use app auth for system logging, shared configuration and operations intentionally identical for all users. Never use an app principal with broad data privileges when the product is supposed to enforce per-user access.

## CI identity

Create a separate Databricks service principal for GitLab, then store these as masked, protected GitLab variables:

- `DATABRICKS_HOST`
- `DATABRICKS_CLIENT_ID`
- `DATABRICKS_CLIENT_SECRET` (or adopt workload identity federation where available)

Production targets and variables should be protected. Rotate secrets, use distinct dev/prod principals, and do not use a developer PAT. OAuth M2M tokens are short-lived and the CLI refreshes them automatically.

References: [authorization](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/auth), [permissions](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/permissions), [headers](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/http-headers), [API token calls](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/connect-local), and [OAuth M2M](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/auth/oauth-m2m).
