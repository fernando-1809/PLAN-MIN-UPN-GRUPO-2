"""Create interactive 3D views of already-positioned exploration data."""

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence, Tuple

import plotly.graph_objects as go
from plotly.colors import qualitative


CoordinateRow = Mapping[str, object]
IntervalRow = Mapping[str, object]


@dataclass(frozen=True)
class TopographySurface:
    """Pre-triangulated topographic surface in the project's local XYZ system."""

    x: Sequence[float]
    y: Sequence[float]
    z: Sequence[float]
    i: Sequence[int]
    j: Sequence[int]
    k: Sequence[int]


class VisualizationDataError(ValueError):
    """Raised when pipeline output cannot be represented as 3D coordinates."""


def _number(value: object, field: str, row_index: int) -> float:
    if isinstance(value, bool):
        raise VisualizationDataError(
            "Row {} field {!r} must be a finite number.".format(row_index, field)
        )
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise VisualizationDataError(
            "Row {} field {!r} must be a finite number.".format(row_index, field)
        ) from error
    if not math.isfinite(number):
        raise VisualizationDataError(
            "Row {} field {!r} must be a finite number.".format(row_index, field)
        )
    return number


def _validate_topography(surface: TopographySurface) -> None:
    vertex_count = len(surface.x)
    if len(surface.y) != vertex_count or len(surface.z) != vertex_count:
        raise VisualizationDataError(
            "Topography x, y, and z arrays must have equal lengths."
        )
    if len(surface.i) == 0 or len(surface.i) != len(surface.j) or len(surface.i) != len(surface.k):
        raise VisualizationDataError(
            "Topography must contain equally sized, non-empty triangle index arrays."
        )
    for index, (x, y, z) in enumerate(zip(surface.x, surface.y, surface.z), 1):
        _number(x, "topography.x", index)
        _number(y, "topography.y", index)
        _number(z, "topography.z", index)
    for triangle in zip(surface.i, surface.j, surface.k):
        if any(
            isinstance(index, bool)
            or not isinstance(index, int)
            or index < 0
            or index >= vertex_count
            for index in triangle
        ):
            raise VisualizationDataError(
                "Topography triangle indices must reference existing vertices."
            )


def _coordinates(
    rows: Iterable[CoordinateRow],
    layer_name: str,
    identity_field: str,
    sort_field: Optional[str] = None,
) -> Tuple[Tuple[str, Tuple[float, ...], Tuple[float, ...], Tuple[float, ...]], ...]:
    grouped = {}
    for row_index, row in enumerate(rows, 1):
        identity = row.get(identity_field)
        if identity is None or not str(identity).strip():
            raise VisualizationDataError(
                "{} row {} has no {!r}.".format(layer_name, row_index, identity_field)
            )
        x = _number(row.get("x"), "x", row_index)
        y = _number(row.get("y"), "y", row_index)
        z = _number(row.get("z"), "z", row_index)
        order = None
        if sort_field is not None:
            order = _number(row.get(sort_field), sort_field, row_index)
        grouped.setdefault(str(identity), []).append((order, x, y, z))

    result = []
    for identity, points in grouped.items():
        if sort_field is not None:
            points.sort(key=lambda point: point[0])
        result.append(
            (
                identity,
                tuple(point[1] for point in points),
                tuple(point[2] for point in points),
                tuple(point[3] for point in points),
            )
        )
    return tuple(result)


def _add_collars(figure: go.Figure, collars: Iterable[CoordinateRow]) -> None:
    rows = tuple(collars)
    if not rows:
        return
    ids, x, y, z, details = [], [], [], [], []
    for row_index, row in enumerate(rows, 1):
        hole_id = row.get("hole_id")
        if hole_id is None or not str(hole_id).strip():
            raise VisualizationDataError(
                "collar row {} has no 'hole_id'.".format(row_index)
            )
        ids.append(str(hole_id))
        x.append(_number(row.get("x"), "x", row_index))
        y.append(_number(row.get("y"), "y", row_index))
        z.append(_number(row.get("z"), "z", row_index))
        details.append(
            [
                str(row.get("campaign_id", "")),
                row.get("azimuth_deg", ""),
                row.get("dip_deg", ""),
                row.get("final_depth_m", ""),
            ]
        )
    figure.add_trace(
        go.Scatter3d(
            x=x,
            y=y,
            z=z,
            mode="markers+text",
            name="Collars",
            marker={"size": 5, "symbol": "diamond", "color": "#20252b"},
            text=ids,
            textposition="top center",
            textfont={"size": 8, "color": "#343a40"},
            customdata=details,
            hovertemplate=(
                "HOLE_ID: %{text}<br>"
                "Campaign: %{customdata[0]}<br>"
                "X: %{x}<br>Y: %{y}<br>Z: %{z}<br>"
                "Azimuth: %{customdata[1]}°<br>"
                "Dip: %{customdata[2]}°<br>"
                "Final depth: %{customdata[3]} m<extra></extra>"
            ),
        )
    )


