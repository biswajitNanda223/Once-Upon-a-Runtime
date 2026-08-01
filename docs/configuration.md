# `databricks.yml` versus `app.yaml`

They operate at different layers and are both intentionally present.

| File | Owner/lifecycle | Purpose | Typical content |
|---|---|---|---|
| `databricks.yml` | CI/IaC, evaluated by Databricks CLI | Declares workspace resources and environments | bundle name, Apps, source paths, resource bindings, permissions, dev/prod targets |
| `app.yaml` | App runtime, read during App deployment | Says how one uploaded app runs | process command and runtime environment variables/`valueFrom` keys |

`databricks.yml` must exist exactly once at the Bundle root; it can include other Bundle YAML fragments. Each deployable App source root may have its own optional `app.yaml`. Do not put Bundle targets in `app.yaml`, and do not put plaintext secrets in either file.

The current Bundle schema also supports an app `config` block that can generate `app.yaml`. This repo keeps physical `app.yaml` files because each independently deployable directory remains understandable and runnable on its own.

## Build behavior that matters here

When the App source root has `package.json`, Databricks installs Node dependencies, installs Python dependencies when declared, runs the package `build` script, and then runs the `app.yaml` command. Therefore the unified App can build React and start only Uvicorn. It does not need two long-running processes. The split frontend uses the same build behavior and starts its thin BFF.

Commands are passed as an argument sequence, not evaluated by a shell. `DATABRICKS_APP_PORT` is a special runtime substitution, while Uvicorn also receives automatic host/port environment settings. All nonstandard configuration belongs in `env`; use `valueFrom` for managed resources and secrets.

References: [`app.yaml` runtime](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/app-runtime), [environment variables](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/environment-variables), [Bundle app resources](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/bundles/resources), and [Bundle variables](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/bundles/variables).

