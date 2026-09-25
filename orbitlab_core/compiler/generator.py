"""Deterministic GMAT Script Compiler for OrbitLab.

Translates high-level OrbitLabExperiment AST into fully validated,
parameterized, deterministic NASA GMAT scripts.

Architectural Rule:
The AI never generates raw GMAT script code directly. The generator utilizes
deterministic templates and parameterized procedural builders.
Strict forward-slash path normalization is enforced on all output paths.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import List, Optional

from orbitlab_core.ast.models import (
    CartesianElements,
    KeplerianElements,
    OrbitLabExperiment,
)
from orbitlab_core.compiler.templates import (
    compute_hohmann_delta_v,
    compute_keplerian_period_seconds,
    normalize_gmat_path,
)
from orbitlab_core.constants import EARTH_MU_KM3_S2


class GmatScriptCompiler:
    """Compiles OrbitLabExperiment AST instances into sanitized, deterministic GMAT scripts."""

    def __init__(self, default_report_filename: str = "telemetry.txt"):
        self.default_report_filename = default_report_filename

    def compile_to_string(
        self,
        experiment: OrbitLabExperiment,
        telemetry_filepath: Optional[str] = None
    ) -> str:
        """Compile an OrbitLabExperiment AST into a GMAT script string.

        Args:
            experiment: The validated OrbitLabExperiment instance.
            telemetry_filepath: Optional custom path for the generated ReportFile telemetry.
                                If None, defaults to self.default_report_filename.

        Returns:
            A string containing the valid, formatted GMAT script.
        """
        report_path = telemetry_filepath if telemetry_filepath else self.default_report_filename
        norm_report_path = normalize_gmat_path(report_path)

        lines: List[str] = []

        # 1. Header
        lines.append("%" + "=" * 78)
        lines.append(f"% OrbitLab Automated GMAT Script")
        lines.append(f"% Experiment: {experiment.experimentName}")
        if experiment.description:
            lines.append(f"% Description: {experiment.description}")
        lines.append("%" + "=" * 78)
        lines.append("")

        sc_name = experiment.spacecraft.name
        central_body = experiment.centralBody

        # 2. Spacecraft Definition
        lines.append("%" + "-" * 40)
        lines.append("%---------- Spacecraft Configuration")
        lines.append("%" + "-" * 40)
        lines.append(f"Create Spacecraft {sc_name};")
        lines.append("")
        lines.append(f"{sc_name}.DateFormat = {experiment.epoch.format};")
        lines.append(f"{sc_name}.Epoch = '{experiment.epoch.value}';")
        lines.append(f"{sc_name}.CoordinateSystem = {experiment.initialOrbit.coordinateSystem};")

        orbit = experiment.initialOrbit
        if orbit.type == "Keplerian":
            elems: KeplerianElements = orbit.elements  # type: ignore
            lines.append(f"{sc_name}.DisplayStateType = Keplerian;")
            lines.append(f"{sc_name}.SMA = {elems.semiMajorAxisKm:.6f};")
            lines.append(f"{sc_name}.ECC = {elems.eccentricity:.6f};")
            lines.append(f"{sc_name}.INC = {elems.inclinationDeg:.6f};")
            lines.append(f"{sc_name}.RAAN = {elems.raanDeg:.6f};")
            lines.append(f"{sc_name}.AOP = {elems.argumentOfPeriapsisDeg:.6f};")
            lines.append(f"{sc_name}.TA = {elems.trueAnomalyDeg:.6f};")
        elif orbit.type == "Cartesian":
            c_elems: CartesianElements = orbit.elements  # type: ignore
            lines.append(f"{sc_name}.DisplayStateType = Cartesian;")
            lines.append(f"{sc_name}.X = {c_elems.xKm:.6f};")
            lines.append(f"{sc_name}.Y = {c_elems.yKm:.6f};")
            lines.append(f"{sc_name}.Z = {c_elems.zKm:.6f};")
            lines.append(f"{sc_name}.VX = {c_elems.vxKmS:.8f};")
            lines.append(f"{sc_name}.VY = {c_elems.vyKmS:.8f};")
            lines.append(f"{sc_name}.VZ = {c_elems.vzKmS:.8f};")

        # Mass and aerodynamic properties
        sc = experiment.spacecraft
        lines.append(f"{sc_name}.DryMass = {sc.dryMassKg:.2f};")
        lines.append(f"{sc_name}.Cd = {sc.coefficientOfDrag:.4f};")
        lines.append(f"{sc_name}.DragArea = {sc.dragAreaM2:.4f};")
        lines.append(f"{sc_name}.Cr = {sc.coefficientOfReflectivity:.4f};")
        lines.append(f"{sc_name}.SRPArea = {sc.srpAreaM2:.4f};")
        lines.append("")

        # 3. Force Model Configuration
        fm_name = "OrbitLabForceModel"
        fm = experiment.forceModel
        lines.append("%" + "-" * 40)
        lines.append("%---------- Force Model Configuration")
        lines.append("%" + "-" * 40)
        lines.append(f"Create ForceModel {fm_name};")
        lines.append("")
        lines.append(f"{fm_name}.CentralBody = {central_body};")
        lines.append(f"{fm_name}.PrimaryBodies = {{{central_body}}};")

        if central_body == "Earth":
            lines.append(f"{fm_name}.GravityField.Earth.Degree = {fm.gravityDegree};")
            lines.append(f"{fm_name}.GravityField.Earth.Order = {fm.gravityOrder};")

        if fm.pointMasses:
            pm_str = ", ".join(fm.pointMasses)
            lines.append(f"{fm_name}.PointMasses = {{{pm_str}}};")

        if fm.atmosphericDrag.enabled and central_body == "Earth":
            lines.append(f"{fm_name}.Drag.AtmosphereModel = {fm.atmosphericDrag.model};")

        srp_val = "On" if fm.solarRadiationPressure else "Off"
        lines.append(f"{fm_name}.SRP = {srp_val};")
        lines.append("")

        # 4. Propagator Configuration
        prop_name = "OrbitLabPropagator"
        prop = experiment.propagation
        lines.append("%" + "-" * 40)
        lines.append("%---------- Propagator Configuration")
        lines.append("%" + "-" * 40)
        lines.append(f"Create Propagator {prop_name};")
        lines.append(f"{prop_name}.FM = {fm_name};")
        # GMAT requires Type before InitialStepSize
        lines.append(f"{prop_name}.Type = {prop.integrator};")
        lines.append(f"{prop_name}.InitialStepSize = {prop.stepSizeSecs:.2f};")
        lines.append("")

        # 5. Maneuvers / Burns Configuration
        lines.append("%" + "-" * 40)
        lines.append("%---------- Maneuvers & Impulsive Burns")
        lines.append("%" + "-" * 40)
        hohmann_transfers = []
        for m in experiment.maneuvers:
            if m.type == "ImpulsiveBurn" and m.burnVector:
                burn_name = f"Burn_{m.id}"
                bv = m.burnVector.deltaVVectorKmS
                lines.append(f"Create ImpulsiveBurn {burn_name};")
                lines.append(f"{burn_name}.CoordinateSystem = Local;")
                lines.append(f"{burn_name}.Origin = {central_body};")
                lines.append(f"{burn_name}.Axes = VNB;")
                lines.append(f"{burn_name}.Element1 = {bv[0]:.6f};")
                lines.append(f"{burn_name}.Element2 = {bv[1]:.6f};")
                lines.append(f"{burn_name}.Element3 = {bv[2]:.6f};")
                lines.append(f"{burn_name}.DecrementMass = false;")
                lines.append("")
            elif m.type == "TargetedHohmannTransfer" and m.targetObjectives:
                hohmann_transfers.append(m)
                # Compute analytical Delta-Vs
                r1 = orbit.elements.semiMajorAxisKm if orbit.type == "Keplerian" else math.sqrt(orbit.elements.xKm**2 + orbit.elements.yKm**2 + orbit.elements.zKm**2)  # type: ignore
                r2 = m.targetObjectives.targetOrbitRadiusKm or (r1 + 1000.0)
                dv1, dv2 = compute_hohmann_delta_v(r1, r2, EARTH_MU_KM3_S2)

                burn1_name = f"Burn_{m.id}_Insertion"
                burn2_name = f"Burn_{m.id}_Circularize"

                lines.append(f"Create ImpulsiveBurn {burn1_name};")
                lines.append(f"{burn1_name}.CoordinateSystem = Local;")
                lines.append(f"{burn1_name}.Origin = {central_body};")
                lines.append(f"{burn1_name}.Axes = VNB;")
                lines.append(f"{burn1_name}.Element1 = {dv1:.6f};")
                lines.append(f"{burn1_name}.Element2 = 0.0;")
                lines.append(f"{burn1_name}.Element3 = 0.0;")
                lines.append(f"{burn1_name}.DecrementMass = false;")
                lines.append("")

                lines.append(f"Create ImpulsiveBurn {burn2_name};")
                lines.append(f"{burn2_name}.CoordinateSystem = Local;")
                lines.append(f"{burn2_name}.Origin = {central_body};")
                lines.append(f"{burn2_name}.Axes = VNB;")
                lines.append(f"{burn2_name}.Element1 = {dv2:.6f};")
                lines.append(f"{burn2_name}.Element2 = 0.0;")
                lines.append(f"{burn2_name}.Element3 = 0.0;")
                lines.append(f"{burn2_name}.DecrementMass = false;")
                lines.append("")

        # 6. Subscribers & Telemetry Output
        report_name = "OrbitLabReport"
        lines.append("%" + "-" * 40)
        lines.append("%---------- Telemetry Subscriber")
        lines.append("%" + "-" * 40)
        lines.append(f"Create ReportFile {report_name};")
        lines.append(f"{report_name}.Filename = '{norm_report_path}';")
        lines.append(f"{report_name}.Precision = 8;")
        lines.append(f"{report_name}.WriteHeaders = true;")
        lines.append(
            f"{report_name}.Add = {{"
            f"{sc_name}.ElapsedSecs, "
            f"{sc_name}.EarthMJ2000Eq.X, {sc_name}.EarthMJ2000Eq.Y, {sc_name}.EarthMJ2000Eq.Z, "
            f"{sc_name}.EarthMJ2000Eq.VX, {sc_name}.EarthMJ2000Eq.VY, {sc_name}.EarthMJ2000Eq.VZ, "
            f"{sc_name}.Earth.SMA, {sc_name}.Earth.ECC, {sc_name}.Earth.Altitude"
            f"}};"
        )
        lines.append("")

        # 7. Mission Sequence
        lines.append("%" + "-" * 40)
        lines.append("%---------- Mission Sequence")
        lines.append("%" + "-" * 40)
        lines.append("BeginMissionSequence;")
        lines.append("")

        # Propagate maneuvers
        for m in experiment.maneuvers:
            if m.type == "ImpulsiveBurn":
                burn_name = f"Burn_{m.id}"
                # Trigger propagation
                if m.trigger.condition == "AtPeriapsis":
                    lines.append(f"Propagate 'Prop to Periapsis' {prop_name}({sc_name}) {{{sc_name}.Earth.Periapsis}};")
                elif m.trigger.condition == "AtApoapsis":
                    lines.append(f"Propagate 'Prop to Apoapsis' {prop_name}({sc_name}) {{{sc_name}.Earth.Apoapsis}};")
                elif m.trigger.condition == "ElapsedTimeSecs":
                    el_s = m.trigger.elapsedSecs or 0.0
                    lines.append(f"Propagate 'Prop to Maneuver Epoch' {prop_name}({sc_name}) {{{sc_name}.ElapsedSecs = {el_s:.2f}}};")

                # Apply burn
                lines.append(f"Maneuver 'Apply {m.id}' {burn_name}({sc_name});")
                lines.append("")

            elif m.type == "TargetedHohmannTransfer":
                burn1_name = f"Burn_{m.id}_Insertion"
                burn2_name = f"Burn_{m.id}_Circularize"

                # Hohmann step 1: Propagate to insertion point (periapsis)
                if m.trigger.condition == "AtApoapsis":
                    lines.append(f"Propagate 'Prop to Apoapsis' {prop_name}({sc_name}) {{{sc_name}.Earth.Apoapsis}};")
                else:
                    lines.append(f"Propagate 'Prop to Periapsis' {prop_name}({sc_name}) {{{sc_name}.Earth.Periapsis}};")

                lines.append(f"Maneuver 'Hohmann Insertion Burn' {burn1_name}({sc_name});")
                # Hohmann step 2: Propagate transfer ellipse to Apoapsis
                lines.append(f"Propagate 'Prop to Hohmann Apoapsis' {prop_name}({sc_name}) {{{sc_name}.Earth.Apoapsis}};")
                lines.append(f"Maneuver 'Hohmann Circularize Burn' {burn2_name}({sc_name});")
                lines.append("")

        # Final mission propagation stop condition
        stop = experiment.propagation.stopCondition
        if stop.type == "ElapsedDays":
            lines.append(f"Propagate 'Mission Propagation' {prop_name}({sc_name}) {{{sc_name}.ElapsedDays = {stop.value:.4f}}};")
        elif stop.type == "ElapsedHours":
            total_secs = stop.value * 3600.0
            lines.append(f"Propagate 'Mission Propagation' {prop_name}({sc_name}) {{{sc_name}.ElapsedSecs = {total_secs:.2f}}};")
        elif stop.type == "ElapsedSeconds":
            lines.append(f"Propagate 'Mission Propagation' {prop_name}({sc_name}) {{{sc_name}.ElapsedSecs = {stop.value:.2f}}};")
        elif stop.type == "OrbitPeriods":
            # Calculate orbital period for Keplerian orbit or derive from SMA
            if orbit.type == "Keplerian":
                a_km = orbit.elements.semiMajorAxisKm  # type: ignore
            else:
                r_mag = math.sqrt(orbit.elements.xKm**2 + orbit.elements.yKm**2 + orbit.elements.zKm**2)  # type: ignore
                v_mag2 = orbit.elements.vxKmS**2 + orbit.elements.vyKmS**2 + orbit.elements.vzKmS**2  # type: ignore
                energy = (v_mag2 / 2.0) - (EARTH_MU_KM3_S2 / r_mag)
                a_km = -EARTH_MU_KM3_S2 / (2.0 * energy) if abs(energy) > 1e-12 else r_mag

            period_s = compute_keplerian_period_seconds(a_km, EARTH_MU_KM3_S2)
            total_duration_s = stop.value * period_s
            lines.append(f"Propagate 'Mission Propagation' {prop_name}({sc_name}) {{{sc_name}.ElapsedSecs = {total_duration_s:.2f}}};")

        lines.append("")
        return "\n".join(lines)

    def compile_to_file(
        self,
        experiment: OrbitLabExperiment,
        output_script_path: str,
        telemetry_filepath: Optional[str] = None
    ) -> Path:
        """Compile AST to a script file on disk.

        Args:
            experiment: The validated OrbitLabExperiment instance.
            output_script_path: File system path where the .script will be written.
            telemetry_filepath: Optional path where the telemetry report will be generated.

        Returns:
            Path object of the written script file.
        """
        script_content = self.compile_to_string(experiment, telemetry_filepath=telemetry_filepath)
        out_path = Path(output_script_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(script_content, encoding="utf-8")
        return out_path
