"""Strict parser for whitespace-delimited GMAT ReportFile telemetry."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Sequence, Tuple

from .errors import TelemetryMissingError, TelemetryParseError, TelemetryValidationError
from .models import TrajectoryPoint


_REQUIRED_FIELDS = (
    "ElapsedSecs",
    "X",
    "Y",
    "Z",
    "VX",
    "VY",
    "VZ",
    "SMA",
    "ECC",
    "INC",
    "Altitude",
)


class GmatReportParser:
    """Parse the baseline OrbitLab ReportFile contract without row recovery."""

    required_fields: Sequence[str] = _REQUIRED_FIELDS

    def parse(self, report_path: Path | str) -> Tuple[TrajectoryPoint, ...]:
        path = Path(report_path)
        if not path.is_file():
            raise TelemetryMissingError(f"GMAT telemetry file was not produced: {path}")

        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError) as exc:
            raise TelemetryParseError(f"Unable to read GMAT telemetry file: {path}") from exc

        nonempty = [(number, line.strip()) for number, line in enumerate(lines, 1) if line.strip()]
        if not nonempty:
            raise TelemetryValidationError("GMAT telemetry file is empty")

        _, header_line = nonempty[0]
        headers = header_line.split()
        indexes = self._map_headers(headers)
        points: list[TrajectoryPoint] = []

        for line_number, line in nonempty[1:]:
            fields = line.split()
            if len(fields) != len(headers):
                raise TelemetryValidationError(
                    f"Telemetry row {line_number} has {len(fields)} fields; expected {len(headers)}"
                )
            values = self._parse_numeric_row(fields, indexes, line_number)
            points.append(TrajectoryPoint(*values))

        if not points:
            raise TelemetryValidationError("GMAT telemetry contains a header but no data rows")
        return tuple(points)

    def _map_headers(self, headers: Sequence[str]) -> dict[str, int]:
        indexes: dict[str, int] = {}
        for required in self.required_fields:
            matches = [
                index
                for index, header in enumerate(headers)
                if header == required or header.rsplit(".", 1)[-1] == required
            ]
            if not matches:
                raise TelemetryValidationError(
                    f"Telemetry is missing required column: {required}"
                )
            if len(matches) > 1:
                raise TelemetryValidationError(
                    f"Telemetry column is ambiguous: {required}"
                )
            indexes[required] = matches[0]
        return indexes

    def _parse_numeric_row(
        self,
        fields: Sequence[str],
        indexes: dict[str, int],
        line_number: int,
    ) -> Tuple[float, ...]:
        values: list[float] = []
        for field in self.required_fields:
            raw = fields[indexes[field]]
            try:
                value = float(raw)
            except ValueError as exc:
                raise TelemetryParseError(
                    f"Telemetry row {line_number}, column {field} is not numeric: {raw!r}"
                ) from exc
            if not math.isfinite(value):
                raise TelemetryValidationError(
                    f"Telemetry row {line_number}, column {field} is not finite"
                )
            values.append(value)
        return tuple(values)
