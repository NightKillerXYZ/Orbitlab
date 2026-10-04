"""Pydantic v2 AST Models for OrbitLab Experiment Specifications.

Matches schemas/experiment.schema.json and provides typed access, validation,
and serialization for orbital experiments.
"""

from __future__ import annotations

import math
from typing import Annotated, Any, List, Literal, Optional, Union
from pydantic import BaseModel, Field, StringConstraints, model_validator


IdentifierString = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Za-z0-9_]{1,30}$", strip_whitespace=True)
]

ManeuverIdString = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Za-z0-9_]{1,20}$", strip_whitespace=True)
]


class SpacecraftConfig(BaseModel):
    """Spacecraft physical characteristics and aerodynamic properties."""
    name: IdentifierString = Field(
        ...,
        description="GMAT identifier-safe spacecraft name (alphanumeric and underscore, up to 30 chars)"
    )
    dryMassKg: float = Field(
        ...,
        ge=0.1,
        le=500000.0,
        description="Dry mass of the spacecraft in kilograms"
    )
    coefficientOfDrag: float = Field(
        default=2.2,
        ge=0.0,
        le=5.0,
        description="Drag coefficient (Cd)"
    )
    dragAreaM2: float = Field(
        default=1.0,
        ge=0.01,
        le=1000.0,
        description="Cross-sectional area for atmospheric drag in m^2"
    )
    coefficientOfReflectivity: float = Field(
        default=1.8,
        ge=0.0,
        le=2.0,
        description="Radiation pressure coefficient (Cr)"
    )
    srpAreaM2: float = Field(
        default=1.0,
        ge=0.01,
        le=1000.0,
        description="Cross-sectional area for solar radiation pressure in m^2"
    )


class EpochConfig(BaseModel):
    """Epoch time definition."""
    format: Literal["UTCGregorian"] = Field(
        default="UTCGregorian",
        description="Epoch time format standard"
    )
    value: str = Field(
        default="01 Jan 2026 12:00:00.000",
        description="Epoch string in UTC Gregorian format"
    )


class KeplerianElements(BaseModel):
    """Classical Keplerian orbital elements."""
    semiMajorAxisKm: float = Field(
        ...,
        gt=0.0,
        allow_inf_nan=False,
        description="Semi-major axis in km; periapsis safety is checked for the selected central body"
    )
    eccentricity: float = Field(
        ...,
        ge=0.0,
        le=0.99,
        allow_inf_nan=False,
        description="Orbital eccentricity (0 for circular, <1 for elliptical)"
    )
    inclinationDeg: float = Field(
        ...,
        ge=0.0,
        le=180.0,
        allow_inf_nan=False,
        description="Orbital inclination in degrees"
    )
    raanDeg: float = Field(
        default=0.0,
        ge=0.0,
        le=360.0,
        allow_inf_nan=False,
        description="Right ascension of the ascending node in degrees"
    )
    argumentOfPeriapsisDeg: float = Field(
        default=0.0,
        ge=0.0,
        le=360.0,
        allow_inf_nan=False,
        description="Argument of periapsis in degrees"
    )
    trueAnomalyDeg: float = Field(
        default=0.0,
        ge=0.0,
        le=360.0,
        allow_inf_nan=False,
        description="True anomaly in degrees"
    )


class CartesianElements(BaseModel):
    """Cartesian position and velocity vector in Earth-Centered Inertial frame."""
    xKm: float = Field(..., description="X position coordinate in km")
    yKm: float = Field(..., description="Y position coordinate in km")
    zKm: float = Field(..., description="Z position coordinate in km")
    vxKmS: float = Field(..., description="X velocity component in km/s")
    vyKmS: float = Field(..., description="Y velocity component in km/s")
    vzKmS: float = Field(..., description="Z velocity component in km/s")


