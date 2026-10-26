#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
scan_python="${PYTHON:-python3}"
if ! "$scan_python" -c 'import PyQt5.QtWidgets; import PIL' >/dev/null 2>&1; then
    echo 'Missing Python dependencies. See README: install Python 3, PyQt5 and Pillow.' >&2
    exit 1
fi
exec "$scan_python" simple.py "$@"
