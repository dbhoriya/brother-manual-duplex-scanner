# Security and privacy

The app runs locally and invokes `scanimage` with argument lists, not shell command strings. It does not upload documents or install drivers automatically.

- Obtain scanner drivers from your distribution or the manufacturer.
- Open project files only from sources you trust: they refer to image files on disk.
- Do not attach confidential scans or unredacted device logs to public issues.
- Keep Python, Qt, Pillow, SANE, and scanner drivers updated.

Report reproducible bugs using the bug template. If a report contains sensitive security details, use GitHub's private vulnerability reporting when enabled for the repository; otherwise request a private reporting channel without posting the details publicly.
