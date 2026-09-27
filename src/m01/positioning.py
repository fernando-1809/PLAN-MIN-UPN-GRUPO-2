"""Position downhole intervals along calculated drillhole trajectories."""

from typing import Dict, Mapping, Sequence, Tuple

from .desurvey import DesurveyError, position_at_md


PositionedInterval = Dict[str, object]


def position_intervals(
    interval_rows: Sequence[Mapping[str, object]],
    trajectories: Mapping[str, Sequence[Mapping[str, object]]],
    *,
    from_field: str = "from_m",
    to_field: str = "to_m",
    identifier_field: str = "sample_id",
) -> Tuple[PositionedInterval, ...]:
    """Return interval endpoints in XYZ; intervals beyond survey coverage fail."""

    positioned = []
    for row_index, row in enumerate(interval_rows, 1):
        hole_value = row.get("hole_id")
        if hole_value is None or not str(hole_value).strip():
            raise DesurveyError(
                "Interval row {} has no hole_id.".format(row_index)
            )
        hole_id = str(hole_value)
        if hole_id not in trajectories:
            raise DesurveyError(
                "Interval row {} references hole {!r} without a trajectory.".format(
                    row_index, hole_id
                )
            )
        try:
            start_md = float(row[from_field])
            end_md = float(row[to_field])
        except (KeyError, TypeError, ValueError) as error:
            raise DesurveyError(
                "Interval row {} has invalid {} or {}.".format(
                    row_index, from_field, to_field
                )
            ) from error
        if start_md < 0 or end_md <= start_md:
            raise DesurveyError(
                "Interval row {} must satisfy 0 <= {} < {}.".format(
                    row_index, from_field, to_field
                )
            )

        start = position_at_md(trajectories[hole_id], start_md)
        end = position_at_md(trajectories[hole_id], end_md)
        result = dict(row)
        result.update(
            {
                "interval_id": row.get(
                    identifier_field,
                    "{}:{}-{}".format(hole_id, start_md, end_md),
                ),
                "start_x": start[0],
                "start_y": start[1],
                "start_z": start[2],
                "end_x": end[0],
                "end_y": end[1],
                "end_z": end[2],
            }
        )
        positioned.append(result)
    return tuple(positioned)
