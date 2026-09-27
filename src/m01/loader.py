"""Load a manifest-declared exploration release without changing source files."""

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple


class ReleaseLoadError(Exception):
    """Raised when a declared release file cannot be loaded safely."""


@dataclass(frozen=True)
class SourceRow:
    """A source CSV record and its physical ending line number."""

    source_file: str
    row_number: int
    values: Mapping[str, Optional[str]]


@dataclass(frozen=True)
class RawTable:
    """CSV headers and records preserved as observed text values."""

    file_name: str
    columns: Tuple[str, ...]
    rows: Tuple[SourceRow, ...]


@dataclass(frozen=True)
class LoadedRelease:
    """Files and metadata loaded from one release directory."""

    raw_dir: Path
    manifest: Mapping[str, Any]
    tables: Mapping[str, RawTable]
    text_files: Mapping[str, str]


def _read_manifest(manifest_path: Path) -> Mapping[str, Any]:
    try:
        with manifest_path.open(encoding="utf-8-sig") as stream:
            manifest = json.load(stream)
    except FileNotFoundError as error:
        raise ReleaseLoadError(
            "Required release manifest is missing: {}".format(manifest_path)
        ) from error
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ReleaseLoadError(
            "Could not read release manifest {}: {}".format(manifest_path, error)
        ) from error

    if not isinstance(manifest, dict):
        raise ReleaseLoadError("Release manifest must contain a JSON object.")
    files = manifest.get("files")
    if not isinstance(files, list) or not all(
        isinstance(name, str) and name.strip() for name in files
    ):
        raise ReleaseLoadError(
            "Release manifest field 'files' must be a list of non-empty file names."
        )
    if len(files) != len(set(files)):
        raise ReleaseLoadError("Release manifest field 'files' contains duplicates.")
    for name in files:
        if name in (".", "..") or "/" in name or "\\" in name:
            raise ReleaseLoadError(
                "Manifest file entries must be names within data/raw/: {!r}".format(
                    name
                )
            )
    return manifest


def _read_csv(path: Path) -> RawTable:
    try:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream, strict=True)
            columns = reader.fieldnames
            if columns is None:
                raise ReleaseLoadError(
                    "CSV file has no header row: {}".format(path.name)
                )
            if any(not column.strip() for column in columns):
                raise ReleaseLoadError(
                    "CSV file contains an empty column name: {}".format(path.name)
                )
            if len(columns) != len(set(columns)):
                raise ReleaseLoadError(
                    "CSV file contains duplicate column names: {}".format(path.name)
                )

            rows = []
            for values in reader:
                if None in values:
                    raise ReleaseLoadError(
                        "CSV row has more fields than its header: {} line {}".format(
                            path.name, reader.line_num
                        )
                    )
                rows.append(
                    SourceRow(
                        source_file=path.name,
                        row_number=reader.line_num,
                        values=values,
                    )
                )
    except ReleaseLoadError:
        raise
    except (OSError, UnicodeError, csv.Error) as error:
        raise ReleaseLoadError(
            "Could not read CSV {}: {}".format(path.name, error)
        ) from error

    return RawTable(
        file_name=path.name,
        columns=tuple(columns),
        rows=tuple(rows),
    )


def load_release(raw_dir: Path) -> LoadedRelease:
    """Load every file listed by release_manifest.json.

    CSV cell values remain strings (or ``None`` when a row omits a trailing
    field). Empty cells remain empty strings. No data is coerced or repaired.
    """

    directory = Path(raw_dir)
    if not directory.is_dir():
        raise ReleaseLoadError(
            "Raw data directory does not exist or is not a directory: {}".format(
                directory
            )
        )

    manifest = _read_manifest(directory / "release_manifest.json")
    tables: Dict[str, RawTable] = {}
    text_files: Dict[str, str] = {}

    for file_name in manifest["files"]:
        path = directory / file_name
        if not path.is_file():
            raise ReleaseLoadError(
                "Manifest-declared release file is missing: {}".format(file_name)
            )
        if path.suffix.lower() == ".csv":
            tables[file_name] = _read_csv(path)
            continue
        try:
            text_files[file_name] = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as error:
            raise ReleaseLoadError(
                "Could not read release file {}: {}".format(file_name, error)
            ) from error

    return LoadedRelease(
        raw_dir=directory,
        manifest=manifest,
        tables=tables,
        text_files=text_files,
    )
