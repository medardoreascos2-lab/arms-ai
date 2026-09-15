#!/usr/bin/env bash
set -o pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT" || exit 1

PY="/c/Users/Thecrazyboss/AppData/Local/Python/pythoncore-3.14-64/python.exe"

if [ ! -x "$PY" ]; then
    PY="python"
fi

exec "$PY" tools/arms_dev_runner.py "$@"
