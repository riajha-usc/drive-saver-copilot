"""Physical quantities and AI4I failure-mode rules for a VFD driven motor.

The AI4I 2020 generator defines each failure mode as an explicit condition on the
operating point. Encoding those conditions here gives the agent a deterministic
simulator to sit next to the learned model: the model supplies risk, the rules
supply the margin to each physical limit and therefore the direction of a fix.

Rules (AI4I 2020, UCI id 601):
  TWF  tool wear in [200, 240] min
  HDF  (process_temp - air_temp) < 8.6 K and rotational speed < 1380 rpm
  PWF  mechanical power outside [3500, 9000] W
  OSF  tool wear * torque above a product-quality dependent threshold
  RNF  0.1 percent random, not modelled
"""

from __future__ import annotations

import math
from dataclasses import dataclass

RPM_TO_RAD_S = 2.0 * math.pi / 60.0

HDF_TEMP_DIFF_MIN_K = 8.6
HDF_SPEED_MIN_RPM = 1380.0
PWF_POWER_MIN_W = 3500.0
PWF_POWER_MAX_W = 9000.0
TWF_WEAR_MIN_MIN = 200.0
TWF_WEAR_MAX_MIN = 240.0
OSF_WEAR_TORQUE_LIMIT = {"L": 11000.0, "M": 12000.0, "H": 13000.0}

QUALITY_TYPES = ("L", "M", "H")


@dataclass(frozen=True)
class OperatingPoint:
    """One telemetry sample from a motor driven by a VFD."""

    type: str
    air_temperature: float       # K
    process_temperature: float   # K
    rotational_speed: float      # rpm
    torque: float                # Nm
    tool_wear: float             # min

    def __post_init__(self) -> None:
        if self.type not in QUALITY_TYPES:
            raise ValueError(f"type must be one of {QUALITY_TYPES}, got {self.type!r}")
        if self.rotational_speed <= 0:
            raise ValueError("rotational_speed must be positive")
        if self.torque < 0:
            raise ValueError("torque must be non negative")

    @property
    def temp_diff(self) -> float:
        """Process minus air temperature in K. Drives heat dissipation."""
        return self.process_temperature - self.air_temperature

    @property
    def power_w(self) -> float:
        """Mechanical shaft power in W."""
        return self.torque * self.rotational_speed * RPM_TO_RAD_S

    @property
    def wear_torque(self) -> float:
        """Overstrain proxy in min Nm."""
        return self.tool_wear * self.torque

    @property
    def osf_limit(self) -> float:
        return OSF_WEAR_TORQUE_LIMIT[self.type]

    def replace(self, **changes: float | str) -> "OperatingPoint":
        base = {
            "type": self.type,
            "air_temperature": self.air_temperature,
            "process_temperature": self.process_temperature,
            "rotational_speed": self.rotational_speed,
            "torque": self.torque,
            "tool_wear": self.tool_wear,
        }
        base.update(changes)
        return OperatingPoint(**base)  # type: ignore[arg-type]

    def scaled(self, torque_pct: float = 0.0, speed_pct: float = 0.0) -> "OperatingPoint":
        """Apply percentage deltas to torque and speed, e.g. torque_pct=-10."""
        return self.replace(
            torque=self.torque * (1.0 + torque_pct / 100.0),
            rotational_speed=self.rotational_speed * (1.0 + speed_pct / 100.0),
        )


@dataclass(frozen=True)
class Margin:
    """Distance from a failure limit. Negative means the limit is violated."""

    mode: str
    label: str
    value: float
    limit: float
    margin: float
    unit: str

    @property
    def violated(self) -> bool:
        return self.margin < 0


def margins(op: OperatingPoint) -> dict[str, Margin]:
    """Signed distance to every deterministic AI4I failure limit."""
    power = op.power_w
    # Power has a two sided band, so report the tighter side.
    low_slack = power - PWF_POWER_MIN_W
    high_slack = PWF_POWER_MAX_W - power
    if low_slack <= high_slack:
        pwf = Margin("PWF", "shaft power against the lower power limit", power, PWF_POWER_MIN_W, low_slack, "W")
    else:
        pwf = Margin("PWF", "shaft power against the upper power limit", power, PWF_POWER_MAX_W, high_slack, "W")

    # HDF needs BOTH conditions true, so the mode is safe while either has slack.
    # The binding margin is the larger of the two individual slacks.
    hdf_temp_slack = op.temp_diff - HDF_TEMP_DIFF_MIN_K
    hdf_speed_slack = op.rotational_speed - HDF_SPEED_MIN_RPM
    if hdf_temp_slack >= hdf_speed_slack:
        hdf = Margin("HDF", "temperature spread against the heat dissipation floor",
                     op.temp_diff, HDF_TEMP_DIFF_MIN_K, hdf_temp_slack, "K")
    else:
        hdf = Margin("HDF", "rotational speed against the heat dissipation floor",
                     op.rotational_speed, HDF_SPEED_MIN_RPM, hdf_speed_slack, "rpm")

    osf = Margin("OSF", "wear times torque against the overstrain limit",
                 op.wear_torque, op.osf_limit, op.osf_limit - op.wear_torque, "min Nm")

    # TWF is a wear window; margin is distance until the window opens.
    twf = Margin("TWF", "tool wear against the tool change window",
                 op.tool_wear, TWF_WEAR_MIN_MIN, TWF_WEAR_MIN_MIN - op.tool_wear, "min")

    return {"PWF": pwf, "HDF": hdf, "OSF": osf, "TWF": twf}


def rule_failures(op: OperatingPoint) -> list[str]:
    """Failure modes whose deterministic AI4I condition is met right now."""
    out = []
    if op.power_w < PWF_POWER_MIN_W or op.power_w > PWF_POWER_MAX_W:
        out.append("PWF")
    if op.temp_diff < HDF_TEMP_DIFF_MIN_K and op.rotational_speed < HDF_SPEED_MIN_RPM:
        out.append("HDF")
    if op.wear_torque > op.osf_limit:
        out.append("OSF")
    if TWF_WEAR_MIN_MIN <= op.tool_wear <= TWF_WEAR_MAX_MIN:
        out.append("TWF")
    return out


def binding_mode(op: OperatingPoint) -> str:
    """The failure mode with the least headroom, normalised per mode scale."""
    scales = {"PWF": PWF_POWER_MAX_W - PWF_POWER_MIN_W, "HDF": HDF_SPEED_MIN_RPM,
              "OSF": op.osf_limit, "TWF": TWF_WEAR_MIN_MIN}
    m = margins(op)
    return min(m, key=lambda k: m[k].margin / scales[k])
