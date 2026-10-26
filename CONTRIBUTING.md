# Contributing

## Set up

1. Install dependencies from the README.
2. Run `python simple.py` for the app.
3. Install `poppler-utils` and run:

```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest test_audit test_scanner_setup test_preferences -v
```

Tests are offline and use temporary files and a simulated scanner. They do not acquire physical scans.

Format Python changes with Black (`black .`); configuration is in `pyproject.toml`.

## Changes

- Keep the main interface simple. Put extra settings in Preferences or Scanner setup.
- Preserve whole-stack acquisition; selecting a thumbnail must not select a scan range.
- Preserve original images and project recovery.
- Add a focused regression test for a bug fix.
- Describe the problem, changed behavior, and test results in the pull request.
- Do not add documents, local logs, device IDs, or credentials.

## Hardware reports

Include printer model, Linux distribution, connection type, backend/driver version, source, resolution, and whether single-sided or manual duplex was tested. Redact serial numbers and document content. Report compatibility through the hardware-report issue template; do not infer support from printing support alone.

## Code map

| File | Responsibility |
|---|---|
| `simple.py` | Main window, whole-stack workflow, editing actions |
| `model.py` | Project persistence, recovery, image rendering, PDF export |
| `scanner_setup.py` | Device selection and backend profiles |
| `preferences.py` | Paper sizes and application preferences |
| `crop.py` | Crop editor |
| `theme.py`, `ui.py` | Styles, vector icons, shared Qt helpers |
| `assets/` | Original application graphics |

Code and original graphics contributed to this repository are covered by the MIT license.
