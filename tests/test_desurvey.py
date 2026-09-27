import unittest

from src.m01.desurvey import DesurveyError, calculate_trajectory, position_at_md
from src.m01.positioning import position_intervals


class DesurveyTests(unittest.TestCase):
    def setUp(self):
        self.collar = {
            "hole_id": "H1",
            "x": 100,
            "y": 200,
            "z": 300,
            "azimuth_deg": 0,
            "dip_deg": -90,
            "final_depth_m": 20,
        }
        self.survey = [
            {
                "hole_id": "H1",
                "depth_m": 0,
                "azimuth_deg": 0,
                "dip_deg": -90,
            },
            {
                "hole_id": "H1",
                "depth_m": 10,
                "azimuth_deg": 0,
                "dip_deg": -90,
            },
            {
                "hole_id": "H1",
                "depth_m": 20,
                "azimuth_deg": 0,
                "dip_deg": -90,
            },
        ]

    def test_vertical_hole_moves_downward_with_positive_md(self):
        trajectory = calculate_trajectory(self.collar, self.survey)

        self.assertEqual(len(trajectory), 3)
        self.assertAlmostEqual(trajectory[-1]["x"], 100)
        self.assertAlmostEqual(trajectory[-1]["y"], 200)
        self.assertAlmostEqual(trajectory[-1]["z"], 280)
        self.assertEqual(trajectory[0]["orientation_source"], "collar")

    def test_collapses_identical_duplicate_station(self):
        trajectory = calculate_trajectory(
            self.collar,
            self.survey + [dict(self.survey[1])],
        )
        self.assertEqual(len(trajectory), 3)

    def test_rejects_contradictory_duplicate_station(self):
        contradictory = dict(self.survey[1], azimuth_deg=45)
        with self.assertRaisesRegex(DesurveyError, "contradictory"):
            calculate_trajectory(self.collar, self.survey + [contradictory])

    def test_rejects_survey_beyond_final_depth(self):
        beyond_end = dict(self.survey[-1], depth_m=21)
        with self.assertRaisesRegex(DesurveyError, "exceeds final depth"):
            calculate_trajectory(self.collar, self.survey + [beyond_end])

    def test_rejects_undefined_180_degree_dogleg(self):
        reverse = [
            self.survey[0],
            dict(self.survey[1], depth_m=10, dip_deg=90),
        ]
        with self.assertRaisesRegex(DesurveyError, "180-degree dogleg"):
            calculate_trajectory(self.collar, reverse)

    def test_positions_intervals_and_rejects_extrapolation(self):
        trajectory = calculate_trajectory(self.collar, self.survey)
        position = position_at_md(trajectory, 5)
        self.assertAlmostEqual(position[2], 295)
        interval = position_intervals(
            [{"hole_id": "H1", "from_m": 5, "to_m": 10, "lith_code": "VOL"}],
            {"H1": trajectory},
            identifier_field="interval_id",
        )[0]
        self.assertAlmostEqual(interval["start_z"], 295)
        self.assertAlmostEqual(interval["end_z"], 290)
        with self.assertRaisesRegex(DesurveyError, "outside surveyed trajectory"):
            position_at_md(trajectory, 21)


if __name__ == "__main__":
    unittest.main()
