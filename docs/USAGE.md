# Usage

## Whole-stack workflow

**One-sided:** load the feeder → Scan all pages → review → Save PDF.

**Two-sided:** load fronts → Scan all fronts → flip the stack once, last sheet's back first → Scan all backs → review Combined PDF → Save PDF.

Keep blank backs. Thumbnail selection controls preview/editing only; scanning always processes the whole loaded stack. On the glass, scan one side at a time and use **Fronts finished** when ready to scan backs in reverse sheet order.

## Review and edit

| Action | Control |
|---|---|
| Preview a page | Click its thumbnail |
| Zoom | Double-click, or Zoom |
| Select several pages | Ctrl-click / Shift-click |
| Select current view | Ctrl+A in the gallery |
| Delete selected pages | Delete key or Delete selected |
| Clear the document | Clear all; confirmation required |
| Undo an edit | Undo or Ctrl+Z in the gallery |
| Rotate | Rotate |
| Crop one/all pages | Crop → drag to keep area → choose scope |
| Preview actual PDF | Preview PDF; opens system viewer |

Delete and crop preserve original images. Cropping all uses the same proportional rectangle on every included page. Full page removes the crop when applied. Starting another scan resets the prior edit-undo history.

## Paper sizes

Preferences contains A4 (default), A5, A6, Letter and Legal. Changing paper affects future scans, not captured pages. For the Brother MFC-L2700DW profile, width is limited to 211.881 mm and Legal cannot be scanned on the glass. Other drivers may impose additional limits.

## Recovery

Closing clears the workspace from the app, and the next launch starts empty. PDFs and original scan files are retained. Use **Open saved** to resume a project. Projects save automatically. Completed files from an interrupted scan are recovered when the project is reopened. An incomplete image is not counted as a finished page.

For a partial pass, remove already-scanned sheets from the input and continue with the remaining sheets in the same order. If you lose track of the backs, restart the entire back pass. Original files remain available through **Originals**.

## Storage

- Projects, raw scans, logs, and PDF previews: `~/Scans/Studio/`.
- Preferences and scanner profile: `$XDG_CONFIG_HOME/brother-scan-studio/`, defaulting to `~/.config/brother-scan-studio/`.
- Exported PDFs: the location chosen in Save PDF.

Clear/delete does not free the original files' disk space. Close a finished project and manage its folder yourself when you no longer need its originals.
