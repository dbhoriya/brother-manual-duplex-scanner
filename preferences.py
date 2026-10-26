"""Small local preferences dialog; no scan ranges or page-selection controls."""

import copy, json, os
from pathlib import Path
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QComboBox,
    QCheckBox,
    QPushButton,
    QHBoxLayout,
    QLabel,
    QMessageBox,
)
from model import atomic_json

CONFIG = (
    Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    / "brother-scan-studio"
    / "preferences.json"
)
PAPERS = {
    "A4": (210, 297),
    "A5": (148, 210),
    "A6": (105, 148),
    "Letter": (215.9, 279.4),
    "Legal": (215.9, 355.6),
}
DEFAULTS = {
    "paper": "A4",
    "theme": "Light",
    "source": 0,
    "speed": 0,
    "color": False,
    "pdf_quality": 1,
    "thumbnail": "Medium",
    "open_pdf": False,
}


def load_preferences():
    values = copy.deepcopy(DEFAULTS)
    try:
        data = json.loads(CONFIG.read_text())
        if not isinstance(data, dict):
            return values
        for key, allowed in [
            ("paper", PAPERS),
            ("theme", ["Light", "Dark"]),
            ("thumbnail", ["Small", "Medium", "Large"]),
            ("source", range(2)),
            ("speed", range(4)),
            ("pdf_quality", range(3)),
        ]:
            if data.get(key) in allowed:
                values[key] = data[key]
        for key in ["color", "open_pdf"]:
            if isinstance(data.get(key), bool):
                values[key] = data[key]
    except (OSError, ValueError, TypeError):
        pass
    return values


def paper_dimensions(name, glass, brother=False):
    width, height = PAPERS.get(name, PAPERS["A4"])
    if brother:
        if glass and height > 297:
            raise ValueError(
                "Legal paper is too long for this Brother glass. Select the feeder or choose a smaller paper size in Preferences."
            )
        width = min(width, 211.881)
    return width, height


class PreferencesDialog(QDialog):
    def __init__(self, parent, values):
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.resize(460, 420)
        self.values = copy.deepcopy(values)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)
        self.fields = {}
        choices = {
            "paper": list(PAPERS),
            "theme": ["Light", "Dark"],
            "source": ["Whole feeder stack", "Glass"],
            "speed": [
                "Fastest · 100 DPI",
                "Balanced · 150 DPI",
                "High detail · 300 DPI",
                "Maximum detail · 600 DPI",
            ],
            "pdf_quality": ["Small file", "Balanced", "Best quality"],
            "thumbnail": ["Small", "Medium", "Large"],
        }
        titles = {
            "paper": "Paper size",
            "theme": "Theme",
            "source": "Default source",
            "speed": "Default scan speed",
            "pdf_quality": "PDF quality",
            "thumbnail": "Preview thumbnails",
        }
        for key, options in choices.items():
            widget = QComboBox()
            widget.addItems(options)
            if key in ["source", "speed", "pdf_quality"]:
                widget.setCurrentIndex(values[key])
            else:
                widget.setCurrentText(values[key])
            form.addRow(titles[key], widget)
            self.fields[key] = widget
        for key, text in [
            ("color", "Scan in color by default"),
            ("open_pdf", "Open PDF after saving"),
        ]:
            w = QCheckBox(text)
            w.setChecked(values[key])
            form.addRow(w)
            self.fields[key] = w
        note = QLabel(
            "These settings apply now and become defaults for new documents. Existing scans keep their original size and quality. A4 is the default."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        caution = QLabel(
            "Brother MFC-L2700DW: Letter/Legal capture is limited to 211.9 mm width. Legal requires the feeder."
        )
        caution.setWordWrap(True)
        layout.addWidget(caution)
        row = QHBoxLayout()
        defaults = QPushButton("Reset defaults")
        defaults.clicked.connect(self.reset)
        row.addWidget(defaults)
        row.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        row.addWidget(cancel)
        save = QPushButton("Apply")
        save.setObjectName("primary")
        save.clicked.connect(self.save)
        row.addWidget(save)
        layout.addLayout(row)

    def reset(self):
        for key, w in self.fields.items():
            value = DEFAULTS[key]
            if isinstance(w, QCheckBox):
                w.setChecked(value)
            elif isinstance(value, int):
                w.setCurrentIndex(value)
            else:
                w.setCurrentText(value)

    def save(self):
        for key, w in self.fields.items():
            self.values[key] = (
                w.isChecked()
                if isinstance(w, QCheckBox)
                else (
                    w.currentIndex()
                    if key in ["source", "speed", "pdf_quality"]
                    else w.currentText()
                )
            )
        try:
            CONFIG.parent.mkdir(parents=True, exist_ok=True)
            atomic_json(CONFIG, self.values)
        except OSError as e:
            QMessageBox.warning(self, "Cannot save preferences", str(e))
            return
        self.accept()
