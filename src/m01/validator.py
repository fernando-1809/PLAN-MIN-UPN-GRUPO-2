"""Validate loaded drillhole data without changing source records."""

import math
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Mapping, Optional, Tuple

from .loader import LoadedRelease, RawTable, SourceRow


ERROR = "ERROR"
WARNING = "WARNING"
INFO = "INFO"
PASS = "PASS"
FAIL = "FAIL"
NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


@dataclass(frozen=True)
class ValidationConfig:
    """Engineering thresholds that must be explicitly approved by callers.

    Angle thresholds are in degrees. Interval length tolerance is in metres.
    A missing threshold leaves the corresponding rule NOT_IMPLEMENTED.
    """

    collar_azimuth_warning_tolerance_deg: Optional[float] = None
    collar_azimuth_error_tolerance_deg: Optional[float] = None
    collar_dip_warning_tolerance_deg: Optional[float] = None
    collar_dip_error_tolerance_deg: Optional[float] = None
    interval_length_tolerance_m: Optional[float] = None

    def __post_init__(self):
        threshold_pairs = (
            (
                self.collar_azimuth_warning_tolerance_deg,
                self.collar_azimuth_error_tolerance_deg,
                "collar azimuth",
            ),
            (
                self.collar_dip_warning_tolerance_deg,
                self.collar_dip_error_tolerance_deg,
                "collar dip",
            ),
        )
        for warning, error, label in threshold_pairs:
            if (warning is None) != (error is None):
                raise ValueError(
                    "{} warning and error tolerances must be configured together".format(
                        label
                    )
                )
            if warning is not None:
                if not math.isfinite(warning) or not math.isfinite(error):
                    raise ValueError("{} tolerances must be finite".format(label))
                if warning < 0 or error < warning:
                    raise ValueError(
                        "{} tolerances must satisfy 0 <= warning <= error".format(
                            label
                        )
                    )
        if self.interval_length_tolerance_m is not None:
            if (
                not math.isfinite(self.interval_length_tolerance_m)
                or self.interval_length_tolerance_m < 0
            ):
                raise ValueError(
                    "interval length tolerance must be finite and non-negative"
                )


@dataclass(frozen=True)
class ValidationFinding:
    """One reproducible issue or informational observation in source data."""

    rule_id: str
    severity: str
    table: str
    row_number: Optional[int]
    hole_id: Optional[str]
    sample_id: Optional[str]
    field: Optional[str]
    observed_value: Optional[str]
    expected_condition: str
    source: Optional[str]
    blocking: bool
    requires_review: bool


@dataclass(frozen=True)
class RuleSummary:
    """Execution status and finding counts for one validation rule."""

    rule_id: str
    family: str
    severity: str
    status: str
    records_checked: int
    finding_count: int
    blocking_finding_count: int
    review_finding_count: int


@dataclass(frozen=True)
class ValidationReport:
    """Deterministic summaries and source-linked findings."""

    summaries: Tuple[RuleSummary, ...]
    findings: Tuple[ValidationFinding, ...]


@dataclass
class _Rule:
    family: str
    severity: str
    records_checked: int = 0
    findings: List[ValidationFinding] = field(default_factory=list)
    not_implemented: bool = False


def _decimal(value) -> Optional[Decimal]:
    if value is None or not str(value).strip():
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return number if number.is_finite() else None


def _value(row: SourceRow, column: str) -> Optional[str]:
    value = row.values.get(column)
    return None if value is None else str(value)


def _circular_difference_degrees(first: Decimal, second: Decimal) -> Decimal:
    difference = abs(first - second) % Decimal("360")
    return min(difference, Decimal("360") - difference)


