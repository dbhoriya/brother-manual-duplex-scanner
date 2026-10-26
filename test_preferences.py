import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from PyQt5.QtWidgets import QApplication
from preferences import PreferencesDialog, DEFAULTS, load_preferences, paper_dimensions

APP = QApplication.instance() or QApplication([])


class PreferencesTests(unittest.TestCase):
    def test_a4_default_and_brother_legal_limit(self):
        self.assertEqual(DEFAULTS["paper"], "A4")
        self.assertEqual(paper_dimensions("A4", True, True), (210, 297))
        with self.assertRaises(ValueError):
            paper_dimensions("Legal", True, True)
        self.assertEqual(paper_dimensions("Letter", False, True), (211.881, 279.4))

    def test_generic_paper_dimensions(self):
        self.assertEqual(paper_dimensions("A5", False), (148, 210))
        self.assertEqual(paper_dimensions("Letter", True), (215.9, 279.4))

    def test_preferences_roundtrip(self):
        with (
            tempfile.TemporaryDirectory() as folder,
            patch("preferences.CONFIG", Path(folder) / "preferences.json"),
        ):
            d = PreferencesDialog(None, dict(DEFAULTS))
            d.fields["theme"].setCurrentText("Dark")
            d.fields["paper"].setCurrentText("A5")
            d.save()
            values = load_preferences()
            self.assertEqual(values["theme"], "Dark")
            self.assertEqual(values["paper"], "A5")
            d.deleteLater()

    def test_bad_preferences_fall_back(self):
        with (
            tempfile.TemporaryDirectory() as folder,
            patch("preferences.CONFIG", Path(folder) / "preferences.json"),
        ):
            path = Path(folder) / "preferences.json"
            path.write_text("{bad")
            self.assertEqual(load_preferences(), DEFAULTS)
            path.write_text(
                json.dumps({"paper": "unknown", "speed": 999, "color": "no"})
            )
            self.assertEqual(load_preferences(), DEFAULTS)

    def test_reset_defaults(self):
        d = PreferencesDialog(None, dict(DEFAULTS, theme="Dark", paper="Letter"))
        d.reset()
        self.assertEqual(d.fields["theme"].currentText(), "Light")
        self.assertEqual(d.fields["paper"].currentText(), "A4")
        d.deleteLater()


if __name__ == "__main__":
    unittest.main(verbosity=2)
