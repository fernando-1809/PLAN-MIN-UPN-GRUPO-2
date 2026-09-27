"""Build M01 release outputs from the raw release without modifying it."""

import argparse
from collections import defaultdict
from pathlib import Path
from typing import Optional, Sequence

from .desurvey import DesurveyError, calculate_trajectory
from .loader import LoadedRelease, load_release
from .positioning import position_intervals
from .visualizer import write_exploration_html


def _table_rows(release: LoadedRelease, file_name: str):
    try:
        return tuple(row.values for row in release.tables[file_name].rows)
    except KeyError as error:
        raise ValueError(
            "Required release table is missing: {}".format(file_name)
        ) from error


def build_release_visualization(
    release: LoadedRelease, output_path: Optional[Path] = None
) -> Path:
    """Desurvey surveys, position lithology, and write the release 3D HTML."""

    collars = _table_rows(release, "collar.csv")
    survey_rows = _table_rows(release, "survey.csv")
    lithology_rows = _table_rows(release, "lithology.csv")

    collars_by_hole = {}
    for row in collars:
        hole_id = row.get("hole_id")
        if hole_id is None or not str(hole_id).strip():
            raise DesurveyError("A collar row has no hole_id.")
        key = str(hole_id)
        if key in collars_by_hole:
            raise DesurveyError("Duplicate collar for hole {!r}.".format(key))
        collars_by_hole[key] = row

    surveys_by_hole = defaultdict(list)
    for row in survey_rows:
        hole_id = row.get("hole_id")
        if hole_id is None or not str(hole_id).strip():
            raise DesurveyError("A survey row has no hole_id.")
        key = str(hole_id)
        if key not in collars_by_hole:
            raise DesurveyError(
                "Survey row references hole {!r} without a collar.".format(key)
            )
        surveys_by_hole[key].append(row)

    trajectories = {}
    trajectory_points = []
    for hole_id, collar in collars_by_hole.items():
        points = calculate_trajectory(collar, surveys_by_hole.get(hole_id, ()))
        trajectories[hole_id] = points
        trajectory_points.extend(points)

    positioned_lithology = position_intervals(
        lithology_rows,
        trajectories,
        from_field="from_m",
        to_field="to_m",
        identifier_field="interval_id",
    )
    return write_exploration_html(
        collars=collars,
        trajectories=trajectory_points,
        intervals=positioned_lithology,
        interval_color_by="lith_code",
        output_path=output_path,
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create an interactive M01 exploration view from surveyed release data."
        )
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("data/raw"),
        help="Release directory containing release_manifest.json.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="HTML output path (defaults to outputs/figures/m01_exploration_3d.html).",
    )
    args = parser.parse_args(argv)
    release = load_release(args.raw_dir)
    output = build_release_visualization(release, args.output)
    print("3D visualization written to {}".format(output.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