def _add_collar_projections(
    figure: go.Figure, collars: Iterable[CoordinateRow]
) -> None:
    """Draw straight illustrative paths from collar orientation and final MD."""

    rows = tuple(collars)
    if not rows:
        return
    projection_fields = ("azimuth_deg", "dip_deg", "final_depth_m")
    available_field_counts = [
        sum(row.get(field) not in (None, "") for field in projection_fields)
        for row in rows
    ]
    if not any(available_field_counts):
        return
    if any(count != len(projection_fields) for count in available_field_counts):
        incomplete_row = next(
            index
            for index, count in enumerate(available_field_counts, 1)
            if count != len(projection_fields)
        )
        raise VisualizationDataError(
            "collar row {} is missing azimuth_deg, dip_deg, or final_depth_m "
            "required for a straight projection.".format(incomplete_row)
        )

    for row_index, row in enumerate(rows, 1):
        hole_id = str(row["hole_id"])
        x0 = _number(row.get("x"), "x", row_index)
        y0 = _number(row.get("y"), "y", row_index)
        z0 = _number(row.get("z"), "z", row_index)
        azimuth = _number(row.get("azimuth_deg"), "azimuth_deg", row_index)
        dip = _number(row.get("dip_deg"), "dip_deg", row_index)
        final_depth = _number(row.get("final_depth_m"), "final_depth_m", row_index)
        if not 0 <= azimuth < 360:
            raise VisualizationDataError(
                "Row {} field 'azimuth_deg' must be in [0, 360).".format(row_index)
            )
        if not -90 <= dip <= 90:
            raise VisualizationDataError(
                "Row {} field 'dip_deg' must be in [-90, 90].".format(row_index)
            )
        if final_depth < 0:
            raise VisualizationDataError(
                "Row {} field 'final_depth_m' must be non-negative.".format(row_index)
            )

        azimuth_rad = math.radians(azimuth)
        dip_rad = math.radians(dip)
        horizontal_distance = final_depth * math.cos(dip_rad)
        x_end = x0 + horizontal_distance * math.sin(azimuth_rad)
        y_end = y0 + horizontal_distance * math.cos(azimuth_rad)
        z_end = z0 + final_depth * math.sin(dip_rad)
        figure.add_trace(
            go.Scatter3d(
                x=(x0, x_end),
                y=(y0, y_end),
                z=(z0, z_end),
                mode="lines",
                name="Proyección recta desde collar",
                legendgroup="collar-projections",
                showlegend=row_index == 1,
                line={"width": 3, "color": "#687887", "dash": "dash"},
                customdata=((hole_id, 0.0), (hole_id, final_depth)),
                hovertemplate=(
                    "Proyección ilustrativa (orientación constante)<br>"
                    "HOLE_ID: %{customdata[0]}<br>"
                    "MD proyectada: %{customdata[1]} m<br>"
                    "X: %{x}<br>Y: %{y}<br>Z: %{z}<extra></extra>"
                ),
            )
        )


def _add_trajectories(figure: go.Figure, trajectories: Iterable[CoordinateRow]) -> None:
    grouped = {}
    for row_index, row in enumerate(trajectories, 1):
        identity = row.get("hole_id")
        if identity is None or not str(identity).strip():
            raise VisualizationDataError(
                "trajectory row {} has no 'hole_id'.".format(row_index)
            )
        hole_id = str(identity)
        md = _number(row.get("md"), "md", row_index)
        point = (
            md,
            _number(row.get("x"), "x", row_index),
            _number(row.get("y"), "y", row_index),
            _number(row.get("z"), "z", row_index),
        )
        grouped.setdefault(hole_id, []).append(point)
    if not grouped:
        return

    x_values, y_values, z_values, details = [], [], [], []
    for hole_id, points in sorted(grouped.items()):
        points.sort(key=lambda point: point[0])
        for md, x, y, z in points:
            x_values.append(x)
            y_values.append(y)
            z_values.append(z)
            details.append((hole_id, md))
        x_values.append(None)
        y_values.append(None)
        z_values.append(None)
        details.append(("", None))
    figure.add_trace(
        go.Scatter3d(
            x=x_values,
            y=y_values,
            z=z_values,
            mode="lines+markers",
            name="Survey",
            legendgroup="survey",
            line={"width": 3, "color": "#168aad"},
            marker={"size": 2, "color": "#168aad"},
            customdata=details,
            hovertemplate=(
                "Survey trajectory XYZ<br>"
                "HOLE_ID: %{customdata[0]}<br>"
                "MD: %{customdata[1]} m<br>"
                "X: %{x}<br>Y: %{y}<br>Z: %{z}<extra></extra>"
            ),
        )
    )


