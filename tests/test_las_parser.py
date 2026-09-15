# tests/test_las_parser.py
#
# Unlike LIF/CZI, laspy can write files, so these tests build real
# synthetic .las fixtures rather than mocking the reader.

import numpy as np
import pytest

laspy = pytest.importorskip("laspy")
pyproj = pytest.importorskip("pyproj")

from metadata_parsers.las_parser import parse_las_metadata, _point_format_description
from standardizers.las_lidar_standardizer import standardize_las_lidar_metadata


def _make_las(path, point_format=3, version="1.4", with_crs=True, n_points=50):
    header = laspy.LasHeader(point_format=point_format, version=version)
    if with_crs:
        header.add_crs(pyproj.CRS.from_epsg(26920))  # NAD83 / UTM zone 20N
    header.generating_software = "IMetVi test suite"

    las = laspy.LasData(header)
    rng = np.random.default_rng(42)
    las.x = rng.uniform(441938, 452301, n_points)
    las.y = rng.uniform(4949061, 4956488, n_points)
    las.z = rng.uniform(0, 50, n_points)
    las.write(str(path))


# ── _point_format_description ────────────────────────────────────────────────

def test_point_format_description_known_ids():
    assert "RGB" in _point_format_description(2)
    assert "GPS time" in _point_format_description(1)
    assert "NIR" in _point_format_description(8)


def test_point_format_description_unknown_id():
    assert "Format 42" in _point_format_description(42)


# ── parse_las_metadata ────────────────────────────────────────────────────────

def test_parse_las_extracts_header_fields(tmp_path):
    las_path = tmp_path / "sample.las"
    _make_las(las_path, point_format=3, n_points=100)

    text_report, raw_metadata = parse_las_metadata(str(las_path))

    assert raw_metadata["LASVersion"] == "1.4"
    assert raw_metadata["PointFormatID"] == 3
    assert raw_metadata["PointCount"] == 100
    assert raw_metadata["GeneratingSoftware"] == "IMetVi test suite"
    assert "Point Count: 100" in text_report


def test_parse_las_extracts_bounding_box(tmp_path):
    las_path = tmp_path / "sample.las"
    _make_las(las_path)

    _, raw_metadata = parse_las_metadata(str(las_path))

    assert 441938 <= raw_metadata["MinX"] <= 452301
    assert 441938 <= raw_metadata["MaxX"] <= 452301
    assert raw_metadata["MinX"] <= raw_metadata["MaxX"]
    assert raw_metadata["MinZ"] <= raw_metadata["MaxZ"]


def test_parse_las_extracts_crs_when_present(tmp_path):
    las_path = tmp_path / "with_crs.las"
    _make_las(las_path, with_crs=True)

    _, raw_metadata = parse_las_metadata(str(las_path))

    assert raw_metadata["CRS_EPSG"] == 26920
    assert "26920" in raw_metadata["CRS_WKT"] or "UTM" in raw_metadata["CRS_WKT"]


def test_parse_las_handles_missing_crs_gracefully(tmp_path):
    las_path = tmp_path / "no_crs.las"
    _make_las(las_path, with_crs=False)

    text_report, raw_metadata = parse_las_metadata(str(las_path))

    assert raw_metadata["CRS_EPSG"] is None
    assert raw_metadata["CRS_WKT"] == ""
    assert "Not found in header" in text_report


def test_parse_las_handles_missing_file():
    text_report, raw_metadata = parse_las_metadata("does_not_exist.las")

    assert "Failed to read LAS/LAZ file" in text_report
    assert "Error" in raw_metadata


# ── standardize_las_lidar_metadata ────────────────────────────────────────────

def test_standardize_las_maps_rembi_fields(tmp_path):
    las_path = tmp_path / "sample.las"
    _make_las(las_path, point_format=1, n_points=250)

    _, raw_metadata = parse_las_metadata(str(las_path))
    result = standardize_las_lidar_metadata(raw_metadata)

    assert result["ImageName"] == "sample.las"
    assert result["LASVersion"] == "1.4"
    assert result["PointCount"] == "250"
    assert result["CRS_EPSG"] == "26920"
    assert "GPS time" in result["PointFormatDescription"]


def test_standardize_las_handles_missing_crs():
    raw_metadata = {
        "FilePath": "no_crs.las",
        "LASVersion": "1.2",
        "PointFormatDescription": "Core (no color, no GPS time)",
        "PointCount": 10,
        "CRS_EPSG": None,
        "CRS_WKT": "",
        "MinX": 0.0, "MinY": 0.0, "MinZ": 0.0,
        "MaxX": 1.0, "MaxY": 1.0, "MaxZ": 1.0,
        "GeneratingSoftware": "",
        "CreationDate": "",
        "FileSizeMB": 0.01,
    }
    result = standardize_las_lidar_metadata(raw_metadata)

    assert result["CRS_EPSG"] == ""
    assert result["CRS_WKT"] == ""