class _Collector:
    def __init__(self):
        self.rules: Dict[str, _Rule] = {}

    def register(self, rule_id: str, family: str, severity: str) -> _Rule:
        if rule_id not in self.rules:
            self.rules[rule_id] = _Rule(family=family, severity=severity)
        return self.rules[rule_id]

    def add(
        self,
        rule_id: str,
        family: str,
        severity: str,
        table: str,
        row: Optional[SourceRow],
        expected_condition: str,
        field_name: Optional[str] = None,
        observed_value: Optional[str] = None,
        hole_id: Optional[str] = None,
        sample_id: Optional[str] = None,
    ):
        rule = self.register(rule_id, family, severity)
        if severity == ERROR:
            rule.severity = ERROR
        if row is not None:
            hole_id = hole_id or _value(row, "hole_id")
            sample_id = sample_id or _value(row, "sample_id")
        rule.findings.append(
            ValidationFinding(
                rule_id=rule_id,
                severity=severity,
                table=table,
                row_number=row.row_number if row is not None else None,
                hole_id=hole_id,
                sample_id=sample_id,
                field=field_name,
                observed_value=observed_value,
                expected_condition=expected_condition,
                source=row.source_file if row is not None else table,
                blocking=severity == ERROR,
                requires_review=severity in (WARNING, INFO),
            )
        )

    def not_implemented(self, rule_id: str, family: str, severity: str):
        rule = self.register(rule_id, family, severity)
        rule.not_implemented = True

    def report(self) -> ValidationReport:
        summaries = []
        all_findings = []
        for rule_id, rule in self.rules.items():
            findings = rule.findings
            if rule.not_implemented:
                status = NOT_IMPLEMENTED
            elif any(item.severity == ERROR for item in findings):
                status = FAIL
            elif any(item.severity == WARNING for item in findings):
                status = "WARNING"
            elif findings:
                status = INFO
            else:
                status = PASS
            summaries.append(
                RuleSummary(
                    rule_id=rule_id,
                    family=rule.family,
                    severity=rule.severity,
                    status=status,
                    records_checked=rule.records_checked,
                    finding_count=len(findings),
                    blocking_finding_count=sum(item.blocking for item in findings),
                    review_finding_count=sum(
                        item.requires_review for item in findings
                    ),
                )
            )
            all_findings.extend(findings)
        return ValidationReport(tuple(summaries), tuple(all_findings))


def _validate_table_schema(
    release: LoadedRelease, collector: _Collector
) -> Mapping[str, Mapping[str, str]]:
    dictionary = release.tables.get("data_dictionary.csv")
    declarations: Dict[str, Dict[str, str]] = defaultdict(dict)
    if dictionary is None:
        collector.add(
            "SCHEMA_DICTIONARY_PRESENT",
            "schema",
            ERROR,
            "data_dictionary.csv",
            None,
            "data_dictionary.csv is loaded",
        )
        return declarations

    expected_by_file: Dict[str, set] = defaultdict(set)
    for row in dictionary.rows:
        filename = _value(row, "file")
        column = _value(row, "column")
        if not filename or not column:
            collector.add(
                "SCHEMA_DICTIONARY_ROW",
                "schema",
                ERROR,
                dictionary.file_name,
                row,
                "file and column are non-empty",
                observed_value=str(dict(row.values)),
            )
            continue
        expected_by_file[filename].add(column)
        declarations[filename][column] = {
            "dtype": _value(row, "dtype") or "",
            "nullable": _value(row, "nullable") or "",
            "unit": _value(row, "unit") or "",
        }

    for filename, expected_columns in expected_by_file.items():
        table = release.tables.get(filename)
        if table is None:
            collector.add(
                "SCHEMA_TABLE_PRESENT",
                "schema",
                ERROR,
                filename,
                None,
                "dictionary-declared table is loaded",
            )
            continue
        missing = expected_columns - set(table.columns)
        extra = set(table.columns) - expected_columns
        collector.register("SCHEMA_COLUMNS_PRESENT", "schema", ERROR).records_checked += 1
        collector.register("SCHEMA_COLUMNS_DECLARED", "schema", WARNING).records_checked += 1
        for column in sorted(missing):
            collector.add(
                "SCHEMA_COLUMNS_PRESENT",
                "schema",
                ERROR,
                filename,
                None,
                "column declared in data_dictionary.csv is present",
                field_name=column,
            )
        for column in sorted(extra):
            collector.add(
                "SCHEMA_COLUMNS_DECLARED",
                "schema",
                WARNING,
                filename,
                None,
                "column is declared in data_dictionary.csv",
                field_name=column,
            )

    return declarations


