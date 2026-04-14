"""Spatial coordinate utilities for mm/Z-up system."""

from typing import Any


def mm_to_meters(mm: float) -> float:
    """Convert millimeters to meters."""
    return mm / 1000.0


def meters_to_mm(meters: float) -> float:
    """Convert meters to millimeters."""
    return meters * 1000.0


def feet_to_mm(feet: float) -> float:
    """Convert feet to millimeters."""
    return feet * 304.8


def inches_to_mm(inches: float) -> float:
    """Convert inches to millimeters."""
    return inches * 25.4


def parse_length(value: float | str, unit: str = "mm") -> float:
    """Parse a length value to millimeters.

    Args:
        value: Numeric value
        unit: Unit type (mm, m, ft, in)
    """
    converters = {
        "mm": lambda v: v,
        "m": meters_to_mm,
        "ft": feet_to_mm,
        "in": inches_to_mm,
    }
    converter = converters.get(unit, lambda v: v)
    return converter(float(value))


def create_bounding_box(vertices: list[list[float]]) -> dict[str, list[float]]:
    """Create bounding box from vertices.

    Args:
        vertices: List of [x, y, z] points

    Returns:
        Dict with min and max points
    """
    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    zs = [v[2] for v in vertices]

    return {
        "min": [min(xs), min(ys), min(zs)],
        "max": [max(xs), max(ys), max(zs)],
    }


def calculate_face_area(vertices: list[list[float]]) -> float:
    """Calculate planar polygon area using Shoelace formula.

    Args:
        vertices: Ordered list of coplanar [x, y, z] points

    Returns:
        Area in square millimeters
    """
    if len(vertices) < 3:
        return 0.0

    # Project to XY plane for area calculation (assuming planar)
    area = 0.0
    for i in range(len(vertices)):
        j = (i + 1) % len(vertices)
        area += vertices[i][0] * vertices[j][1]
        area -= vertices[j][0] * vertices[i][1]

    return abs(area) / 2.0


def calculate_box_volume(width: float, depth: float, height: float) -> float:
    """Calculate box volume.

    Args:
        width: Width in mm
        depth: Depth in mm
        height: Height in mm

    Returns:
        Volume in cubic millimeters
    """
    return width * depth * height
