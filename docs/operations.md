# Networking, observability and operations

## Networking

- User traffic to the Apps domain is TLS-protected. Configure workspace IP access lists and front-end Private Link where required.
- In Private Link environments, configure conditional DNS forwarding for `databricksapps.com`.
- Restricted egress policies must allow package sources used during builds (`pypi.org`, `files.pythonhosted.org`, `registry.npmjs.org`) plus required Apps/Azure endpoints.
- Do not add browser CORS for the split pattern. The BFF creates a same-origin browser surface and makes the authenticated server-to-server call.

## Secrets and storage

- Bind Databricks secrets/resources and expose them with `valueFrom`; never hardcode secrets in YAML, Python, TypeScript, GitLab logs, or Vite variables.
- Local App disk is ephemeral. Use Unity Catalog volumes/tables or Lakebase for durable state.
- Do not cache user OAuth tokens. If caching user-specific data, key it by a stable user identity and apply short TTLs without storing credentials.

## Observability

- Emit structured JSON to stdout/stderr and inspect the App Logs tab.
- Include `X-Request-Id`, app name and operation, but redact `Authorization`, cookies, access tokens and sensitive query parameters.
- Monitor startup/deployment failures, 4xx/5xx rate, backend latency, app-to-app failures and dependency saturation.
- Apps have default runtime resource limits; select supported compute size based on measured workload, not guesswork.

## Troubleshooting order

1. App does not start: inspect build/runtime logs, root dependency manifests, `app.yaml` command, and ensure the server binds `0.0.0.0` on the injected port.
2. Split proxy returns 401: confirm user authorization is enabled and scoped, or set app auth and ensure the App Resource grants `CAN USE`.
3. Split proxy returns 403: verify the caller permission, token scopes and target resource privileges independently.
4. `BACKEND_APP_NAME` missing: confirm the `backend-app` resource exists and `valueFrom` matches its key.
5. Local SPA returns missing `index.html`: run `npm run build` before Uvicorn.
6. Deployment downloads fail: check network policy allowlists and private DNS.

References: [networking](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/networking), [runtime environment](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/system-env), and [logging/monitoring](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/monitor).