def _validate_required_values_and_types(
    release: LoadedRelease,
    declarations: Mapping[str, Mapping[str, Mapping[str, str]]],
    collector: _Collector,
):
    for filename, table in release.tables.items():
        table_declarations = declarations.get(filename, {})
        for row in table.rows:
            for column in table.columns:
                declaration = table_declarations.get(column)
                if declaration is None:
                    continue
                raw_value = _value(row, column)
                if raw_value is None or not raw_value.strip():
                    if declaration["nullable"].lower() != "true":
                        collector.add(
                            "REQUIRED_VALUE_PRESENT",
                            "schema",
                            ERROR,
                            filename,
                            row,
                            "non-nullable declared field is non-empty",
                            field_name=column,
                            observed_value=raw_value,
                        )
                    continue

                declared_type = declaration["dtype"].lower()
                if declared_type in ("float", "integer", "number"):
                    number = _decimal(raw_value)
                    if number is None or (
                        declared_type == "integer"
                        and number != number.to_integral_value()
                    ):
                        collector.add(
                            "DECLARED_TYPE_VALID",
                            "schema",
                            ERROR,
                            filename,
                            row,
                            "value parses as declared {}".format(
                                declaration["dtype"]
                            ),
                            field_name=column,
                            observed_value=raw_value,
                        )
                elif declared_type == "string":
                    continue
                else:
                    collector.register(
                        "DECLARED_TYPE_VALID", "schema", ERROR
                    ).not_implemented = True


def _rows(release: LoadedRelease, filename: str) -> Tuple[SourceRow, ...]:
    table = release.tables.get(filename)
    return table.rows if table is not None else ()


def _validate_collar(release: LoadedRelease, collector: _Collector):
    rows = _rows(release, "collar.csv")
    collector.register("COLLAR_HOLE_ID_UNIQUE", "collar", ERROR).records_checked = len(rows)
    collector.register("COLLAR_NUMERIC_FIELDS_VALID", "collar", ERROR).records_checked = len(rows)
    collector.register("COLLAR_FINAL_DEPTH_POSITIVE", "collar", ERROR).records_checked = len(rows)
    collector.register("COLLAR_ANGLES_IN_RANGE", "collar", ERROR).records_checked = len(rows)
    seen = {}
    numeric_fields = ("x", "y", "z", "final_depth_m", "azimuth_deg", "dip_deg")
    for row in rows:
        hole_id = _value(row, "hole_id")
        if not hole_id:
            continue
        if hole_id in seen:
            collector.add(
                "COLLAR_HOLE_ID_UNIQUE",
                "collar",
                ERROR,
                "collar.csv",
                row,
                "hole_id occurs once in collar.csv",
                field_name="hole_id",
                observed_value=hole_id,
            )
        else:
            seen[hole_id] = row

        parsed = {}
        for column in numeric_fields:
            raw_value = _value(row, column)
            number = _decimal(raw_value)
            if number is None:
                collector.add(
                    "COLLAR_NUMERIC_FIELDS_VALID",
                    "collar",
                    ERROR,
                    "collar.csv",
                    row,
                    "field is a finite numeric value",
                    field_name=column,
                    observed_value=raw_value,
                )
            else:
                parsed[column] = number
        if "final_depth_m" in parsed and parsed["final_depth_m"] <= 0:
            collector.add(
                "COLLAR_FINAL_DEPTH_POSITIVE",
                "collar",
                ERROR,
                "collar.csv",
                row,
                "final_depth_m > 0 m",
                field_name="final_depth_m",
                observed_value=str(parsed["final_depth_m"]),
            )
        if "azimuth_deg" in parsed and "dip_deg" in parsed:
            azimuth = parsed["azimuth_deg"]
            dip = parsed["dip_deg"]
            if not (Decimal("0") <= azimuth < Decimal("360")):
                collector.add(
                    "COLLAR_ANGLES_IN_RANGE",
                    "collar",
                    ERROR,
                    "collar.csv",
                    row,
                    "azimuth_deg is in [0, 360) under project convention",
                    field_name="azimuth_deg",
                    observed_value=str(azimuth),
                )
            if not (Decimal("-90") <= dip <= Decimal("0")):
                collector.add(
                    "COLLAR_ANGLES_IN_RANGE",
                    "collar",
                    ERROR,
                    "collar.csv",
                    row,
                    "dip_deg is in [-90, 0] under project convention",
                    field_name="dip_deg",
                    observed_value=str(dip),
                )


