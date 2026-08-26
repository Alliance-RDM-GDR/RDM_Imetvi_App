# tests/test_tiff_parser.py

from metadata_parsers.tiff_parser import parse_tiff_metadata, _format_report_value


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


def test_format_report_value_leaves_short_values_untouched():
    assert _format_report_value(42) == "42"
    assert _format_report_value("hello") == "hello"
    assert _format_report_value((1, 2, 3)) == "(1, 2, 3)"


def test_format_report_value_truncates_long_sequences():
    values = tuple(range(500))
    formatted = _format_report_value(values)

    assert formatted.startswith("(0, 1, 2, 3, 4, 5, 6, 7, ...")
    assert "492 more" in formatted
    assert "500 total" in formatted
    # The full 500-item line must never appear in the truncated report
    assert "499" not in formatted


def test_format_report_value_boundary_not_truncated():
    # Exactly at the inline limit — should print in full, no truncation marker
    values = tuple(range(8))
    assert _format_report_value(values) == str(values)
