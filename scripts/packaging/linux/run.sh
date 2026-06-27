#!/bin/sh
# Launch TaxFlow Pro 3.11.5 from extracted tarball
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
export PATH="$HERE:$PATH"
exec "$HERE/TaxFlowPro" "$@"