def _validate_survey(
    release: LoadedRelease, config: ValidationConfig, collector: _Collector
):
    collar_rows = _rows(release, "collar.csv")
    collars = {
        _value(row, "hole_id"): row
        for row in collar_rows
        if _value(row, "hole_id")
    }
    survey_rows = _rows(release, "survey.csv")
    surveys_by_hole: Dict[str, List[SourceRow]] = defaultdict(list)
    for row in survey_rows:
        hole_id = _value(row, "hole_id")
        if hole_id:
            surveys_by_hole[hole_id].append(row)

    collector.register("SURVEY_DEPTH_VALID", "survey", ERROR).records_checked = len(survey_rows)
    collector.register("SURVEY_DEPTH_ORDERED", "survey", WARNING).records_checked = len(survey_rows)
    collector.register("SURVEY_DEPTH_WITHIN_FINAL", "survey", ERROR).records_checked = len(survey_rows)
    collector.register("SURVEY_ANGLES_IN_RANGE", "survey", ERROR).records_checked = len(survey_rows)
    collector.not_implemented(
        "SURVEY_ANGULAR_CHANGE_LIMIT", "survey", WARNING
    )
    collector.register("SURVEY_DUPLICATE_IDENTICAL", "survey", WARNING).records_checked = len(survey_rows)
    collector.register("SURVEY_DUPLICATE_CONTRADICTORY", "survey", ERROR).records_checked = len(survey_rows)
    collector.register("SURVEY_HOLE_HAS_STATION", "survey", WARNING).records_checked = len(collar_rows)
    collector.register("SURVEY_INITIAL_STATION_PRESENT", "survey", WARNING).records_checked = len(collar_rows)

    for row in survey_rows:
        hole_id = _value(row, "hole_id")
        depth = _decimal(_value(row, "depth_m"))
        if depth is None or depth < 0:
            collector.add(
                "SURVEY_DEPTH_VALID",
                "survey",
                ERROR,
                "survey.csv",
                row,
                "depth_m is finite and >= 0 m",
                field_name="depth_m",
                observed_value=_value(row, "depth_m"),
            )
        collar = collars.get(hole_id)
        final_depth = _decimal(_value(collar, "final_depth_m")) if collar else None
        if depth is not None and final_depth is not None and depth > final_depth:
            collector.add(
                "SURVEY_DEPTH_WITHIN_FINAL",
                "survey",
                ERROR,
                "survey.csv",
                row,
                "depth_m <= collar.final_depth_m",
                field_name="depth_m",
                observed_value=str(depth),
            )
        azimuth = _decimal(_value(row, "azimuth_deg"))
        dip = _decimal(_value(row, "dip_deg"))
        if azimuth is None or not (Decimal("0") <= azimuth < Decimal("360")):
            collector.add(
                "SURVEY_ANGLES_IN_RANGE",
                "survey",
                ERROR,
                "survey.csv",
                row,
                "azimuth_deg is finite and in [0, 360)",
                field_name="azimuth_deg",
                observed_value=_value(row, "azimuth_deg"),
            )
        if dip is None or not (Decimal("-90") <= dip <= Decimal("0")):
            collector.add(
                "SURVEY_ANGLES_IN_RANGE",
                "survey",
                ERROR,
                "survey.csv",
                row,
                "dip_deg is finite and in [-90, 0]",
                field_name="dip_deg",
                observed_value=_value(row, "dip_deg"),
            )

    for hole_id, rows in surveys_by_hole.items():
        valid_depth_rows = [
            (depth, row)
            for row in rows
            if (depth := _decimal(_value(row, "depth_m"))) is not None
        ]
        previous_depth = None
        for depth, row in valid_depth_rows:
            if previous_depth is not None and depth < previous_depth:
                collector.add(
                    "SURVEY_DEPTH_ORDERED",
                    "survey",
                    WARNING,
                    "survey.csv",
                    row,
                    "survey depth does not decrease in source row order within hole_id",
                    field_name="depth_m",
                    observed_value=str(depth),
                )
            previous_depth = depth

        station_groups: Dict[Decimal, List[SourceRow]] = defaultdict(list)
        for depth, row in valid_depth_rows:
            station_groups[depth].append(row)
        for depth, station_rows in station_groups.items():
            if len(station_rows) < 2:
                continue
            orientations = {
                (_decimal(_value(row, "azimuth_deg")), _decimal(_value(row, "dip_deg")))
                for row in station_rows
            }
            contradictory = len(orientations) > 1
            duplicate_rule = (
                "SURVEY_DUPLICATE_CONTRADICTORY"
                if contradictory
                else "SURVEY_DUPLICATE_IDENTICAL"
            )
            severity = ERROR if contradictory else WARNING
            expected = (
                "one azimuth/dip pair per hole_id and depth_m"
                if contradictory
                else "duplicate station has an identical azimuth/dip pair"
            )
            for duplicate_row in station_rows[1:]:
                collector.add(
                    duplicate_rule,
                    "survey",
                    severity,
                    "survey.csv",
                    duplicate_row,
                    expected,
                    field_name="depth_m",
                    observed_value=str(depth),
                )

    holes_with_survey = set(surveys_by_hole)
    for collar in collar_rows:
        hole_id = _value(collar, "hole_id")
        rows = surveys_by_hole.get(hole_id or "", [])
        if not rows:
            collector.add(
                "SURVEY_HOLE_HAS_STATION",
                "survey",
                WARNING,
                "collar.csv",
                collar,
                "collar hole_id has at least one survey station",
                field_name="hole_id",
                observed_value=hole_id,
            )
            continue
        if not any(_decimal(_value(row, "depth_m")) == 0 for row in rows):
            collector.add(
                "SURVEY_INITIAL_STATION_PRESENT",
                "survey",
                WARNING,
                "collar.csv",
                collar,
                "survey has a station at depth_m = 0",
                field_name="hole_id",
                observed_value=hole_id,
            )

    _validate_initial_orientation(
        collar_rows, surveys_by_hole, config, collector
    )


