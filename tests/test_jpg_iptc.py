# tests/test_jpg_iptc.py

from metadata_parsers.jpg_parser import parse_jpg_metadata
from standardizers.jpg_general_standardizer import standardize_jpg_general_metadata


def test_parse_jpg_extracts_iptc_fields(synthetic_jpg_with_iptc):
    _, raw_metadata = parse_jpg_metadata(synthetic_jpg_with_iptc)

    assert raw_metadata["IPTC_caption_abstract"] == "A test caption"
    assert raw_metadata["IPTC_keywords"] == ["test", "sample"]
    assert raw_metadata["IPTC_by-line"] == "Jane Doe"
    assert raw_metadata["IPTC_credit"] == "Test Lab"
    assert raw_metadata["IPTC_copyright_notice"] == "CC-BY 4.0"
    assert raw_metadata["IPTC_city"] == "Saskatoon"
    assert raw_metadata["IPTC_country_primary_location_name"] == "Canada"


def test_standardize_jpg_maps_iptc_fields(synthetic_jpg_with_iptc):
    _, raw_metadata = parse_jpg_metadata(synthetic_jpg_with_iptc)
    result = standardize_jpg_general_metadata(raw_metadata)

    assert result["Caption"] == "A test caption"
    assert result["Keywords"] == "test, sample"
    assert result["Byline"] == "Jane Doe"
    assert result["Credit"] == "Test Lab"
    assert result["IPTCCopyrightNotice"] == "CC-BY 4.0"
    assert result["City"] == "Saskatoon"
    assert result["Country"] == "Canada"