def _add_topography(figure: go.Figure, surface: TopographySurface) -> None:
    if len(surface.x) == 0:
        return
    _validate_topography(surface)
    figure.add_trace(
        go.Mesh3d(
            x=surface.x,
            y=surface.y,
            z=surface.z,
            i=surface.i,
            j=surface.j,
            k=surface.k,
            name="Topography",
            opacity=0.45,
            hovertemplate="X: %{x}<br>Y: %{y}<br>Z: %{z}<extra></extra>",
        )
    )


def _add_categorical_intervals(
    figure: go.Figure, intervals: Sequence[IntervalRow], color_by: str
) -> None:
    categories = {}
    for row_index, row in enumerate(intervals, 1):
        category = row.get(color_by)
        if category is None or not str(category).strip():
            raise VisualizationDataError(
                "Interval row {} has no value for {!r}.".format(row_index, color_by)
            )
        categories.setdefault(str(category), []).append((row_index, row))

    palette = qualitative.Safe
    for category_index, (category, rows) in enumerate(sorted(categories.items())):
        x_values, y_values, z_values, hover = [], [], [], []
        for row_index, row in rows:
            start = tuple(
                _number(row.get("start_" + axis), "start_" + axis, row_index)
                for axis in ("x", "y", "z")
            )
            end = tuple(
                _number(row.get("end_" + axis), "end_" + axis, row_index)
                for axis in ("x", "y", "z")
            )
            x_values.extend((start[0], end[0], None))
            y_values.extend((start[1], end[1], None))
            z_values.extend((start[2], end[2], None))
            hover.extend(
                (
                    "HOLE_ID: {}<br>Interval: {}<br>{}: {}".format(
                        row.get("hole_id", ""), row.get("interval_id", ""), color_by, category
                    ),
                    "HOLE_ID: {}<br>Interval: {}<br>{}: {}".format(
                        row.get("hole_id", ""), row.get("interval_id", ""), color_by, category
                    ),
                    None,
                )
            )
        figure.add_trace(
            go.Scatter3d(
                x=x_values,
                y=y_values,
                z=z_values,
                mode="lines",
                name=(
                    "Litología: {}".format(category)
                    if color_by == "lith_code"
                    else "{}: {}".format(color_by, category)
                ),
                legendgroup="intervals",
                line={"width": 7, "color": palette[category_index % len(palette)]},
                text=hover,
                hovertemplate="%{text}<br>X: %{x}<br>Y: %{y}<br>Z: %{z}<extra></extra>",
            )
        )


def _add_numeric_intervals(
    figure: go.Figure, intervals: Sequence[IntervalRow], color_by: str
) -> None:
    values = [_number(row.get(color_by), color_by, row_index) for row_index, row in enumerate(intervals, 1)]
    color_min, color_max = min(values), max(values)
    for row_index, row in enumerate(intervals, 1):
        color_value = values[row_index - 1]
        start = tuple(
            _number(row.get("start_" + axis), "start_" + axis, row_index)
            for axis in ("x", "y", "z")
        )
        end = tuple(
            _number(row.get("end_" + axis), "end_" + axis, row_index)
            for axis in ("x", "y", "z")
        )
        interval_name = str(row.get("interval_id", row.get("sample_id", row_index)))
        hover = (
            "HOLE_ID: {}<br>Interval: {}<br>{}: {}".format(
                row.get("hole_id", ""), interval_name, color_by, color_value
            )
        )
        figure.add_trace(
            go.Scatter3d(
                x=(start[0], end[0]),
                y=(start[1], end[1]),
                z=(start[2], end[2]),
                mode="lines",
                name="Intervals colored by {}".format(color_by),
                legendgroup="intervals",
                line={
                    "width": 7,
                    "color": color_value,
                    "colorscale": "Viridis",
                    "cmin": color_min,
                    "cmax": color_max,
                    "showscale": row_index == 1,
                    "colorbar": {"title": color_by} if row_index == 1 else None,
                },
                text=(hover, hover),
                hovertemplate="%{text}<br>X: %{x}<br>Y: %{y}<br>Z: %{z}<extra></extra>",
                showlegend=row_index == 1,
            )
        )


