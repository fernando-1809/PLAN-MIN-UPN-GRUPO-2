"""Calculate surveyed drillhole coordinates with the Minimum Curvature method."""

import math
from typing import Dict, Mapping, Sequence, Tuple


Coordinate = Tuple[float, float, float]
TrajectoryPoint = Dict[str, object]


class DesurveyError(ValueError):
    """Raised when survey records cannot define a valid trajectory."""


def _number(value: object, field: str, hole_id: str) -> float:
    if isinstance(value, bool):
        raise DesurveyError(
            "Hole {!r} field {!r} must be a finite number.".format(hole_id, field)
        )
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise DesurveyError(
            "Hole {!r} field {!r} must be a finite number.".format(hole_id, field)
        ) from error
    if not math.isfinite(number):
        raise DesurveyError(
            "Hole {!r} field {!r} must be a finite number.".format(hole_id, field)
        )
    return number


def _direction(azimuth_deg: float, dip_deg: float) -> Coordinate:
    azimuth = math.radians(azimuth_deg)
    dip = math.radians(dip_deg)
    return (
        math.cos(dip) * math.sin(azimuth),
        math.cos(dip) * math.cos(azimuth),
        math.sin(dip),
    )


def _dogleg(first: Coordinate, second: Coordinate) -> float:
    cosine = sum(a * b for a, b in zip(first, second))
    return math.acos(max(-1.0, min(1.0, cosine)))


def _minimum_curvature_displacement(
    measured_depth_delta: float,
    first_direction: Coordinate,
    second_direction: Coordinate,
) -> Coordinate:
    angle = _dogleg(first_direction, second_direction)
    if math.pi - angle < 1e-10:
        raise DesurveyError(
            "Minimum Curvature is undefined for an approximately 180-degree dogleg."
        )
    if angle < 1e-12:
        ratio_factor = 1.0
    else:
        ratio_factor = 2.0 * math.tan(angle / 2.0) / angle
    scale = measured_depth_delta * ratio_factor / 2.0
    return tuple(
        scale * (first + second)
        for first, second in zip(first_direction, second_direction)
    )


def _slerp(first: Coordinate, second: Coordinate, fraction: float) -> Coordinate:
    angle = _dogleg(first, second)
    if angle < 1e-12:
        vector = tuple(
            start + fraction * (end - start)
            for start, end in zip(first, second)
        )
    else:
        denominator = math.sin(angle)
        first_weight = math.sin((1.0 - fraction) * angle) / denominator
        second_weight = math.sin(fraction * angle) / denominator
        vector = tuple(
            first_weight * start + second_weight * end
            for start, end in zip(first, second)
        )
    magnitude = math.sqrt(sum(component * component for component in vector))
    if magnitude == 0:
        raise DesurveyError("Could not interpolate survey orientation.")
    return tuple(component / magnitude for component in vector)


