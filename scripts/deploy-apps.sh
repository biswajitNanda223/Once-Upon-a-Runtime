#!/usr/bin/env sh
set -eu
pattern="${1:-both}"
target="${2:-dev}"
case "$pattern" in
  unified) databricks bundle run unified_app -t "$target" ;;
  split)
    databricks bundle run split_backend -t "$target"
    databricks bundle run split_frontend -t "$target"
    ;;
  both)
    databricks bundle run unified_app -t "$target"
    databricks bundle run split_backend -t "$target"
    databricks bundle run split_frontend -t "$target"
    ;;
  *) echo "DEPLOY_PATTERN must be unified, split, or both" >&2; exit 2 ;;
esac

