#!/usr/bin/env bash
# The Python entry owns all configuration and startup policy.
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
exec python3 "$root/src/bridge/web/__main__.py" "$@"
