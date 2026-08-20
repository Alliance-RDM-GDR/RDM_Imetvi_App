# tests/test_tiff_parser.py

from metadata_parsers.tiff_parser import parse_tiff_metadata


def test_parse_tiff_returns_text_and_dict(synthetic_tiff):
    text_report, raw_metadata = parse_tiff_metadata(synthetic_tiff)

    assert isinstance(text_report, str)
    assert isinstance(raw_metadata, dict)


def test_parse_tiff_extracts_expected_keys(synthetic_tiff):
    _, raw_metadata = parse_tiff_metadata(synthetic_tiff)

    assert raw_metadata["ImageWidth"] == 32
    assert raw_metadata["ImageLength"] == 32
    assert "ImageDescription" in raw_metadata
    assert "ImageJ" in raw_metadata["ImageDescription"]
    assert raw_metadata["SoftwareHint"] == "ImageJ-based"


def test_parse_tiff_handles_missing_file_gracefully():
    text_report, raw_metadata = parse_tiff_metadata("does_not_exist.tiff")

    assert "Failed to read TIFF file" in text_report
    assert raw_metadata["FilePath"] == "does_not_exist.tiff"
