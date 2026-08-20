# tests/test_jpg_parser.py

from metadata_parsers.jpg_parser import parse_jpg_metadata


def test_parse_jpg_returns_text_and_dict(synthetic_jpg):
    text_report, raw_metadata = parse_jpg_metadata(synthetic_jpg)

    assert isinstance(text_report, str)
    assert isinstance(raw_metadata, dict)


def test_parse_jpg_extracts_expected_keys(synthetic_jpg):
    _, raw_metadata = parse_jpg_metadata(synthetic_jpg)

    assert raw_metadata["Make"] == "AcmeCam"
    assert raw_metadata["Model"] == "Model X"
    assert raw_metadata["Software"] == "PytestSuite"
    assert raw_metadata["DateTimeOriginal"] == "2026:01:01 10:00:00"
    assert raw_metadata["ImageWidth"] == 64
    assert raw_metadata["ImageLength"] == 48
    assert "GPSInfo" in raw_metadata


def test_parse_jpg_handles_missing_file_gracefully():
    text_report, raw_metadata = parse_jpg_metadata("does_not_exist.jpg")

    assert "Failed to read JPG file" in text_report
    assert raw_metadata["FilePath"] == "does_not_exist.jpg"
