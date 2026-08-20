# tests/test_fits_parser.py

from metadata_parsers.fits_parser import parse_fits_metadata
from standardizers.fits_astronomy_standardizer import standardize_fits_astronomy_metadata


def test_parse_fits_extracts_expected_keys(synthetic_fits):
    text_report, raw_metadata = parse_fits_metadata(synthetic_fits)

    assert isinstance(text_report, str)
    assert raw_metadata["TELESCOP"] == "TestScope"
    assert raw_metadata["OBJECT"] == "M31"
    assert raw_metadata["NAXIS1"] == 20
    assert raw_metadata["CTYPE1"] == "RA---TAN"


def test_standardize_fits_astronomy_maps_fields(synthetic_fits):
    _, raw_metadata = parse_fits_metadata(synthetic_fits)
    result = standardize_fits_astronomy_metadata(raw_metadata)

    assert result["Telescope"] == "TestScope"
    assert result["Object"] == "M31"
    assert result["DimensionX"] == "20"
    assert result["WCS_RefValueX"] == "10.5"
    assert result["WCS_CTYPE1"] == "RA---TAN"


def test_parse_fits_handles_missing_file_gracefully():
    text_report, raw_metadata = parse_fits_metadata("does_not_exist.fits")

    assert "Failed to read FITS file" in text_report
    assert raw_metadata["FilePath"] == "does_not_exist.fits"
