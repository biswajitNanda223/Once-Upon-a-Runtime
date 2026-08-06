# Official references: Databricks Apps U2M and App-to-App authentication

> Verified against current Microsoft Learn documentation on **2026-08-06**. This catalog intentionally uses official Microsoft/Azure Databricks sources rather than blogs or community examples.

## 1. How to use this reference

The U2M scenario has two separate identity hops. The documentation uses “U2M” precisely so these mechanisms are not mixed together:

| Hop | Identity model | Repository implementation | Primary official reference |
|---|---|---|---|
| Browser → frontend Databricks App | Human sign-in and gateway-established identity | Reads trusted `X-Forwarded-User`, preferred username and email | [Configure authorization in a Databricks app](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/auth) |
| Frontend App → backend App | App authorization / OAuth M2M | Frontend App service principal obtains a token and calls the backend protected by `CAN_USE` | [Add a Databricks app resource](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/apps-resource) |
| App → Databricks resource as the human | User authorization / on-behalf-of-user (U2M) | Not required by profile sync; use only for a scoped downstream Databricks action | [Databricks Apps user authorization](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/auth#user-authorization) |

The first hop authenticates the person using Databricks. The second authenticates the calling application. They are complementary, not interchangeable.

## 2. Required reading: Databricks Apps authorization

### Configure authorization in a Databricks app

Official documentation: [Configure authorization in a Databricks app](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/auth)

Use this page for:

- the difference between **App authorization** and **User authorization**;
- the dedicated service principal created for each App;
- on-behalf-of-user access and Unity Catalog enforcement;
- OAuth scopes, consent and scope restrictions;
- retrieving `X-Forwarded-Access-Token` when a downstream Databricks API must run as the person.

As of the verification date, Databricks Apps user authorization/on-behalf-of-user is documented as **Public Preview**. Confirm its status, regional availability and workspace requirements before making it a production dependency.

Repository mapping:

- [`frontend/server/identity.ts`](../../scenarios/u2m-postgres/frontend/server/identity.ts) consumes user identity.
- [`frontend/server/backend-client.ts`](../../scenarios/u2m-postgres/frontend/server/backend-client.ts) uses App authorization for the backend call.
- The scenario deliberately does not read or forward `X-Forwarded-Access-Token` because PostgreSQL profile synchronization is not a user-scoped Databricks resource operation.

### Access HTTP headers passed to Databricks Apps

Official documentation: [Access HTTP headers passed to Databricks Apps](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/http-headers)

This page defines the reverse-proxy headers used by the identity adapter, including:

- `X-Forwarded-User` — user identifier provided by the identity provider;
- `X-Forwarded-Preferred-Username` — preferred user name;
- `X-Forwarded-Email` — user email;
- `X-Request-Id` — request correlation identifier;
- `X-Forwarded-Host` and `X-Real-Ip` — original request metadata.

The headers exist in the Databricks Apps runtime and must be simulated only in explicit local-development mode. Browser request fields are not a replacement for gateway-created identity headers.

Repository mapping: [`frontend/server/identity.ts`](../../scenarios/u2m-postgres/frontend/server/identity.ts).

### Configure permissions for a Databricks App

Official documentation: [Configure permissions for a Databricks app](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/permissions)

Use this page to distinguish:

- App ACLs such as `CAN_USE` and `CAN_MANAGE`;
- user access to the frontend App;
- the identity forwarded after a user is authenticated;
- authorization of an App service principal to use resources.

Repository mapping: root [`databricks.yml`](../../databricks.yml) grants people `CAN_USE` on the frontend and grants the frontend App service principal `CAN_USE` on the backend through an App Resource.

## 3. App-to-App OAuth and service principals

### Add a Databricks App Resource

Official documentation: [Add a Databricks app resource to a Databricks app](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/apps-resource)

This is the principal reference for the two-App connection. It documents that:

- a Databricks App can be attached as another App's resource;
- `CAN_USE` is granted to the calling App's service principal;
- `valueFrom` exposes the target App **name**, not a hardcoded URL;
- the caller resolves the target App URL at runtime;
- removing the resource removes the corresponding permission.

Repository mapping:

- [`databricks.yml`](../../databricks.yml) declares `u2m-backend-app` under `u2m_frontend`.
- [`frontend/app.yaml`](../../scenarios/u2m-postgres/frontend/app.yaml) maps it to `BACKEND_APP_NAME`.
- [`frontend/server/backend-client.ts`](../../scenarios/u2m-postgres/frontend/server/backend-client.ts) resolves the App URL and calls `/api/internal/users/sync`.

### Add resources to a Databricks App

Official documentation: [Add resources to a Databricks app](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/resources)

Use this overview for resource types, dedicated App service principals, automatic credential injection, least privilege and avoiding hardcoded resource identifiers. It documents the runtime credential variables `DATABRICKS_CLIENT_ID` and `DATABRICKS_CLIENT_SECRET`.

### OAuth M2M for service principals

Official documentation: [Authorize service principal access with OAuth](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/auth/oauth-m2m)

Use this page for:

- unified authentication as the preferred approach;
- workspace-level OAuth token endpoints;
- `client_credentials` and `scope=all-apis` when a supported SDK is unavailable;
- token expiry/refresh behavior;
- `DATABRICKS_HOST`, client ID and client secret troubleshooting;
- the difference between HTTP 401 authentication failures and HTTP 403 permission failures.

Repository mapping: [`frontend/server/backend-client.ts`](../../scenarios/u2m-postgres/frontend/server/backend-client.ts) implements the documented manual client-credentials exchange for the Node BFF and caches the token short of expiry.

### Service-principal lifecycle

Official documentation:

- [Service principals in Azure Databricks](https://learn.microsoft.com/en-us/azure/databricks/admin/users-groups/service-principals)
- [Manage service principals](https://learn.microsoft.com/en-us/azure/databricks/admin/users-groups/manage-service-principals)

Use these references for Databricks-managed versus Microsoft Entra-managed service principals, workspace assignment, OAuth secret lifecycle and administrative roles. The GitLab deployment principal is operationally separate from the service principal automatically assigned to each Databricks App.

## 4. OAuth U2M outside and inside Databricks Apps

### Generic Databricks OAuth U2M

Official documentation: [Authorize user access to Azure Databricks with OAuth](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/auth/oauth-u2m)

This page describes interactive OAuth for a CLI, SDK or external application acting as a user. It is useful background, but a custom sign-in callback in React is not needed merely to identify a visitor to a Databricks App: the Databricks App gateway already protects the App URL and forwards identity.

### When `X-Forwarded-Access-Token` is appropriate

Use the token described under [Retrieve user authorization credentials](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/auth#retrieve-user-authorization-credentials) only when the App must call a Databricks API or resource under the current user's permissions—for example, querying governed data where Unity Catalog row filters and masks must apply to that person.

Required controls include:

1. enable Databricks Apps user authorization in the workspace;
2. configure only the required App OAuth scopes;
3. obtain user/admin consent as documented;
4. keep the forwarded token in server memory only;
5. never expose it to React, persist it, place it in a URL or log it;
6. let Databricks/Unity Catalog evaluate the user's permissions.

Do not use the user's token for the frontend-to-backend profile-sync hop. That hop authorizes a service, not an individual Databricks data operation.

## 5. Runtime YAML and resource values

### `app.yaml`

Official documentation: [Configure App execution with `app.yaml`](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/app-runtime)

This page defines the App start `command`, `env`, `value` and `valueFrom` behavior. It also explains that the command is not run by a shell. Keep variable expansion and shell-specific syntax out of the command array.

Repository mapping:

- [`frontend/app.yaml`](../../scenarios/u2m-postgres/frontend/app.yaml)
- [`backend/app.yaml`](../../scenarios/u2m-postgres/backend/app.yaml)

### Environment variables and `valueFrom`

Official documentation:

- [Define environment variables in a Databricks app](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/environment-variables)
- [Databricks Apps system environment](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/system-env)

Use these pages for system-injected variables, runtime resource keys and `valueFrom`. A `valueFrom` entry refers to an authorized App resource key. It is not the secret value and must exactly match the key defined for that App.

### Secret resources

Official documentation: [Add a secret resource to a Databricks app](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/secrets)

Use this page for binding a secret-scope entry to an App and exposing it through `valueFrom`. The official guidance notes that secret permissions apply at the scope level. Therefore this repository uses a backend-only database scope and a separate signing-only scope shared by the two server processes. The signing secret is never part of the React build.

Repository mapping: the `u2m_backend` and `u2m_frontend` resource sections in [`databricks.yml`](../../databricks.yml).

## 6. Declarative Automation Bundles

Official documentation:

- [What are Declarative Automation Bundles?](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/bundles/)
- [Bundle configuration and `databricks.yml`](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/bundles/settings)
- [Bundle resource reference](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/bundles/resources)
- [Bundle configuration examples](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/bundles/examples)
- [Manage Databricks Apps using Bundles](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/bundles/apps-tutorial)

These references establish that `databricks.yml` is the root deployment definition, describe the App resource schema, targets and variables, and provide official App/database examples.

Repository mapping: [`databricks.yml`](../../databricks.yml) creates the two Apps, binds resources, sets permissions and selects environment-specific secret scopes. Each scenario-level `app.yaml` controls only that App process.

## 7. Networking and API routing

Official documentation:

- [Databricks Apps networking](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/networking)
- [Connect to an API App using token authentication](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/connect-local)

Use these references for outbound connectivity, network controls and the `/api/` route requirement. The repository keeps browser traffic same-origin at `/api/me`; the Node BFF calls the second App server-to-server. Therefore the supported production path does not require a permissive backend CORS policy.

Repository mapping:

- [`frontend/server/index.ts`](../../scenarios/u2m-postgres/frontend/server/index.ts) registers APIs before the SPA fallback.
- [`frontend/vite.config.ts`](../../scenarios/u2m-postgres/frontend/vite.config.ts) contains a local-development proxy only.

## 8. PostgreSQL security references

The example uses PostgreSQL as an external application database. Official Azure references:

- [Azure Database for PostgreSQL security overview](https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/security-overview)
- [Private access and virtual network integration](https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/concepts-networking-private)
- [Configure TLS connections](https://learn.microsoft.com/en-us/azure/postgresql/security/security-tls-how-to-connect)
- [Backup and restore concepts](https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/concepts-backup-restore)

These sources support TLS, private networking, least-privilege database roles and recovery planning. Database authentication is independent from Databricks human U2M and App-to-App OAuth.

Repository mapping:

- [`backend/migrations/001_create_users.sql`](../../scenarios/u2m-postgres/backend/migrations/001_create_users.sql)
- [`backend/app/users.py`](../../scenarios/u2m-postgres/backend/app/users.py)
- [`backend/app/database.py`](../../scenarios/u2m-postgres/backend/app/database.py)

## 9. Evidence-to-implementation checklist

| Design statement | Official evidence | Repository evidence |
|---|---|---|
| Gateway supplies user identity | [HTTP headers](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/http-headers) | `identity.ts` |
| Each App has a dedicated identity | [App authorization](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/auth#app-authorization) | App resources in `databricks.yml` |
| Calling App needs backend `CAN_USE` | [App Resource](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/apps-resource) | `u2m-backend-app` binding |
| Target App name is injected via `valueFrom` | [App Resource environment variables](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/apps-resource#environment-variables) | Frontend `app.yaml` |
| Service automation should use OAuth | [OAuth M2M](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/auth/oauth-m2m) | `backend-client.ts` |
| User token is only for scoped OBO calls | [User authorization](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/auth#user-authorization) | Token intentionally absent from profile flow |
| Secrets should be App resources | [Secret resource](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/secrets) | HMAC/DB bindings |
| Bundle owns deployable resources | [Bundle resource reference](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/bundles/resources) | Root `databricks.yml` |

## 10. Review cadence

Re-check these references before a production release because Databricks Apps evolves rapidly. In particular, verify:

- the preview/GA state of Databricks Apps user authorization;
- supported OAuth scopes and workspace restrictions;
- App Resource and Bundle schema changes;
- system environment variable behavior;
- Apps networking support for the selected Azure PostgreSQL topology;
- current Databricks CLI version and bundle validation schema.
