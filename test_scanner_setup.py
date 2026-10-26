import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import unittest, tempfile
from pathlib import Path
from unittest.mock import patch
from PyQt5.QtWidgets import QApplication
from scanner_setup import (
    ScannerSetup,
    PROFILES,
    scanner_options,
    option_values,
    load_scanner_config,
    device_ids,
)

APP = QApplication.instance() or QApplication([])


class SetupTests(unittest.TestCase):
    def test_brother_defaults(self):
        self.assertEqual(
            scanner_options({}, "brother4:test", False, False, 100),
            ("Automatic Document Feeder(centrally aligned)", "True Gray", 100),
        )

    def test_standard_profile_and_nearest_supported_dpi(self):
        c = dict(
            PROFILES["Standard SANE / AirScan"],
            device="airscan:test",
            dpi=[75, 150, 300],
        )
        self.assertEqual(
            scanner_options(c, "airscan:test", False, True, 100), ("ADF", "Color", 75)
        )

    def test_custom_requires_source(self):
        c = dict(PROFILES["Custom backend"], device="custom")
        with self.assertRaises(ValueError):
            scanner_options(c, "custom", False, False, 100)

    def test_option_parser_preserves_brother_brackets(self):
        data = "    --mode True Gray|24bit Color[Fast] [24bit Color[Fast]]\n    --source FlatBed|ADF [FlatBed]\n    --resolution 100|150|300dpi [150]"
        self.assertEqual(
            option_values(data, "mode"), ["True Gray", "24bit Color[Fast]"]
        )
        self.assertEqual(option_values(data, "resolution"), ["100", "150", "300dpi"])

    def test_device_id_parser(self):
        self.assertEqual(
            device_ids(
                "device `airscan:e0:Office' is a scanner\ndevice `brother4:usb' is a Brother scanner"
            ),
            ["airscan:e0:Office", "brother4:usb"],
        )

    def test_save_profile_and_reload(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch("scanner_setup.CONFIG", Path(directory) / "scanner.json"),
        ):
            d = ScannerSetup(devices=["airscan:test"])
            d.profile.setCurrentText("Standard SANE / AirScan")
            d.dpis.setText("75,150,300")
            d.save()
            c = load_scanner_config()
            self.assertEqual(c["device"], "airscan:test")
            self.assertEqual(c["gray"], "Gray")
            self.assertEqual(c["dpi"], [75, 150, 300])
            d.deleteLater()


if __name__ == "__main__":
    unittest.main(verbosity=2)