def _add_intervals(
    figure: go.Figure, intervals: Iterable[IntervalRow], color_by: str
) -> None:
    rows = tuple(intervals)
    if not rows:
        return
    first_value = rows[0].get(color_by)
    if _is_numeric(first_value):
        _add_numeric_intervals(figure, rows, color_by)
    else:
        _add_categorical_intervals(figure, rows, color_by)


def _is_numeric(value: object) -> bool:
    if isinstance(value, bool) or value is None:
        return False
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def create_exploration_figure(
    *,
    topography: Optional[TopographySurface] = None,
    collars: Iterable[CoordinateRow] = (),
    trajectories: Iterable[CoordinateRow] = (),
    intervals: Iterable[IntervalRow] = (),
    interval_color_by: str = "lith_code",
) -> go.Figure:
    """Build a figure from precomputed pipeline outputs without recalculation.

    Collar rows require ``hole_id, x, y, z``. Trajectory rows require
    ``hole_id, md, x, y, z``. Positioned interval rows require
    ``start_x, start_y, start_z, end_x, end_y, end_z`` and a categorical
    (for example ``lith_code``) or numeric (for example ``cu_pct``) color
    field. The interval endpoints must already have been produced upstream.

    When collar rows also contain ``azimuth_deg``, ``dip_deg``, and
    ``final_depth_m``, a dashed straight projection is drawn from the collar.
    It assumes constant collar orientation and is illustrative, not a surveyed
    or desurveyed trajectory.
    """

    figure = go.Figure()
    if topography is not None:
        _add_topography(figure, topography)
    collar_rows = tuple(collars)
    trajectory_rows = tuple(trajectories)
    _add_collars(figure, collar_rows)
    if not trajectory_rows:
        _add_collar_projections(figure, collar_rows)
    _add_trajectories(figure, trajectory_rows)
    _add_intervals(figure, intervals, interval_color_by)

    if not figure.data:
        raise VisualizationDataError(
            "At least one prepared topography, collar, trajectory, or interval is required."
        )

    figure.update_layout(
        title={
            "text": (
                "M01 — Exploración 3D interactiva"
                "<br><sup>Sistema cartesiano local, sin CRS/EPSG — ver DECISION-06</sup>"
            ),
            "x": 0.02,
            "xanchor": "left",
            "font": {"size": 18, "color": "#343a40"},
        },
        paper_bgcolor="#ffffff",
        font={"family": "Arial, sans-serif", "color": "#343a40"},
        scene={
            "xaxis_title": "X — Easting (m)",
            "yaxis_title": "Y — Northing (m)",
            "zaxis_title": "Z — Elevation (m)",
            "aspectmode": "data",
            "xaxis": {
                "showbackground": True,
                "backgroundcolor": "#eef3f8",
                "gridcolor": "#ffffff",
                "zerolinecolor": "#ffffff",
            },
            "yaxis": {
                "showbackground": True,
                "backgroundcolor": "#eef3f8",
                "gridcolor": "#ffffff",
                "zerolinecolor": "#ffffff",
            },
            "zaxis": {
                "showbackground": True,
                "backgroundcolor": "#eef3f8",
                "gridcolor": "#ffffff",
                "zerolinecolor": "#ffffff",
            },
        },
        legend={
            "title": "Capas",
            "yanchor": "top",
            "y": 0.98,
            "xanchor": "right",
            "x": 0.99,
            "bgcolor": "rgba(255,255,255,0.85)",
        },
        margin={"l": 0, "r": 0, "t": 70, "b": 0},
    )
    return figure


def write_exploration_html(
    *,
    topography: Optional[TopographySurface] = None,
    collars: Iterable[CoordinateRow] = (),
    trajectories: Iterable[CoordinateRow] = (),
    intervals: Iterable[IntervalRow] = (),
    interval_color_by: str = "lith_code",
    output_path: Optional[Path] = None,
) -> Path:
    """Write a self-contained interactive HTML visualization.

    If no output path is supplied, the file is written to
    ``outputs/figures/m01_exploration_3d.html`` at the repository root.
    """

    if output_path is None:
        output_path = Path(__file__).resolve().parents[2] / "outputs" / "figures" / "m01_exploration_3d.html"
    destination = Path(output_path)
    figure = create_exploration_figure(
        topography=topography,
        collars=collars,
        trajectories=trajectories,
        intervals=intervals,
        interval_color_by=interval_color_by,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    figure.write_html(
        str(destination),
        full_html=True,
        include_plotlyjs=True,
        auto_open=False,
    )
    return destination
