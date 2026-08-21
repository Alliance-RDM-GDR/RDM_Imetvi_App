# tests/test_curation_flags.py

import shutil
from utils.curation_flags import compute_curation_flags


def _make_result(file_path, report="", meta=None):
    return (file_path, report, meta or {})


def test_duplicate_flagged_when_files_identical(synthetic_jpg, tmp_path):
    copy_path = str(tmp_path / "copy.jpg")
    shutil.copy2(synthetic_jpg, copy_path)

    results = [
        _make_result(synthetic_jpg),
        _make_result(copy_path),
    ]
    flags_by_path, checksums = compute_curation_flags(results)

    assert "DUPLICATE" in flags_by_path[synthetic_jpg]
    assert "DUPLICATE" in flags_by_path[copy_path]
    assert checksums[synthetic_jpg] == checksums[copy_path]


def test_no_duplicate_for_unique_files(synthetic_jpg, synthetic_tiff):
    results = [_make_result(synthetic_jpg), _make_result(synthetic_tiff)]
    flags_by_path, _ = compute_curation_flags(results)

    assert "DUPLICATE" not in flags_by_path[synthetic_jpg]
    assert "DUPLICATE" not in flags_by_path[synthetic_tiff]


def test_gps_flag_on_jpg_with_gps(synthetic_jpg):
    # synthetic_jpg fixture has GPS EXIF tags; expose them in the metadata dict
    meta = {"GPSLatitude": "52.0", "GPSLongitude": "-106.0"}
    results = [_make_result(synthetic_jpg, meta=meta)]
    flags_by_path, _ = compute_curation_flags(results)

    assert "HAS_GPS_DATA" in flags_by_path[synthetic_jpg]


def test_no_gps_flag_when_absent(synthetic_tiff):
    results = [_make_result(synthetic_tiff, meta={"DimensionX": "32"})]
    flags_by_path, _ = compute_curation_flags(results)

    assert "HAS_GPS_DATA" not in flags_by_path[synthetic_tiff]


def test_dimension_outlier_flagged(synthetic_jpg, synthetic_tiff, tmp_path):
    # Two files with same dims + one outlier
    copy1 = str(tmp_path / "a.jpg")
    copy2 = str(tmp_path / "b.jpg")
    shutil.copy2(synthetic_jpg, copy1)
    shutil.copy2(synthetic_jpg, copy2)

    results = [
        _make_result(copy1, meta={"DimensionX": "64", "DimensionY": "48"}),
        _make_result(copy2, meta={"DimensionX": "64", "DimensionY": "48"}),
        _make_result(synthetic_tiff, meta={"DimensionX": "32", "DimensionY": "32"}),
    ]
    flags_by_path, _ = compute_curation_flags(results)

    assert "DIMENSION_OUTLIER" in flags_by_path[synthetic_tiff]
    assert "DIMENSION_OUTLIER" not in flags_by_path[copy1]


def test_md5_checksum_computed(synthetic_jpg):
    results = [_make_result(synthetic_jpg)]
    _, checksums = compute_curation_flags(results)

    assert checksums[synthetic_jpg] is not None
    assert len(checksums[synthetic_jpg]) == 32  # MD5 hex digest


def test_lossy_tiff_flag_via_meta(synthetic_tiff):
    meta = {"Compression": "7", "CompressionWarning": "JPEG detected"}
    results = [_make_result(synthetic_tiff, meta=meta)]
    flags_by_path, _ = compute_curation_flags(results)

    assert "LOSSY_TIFF" in flags_by_path[synthetic_tiff]
