import tempfile
import unittest
from pathlib import Path

from src.m01.visualizer import (
    TopographySurface,
    VisualizationDataError,
    create_exploration_figure,
    write_exploration_html,
)


class ExplorationVisualizerTests(unittest.TestCase):
    def setUp(self):
        self.collars = [{"hole_id": "H1", "x": 100, "y": 200, "z": 300}]
        self.trajectories = [
            {"hole_id": "H1", "md": 0, "x": 100, "y": 200, "z": 300},
            {"hole_id": "H1", "md": 10, "x": 100, "y": 200, "z": 290},
        ]
        self.intervals = [
            {
                "hole_id": "H1",
                "interval_id": "I1",
                "start_x": 100,
                "start_y": 200,
                "start_z": 290,
                "end_x": 100,
                "end_y": 200,
                "end_z": 280,
                "lith_code": "VOL",
            }
        ]
        self.topography = TopographySurface(
            x=(0, 1, 0),
            y=(0, 0, 1),
            z=(10, 10, 10),
            i=(0,),
            j=(1,),
            k=(2,),
        )

    def test_builds_figure_from_available_layers(self):
        figure = create_exploration_figure(
            topography=self.topography,
            collars=self.collars,
            trajectories=self.trajectories,
            intervals=self.intervals,
        )

        self.assertEqual(len(figure.data), 4)
        self.assertEqual([trace.name for trace in figure.data][0], "Topography")
        self.assertIn("Collars", [trace.name for trace in figure.data])
        self.assertIn("Survey", [trace.name for trace in figure.data])
        self.assertIn("Litología: VOL", [trace.name for trace in figure.data])
        self.assertEqual(figure.layout.scene.xaxis.title.text, "X — Easting (m)")
        collar_trace = next(trace for trace in figure.data if trace.name == "Collars")
        self.assertEqual(collar_trace.mode, "markers+text")
        self.assertEqual(tuple(collar_trace.text), ("H1",))
        self.assertIn("sin CRS/EPSG", figure.layout.title.text)
        self.assertEqual(figure.layout.scene.xaxis.backgroundcolor, "#eef3f8")

    def test_supports_numeric_assay_interval_coloring(self):
        assay_interval = dict(self.intervals[0], cu_pct=0.45)
        figure = create_exploration_figure(
            intervals=[assay_interval],
            interval_color_by="cu_pct",
        )

        self.assertEqual(len(figure.data), 1)
        self.assertEqual(figure.data[0].line.showscale, True)
        self.assertEqual(figure.data[0].line.color, 0.45)

    def test_draws_every_numeric_interval(self):
        assay_intervals = [
            dict(self.intervals[0], cu_pct=0.45),
            dict(
                self.intervals[0],
                interval_id="I2",
                start_z=280,
                end_z=270,
                cu_pct=0.9,
            ),
        ]
        figure = create_exploration_figure(
            intervals=assay_intervals,
            interval_color_by="cu_pct",
        )

        self.assertEqual(len(figure.data), 2)
        self.assertEqual(figure.data[0].line.color, 0.45)
        self.assertEqual(figure.data[1].line.color, 0.9)
        self.assertTrue(figure.data[0].line.showscale)
        self.assertFalse(figure.data[1].line.showscale)

    def test_projects_straight_hole_from_collar_orientation(self):
        collar = {
            "hole_id": "H1",
            "x": 100,
            "y": 200,
            "z": 300,
            "azimuth_deg": 90,
            "dip_deg": -45,
            "final_depth_m": 10,
        }
        figure = create_exploration_figure(collars=[collar])
        projection = next(
            trace
            for trace in figure.data
            if trace.name == "Proyección recta desde collar"
        )

        self.assertAlmostEqual(projection.x[0], 100)
        self.assertAlmostEqual(projection.x[1], 100 + 10 / 2**0.5)
        self.assertEqual(tuple(projection.y), (200, 200))
        self.assertAlmostEqual(projection.z[1], 300 - 10 / 2**0.5)
        self.assertIn("Proyección ilustrativa", projection.hovertemplate)

    def test_rejects_partial_collar_projection_data(self):
        collar = dict(self.collars[0], azimuth_deg=90, dip_deg=-45)
        with self.assertRaisesRegex(VisualizationDataError, "final_depth_m"):
            create_exploration_figure(collars=[collar])

    def test_raises_for_missing_coordinate_and_empty_layers(self):
        with self.assertRaises(VisualizationDataError):
            create_exploration_figure(collars=[{"hole_id": "H1", "x": 1, "y": 2}])
        with self.assertRaises(VisualizationDataError):
            create_exploration_figure()

    def test_writes_self_contained_interactive_html(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "m01_exploration_3d.html"
            result = write_exploration_html(
                collars=self.collars,
                output_path=output,
            )

            html = result.read_text(encoding="utf-8")
            self.assertEqual(result, output)
            self.assertIn("<html>", html.lower())
            self.assertIn("Plotly.newPlot", html)
            self.assertIn("plotly.js", html.lower())


if __name__ == "__main__":
    unittest.main()
