import json
import tempfile
import unittest
from pathlib import Path

from src.m01.loader import load_release
from src.m01.validator import (
    ERROR,
    INFO,
    NOT_IMPLEMENTED,
    PASS,
    WARNING,
    ValidationConfig,
    validate_release,
)


class ValidateReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.raw_dir = Path(self.temp_dir.name)
        self.write("release_manifest.json", json.dumps({"files": [
            "release_manifest.json",
            "data_dictionary.csv",
            "collar.csv",
            "survey.csv",
            "lithology.csv",
            "alteration.csv",
            "assay.csv",
            "density.csv",
        ]}))
        self.write(
            "data_dictionary.csv",
            "file,column,description,unit,dtype,nullable\n"
            "collar.csv,hole_id,Drillhole ID,,string,false\n"
            "collar.csv,dataset_id,Dataset ID,,string,false\n"
            "collar.csv,project_id,Project ID,,string,false\n"
            "collar.csv,campaign_id,Campaign ID,,string,false\n"
            "collar.csv,x,X,m,float,false\n"
            "collar.csv,y,Y,m,float,false\n"
            "collar.csv,z,Z,m,float,false\n"
            "collar.csv,azimuth_deg,Azimuth,degree,float,false\n"
            "collar.csv,dip_deg,Dip,degree,float,false\n"
            "collar.csv,final_depth_m,Final depth,m,float,false\n"
            "survey.csv,hole_id,Drillhole ID,,string,false\n"
            "survey.csv,dataset_id,Dataset ID,,string,false\n"
            "survey.csv,project_id,Project ID,,string,false\n"
            "survey.csv,campaign_id,Campaign ID,,string,false\n"
            "survey.csv,depth_m,Depth,m,float,false\n"
            "survey.csv,azimuth_deg,Azimuth,degree,float,false\n"
            "survey.csv,dip_deg,Dip,degree,float,false\n"
            "assay.csv,sample_id,Sample ID,,string,false\n"
            "assay.csv,hole_id,Drillhole ID,,string,false\n"
            "assay.csv,dataset_id,Dataset ID,,string,false\n"
            "assay.csv,project_id,Project ID,,string,false\n"
            "assay.csv,campaign_id,Campaign ID,,string,false\n"
            "assay.csv,from_m,From,m,float,false\n"
            "assay.csv,to_m,To,m,float,false\n"
            "assay.csv,length_m,Length,m,float,false\n"
            "assay.csv,cu_pct,Copper,percent,float,false\n"
            "assay.csv,mo_pct,Molybdenum,percent,float,false\n"
            "assay.csv,au_gt,Gold,g/t,float,false\n"
            "lithology.csv,hole_id,Drillhole ID,,string,false\n"
            "lithology.csv,dataset_id,Dataset ID,,string,false\n"
            "lithology.csv,project_id,Project ID,,string,false\n"
            "lithology.csv,campaign_id,Campaign ID,,string,false\n"
            "lithology.csv,from_m,From,m,float,false\n"
            "lithology.csv,to_m,To,m,float,false\n"
            "lithology.csv,length_m,Length,m,float,false\n"
            "lithology.csv,lith_code,Lithology,,string,false\n"
            "alteration.csv,hole_id,Drillhole ID,,string,false\n"
            "alteration.csv,dataset_id,Dataset ID,,string,false\n"
            "alteration.csv,project_id,Project ID,,string,false\n"
            "alteration.csv,campaign_id,Campaign ID,,string,false\n"
            "alteration.csv,from_m,From,m,float,false\n"
            "alteration.csv,to_m,To,m,float,false\n"
            "alteration.csv,length_m,Length,m,float,false\n"
            "alteration.csv,alteration_code,Alteration,,string,false\n"
            "alteration.csv,alteration_intensity,Intensity,,string,false\n"
            "density.csv,density_sample_id,Density ID,,string,false\n"
            "density.csv,hole_id,Drillhole ID,,string,false\n"
            "density.csv,dataset_id,Dataset ID,,string,false\n"
            "density.csv,project_id,Project ID,,string,false\n"
            "density.csv,campaign_id,Campaign ID,,string,false\n"
            "density.csv,from_m,From,m,float,false\n"
            "density.csv,to_m,To,m,float,false\n"
            "density.csv,length_m,Length,m,float,false\n"
            "density.csv,density_t_m3,Density,t/m3,float,false\n",
        )
        self.write(
            "collar.csv",
            "hole_id,dataset_id,project_id,campaign_id,x,y,z,azimuth_deg,dip_deg,final_depth_m\n"
            "H1,DS02,P1,C1,100,200,300,0,-90,100\n"
            "H2,DS02,P1,C1,110,210,310,10,-80,50\n",
        )
        self.write(
            "survey.csv",
            "hole_id,dataset_id,project_id,campaign_id,depth_m,azimuth_deg,dip_deg\n"
            "H1,DS02,P1,C1,0,0,-90\n"
            "H1,DS02,P1,C1,50,0,-90\n"
            "H1,DS02,P1,C1,50,0,-90\n"
            "H2,DS02,P1,C1,10,10,-80\n",
        )
        self.write(
            "lithology.csv",
            "hole_id,dataset_id,project_id,campaign_id,from_m,to_m,length_m,lith_code\n"
            "H1,DS02,P1,C1,0,50,50,OVB\n"
            "H1,DS02,P1,C1,60,100,40,VOL\n",
        )
        self.write(
            "alteration.csv",
            "hole_id,dataset_id,project_id,campaign_id,from_m,to_m,length_m,alteration_code,alteration_intensity\n",
        )
        self.write(
            "assay.csv",
            "sample_id,hole_id,dataset_id,project_id,campaign_id,from_m,to_m,length_m,cu_pct,mo_pct,au_gt\n"
            "S1,H1,DS02,P1,C1,0,1,1,0,0.2,0.1\n"
            "S2,H1,DS02,P1,C1,1,2,1,-0.1,0.2,0.1\n"
            "S3,H9,DS02,P1,C1,2,3,1,0.1,0.2,0.1\n",
        )
        self.write(
            "density.csv",
            "density_sample_id,hole_id,dataset_id,project_id,campaign_id,from_m,to_m,length_m,density_t_m3\n"
            "D1,H1,DS02,P1,C1,0,1,1,2.7\n",
        )
        self.release = load_release(self.raw_dir)

    def tearDown(self):
        self.temp_dir.cleanup()

    def write(self, filename, text):
        (self.raw_dir / filename).write_text(text, encoding="utf-8")

    def findings_for(self, report, rule_id):
        return [finding for finding in report.findings if finding.rule_id == rule_id]

    def summary_for(self, report, rule_id):
        return next(summary for summary in report.summaries if summary.rule_id == rule_id)

    def test_reports_confirmed_duplicate_and_relationship_findings(self):
        report = validate_release(self.release)

        duplicate = self.findings_for(report, "SURVEY_DUPLICATE_IDENTICAL")
        self.assertEqual(len(duplicate), 1)
        self.assertEqual(duplicate[0].severity, WARNING)
        self.assertEqual(duplicate[0].row_number, 4)
        self.assertEqual(duplicate[0].hole_id, "H1")
        self.assertEqual(
            [(finding.table, finding.hole_id) for finding in self.findings_for(report, "REL_HOLE_IN_COLLAR")],
            [("assay.csv", "H9")],
        )
        self.assertEqual(self.summary_for(report, "SURVEY_COLLAR_DIP_MATCH").status, NOT_IMPLEMENTED)

    def test_reports_contradictory_duplicate_as_error_and_checks_end_of_hole(self):
        survey_path = self.raw_dir / "survey.csv"
        survey_path.write_text(
            "hole_id,dataset_id,project_id,campaign_id,depth_m,azimuth_deg,dip_deg\n"
            "H1,DS02,P1,C1,0,0,-90\n"
            "H1,DS02,P1,C1,50,0,-90\n"
            "H1,DS02,P1,C1,50,5,-90\n"
            "H2,DS02,P1,C1,60,10,-80\n",
            encoding="utf-8",
        )
        report = validate_release(load_release(self.raw_dir))

        conflicting = self.findings_for(report, "SURVEY_DUPLICATE_CONTRADICTORY")
        self.assertEqual(len(conflicting), 1)
        self.assertEqual(conflicting[0].severity, ERROR)
        self.assertEqual(len(self.findings_for(report, "SURVEY_DEPTH_WITHIN_FINAL")), 1)

    def test_reports_interval_and_assay_findings(self):
        report = validate_release(self.release)

        gap = self.findings_for(report, "INTERVAL_GAP")
        self.assertEqual(len(gap), 1)
        self.assertEqual(gap[0].severity, INFO)
        negative_assay = self.findings_for(report, "ASSAY_CU_PCT_NONNEGATIVE")
        self.assertEqual(len(negative_assay), 1)
        self.assertTrue(negative_assay[0].blocking)
        zero_values = self.findings_for(report, "ASSAY_CU_PCT_ZERO_RECORDED")
        self.assertEqual(len(zero_values), 1)
        self.assertFalse(zero_values[0].blocking)

    def test_configured_tolerances_classify_initial_orientation(self):
        report = validate_release(
            self.release,
            ValidationConfig(
                collar_azimuth_warning_tolerance_deg=1,
                collar_azimuth_error_tolerance_deg=5,
                collar_dip_warning_tolerance_deg=1,
                collar_dip_error_tolerance_deg=5,
                interval_length_tolerance_m=0.001,
            ),
        )

        self.assertEqual(self.summary_for(report, "SURVEY_COLLAR_AZIMUTH_MATCH").status, PASS)
        self.assertEqual(self.summary_for(report, "SURVEY_COLLAR_DIP_MATCH").status, PASS)
        self.assertEqual(self.summary_for(report, "INTERVAL_LENGTH_MATCH").status, PASS)

    def test_orientation_tolerances_separate_warning_from_error(self):
        survey_path = self.raw_dir / "survey.csv"
        survey_path.write_text(
            "hole_id,dataset_id,project_id,campaign_id,depth_m,azimuth_deg,dip_deg\n"
            "H1,DS02,P1,C1,0,2,-87\n"
            "H1,DS02,P1,C1,50,0,-90\n"
            "H2,DS02,P1,C1,0,17,-80\n",
            encoding="utf-8",
        )
        report = validate_release(
            load_release(self.raw_dir),
            ValidationConfig(
                collar_azimuth_warning_tolerance_deg=1,
                collar_azimuth_error_tolerance_deg=5,
                collar_dip_warning_tolerance_deg=1,
                collar_dip_error_tolerance_deg=5,
            ),
        )

        self.assertEqual(
            self.findings_for(report, "SURVEY_COLLAR_AZIMUTH_MATCH")[0].severity,
            WARNING,
        )
        self.assertEqual(
            self.findings_for(report, "SURVEY_COLLAR_DIP_MATCH")[0].severity,
            WARNING,
        )
        self.assertEqual(
            self.findings_for(report, "SURVEY_COLLAR_AZIMUTH_MATCH")[1].severity,
            ERROR,
        )

    def test_length_difference_exceeds_explicit_tolerance(self):
        assay_path = self.raw_dir / "assay.csv"
        assay_path.write_text(
            "sample_id,hole_id,dataset_id,project_id,campaign_id,from_m,to_m,length_m,cu_pct,mo_pct,au_gt\n"
            "S1,H1,DS02,P1,C1,0,1,0.9,0.1,0.2,0.1\n",
            encoding="utf-8",
        )
        report = validate_release(
            load_release(self.raw_dir),
            ValidationConfig(interval_length_tolerance_m=0.01),
        )

        mismatch = self.findings_for(report, "INTERVAL_LENGTH_MATCH")
        self.assertEqual(len(mismatch), 1)
        self.assertEqual(mismatch[0].severity, ERROR)
        self.assertEqual(mismatch[0].observed_value, "0.1")

    def test_rejects_inconsistent_threshold_configuration(self):
        with self.assertRaises(ValueError):
            ValidationConfig(collar_dip_warning_tolerance_deg=1)


if __name__ == "__main__":
    unittest.main()