def _validate_initial_orientation(collars, surveys_by_hole, config, collector):
    for attribute, collar_field, tolerance_name, rule_id in (
        (
            "azimuth_deg",
            "azimuth_deg",
            "collar_azimuth",
            "SURVEY_COLLAR_AZIMUTH_MATCH",
        ),
        ("dip_deg", "dip_deg", "collar_dip", "SURVEY_COLLAR_DIP_MATCH"),
    ):
        warning_tolerance = getattr(
            config, tolerance_name + "_warning_tolerance_deg"
        )
        error_tolerance = getattr(config, tolerance_name + "_error_tolerance_deg")
        if warning_tolerance is None:
            collector.not_implemented(rule_id, "survey_collar_orientation", WARNING)
            continue
        collector.register(rule_id, "survey_collar_orientation", WARNING)
        for collar in collars:
            hole_id = _value(collar, "hole_id")
            initial_rows = [
                row
                for row in surveys_by_hole.get(hole_id or "", [])
                if _decimal(_value(row, "depth_m")) == 0
            ]
            if not initial_rows:
                continue
            collar_angle = _decimal(_value(collar, collar_field))
            survey_angle = _decimal(_value(initial_rows[0], attribute))
            if collar_angle is None or survey_angle is None:
                continue
            difference = (
                _circular_difference_degrees(collar_angle, survey_angle)
                if attribute == "azimuth_deg"
                else abs(collar_angle - survey_angle)
            )
            rule = collector.rules[rule_id]
            rule.records_checked += 1
            if difference > Decimal(str(error_tolerance)):
                collector.add(
                    rule_id,
                    "survey_collar_orientation",
                    ERROR,
                    "survey.csv",
                    initial_rows[0],
                    "angular difference from collar <= {} degree".format(
                        error_tolerance
                    ),
                    field_name=attribute,
                    observed_value=str(difference),
                    hole_id=hole_id,
                )
            elif difference > Decimal(str(warning_tolerance)):
                collector.add(
                    rule_id,
                    "survey_collar_orientation",
                    WARNING,
                    "survey.csv",
                    initial_rows[0],
                    "angular difference from collar <= {} degree".format(
                        warning_tolerance
                    ),
                    field_name=attribute,
                    observed_value=str(difference),
                    hole_id=hole_id,
                )


