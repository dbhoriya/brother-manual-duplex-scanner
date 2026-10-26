"""SANE scanner selection and editable backend profiles; never installs drivers."""

import copy
import os
import re
from pathlib import Path
from PyQt5.QtCore import QProcess, QTimer
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QLineEdit,
    QPlainTextEdit,
    QMessageBox,
)
from model import atomic_json

CONFIG = (
    Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    / "brother-scan-studio"
    / "scanner.json"
)
PROFILES = {
    "Brother brscan": {
        "flatbed": "FlatBed",
        "feeder": "Automatic Document Feeder(centrally aligned)",
        "gray": "True Gray",
        "color": "24bit Color[Fast]",
        "dpi": [100, 150, 200, 300, 400, 600],
    },
    "Standard SANE / AirScan": {
        "flatbed": "Flatbed",
        "feeder": "ADF",
        "gray": "Gray",
        "color": "Color",
        "dpi": [],
    },
    "Custom backend": {"flatbed": "", "feeder": "", "gray": "", "color": "", "dpi": []},
}


def load_scanner_config():
    import json

    try:
        value = json.loads(CONFIG.read_text())
        if not isinstance(value, dict) or not isinstance(value.get("device"), str):
            return {}
        for key in ["flatbed", "feeder", "gray", "color"]:
            if not isinstance(value.get(key), str):
                return {}
        if not isinstance(value.get("dpi", []), list) or any(
            not isinstance(x, int) or x < 1 for x in value.get("dpi", [])
        ):
            return {}
        return value
    except (OSError, ValueError):
        return {}


def scanner_options(config, device, glass, color, requested_dpi):
    profile = (
        config
        if config and config.get("device") == device
        else PROFILES["Brother brscan"]
    )
    source = profile["flatbed" if glass else "feeder"]
    mode = profile["color" if color else "gray"]
    if not source or not mode:
        raise ValueError(
            "Open Scanner setup and select a source and color mode supported by this driver."
        )
    choices = profile.get("dpi", [])
    dpi = (
        min(choices, key=lambda x: (abs(x - requested_dpi), x))
        if choices
        else requested_dpi
    )
    return source, mode, dpi


def device_ids(text):
    return re.findall(r"device `([^']+)'", text)


def option_values(text, option):
    for line in text.splitlines():
        match = re.match(r"\s*--" + re.escape(option) + r"\s+(.*)", line)
        if match:
            # Only strip the final default marker; preserve brackets inside mode names.
            value = re.sub(r"\s+\[[^\n]*\]\s*$", "", match.group(1)).strip()
            return [s.strip() for s in value.split("|")] if "|" in value else [value]
    return []


