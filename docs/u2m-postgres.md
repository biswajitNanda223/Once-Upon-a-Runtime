# U2M identity with two Databricks Apps and PostgreSQL

This is the implementation guide for [`scenarios/u2m-postgres`](../scenarios/u2m-postgres). It separates a React/Node frontend App from a FastAPI/PostgreSQL backend App without exposing backend addresses, OAuth credentials, database credentials, or mutable browser identity to React.

## What “U2M” means here

There are two different authentication hops. Keeping them distinct prevents the most common design mistake.

| Hop | Identity | Protocol and enforcement |
|---|---|---|
| Browser → frontend App | Human user (U2M) | Databricks sign-in and App gateway; gateway supplies trusted identity headers |
| Frontend App → backend App | Frontend App service principal (M2M) | OAuth client credentials and backend `CAN_USE`; Databricks App gateway validates it |
| Frontend BFF → backend payload | Human context delegated by a trusted server | Minimal JSON signed with a shared HMAC; never accepted directly from browser input |

Do not forward `X-Forwarded-Access-Token` merely to synchronize a profile. That token is relevant only when downstream Databricks APIs must execute with the individual user's permissions. The profile-sync call uses the frontend App identity instead.

## High-level design

```mermaid
flowchart LR
  USER[User browser] -->|Databricks SSO / U2M| FRONT_GATE[Frontend App gateway]
  FRONT_GATE -->|trusted X-Forwarded identity| BFF[Node and Express BFF]
  BFF -->|same origin| SPA[React static files]
  BFF -->|OAuth as frontend App SP| BACK_GATE[Backend App gateway]
  BACK_GATE -->|CAN_USE passed| API[FastAPI profile API]
  API -->|TLS connection| PG[(PostgreSQL)]
  SCOPE[Databricks secret scope] -. database URL .-> API
  SCOPE -. signing secret .-> API
  SCOPE -. signing secret .-> BFF
```

The React application calls only `/api/me`. This is a relative, same-origin route handled by Express. Express—not the browser—discovers the backend App URL and adds OAuth. Consequently browser CORS configuration is unnecessary in production.

## Low-level request sequence

```mermaid
sequenceDiagram
  autonumber
  actor User
  participant Gateway as Frontend Databricks gateway
  participant BFF as Node BFF
  participant OAuth as Databricks OAuth
  participant Apps as Workspace Apps API
  participant BackendGateway as Backend Databricks gateway
  participant API as FastAPI
  participant DB as PostgreSQL
  User->>Gateway: GET / (Databricks session)
  Gateway->>BFF: GET / + trusted identity headers
  BFF-->>User: React index.html
  User->>Gateway: GET /api/me
  Gateway->>BFF: /api/me + trusted identity headers
  BFF->>OAuth: client_credentials (App SP)
  OAuth-->>BFF: short-lived access token
  BFF->>Apps: resolve BACKEND_APP_NAME
  Apps-->>BFF: backend App URL
  BFF->>BFF: HMAC(timestamp + exact JSON body)
  BFF->>BackendGateway: POST /api/internal/users/sync + Bearer token
  BackendGateway->>BackendGateway: validate SP and CAN_USE
  BackendGateway->>API: authenticated request
  API->>API: verify HMAC and freshness
  API->>DB: INSERT ... ON CONFLICT DO UPDATE RETURNING
  DB-->>API: canonical user row
  API-->>BFF: safe profile
  BFF-->>User: id, username, email only
```

### Identity contract

The BFF reads these headers only after traffic has passed through the frontend Databricks gateway:

- `X-Forwarded-User`: stable `external_user_id` and the database uniqueness key.
- `X-Forwarded-Preferred-Username`: optional display value.
- `X-Forwarded-Email`: optional and mutable contact value.

The browser cannot select these values. Query parameters, request bodies, cookies created by this application, and browser-created lookalike headers are never used as identity. `AUTH_MODE=local` is an explicit development adapter and deliberately throws if `NODE_ENV=production`.

The backend receives only `external_user_id`, `username`, and `email`. The HMAC covers the Unix timestamp and exact request bytes, uses constant-time comparison, and expires after 60 seconds. It provides payload integrity after the gateway's M2M authorization. It does not replace OAuth or `CAN_USE`.

## Why proxying fixes CORS and dynamic routes

In a two-App design, directly putting the backend URL into `VITE_*` creates four problems: it exposes topology, makes the browser acquire credentials, introduces cross-origin preflights, and lets frontend configuration drift by environment. This implementation uses a BFF:

```text
Browser /api/me → frontend gateway → Node BFF → backend gateway → FastAPI
```

Vite's proxy exists only for local development. Production requests do not use Vite; Express serves `dist` and owns `/api/*`.

Express registers the API routes before the SPA fallback. `/{*path}` then serves `index.html`, allowing React Router paths such as `/projects/42` to refresh correctly. Never register the fallback before `/api/*`, or API failures will incorrectly return HTML. Databricks App API endpoints must remain under `/api/`.

If a browser must call the backend App directly, configure an exact origin allow-list, credentials behavior, preflight responses, and OAuth in the browser. That architecture is intentionally not used here.

## `app.yaml` versus `databricks.yml`

| File | Scope | Purpose |
|---|---|---|
| `frontend/app.yaml` | One running frontend App | Start command and mapping of already-authorized resources into process environment variables |
| `backend/app.yaml` | One running backend App | FastAPI command and runtime environment mapping |
| Root `databricks.yml` | Whole deployment | Creates both Apps, grants permissions, binds App/secret resources, selects source folders, and defines dev/prod targets |

`app.yaml` does not create an App, permission, secret, or database. Its `valueFrom` names must exactly match resource names under the corresponding App in `databricks.yml`. Do not put secret values in either YAML file.