def _validate_relationship_ids(release: LoadedRelease, collector: _Collector):
    collar_rows = _rows(release, "collar.csv")
    collar_by_id = {
        _value(row, "hole_id"): row
        for row in collar_rows
        if _value(row, "hole_id")
    }
    for filename in (
        "survey.csv",
        "lithology.csv",
        "alteration.csv",
        "assay.csv",
        "density.csv",
    ):
        hole_rule = "REL_HOLE_IN_COLLAR"
        rows = _rows(release, filename)
        collector.register(hole_rule, "relationships", ERROR).records_checked += len(rows)
        for row in rows:
            hole_id = _value(row, "hole_id")
            if not hole_id or hole_id not in collar_by_id:
                collector.add(
                    hole_rule,
                    "relationships",
                    ERROR,
                    filename,
                    row,
                    "hole_id exists in collar.csv",
                    field_name="hole_id",
                    observed_value=hole_id,
                )
        for field_name, severity in (
            ("dataset_id", ERROR),
            ("project_id", ERROR),
            ("campaign_id", WARNING),
        ):
            rule_id = "REL_{}_MATCH".format(field_name.upper())
            collector.register(rule_id, "relationships", severity).records_checked += len(rows)
            for row in rows:
                collar = collar_by_id.get(_value(row, "hole_id"))
                if collar is None:
                    continue
                observed = _value(row, field_name)
                expected = _value(collar, field_name)
                if observed != expected:
                    collector.add(
                        rule_id,
                        "relationships",
                        severity,
                        filename,
                        row,
                        "{} equals collar.{}".format(field_name, field_name),
                        field_name=field_name,
                        observed_value=observed,
                    )

    assay_holes = {
        _value(row, "hole_id")
        for row in _rows(release, "assay.csv")
        if _value(row, "hole_id")
    }
    assay_coverage = collector.register(
        "COLLAR_HOLE_HAS_ASSAY", "relationships", INFO
    )
    assay_coverage.records_checked = len(collar_rows)
    for collar in collar_rows:
        hole_id = _value(collar, "hole_id")
        if hole_id and hole_id not in assay_holes:
            collector.add(
                "COLLAR_HOLE_HAS_ASSAY",
                "relationships",
                INFO,
                "collar.csv",
                collar,
                "assay presence is reported descriptively; no completeness requirement is declared",
                field_name="hole_id",
                observed_value=hole_id,
            )


