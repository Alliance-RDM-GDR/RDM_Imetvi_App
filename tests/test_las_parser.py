# tests/test_las_parser.py
#
# Unlike LIF/CZI, laspy can write files, so these tests build real
# synthetic .las fixtures rather than mocking the reader.

import numpy as np
import pytest

laspy = pytest.importorskip("laspy")
pyproj = pytest.importorskip("pyproj")

from metadata_parsers.las_parser import (
    parse_las_metadata,
    analyze_las_point_data,
    _point_format_description,
    _classification_name,
)
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


# ── _classification_name ─────────────────────────────────────────────────────

def test_classification_name_known_codes():
    assert _classification_name(2) == "Ground"
    assert _classification_name(6) == "Building"


def test_classification_name_reserved_and_user_definable():
    assert "reserved" in _classification_name(30)
    assert "user-definable" in _classification_name(100)


# ── analyze_las_point_data ────────────────────────────────────────────────────

def _make_las_with_points(path, point_format, classifications, scan_angles=None,
                           gps_times=None, point_source_ids=None, version="1.4"):
    header = laspy.LasHeader(point_format=point_format, version=version)
    las = laspy.LasData(header)
    n = len(classifications)
    rng = np.random.default_rng(0)
    las.x = rng.uniform(0, 100, n)
    las.y = rng.uniform(0, 100, n)
    las.z = rng.uniform(0, 20, n)
    las.classification = np.array(classifications)

    scan_angle_field = "scan_angle" if "scan_angle" in {d.name for d in header.point_format.dimensions} else "scan_angle_rank"
    if scan_angles is not None:
        setattr(las, scan_angle_field, np.array(scan_angles))

    if gps_times is not None:
        las.gps_time = np.array(gps_times)

    las.point_source_id = np.array(point_source_ids) if point_source_ids is not None else np.ones(n, dtype=int)

    las.write(str(path))


def test_analyze_las_point_data_classification_breakdown(tmp_path):
    path = tmp_path / "points.las"
    _make_las_with_points(
        path, point_format=3,
        classifications=[2, 2, 2, 6, 6, 1],
        scan_angles=[100, -200, 300, -400, 500, -600],
        gps_times=[10.0, 20.0, 30.0, 40.0, 50.0, 60.0],
        point_source_ids=[1, 1, 2, 2, 3, 3],
    )

    result = analyze_las_point_data(str(path))

    assert result["ClassificationCounts"]["Ground"] == 3
    assert result["ClassificationCounts"]["Building"] == 2
    assert result["ClassificationCounts"]["Unclassified"] == 1
    assert result["FlightLineCount"] == 3


def test_analyze_las_point_data_scan_angle_range(tmp_path):
    path = tmp_path / "points.las"
    _make_las_with_points(
        path, point_format=6,
        classifications=[1, 1, 1],
        scan_angles=[-1000, 500, 2000],
    )

    result = analyze_las_point_data(str(path))

    assert result["ScanAngleMin"] == -1000.0
    assert result["ScanAngleMax"] == 2000.0


def test_analyze_las_point_data_gps_time_present_for_extended_format(tmp_path):
    path = tmp_path / "points.las"
    _make_las_with_points(
        path, point_format=6,
        classifications=[1, 1, 1],
        gps_times=[100.5, 200.25, 50.0],
    )

    result = analyze_las_point_data(str(path))

    assert result["HasGPSTime"] is True
    assert result["GPSTimeMin"] == 50.0
    assert result["GPSTimeMax"] == 200.25
    assert result["GPSTimeType"] is not None


def test_analyze_las_point_data_gps_time_absent_for_legacy_format_without_it(tmp_path):
    path = tmp_path / "points.las"
    _make_las_with_points(
        path, point_format=2, version="1.2",
        classifications=[2, 3, 9],
    )

    result = analyze_las_point_data(str(path))

    assert result["HasGPSTime"] is False
    assert result["GPSTimeMin"] is None
    assert result["GPSTimeMax"] is None
    assert result["GPSTimeType"] is None


def test_analyze_las_point_data_handles_missing_file():
    result = analyze_las_point_data("does_not_exist.las")
    assert "Error" in result