class ScannerSetup(QDialog):
    def __init__(self, parent=None, initial=None, devices=None):
        super().__init__(parent)
        self.setWindowTitle("Scanner & driver setup")
        self.resize(680, 670)
        self.result_config = None
        self.proc = None
        self.current = copy.deepcopy(initial or {})
        layout = QVBoxLayout(self)
        heading = QLabel("Select your scanner")
        heading.setStyleSheet("font-size:20px;font-weight:600;")
        layout.addWidget(heading)
        note = QLabel(
            "A profile supplies scan settings. The SANE driver must already be installed on this computer."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        row = QHBoxLayout()
        self.device = QComboBox()
        self.device.setEditable(True)
        self.device.addItems(devices or [])
        self.device.setEditText(self.current.get("device", (devices or [""])[0]))
        row.addWidget(self.device, 1)
        self.refresh = QPushButton("Find scanners")
        self.refresh.clicked.connect(self.discover)
        row.addWidget(self.refresh)
        layout.addLayout(row)
        layout.addWidget(
            QLabel(
                "You may also paste an exact SANE device ID, for example a network backend address."
            )
        )
        self.profile = QComboBox()
        self.profile.addItems(PROFILES)
        self.profile.setCurrentText(self.current.get("profile", "Brother brscan"))
        layout.addWidget(self.profile)
        form = QFormLayout()
        self.fields = {}
        for key, title in [
            ("flatbed", "Glass source"),
            ("feeder", "Feeder source"),
            ("gray", "Grayscale mode"),
            ("color", "Color mode"),
        ]:
            field = QComboBox()
            field.setEditable(True)
            self.fields[key] = field
            form.addRow(title, field)
        self.dpis = QLineEdit()
        self.dpis.setPlaceholderText(
            "Optional: 75, 150, 300 (leave empty to request preset DPI)"
        )
        form.addRow("Supported DPI", self.dpis)
        layout.addLayout(form)
        self.read = QPushButton("Read options from this driver")
        self.read.clicked.connect(self.probe)
        layout.addWidget(self.read)
        self.status = QLabel("Choose a scanner and a profile, then save.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(145)
        layout.addWidget(self.log)
        links = QLabel(
            '<b>Scanner missing?</b> Install sane-utils and your scanner backend, then Find scanners again.<br><a href="https://www.sane-project.org/sane-supported-devices.html">SANE supported devices</a> · <a href="https://support.brother.com/g/b/productsearch.aspx?c=us&lang=en">Brother drivers</a> · <a href="https://github.com/alexpevzner/sane-airscan">AirScan / WSD setup</a>'
        )
        links.setWordWrap(True)
        links.setOpenExternalLinks(True)
        layout.addWidget(links)
        buttons = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        buttons.addStretch()
        self.save_button = QPushButton("Use this scanner")
        self.save_button.setObjectName("primary")
        self.save_button.clicked.connect(self.save)
        buttons.addWidget(self.save_button)
        layout.addLayout(buttons)
        self.profile.currentTextChanged.connect(self.apply_profile)
        self.apply_profile(self.profile.currentText())
        if self.current:
            for key, field in self.fields.items():
                field.setEditText(self.current.get(key, ""))
            self.dpis.setText(", ".join(map(str, self.current.get("dpi", []))))

    def apply_profile(self, name):
        data = PROFILES[name]
        for key, field in self.fields.items():
            field.clear()
            field.addItem(data[key])
        self.dpis.setText(", ".join(map(str, data["dpi"])))

    def run(self, args, kind):
        if self.proc and self.proc.state() != QProcess.NotRunning:
            return
        self.kind = kind
        self.proc = QProcess(self)
        self.proc.finished.connect(self.finished)
        self.proc.errorOccurred.connect(self.failed)
        self.refresh.setEnabled(False)
        self.read.setEnabled(False)
        self.save_button.setEnabled(False)
        self.status.setText("Checking… No scan will be taken.")
        self.proc.start("scanimage", args)
        process = self.proc
        QTimer.singleShot(
            30000,
            lambda: process.kill() if process.state() != QProcess.NotRunning else None,
        )

    def discover(self):
        self.run(["-L"], "devices")

    def probe(self):
        device = self.device.currentText().strip()
        if not device:
            self.status.setText("Select a scanner or enter its device ID first.")
            return
        self.run(["-d", device, "--all-options"], "options")

    def failed(self, error):
        if error == QProcess.FailedToStart:
            self.enable()
            self.status.setText(
                "scanimage is missing. Install sane-utils, then try again."
            )

    def enable(self):
        for w in [self.refresh, self.read, self.save_button]:
            w.setEnabled(True)

    def finished(self, code, *args):
        output = bytes(self.proc.readAllStandardOutput()).decode(errors="replace")
        errors = bytes(self.proc.readAllStandardError()).decode(errors="replace")
        self.log.setPlainText(output + errors)
        self.enable()
        if code:
            self.status.setText(
                "The driver could not be read. Check installation, connection, device ID and permissions."
            )
            return
        if self.kind == "devices":
            ids = device_ids(output)
            previous = self.device.currentText()
            self.device.clear()
            self.device.addItems(ids)
            if previous in ids:
                self.device.setCurrentText(previous)
            elif not ids:
                self.device.setEditText(previous)
            self.status.setText(
                f"{len(ids)} scanner(s) found."
                if ids
                else "No scanner found. Install the correct driver/backend and check USB or network connectivity."
            )
        else:
            for option, keys in [
                ("source", ["flatbed", "feeder"]),
                ("mode", ["gray", "color"]),
            ]:
                values = option_values(output, option)
                if values and ".." not in values[0]:
                    for key in keys:
                        field = self.fields[key]
                        previous = field.currentText()
                        field.clear()
                        field.addItems(values)
                        candidate = next(
                            (
                                v
                                for v in values
                                if (
                                    ("flat" in v.lower() or "glass" in v.lower())
                                    if key == "flatbed"
                                    else (
                                        ("adf" in v.lower() or "feeder" in v.lower())
                                        if key == "feeder"
                                        else (
                                            ("gray" in v.lower() or "grey" in v.lower())
                                            if key == "gray"
                                            else (
                                                "color" in v.lower()
                                                or "colour" in v.lower()
                                            )
                                        )
                                    )
                                )
                            ),
                            previous,
                        )
                        field.setEditText(candidate)
            values = option_values(output, "resolution")
            if values and all(re.fullmatch(r"\d+(?:dpi)?", v) for v in values):
                self.dpis.setText(", ".join(re.sub("dpi$", "", v) for v in values))
            self.status.setText(
                "Options loaded. Check the source and color selections before saving. A missing feeder option means the driver may not support it."
            )

    def save(self):
        device = self.device.currentText().strip()
        if not device:
            self.status.setText("Select a scanner or enter a device ID.")
            return
        try:
            dpis = [int(x.strip()) for x in self.dpis.text().split(",") if x.strip()]
            if any(x < 1 or x > 19200 for x in dpis):
                raise ValueError()
        except ValueError:
            self.status.setText("Use positive DPI values separated by commas.")
            return
        data = {
            "device": device,
            "profile": self.profile.currentText(),
            "dpi": sorted(set(dpis)),
            **{key: w.currentText().strip() for key, w in self.fields.items()},
        }
        try:
            CONFIG.parent.mkdir(parents=True, exist_ok=True)
            atomic_json(CONFIG, data)
        except OSError as e:
            QMessageBox.warning(self, "Cannot save scanner settings", str(e))
            return
        self.result_config = data
        self.accept()

    def done(self, result):
        if self.proc and self.proc.state() != QProcess.NotRunning:
            self.proc.kill()
            self.proc.waitForFinished(1000)
        super().done(result)
