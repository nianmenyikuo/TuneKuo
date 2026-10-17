#!/usr/bin/env bash
set -e
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${PYTHON:-python3}" "$here/../app/main.py" "$@"
