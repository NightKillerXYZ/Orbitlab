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
from orbitlab_core.ast.validation import (
    compute_orbital_properties_from_cartesian,
    get_body_constants,
)
from orbitlab_core.constants import CENTRAL_BODY_PROPERTIES


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
        body_radius_km, body_mu_km3_s2 = get_body_constants(central_body)
        gmat_body, _ = CENTRAL_BODY_PROPERTIES[central_body][2:]
        coordinate_system = experiment.initialOrbit.coordinateSystem

        # 2. Spacecraft Definition
        lines.append("%" + "-" * 40)
        lines.append("%---------- Spacecraft Configuration")
        lines.append("%" + "-" * 40)
        if central_body != "Earth":
            lines.append(f"Create CoordinateSystem {coordinate_system};")
            lines.append(f"{coordinate_system}.Origin = {gmat_body};")
            lines.append(f"{coordinate_system}.Axes = MJ2000Eq;")
            lines.append("")

        lines.append(f"Create Spacecraft {sc_name};")
        lines.append("")

        lines.append(f"{sc_name}.DateFormat = {experiment.epoch.format};")
        lines.append(f"{sc_name}.Epoch = '{experiment.epoch.value}';")
        lines.append(f"{sc_name}.CoordinateSystem = {coordinate_system};")

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
        lines.append(f"{fm_name}.CentralBody = {gmat_body};")
        lines.append(f"{fm_name}.PrimaryBodies = {{{gmat_body}}};")
        if central_body == "Mars":
            lines.append(f"{fm_name}.GravityField.{gmat_body}.PotentialFile = Mars50c.cof;")
        elif central_body == "Moon":
            lines.append(f"{fm_name}.GravityField.{gmat_body}.PotentialFile = LP165P.cof;")
        lines.append(f"{fm_name}.GravityField.{gmat_body}.Degree = {fm.gravityDegree};")
        lines.append(f"{fm_name}.GravityField.{gmat_body}.Order = {fm.gravityOrder};")

        point_masses = [body for body in fm.pointMasses if body != gmat_body]
        if point_masses:
            pm_str = ", ".join(point_masses)
            lines.append(f"{fm_name}.PointMasses = {{{pm_str}}};")

        if fm.atmosphericDrag.enabled:
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
        hohmann_transfers = {}
        for m in experiment.maneuvers:
            if m.type == "ImpulsiveBurn" and m.burnVector:
                burn_name = f"Burn_{m.id}"
                bv = m.burnVector.deltaVVectorKmS
                lines.append(f"Create ImpulsiveBurn {burn_name};")
                lines.append(f"{burn_name}.CoordinateSystem = Local;")
                lines.append(f"{burn_name}.Origin = {gmat_body};")
                lines.append(f"{burn_name}.Axes = VNB;")
                lines.append(f"{burn_name}.Element1 = {bv[0]:.6f};")
                lines.append(f"{burn_name}.Element2 = {bv[1]:.6f};")
                lines.append(f"{burn_name}.Element3 = {bv[2]:.6f};")
                lines.append(f"{burn_name}.DecrementMass = false;")
                lines.append("")
            elif m.type == "TargetedHohmannTransfer" and m.targetObjectives:
                # Compute analytical Delta-Vs
                if m.targetObjectives.targetOrbitRadiusKm is None:
                    raise ValueError(f"TargetedHohmannTransfer '{m.id}' requires targetOrbitRadiusKm")
                if orbit.type == "Keplerian":
                    elements: KeplerianElements = orbit.elements  # type: ignore
                    r1 = (
                        elements.semiMajorAxisKm * (1.0 - elements.eccentricity)
                        if m.trigger.condition == "AtPeriapsis"
                        else elements.semiMajorAxisKm * (1.0 + elements.eccentricity)
                    )
                    source_semi_major_axis = elements.semiMajorAxisKm
                else:
                    cartesian: CartesianElements = orbit.elements  # type: ignore
                    properties = compute_orbital_properties_from_cartesian(
                        cartesian,
                        body_radius_km,
                        body_mu_km3_s2,
                    )
                    if not properties.is_bound:
                        raise ValueError("TargetedHohmannTransfer requires a bound initial orbit")
                    source_semi_major_axis = properties.semi_major_axis_km
                    r1 = (
                        properties.periapsis_radius_km
                        if m.trigger.condition == "AtPeriapsis"
                        else properties.apoapsis_radius_km
                    )
                r2 = m.targetObjectives.targetOrbitRadiusKm
                if r2 is None:
                    raise ValueError(f"TargetedHohmannTransfer '{m.id}' requires targetOrbitRadiusKm")
                if math.isclose(r1, r2, rel_tol=1e-12):
                    raise ValueError(
                        f"TargetedHohmannTransfer '{m.id}' target radius must differ from the burn radius"
                    )
                initial_velocity = math.sqrt(body_mu_km3_s2 * (2.0 / r1 - 1.0 / source_semi_major_axis))
                target_eccentricity = m.targetObjectives.targetEccentricity or 0.0
                dv1, dv2 = compute_hohmann_delta_v(
                    r1,
                    r2,
                    body_mu_km3_s2,
                    initial_velocity_km_s=initial_velocity,
                    target_eccentricity=target_eccentricity,
                )
                hohmann_transfers[m.id] = "Apoapsis" if r2 > r1 else "Periapsis"

                burn1_name = f"Burn_{m.id}_Insertion"
                burn2_name = f"Burn_{m.id}_TargetInsertion"

                lines.append(f"Create ImpulsiveBurn {burn1_name};")
                lines.append(f"{burn1_name}.CoordinateSystem = Local;")
                lines.append(f"{burn1_name}.Origin = {gmat_body};")
                lines.append(f"{burn1_name}.Axes = VNB;")
                lines.append(f"{burn1_name}.Element1 = {dv1:.6f};")
                lines.append(f"{burn1_name}.Element2 = 0.0;")
                lines.append(f"{burn1_name}.Element3 = 0.0;")
                lines.append(f"{burn1_name}.DecrementMass = false;")
                lines.append("")

                lines.append(f"Create ImpulsiveBurn {burn2_name};")
                lines.append(f"{burn2_name}.CoordinateSystem = Local;")
                lines.append(f"{burn2_name}.Origin = {gmat_body};")
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
            f"{sc_name}.{coordinate_system}.X, {sc_name}.{coordinate_system}.Y, {sc_name}.{coordinate_system}.Z, "
            f"{sc_name}.{coordinate_system}.VX, {sc_name}.{coordinate_system}.VY, {sc_name}.{coordinate_system}.VZ, "
            f"{sc_name}.{gmat_body}.SMA, {sc_name}.{gmat_body}.ECC, {sc_name}.INC, {sc_name}.{gmat_body}.Altitude"
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
                    lines.append(f"Propagate 'Prop to Periapsis' {prop_name}({sc_name}) {{{sc_name}.{gmat_body}.Periapsis}};")
                elif m.trigger.condition == "AtApoapsis":
                    lines.append(f"Propagate 'Prop to Apoapsis' {prop_name}({sc_name}) {{{sc_name}.{gmat_body}.Apoapsis}};")
                elif m.trigger.condition == "ElapsedTimeSecs":
                    el_s = m.trigger.elapsedSecs or 0.0
                    lines.append(f"Propagate 'Prop to Maneuver Epoch' {prop_name}({sc_name}) {{{sc_name}.ElapsedSecs = {el_s:.2f}}};")

                # Apply burn
                lines.append(f"Maneuver 'Apply {m.id}' {burn_name}({sc_name});")
                lines.append("")

            elif m.type == "TargetedHohmannTransfer":
                burn1_name = f"Burn_{m.id}_Insertion"
                burn2_name = f"Burn_{m.id}_TargetInsertion"

                # Hohmann step 1: Propagate to insertion point (periapsis)
                if m.trigger.condition == "AtApoapsis":
                    lines.append(f"Propagate 'Prop to Apoapsis' {prop_name}({sc_name}) {{{sc_name}.{gmat_body}.Apoapsis}};")
                else:
                    lines.append(f"Propagate 'Prop to Periapsis' {prop_name}({sc_name}) {{{sc_name}.{gmat_body}.Periapsis}};")

                lines.append(f"Maneuver 'Hohmann Insertion Burn' {burn1_name}({sc_name});")
                # Propagate to the transfer ellipse's opposite apsis.
                transfer_apsis = hohmann_transfers[m.id]
                lines.append(
                    f"Propagate 'Prop to Hohmann {transfer_apsis}' "
                    f"{prop_name}({sc_name}) {{{sc_name}.{gmat_body}.{transfer_apsis}}};"
                )
                lines.append(f"Maneuver 'Hohmann Target Insertion Burn' {burn2_name}({sc_name});")
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
                energy = (v_mag2 / 2.0) - (body_mu_km3_s2 / r_mag)
                if energy >= 0.0:
                    raise ValueError("OrbitPeriods propagation requires a bound initial orbit")
                a_km = -body_mu_km3_s2 / (2.0 * energy)

            period_s = compute_keplerian_period_seconds(a_km, body_mu_km3_s2)
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