class InitialOrbitConfig(BaseModel):
    """Initial orbit state specification."""
    type: Literal["Keplerian", "Cartesian"] = Field(
        ...,
        description="Orbit state parameterization type"
    )
    coordinateSystem: Optional[Literal["EarthMJ2000Eq", "LunaMJ2000Eq", "MarsMJ2000Eq"]] = Field(
        default=None,
        description="Body-centered inertial coordinate reference system"
    )
    elements: Union[KeplerianElements, CartesianElements] = Field(
        ...,
        description="Orbital elements matching the state type"
    )

    @model_validator(mode="before")
    @classmethod
    def parse_elements(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = data.copy()
        orbit_type = data.get("type")
        elements_data = data.get("elements")
        if isinstance(elements_data, dict):
            if orbit_type == "Keplerian" and not isinstance(elements_data, KeplerianElements):
                data["elements"] = KeplerianElements(**elements_data)
            elif orbit_type == "Cartesian" and not isinstance(elements_data, CartesianElements):
                data["elements"] = CartesianElements(**elements_data)
        return data


class AtmosphericDragConfig(BaseModel):
    """Atmospheric drag perturbation model settings."""
    enabled: bool = Field(
        default=False,
        description="Whether atmospheric drag is included in propagation"
    )
    model: Literal["JacchiaRoberts", "MSISE90"] = Field(
        default="JacchiaRoberts",
        description="Atmospheric density model"
    )


class ForceModelConfig(BaseModel):
    """Environmental and gravitational perturbations force model."""
    gravityDegree: int = Field(
        default=4,
        ge=0,
        le=20,
        description="Primary body spherical harmonic gravity degree"
    )
    gravityOrder: int = Field(
        default=4,
        ge=0,
        le=20,
        description="Primary body spherical harmonic gravity order"
    )
    pointMasses: List[Literal["Luna", "Sun", "Jupiter"]] = Field(
        default_factory=lambda: ["Luna", "Sun"],
        description="Third-body celestial point masses"
    )
    atmosphericDrag: AtmosphericDragConfig = Field(
        default_factory=AtmosphericDragConfig,
        description="Atmospheric drag configuration"
    )
    solarRadiationPressure: bool = Field(
        default=True,
        description="Whether solar radiation pressure perturbation is active"
    )

    @model_validator(mode="after")
    def validate_gravity_order(self) -> ForceModelConfig:
        if self.gravityOrder > self.gravityDegree:
            raise ValueError("gravityOrder must not exceed gravityDegree")
        return self

class ManeuverTrigger(BaseModel):
    """Execution trigger condition for a maneuver."""
    condition: Literal["AtPeriapsis", "AtApoapsis", "ElapsedTimeSecs"] = Field(
        ...,
        description="Trigger event condition"
    )
    elapsedSecs: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Elapsed seconds from epoch when condition is ElapsedTimeSecs"
    )

    @model_validator(mode="after")
    def validate_elapsed_secs(self) -> ManeuverTrigger:
        if self.condition == "ElapsedTimeSecs" and self.elapsedSecs is None:
            raise ValueError("elapsedSecs must be provided when trigger condition is ElapsedTimeSecs")
        return self


class BurnVector(BaseModel):
    """Local orbital coordinate Delta-V vector."""
    coordinateSystem: Literal["LocalVNB"] = Field(
        default="LocalVNB",
        description="Coordinate system for Delta-V vector: Velocity, Normal, Binormal"
    )
    deltaVVectorKmS: List[float] = Field(
        ...,
        min_length=3,
        max_length=3,
        description="[V_velocity, N_normal, B_binormal] components in km/s"
    )

    @model_validator(mode="after")
    def validate_finite_components(self) -> BurnVector:
        if any(not math.isfinite(component) for component in self.deltaVVectorKmS):
            raise ValueError("Delta-V vector components must be finite")
        return self


class TargetObjectives(BaseModel):
    """Target orbital parameters for automated differential correction transfers."""
    targetOrbitRadiusKm: Optional[float] = Field(
        default=None,
        gt=0.0,
        description="Target orbit apsis radius in km; it is apoapsis for outward transfers and periapsis for inward transfers"
    )
    targetEccentricity: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=0.99,
        description="Desired target eccentricity"
    )


class ManeuverConfig(BaseModel):
    """Propulsive maneuver configuration."""
    id: ManeuverIdString = Field(
        ...,
        description="Unique identifier for the maneuver"
    )
    type: Literal["ImpulsiveBurn", "TargetedHohmannTransfer"] = Field(
        ...,
        description="Maneuver strategy"
    )
    trigger: ManeuverTrigger = Field(
        ...,
        description="Timing or orbital position trigger for the burn"
    )
    burnVector: Optional[BurnVector] = Field(
        default=None,
        description="Burn vector in km/s (required for ImpulsiveBurn)"
    )
    targetObjectives: Optional[TargetObjectives] = Field(
        default=None,
        description="Target orbit parameters (required for TargetedHohmannTransfer)"
    )

    @model_validator(mode="after")
    def validate_maneuver_requirements(self) -> ManeuverConfig:
        if self.type == "ImpulsiveBurn" and self.burnVector is None:
            raise ValueError(f"Maneuver '{self.id}' of type ImpulsiveBurn requires burnVector")
        if self.type == "TargetedHohmannTransfer" and self.targetObjectives is None:
            raise ValueError(f"Maneuver '{self.id}' of type TargetedHohmannTransfer requires targetObjectives")
        if self.type == "TargetedHohmannTransfer":
            if self.targetObjectives.targetOrbitRadiusKm is None:
                raise ValueError(
                    f"Maneuver '{self.id}' of type TargetedHohmannTransfer requires targetOrbitRadiusKm"
                )
            if self.trigger.condition == "ElapsedTimeSecs":
                raise ValueError(
                    f"Maneuver '{self.id}' of type TargetedHohmannTransfer requires an apsis trigger"
                )
        return self


