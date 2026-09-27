import json
import tempfile
import unittest
from pathlib import Path

from src.m01.loader import ReleaseLoadError, load_release


class LoadReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.raw_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_manifest(self, files):
        (self.raw_dir / "release_manifest.json").write_text(
            json.dumps({"files": files}),
            encoding="utf-8",
        )

    def test_preserves_text_values_row_numbers_and_header_only_csv(self):
        self.write_manifest(["collar.csv", "alteration.csv", "README.md"])
        (self.raw_dir / "collar.csv").write_text(
            "hole_id,final_depth_m,note\nH-01,12.50,\n",
            encoding="utf-8",
        )
        (self.raw_dir / "alteration.csv").write_text(
            "hole_id,from_m,to_m\n",
            encoding="utf-8",
        )
        (self.raw_dir / "README.md").write_text("Release notes", encoding="utf-8")

        release = load_release(self.raw_dir)

        collar_row = release.tables["collar.csv"].rows[0]
        self.assertEqual(collar_row.row_number, 2)
        self.assertEqual(collar_row.values["final_depth_m"], "12.50")
        self.assertEqual(collar_row.values["note"], "")
        self.assertEqual(release.tables["alteration.csv"].columns, ("hole_id", "from_m", "to_m"))
        self.assertEqual(release.tables["alteration.csv"].rows, ())
        self.assertEqual(release.text_files["README.md"], "Release notes")

    def test_preserves_missing_trailing_value_as_none(self):
        self.write_manifest(["collar.csv"])
        (self.raw_dir / "collar.csv").write_text(
            "hole_id,final_depth_m\nH-01\n",
            encoding="utf-8",
        )

        release = load_release(self.raw_dir)

        self.assertIsNone(release.tables["collar.csv"].rows[0].values["final_depth_m"])

    def test_missing_manifest_declared_file_raises_load_error(self):
        self.write_manifest(["missing.csv"])

        with self.assertRaisesRegex(ReleaseLoadError, "missing.csv"):
            load_release(self.raw_dir)

    def test_duplicate_csv_headers_raise_load_error(self):
        self.write_manifest(["collar.csv"])
        (self.raw_dir / "collar.csv").write_text(
            "hole_id,hole_id\nH-01,H-02\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ReleaseLoadError, "duplicate column"):
            load_release(self.raw_dir)

    def test_extra_csv_field_raises_load_error(self):
        self.write_manifest(["collar.csv"])
        (self.raw_dir / "collar.csv").write_text(
            "hole_id,final_depth_m\nH-01,12,extra\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ReleaseLoadError, "more fields"):
            load_release(self.raw_dir)


if __name__ == "__main__":
    unittest.main()