The frontend App Resource is the key connection:

```yaml
resources:
  - name: u2m-backend-app
    app:
      name: ${resources.apps.u2m_backend.name}
      permission: CAN_USE
```

During deployment, Databricks grants the frontend App service principal `CAN_USE` on the backend App and injects the backend App name. The BFF exchanges its system-injected `DATABRICKS_CLIENT_ID` and `DATABRICKS_CLIENT_SECRET` for a short-lived token, caches it short of expiry, resolves the target through the Workspace Apps API, and calls the target URL. Credentials and tokens are never logged.

## PostgreSQL and idempotency

Run [`001_create_users.sql`](../scenarios/u2m-postgres/backend/migrations/001_create_users.sql) with a migration principal before the first App deployment. The runtime principal should receive only `SELECT`, `INSERT`, and `UPDATE` on `users`; it does not need schema-owner permissions.

`external_user_id` is unique and immutable. `email` and `username` are mutable. One PostgreSQL `INSERT ... ON CONFLICT DO UPDATE ... RETURNING` statement makes first login, repeat login, changed attributes, and simultaneous login requests idempotent. The SQLAlchemy session rolls back on every failure.

Use Azure Database for PostgreSQL Flexible Server with TLS required and private connectivity for production. Put a URL in this form in a Databricks secret (URL-encode password characters):

```text
postgresql+psycopg://app_runtime:ENCODED_PASSWORD@server.postgres.database.azure.com:5432/runtime?sslmode=require
```

## Secrets and least privilege

Create different scopes and values per environment. Generate the HMAC using a cryptographic random generator; both Apps need the same value for a coordinated rotation.

```bash
databricks secrets create-scope once-upon-runtime-u2m-dev
databricks secrets put-secret once-upon-runtime-u2m-dev database-url
databricks secrets put-secret once-upon-runtime-u2m-dev identity-hmac-secret
```

The bundle gives the database URL only to the backend. It gives the HMAC secret to both server processes. Neither value is prefixed `VITE_`, returned from an endpoint, stored in Git, or available to React. Use a separate production scope, database role, and signing key. Rotate the signing key by supporting current/next keys during a controlled rollout if zero downtime is required.

## Local development

Prerequisites are Node.js 20+, Python 3.11+, and Docker. Copy the example variables into your shell or untracked `.env` files; use the same development HMAC value in both processes.

```bash
docker compose -f scenarios/u2m-postgres/docker-compose.local.yml up -d
python -m venv .venv
.venv/Scripts/pip install -r scenarios/u2m-postgres/backend/requirements-test.txt
set AUTH_MODE=local
set DATABASE_URL=postgresql+psycopg://runtime:local-only-password@127.0.0.1:5432/runtime
set INTERNAL_IDENTITY_HMAC_SECRET=replace-with-a-random-32-character-development-value
uvicorn app.main:app --app-dir scenarios/u2m-postgres/backend --port 8001
```

In a second terminal:

```bash
cd scenarios/u2m-postgres/frontend
npm ci
set AUTH_MODE=local
set LOCAL_BACKEND_URL=http://127.0.0.1:8001
set INTERNAL_IDENTITY_HMAC_SECRET=replace-with-a-random-32-character-development-value
npm run build
npm run start
```

Open `http://localhost:8000`. Local mode is fixed test identity, not a production authentication substitute.

## Deploy and verify

Authenticate the CLI using a CI service principal, create the secret values, and validate before changing the workspace:

```bash
databricks bundle validate -t dev
databricks bundle deploy -t dev
databricks bundle run u2m_backend -t dev
databricks bundle run u2m_frontend -t dev
```

Grant human users or groups `CAN_USE` only on the frontend. The bundle grants the frontend service principal access to the backend through the App Resource. Do not grant general workspace users access to the internal backend unless they have a separate supported use case.

Verification checklist:

1. A signed-in user sees `/api/me` return only safe profile fields.
2. First access creates one row; repeat and concurrent access keep one row.
3. Changed username/email updates the same row and `last_login_at`.
4. Missing frontend identity returns 401; missing, altered, or expired internal signature returns 401.
5. Direct browser access to the backend is denied by App permissions.
6. Refreshing a React dynamic route returns the SPA, while unknown `/api/*` paths remain API 404s.
7. Logs contain request IDs and outcomes, never authorization headers, OAuth tokens, signing keys, database URLs, or request bodies.

## CI/CD and service principals

GitLab uses one non-human Databricks service principal through protected, masked `DATABRICKS_HOST`, `DATABRICKS_CLIENT_ID`, and `DATABRICKS_CLIENT_SECRET` variables. Give it only the workspace permissions necessary to deploy the bundle and manage these Apps. It is distinct from each App's Databricks-managed runtime service principal.

The pipeline validates TypeScript/Python, runs tests, builds React, runs GitLab SAST and dependency scanning, scans the existing container examples, validates the bundle, deploys development, performs authenticated DAST when `DAST_WEBSITE` is configured, and requires a manual tagged production promotion. `deploy_u2m_dev` is manual until its database and secrets are provisioned. Production secrets are never copied from development.

## Official references

- [Databricks Apps authentication and user authorization](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/auth)
- [Databricks Apps HTTP identity headers](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/http-headers)
- [Connect Databricks Apps using an App Resource](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/apps-resource)
- [Databricks Apps runtime and `app.yaml`](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/app-runtime)
- [Manage Apps with Declarative Automation Bundles](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/bundles/apps-tutorial)
- [Databricks Apps system environment variables](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/system-env)
- [Databricks Apps permissions](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/permissions)
- [Azure Database for PostgreSQL security](https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/security-overview)