class StopCondition(BaseModel):
    """Propagation stop criterion."""

    type: Literal[
        "ElapsedDays",
        "ElapsedHours",
        "ElapsedSeconds",
        "OrbitPeriods"
    ] = Field(
        ...,
        description="Type of stop condition"
    )

    value: float = Field(
        ...,
        ge=0.001,
        description="Numerical threshold value for stop condition"
    )

    @model_validator(mode="after")
    def validate_value_range(self) -> "StopCondition":
        limits = {
            "ElapsedDays": 365.0,
            "ElapsedHours": 8760.0,
            "ElapsedSeconds": 31536000.0,
            "OrbitPeriods": 365.0,
        }

        maximum = limits[self.type]

        if self.value > maximum:
            raise ValueError(
                f"{self.type} value must be between 0.001 and {maximum}"
            )

        return self

class PropagationConfig(BaseModel):
    """Numerical propagation and integrator configuration."""
    integrator: Literal["RungeKutta89", "PrinceDormand78"] = Field(
        default="RungeKutta89",
        description="Numerical integration algorithm"
    )
    stopCondition: StopCondition = Field(
        ...,
        description="Propagation termination condition"
    )
    stepSizeSecs: float = Field(
        default=60.0,
        ge=0.1,
        le=3600.0,
        description="Integrator initial step size in seconds"
    )


class OrbitLabExperiment(BaseModel):
    """Top-level specification for an OrbitLab orbital experiment."""
    version: Literal["1.0"] = Field(
        default="1.0",
        description="Schema version"
    )
    experimentName: str = Field(
        ...,
        max_length=100,
        description="Human-readable label for the orbital experiment"
    )
    description: Optional[str] = Field(
        default=None,
        description="Detailed description or user prompt intent"
    )
    spacecraft: SpacecraftConfig = Field(
        ...,
        description="Spacecraft physical configuration"
    )
    centralBody: Literal["Earth", "Moon", "Mars"] = Field(
        default="Earth",
        description="Primary gravitational central body"
    )
    epoch: EpochConfig = Field(
        default_factory=EpochConfig,
        description="Mission start epoch"
    )
    initialOrbit: InitialOrbitConfig = Field(
        ...,
        description="Initial orbital state vector"
    )
    forceModel: ForceModelConfig = Field(
        default_factory=ForceModelConfig,
        description="Force model and perturbation environment"
    )
    maneuvers: List[ManeuverConfig] = Field(
        default_factory=list,
        description="Sequence of propulsive maneuvers"
    )
    propagation: PropagationConfig = Field(
        ...,
        description="Numerical integrator and propagation duration"
    )

    @model_validator(mode="before")
    @classmethod
    def validate_central_body_coordinate_system(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = data.copy()
        body = data.get("centralBody", "Earth")
        expected = {
            "Earth": "EarthMJ2000Eq",
            "Moon": "LunaMJ2000Eq",
            "Mars": "MarsMJ2000Eq",
        }.get(body)
        orbit = data.get("initialOrbit")
        if expected is None:
            return data
        if isinstance(orbit, InitialOrbitConfig):
            coordinate_system = orbit.coordinateSystem
            if coordinate_system is None:
                data["initialOrbit"] = orbit.model_copy(
                    update={"coordinateSystem": expected}
                )
            elif coordinate_system != expected:
                raise ValueError(
                    f"initialOrbit.coordinateSystem must be {expected!r} for centralBody {body!r}"
                )
            return data
        if not isinstance(orbit, dict):
            return data
        orbit = orbit.copy()
        coordinate_system = orbit.get("coordinateSystem")
        if coordinate_system is None:
            orbit["coordinateSystem"] = expected
        elif coordinate_system != expected:
            raise ValueError(
                f"initialOrbit.coordinateSystem must be {expected!r} for centralBody {body!r}"
            )
        data["initialOrbit"] = orbit
        return data

    @model_validator(mode="after")
    def validate_finite_physics_values(self) -> OrbitLabExperiment:
        def check(value: Any, path: str) -> None:
            if isinstance(value, dict):
                for key, nested_value in value.items():
                    check(nested_value, f"{path}.{key}")
            elif isinstance(value, (list, tuple)):
                for index, nested_value in enumerate(value):
                    check(nested_value, f"{path}[{index}]")
            elif isinstance(value, float) and not math.isfinite(value):
                raise ValueError(f"{path} must be finite")

        check(self.model_dump(mode="python"), "experiment")
        return self
