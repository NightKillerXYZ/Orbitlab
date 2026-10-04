import tempfile
import unittest
from pathlib import Path

from orbitlab_simulation_engine import (
    GmatReportParser,
    TelemetryMissingError,
    TelemetryParseError,
    TelemetryValidationError,
)


HEADER = (
    "Sat.ElapsedSecs Sat.EarthMJ2000Eq.X Sat.EarthMJ2000Eq.Y "
    "Sat.EarthMJ2000Eq.Z Sat.EarthMJ2000Eq.VX Sat.EarthMJ2000Eq.VY "
    "Sat.EarthMJ2000Eq.VZ Sat.Earth.SMA Sat.Earth.ECC Sat.Earth.INC "
    "Sat.Earth.Altitude"
)


class TestGmatReportParser(unittest.TestCase):
    def setUp(self):
        self.parser = GmatReportParser()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.report = Path(self.temp_dir.name) / "telemetry.txt"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_parses_complete_whitespace_delimited_report(self):
        self.report.write_text(
            HEADER + "\n0 7000 0 0 0 7.5 0 7000 0.001 28.5 621.864\n",
            encoding="utf-8",
        )

        points = self.parser.parse(self.report)

        self.assertEqual(len(points), 1)
        self.assertEqual(points[0].x_km, 7000.0)
        self.assertEqual(points[0].inclination_deg, 28.5)

    def test_rejects_missing_inc_dependency(self):
        header_without_inc = HEADER.replace(" Sat.Earth.INC", "")
        self.report.write_text(
            header_without_inc + "\n0 7000 0 0 0 7.5 0 7000 0.001 621.864\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(TelemetryValidationError, "INC"):
            self.parser.parse(self.report)

    def test_rejects_invalid_numeric_data(self):
        self.report.write_text(
            HEADER + "\n0 not-a-number 0 0 0 7.5 0 7000 0.001 28.5 621.864\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(TelemetryParseError, "not numeric"):
            self.parser.parse(self.report)

    def test_rejects_non_finite_numeric_data(self):
        self.report.write_text(
            HEADER + "\n0 nan 0 0 0 7.5 0 7000 0.001 28.5 621.864\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(TelemetryValidationError, "not finite"):
            self.parser.parse(self.report)

    def test_rejects_structurally_incomplete_row(self):
        self.report.write_text(HEADER + "\n0 7000 0\n", encoding="utf-8")

        with self.assertRaisesRegex(TelemetryValidationError, "expected"):
            self.parser.parse(self.report)

    def test_rejects_missing_and_header_only_reports(self):
        with self.assertRaises(TelemetryMissingError):
            self.parser.parse(self.report)

        self.report.write_text(HEADER + "\n", encoding="utf-8")
        with self.assertRaisesRegex(TelemetryValidationError, "no data rows"):
            self.parser.parse(self.report)