def calculate_trajectory(
    collar: Mapping[str, object],
    survey_rows: Sequence[Mapping[str, object]],
) -> Tuple[TrajectoryPoint, ...]:
    """Return XYZ at survey stations using collar orientation at MD=0.

    Input dip is positive upward / negative downward from the horizontal;
    azimuth is clockwise from north. Duplicate stations with identical
    measurements are collapsed in memory. Contradictory duplicates, stations
    beyond final depth, and invalid angular/depth values raise ``DesurveyError``.
    No stations are invented and the path is not extrapolated past the last
    observed survey station.
    """

    hole_value = collar.get("hole_id")
    if hole_value is None or not str(hole_value).strip():
        raise DesurveyError("Collar row has no hole_id.")
    hole_id = str(hole_value)
    x0 = _number(collar.get("x"), "x", hole_id)
    y0 = _number(collar.get("y"), "y", hole_id)
    z0 = _number(collar.get("z"), "z", hole_id)
    collar_azimuth = _number(collar.get("azimuth_deg"), "azimuth_deg", hole_id)
    collar_dip = _number(collar.get("dip_deg"), "dip_deg", hole_id)
    final_depth = _number(collar.get("final_depth_m"), "final_depth_m", hole_id)
    if not 0.0 <= collar_azimuth < 360.0:
        raise DesurveyError("Hole {!r} collar azimuth is outside [0, 360).".format(hole_id))
    if not -90.0 <= collar_dip <= 90.0:
        raise DesurveyError("Hole {!r} collar dip is outside [-90, 90].".format(hole_id))
    if final_depth < 0:
        raise DesurveyError("Hole {!r} final depth must be non-negative.".format(hole_id))
    if not survey_rows:
        raise DesurveyError("Hole {!r} has no survey stations.".format(hole_id))

    stations = {}
    for row_index, row in enumerate(survey_rows, 1):
        row_hole = row.get("hole_id")
        if row_hole is not None and str(row_hole) != hole_id:
            raise DesurveyError(
                "Survey row {} belongs to hole {!r}, expected {!r}.".format(
                    row_index, row_hole, hole_id
                )
            )
        depth = _number(row.get("depth_m"), "depth_m", hole_id)
        azimuth = _number(row.get("azimuth_deg"), "azimuth_deg", hole_id)
        dip = _number(row.get("dip_deg"), "dip_deg", hole_id)
        if depth < 0:
            raise DesurveyError("Hole {!r} has negative survey depth.".format(hole_id))
        if depth > final_depth:
            raise DesurveyError(
                "Hole {!r} survey at {} m exceeds final depth {} m.".format(
                    hole_id, depth, final_depth
                )
            )
        if not 0.0 <= azimuth < 360.0:
            raise DesurveyError(
                "Hole {!r} survey azimuth is outside [0, 360).".format(hole_id)
            )
        if not -90.0 <= dip <= 90.0:
            raise DesurveyError(
                "Hole {!r} survey dip is outside [-90, 90].".format(hole_id)
            )
        orientation = (azimuth, dip)
        if depth in stations and stations[depth] != orientation:
            raise DesurveyError(
                "Hole {!r} has contradictory survey stations at {} m.".format(
                    hole_id, depth
                )
            )
        stations[depth] = orientation

    ordered_depths = sorted(stations)
    if not ordered_depths or ordered_depths[0] != 0.0:
        raise DesurveyError(
            "Hole {!r} survey must include an observed station at MD=0.".format(
                hole_id
            )
        )

    points = [
        {
            "hole_id": hole_id,
            "md": 0.0,
            "x": x0,
            "y": y0,
            "z": z0,
            "azimuth_deg": collar_azimuth,
            "dip_deg": collar_dip,
            "orientation_source": "collar",
        }
    ]
    previous_direction = _direction(collar_azimuth, collar_dip)
    x, y, z = x0, y0, z0
    previous_depth = 0.0
    for depth in ordered_depths:
        if depth == 0.0:
            continue
        azimuth, dip = stations[depth]
        direction = _direction(azimuth, dip)
        delta = _minimum_curvature_displacement(
            depth - previous_depth, previous_direction, direction
        )
        x += delta[0]
        y += delta[1]
        z += delta[2]
        points.append(
            {
                "hole_id": hole_id,
                "md": depth,
                "x": x,
                "y": y,
                "z": z,
                "azimuth_deg": azimuth,
                "dip_deg": dip,
                "orientation_source": "survey",
            }
        )
        previous_depth = depth
        previous_direction = direction
    return tuple(points)


def position_at_md(
    trajectory: Sequence[Mapping[str, object]], measured_depth: float
) -> Coordinate:
    """Interpolate XYZ at an MD inside the surveyed trajectory, without extrapolation."""

    if not trajectory:
        raise DesurveyError("Cannot position a depth on an empty trajectory.")
    hole_id = str(trajectory[0].get("hole_id", "UNKNOWN"))
    target = _number(measured_depth, "measured_depth", hole_id)
    points = sorted(
        trajectory,
        key=lambda point: _number(point.get("md"), "md", hole_id),
    )
    first_md = _number(points[0].get("md"), "md", hole_id)
    last_md = _number(points[-1].get("md"), "md", hole_id)
    if target < first_md or target > last_md:
        raise DesurveyError(
            "Hole {!r} MD {} is outside surveyed trajectory [{}, {}].".format(
                hole_id, target, first_md, last_md
            )
        )
    for point in points:
        point_md = _number(point.get("md"), "md", hole_id)
        if target == point_md:
            return tuple(
                _number(point.get(axis), axis, hole_id) for axis in ("x", "y", "z")
            )

    for start, end in zip(points, points[1:]):
        start_md = _number(start.get("md"), "md", hole_id)
        end_md = _number(end.get("md"), "md", hole_id)
        if start_md < target < end_md:
            fraction = (target - start_md) / (end_md - start_md)
            start_direction = _direction(
                _number(start.get("azimuth_deg"), "azimuth_deg", hole_id),
                _number(start.get("dip_deg"), "dip_deg", hole_id),
            )
            end_direction = _direction(
                _number(end.get("azimuth_deg"), "azimuth_deg", hole_id),
                _number(end.get("dip_deg"), "dip_deg", hole_id),
            )
            partial_direction = _slerp(start_direction, end_direction, fraction)
            partial_displacement = _minimum_curvature_displacement(
                target - start_md, start_direction, partial_direction
            )
            return tuple(
                _number(start.get(axis), axis, hole_id) + partial_displacement[index]
                for index, axis in enumerate(("x", "y", "z"))
            )
    raise DesurveyError(
        "Could not locate MD {} on trajectory for hole {!r}.".format(target, hole_id)
    )
