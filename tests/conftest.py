import pytest

from backend.ml.predict import load_bundle
from backend.physics import OperatingPoint


@pytest.fixture(scope="session")
def bundle():
    return load_bundle()


@pytest.fixture
def healthy_point():
    """Comfortably inside every AI4I limit."""
    return OperatingPoint("M", 298.1, 308.6, 1551, 42.8, 20)


@pytest.fixture
def overstrain_point():
    """wear * torque = 13120 against an L class limit of 11000."""
    return OperatingPoint("L", 298.4, 308.9, 1330, 64.0, 205)


@pytest.fixture
def heat_point():
    """temp spread 8.0 K and speed 1345 rpm, so both HDF conditions hold."""
    return OperatingPoint("L", 302.0, 310.0, 1345, 42.0, 110)


@pytest.fixture
def low_power_point():
    """Near the 3500 W floor, where a naive torque cut causes a Power Failure."""
    return OperatingPoint("L", 297.0, 305.4, 1370, 26.0, 150)


@pytest.fixture
def unfixable_point():
    """A real AI4I power fault: 1378 W against a 3500 W floor.

    No torque or speed trim inside the drive's range gets back into the band,
    so the only honest answer is to take the asset off line.
    """
    return OperatingPoint("L", 298.5, 308.7, 2861, 4.6, 143)


@pytest.fixture
def two_kind_point():
    """Breaches two limits that need different kinds of fix.

    Tool wear is 210 min, inside the 200 to 240 minute failure window, which only
    a tool change clears. The temperature spread is 8.0 K at 1345 rpm, a heat
    dissipation failure, which only more speed clears.
    """
    return OperatingPoint("L", 302.0, 310.0, 1345, 42.0, 210)
