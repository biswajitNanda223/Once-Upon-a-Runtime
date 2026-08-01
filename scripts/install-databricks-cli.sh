#!/usr/bin/env sh
set -eu
export DATABRICKS_CLI_VERSION="${DATABRICKS_CLI_VERSION:-0.299.1}"
curl -fsSL https://raw.githubusercontent.com/databricks/setup-cli/main/install.sh | sh
databricks version