def _validate_intervals(release: LoadedRelease, config, collector):
    collar_by_id = {
        _value(row, "hole_id"): row
        for row in _rows(release, "collar.csv")
        if _value(row, "hole_id")
    }
    for filename in ("lithology.csv", "alteration.csv", "assay.csv", "density.csv"):
        rows = _rows(release, filename)
        family = "intervals"
        if config.interval_length_tolerance_m is None:
            collector.not_implemented("INTERVAL_LENGTH_MATCH", family, ERROR)
        for rule_id, severity in (
            ("INTERVAL_ORDER_VALID", ERROR),
            ("INTERVAL_NONNEGATIVE", ERROR),
            ("INTERVAL_LENGTH_MATCH", ERROR),
            ("INTERVAL_WITHIN_FINAL_DEPTH", ERROR),
            ("INTERVAL_OVERLAP", WARNING),
            ("INTERVAL_GAP", INFO),
            ("INTERVAL_DUPLICATE", WARNING),
        ):
            collector.register(rule_id, family, severity).records_checked += len(rows)

        groups: Dict[str, List[Tuple[Decimal, Decimal, SourceRow]]] = defaultdict(list)
        for row in rows:
            start = _decimal(_value(row, "from_m"))
            end = _decimal(_value(row, "to_m"))
            length = _decimal(_value(row, "length_m"))
            if start is None or end is None:
                continue
            hole_id = _value(row, "hole_id") or ""
            if start >= end:
                collector.add(
                    "INTERVAL_ORDER_VALID",
                    family,
                    ERROR,
                    filename,
                    row,
                    "from_m < to_m",
                    field_name="from_m,to_m",
                    observed_value="{},{}".format(start, end),
                )
            if start < 0 or end < 0:
                collector.add(
                    "INTERVAL_NONNEGATIVE",
                    family,
                    ERROR,
                    filename,
                    row,
                    "from_m >= 0 m and to_m >= 0 m",
                    field_name="from_m,to_m",
                    observed_value="{},{}".format(start, end),
                )
            if config.interval_length_tolerance_m is None:
                pass
            elif length is not None:
                difference = abs((end - start) - length)
                if difference > Decimal(str(config.interval_length_tolerance_m)):
                    collector.add(
                        "INTERVAL_LENGTH_MATCH",
                        family,
                        ERROR,
                        filename,
                        row,
                        "abs((to_m - from_m) - length_m) <= {} m".format(
                            config.interval_length_tolerance_m
                        ),
                        field_name="length_m",
                        observed_value=str(difference),
                    )
            collar = collar_by_id.get(hole_id)
            final_depth = _decimal(_value(collar, "final_depth_m")) if collar else None
            if start < 0 or (final_depth is not None and end > final_depth):
                collector.add(
                    "INTERVAL_WITHIN_FINAL_DEPTH",
                    family,
                    ERROR,
                    filename,
                    row,
                    "0 m <= from_m < to_m <= collar.final_depth_m",
                    field_name="from_m,to_m",
                    observed_value="{},{}".format(start, end),
                )
            groups[hole_id].append((start, end, row))

        for hole_id, intervals in groups.items():
            intervals.sort(key=lambda item: (item[0], item[1], item[2].row_number))
            seen = set()
            previous_end = None
            for start, end, row in intervals:
                if (start, end) in seen:
                    collector.add(
                        "INTERVAL_DUPLICATE",
                        family,
                        WARNING,
                        filename,
                        row,
                        "interval bounds are unique within hole_id and table",
                        field_name="from_m,to_m",
                        observed_value="{},{}".format(start, end),
                    )
                seen.add((start, end))
                if previous_end is not None:
                    if start < previous_end:
                        collector.add(
                            "INTERVAL_OVERLAP",
                            family,
                            WARNING,
                            filename,
                            row,
                            "interval does not overlap the preceding covered interval",
                            field_name="from_m",
                            observed_value=str(start),
                        )
                    elif start > previous_end:
                        collector.add(
                            "INTERVAL_GAP",
                            family,
                            INFO,
                            filename,
                            row,
                            "interval starts at the preceding interval end",
                            field_name="from_m",
                            observed_value=str(start),
                        )
                previous_end = (
                    end if previous_end is None else max(previous_end, end)
                )

    for filename, id_column in (
        ("assay.csv", "sample_id"),
        ("density.csv", "density_sample_id"),
    ):
        rows = _rows(release, filename)
        rule_id = "SAMPLE_ID_UNIQUE"
        collector.register(rule_id, "intervals", ERROR).records_checked += len(rows)
        seen = set()
        for row in rows:
            value = _value(row, id_column)
            if not value:
                continue
            key = (filename, value)
            if key in seen:
                collector.add(
                    rule_id,
                    "intervals",
                    ERROR,
                    filename,
                    row,
                    "{} is unique within its table".format(id_column),
                    field_name=id_column,
                    observed_value=value,
                )
            seen.add(key)


