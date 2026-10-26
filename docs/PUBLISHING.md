# Publishing this repository

Public repository: https://github.com/dbhoriya/brother-manual-duplex-scanner

This guide records the repository metadata and maintainer publishing steps.

## Suggested repository metadata

- **Name:** `brother-manual-duplex-scanner`
- **Description:** Fast two-sided scanning for Brother printers with single-sided feeders. One manual flip, automatic page ordering, local PDFs. Linux / SANE.
- **Topics:** `brother-printer`, `duplex-scanning`, `manual-duplex`, `scanner`, `sane`, `linux`, `pyqt5`, `pdf`, `document-scanning`
- **Author:** Deepak Bhoriya
- **License:** MIT

The README title and model/workflow sections describe real search terms. They do not guarantee a search-engine ranking. Keep compatibility claims tied to actual testing.

## Before the first push

1. Read the license and README.
2. Run the test command in CONTRIBUTING.md.
3. Inspect `git status --short` and staged files; include no scans, device settings or logs.
4. Create an empty public repository on GitHub.
5. From this folder:

```bash
git add .
git diff --cached --stat
git commit -m "Initial release: Brother manual duplex scanner"
git remote add origin YOUR_GITHUB_REPOSITORY_URL
git push -u origin main
```

Replace `YOUR_GITHUB_REPOSITORY_URL` with the URL GitHub provides. Set your own Git author identity if Git requests it. The default branch is `main`. Skip adding the remote if `origin` is already configured.

After pushing, set the description/topics above, confirm the CI workflow passes, and enable issue reporting. Screenshots use synthetic demonstration documents.