def _validate_assays_and_density(release: LoadedRelease, collector: _Collector):
    for column in ("cu_pct", "mo_pct", "au_gt"):
        rule_id = "ASSAY_{}_NONNEGATIVE".format(column.upper())
        zero_rule = "ASSAY_{}_ZERO_RECORDED".format(column.upper())
        rows = _rows(release, "assay.csv")
        collector.register(rule_id, "assay", ERROR).records_checked = len(rows)
        collector.register(zero_rule, "assay", INFO).records_checked = len(rows)
        for row in rows:
            raw_value = _value(row, column)
            number = _decimal(raw_value)
            if number is None:
                continue
            if number < 0:
                collector.add(
                    rule_id,
                    "assay",
                    ERROR,
                    "assay.csv",
                    row,
                    "{} >= 0".format(column),
                    field_name=column,
                    observed_value=raw_value,
                )
            elif number == 0:
                collector.add(
                    zero_rule,
                    "assay",
                    INFO,
                    "assay.csv",
                    row,
                    "zero value is recorded; its semantics are not specified in the release",
                    field_name=column,
                    observed_value=raw_value,
                )

    rows = _rows(release, "density.csv")
    collector.register("DENSITY_POSITIVE", "density", ERROR).records_checked = len(rows)
    collector.not_implemented(
        "DENSITY_PLAUSIBILITY_RANGE", "density", WARNING
    )
    for row in rows:
        raw_value = _value(row, "density_t_m3")
        number = _decimal(raw_value)
        if number is not None and number <= 0:
            collector.add(
                "DENSITY_POSITIVE",
                "density",
                ERROR,
                "density.csv",
                row,
                "density_t_m3 > 0 t/m3",
                field_name="density_t_m3",
                observed_value=raw_value,
            )


def validate_release(
    release: LoadedRelease, config: Optional[ValidationConfig] = None
) -> ValidationReport:
    """Validate data in a loaded release and return summaries and findings.

    The function is read-only. Engineering tolerances are never inferred:
    orientation comparisons and interval-length checks remain
    NOT_IMPLEMENTED until their thresholds are supplied explicitly.
    """

    if config is None:
        config = ValidationConfig()
    collector = _Collector()
    declarations = _validate_table_schema(release, collector)
    _validate_required_values_and_types(release, declarations, collector)
    _validate_collar(release, collector)
    _validate_survey(release, config, collector)
    _validate_relationship_ids(release, collector)
    _validate_intervals(release, config, collector)
    _validate_assays_and_density(release, collector)
    return collector.report()
