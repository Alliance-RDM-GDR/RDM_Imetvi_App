# tests/test_fits_parser.py

import numpy as np
import pytest
from astropy.io import fits

from metadata_parsers.fits_parser import parse_fits_metadata
from metadata_profiles.profile_registry import get_profile
from metadata_profiles.required_fields_registry import compute_missing_fields
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


# ── Multi-extension, tables, compression, WCS ────────────────────────────

@pytest.fixture
def multi_extension_fits(tmp_path):
    """Empty primary + SCI image (CD-matrix WCS) + BINTABLE + ASCII TABLE."""
    primary = fits.PrimaryHDU()
    primary.header["TELESCOP"] = "MultiScope"
    primary.header["INSTRUME"] = "MEF-Cam"
    primary.header["DATE-OBS"] = "2026-02-02T01:02:03"
    primary.header["AUTHOR"] = "A. Observer"
    primary.header["ORIGIN"] = "Test Institute"
    primary.header["CREATOR"] = "pytest"
    primary.header["OBSERVER"] = "Dr. Star"
    primary.header["PROPOSID"] = "P-123"
    primary.header["TIMESYS"] = "UTC"
    primary.header["MJD-OBS"] = 61073.04
    primary.header["DATE-END"] = "2026-02-02T01:32:03"
    primary.header["HISTORY"] = "calibrated"
    primary.header["HISTORY"] = "stacked"
    primary.header["COMMENT"] = "synthetic test file"

    sci = fits.ImageHDU(np.zeros((30, 40), dtype=np.float32), name="SCI")
    sci.header["BUNIT"] = "electron/s"
    sci.header["CTYPE1"], sci.header["CTYPE2"] = "RA---TAN", "DEC--TAN"
    sci.header["CRVAL1"], sci.header["CRVAL2"] = 150.0, 2.0
    sci.header["CRPIX1"], sci.header["CRPIX2"] = 20.0, 15.0
    sci.header["CD1_1"], sci.header["CD1_2"] = -0.5 / 3600, 0.0     # 0.5 arcsec/pixel
    sci.header["CD2_1"], sci.header["CD2_2"] = 0.0, 0.5 / 3600
    sci.header["CUNIT1"] = sci.header["CUNIT2"] = "deg"
    sci.header["LONPOLE"], sci.header["LATPOLE"] = 180.0, 2.0

    cols = [
        fits.Column(name="RA", format="D", unit="deg", array=np.arange(5.0)),
        fits.Column(name="FLUX", format="E", unit="Jy", array=np.ones(5, dtype=np.float32)),
    ]
    catalog = fits.BinTableHDU.from_columns(cols, name="CATALOG")
    ascii_tbl = fits.TableHDU.from_columns(
        [fits.Column(name="ID", format="I4", array=np.arange(3))], name="LEGACY")

    path = tmp_path / "mef.fits"
    fits.HDUList([primary, sci, catalog, ascii_tbl]).writeto(str(path))
    return str(path)


def test_hdu_inventory_lists_every_hdu(multi_extension_fits):
    text, raw = parse_fits_metadata(multi_extension_fits)
    hdus = {h["Name"] or "PRIMARY": h for h in raw["HDUs"]}

    assert raw["HDUCount"] == 4 and raw["TableHDUCount"] == 2
    assert hdus["PRIMARY"]["Type"] == "IMAGE" and hdus["PRIMARY"]["Shape"] == []
    assert hdus["SCI"]["Shape"] == [40, 30] and hdus["SCI"]["DType"] == "float32"
    assert hdus["CATALOG"]["Type"] == "BINTABLE" and hdus["CATALOG"]["Rows"] == 5
    assert [(c["Name"], c["Unit"]) for c in hdus["CATALOG"]["Columns"]] == [("RA", "deg"), ("FLUX", "Jy")]
    assert hdus["LEGACY"]["Type"] == "TABLE" and hdus["LEGACY"]["ColumnCount"] == 1
    assert "CATALOG BINTABLE 5 rows" in text


def test_image_in_extension_supplies_dimensions_and_bitpix(multi_extension_fits):
    _, raw = parse_fits_metadata(multi_extension_fits)
    result = standardize_fits_astronomy_metadata(raw)

    assert raw["ScienceHDUIndex"] == 1
    assert result["DimensionX"] == "40" and result["DimensionY"] == "30"
    assert result["BitsPerPixel"] == "-32"          # not the empty primary's 8
    assert result["Telescope"] == "MultiScope"      # primary keys still win
    assert result["BrightnessUnit"] == "electron/s"
    assert result["WCS_CTYPE1"] == "RA---TAN"       # WCS keys found in the extension
    assert compute_missing_fields("FITS", result, "Astronomy") == []


def test_extra_keys_and_commentary_counts(multi_extension_fits):
    _, raw = parse_fits_metadata(multi_extension_fits)
    result = standardize_fits_astronomy_metadata(raw)

    assert raw["HistoryCardCount"] == 2 and raw["CommentCardCount"] == 1
    assert result["Author"] == "A. Observer" and result["Origin"] == "Test Institute"
    assert result["Creator"] == "pytest" and result["Observer"] == "Dr. Star"
    assert result["ProgramID"] == "P-123" and result["TimeSystem"] == "UTC"
    assert result["ObservationMJD"] == "61073.04" and result["ObservationEndDate"].startswith("2026-02-02")
    assert float(result["WCS_CD1_1"]) == pytest.approx(-0.5 / 3600) and result["WCS_UnitX"] == "deg"
    assert result["WCS_LonPole"] == "180.0" and result["WCS_LatPole"] == "2.0"


def test_wcs_validity_and_pixel_scale_in_arcsec(multi_extension_fits):
    _, raw = parse_fits_metadata(multi_extension_fits)
    result = standardize_fits_astronomy_metadata(raw)

    assert raw["WCSHasCelestial"] is True
    assert raw["PixelScaleXArcsec"] == pytest.approx(0.5, rel=1e-6)
    assert raw["PixelScaleYArcsec"] == pytest.approx(0.5, rel=1e-6)
    assert result["WCS_Valid"] == "yes" and result["WCS_PixelScaleXArcsec"] == "0.5"


def test_file_without_celestial_wcs_reports_invalid(tmp_path):
    plain = tmp_path / "plain.fits"
    fits.PrimaryHDU(np.zeros((5, 5))).writeto(str(plain))
    _, raw = parse_fits_metadata(str(plain))

    assert raw["WCSHasCelestial"] is False
    assert "PixelScaleXArcsec" not in raw
    assert standardize_fits_astronomy_metadata(raw)["WCS_Valid"] == "no"


def test_malformed_wcs_does_not_break_parsing(tmp_path):
    bad = fits.PrimaryHDU(np.zeros((5, 5)))
    bad.header["CTYPE1"], bad.header["CTYPE2"] = "RA---TAN", "DEC--TAN"
    bad.header["CD1_1"], bad.header["CD1_2"] = 0.0, 0.0     # singular matrix
    bad.header["CD2_1"], bad.header["CD2_2"] = 0.0, 0.0
    path = tmp_path / "bad_wcs.fits"
    bad.writeto(str(path))

    text, raw = parse_fits_metadata(str(path))

    assert "Failed to read FITS file" not in text
    assert raw["NAXIS1"] == 5
    assert isinstance(raw["WCSHasCelestial"], bool)


def test_compressed_image_hdu(tmp_path):
    data = (np.arange(400).reshape(20, 20) % 7).astype(np.int16)
    comp = fits.CompImageHDU(data, name="SCI", compression_type="RICE_1")
    comp.header["BUNIT"] = "adu"
    path = tmp_path / "comp.fits"
    fits.HDUList([fits.PrimaryHDU(), comp]).writeto(str(path))

    _, raw = parse_fits_metadata(str(path))
    result = standardize_fits_astronomy_metadata(raw)

    sci = raw["HDUs"][1]
    assert sci["Type"] == "COMPRESSED_IMAGE" and sci["Shape"] == [20, 20]
    assert raw["IsCompressed"] is True and raw["CompressionType"] == "RICE_1"
    assert result["Compression"] == "RICE_1"
    assert result["DimensionX"] == "20" and result["BrightnessUnit"] == "adu"


def test_unsigned_dtype_detected_from_bzero(tmp_path):
    path = tmp_path / "u16.fits"
    fits.PrimaryHDU(np.arange(4, dtype=np.uint16).reshape(2, 2)).writeto(str(path))
    _, raw = parse_fits_metadata(str(path))

    assert raw["HDUs"][0]["DType"] == "uint16"


def test_table_only_fits_still_parses(tmp_path):
    cols = [fits.Column(name="X", format="J", array=np.arange(3))]
    path = tmp_path / "table.fits"
    fits.HDUList([fits.PrimaryHDU(), fits.BinTableHDU.from_columns(cols, name="T")]).writeto(str(path))

    text, raw = parse_fits_metadata(str(path))

    assert "Failed to read FITS file" not in text
    assert raw["ScienceHDUIndex"] is None and raw["TableHDUCount"] == 1


def test_many_columns_are_capped_but_counted(tmp_path):
    cols = [fits.Column(name=f"C{i}", format="J", array=np.zeros(2, dtype=np.int32)) for i in range(80)]
    path = tmp_path / "wide.fits"
    fits.HDUList([fits.PrimaryHDU(), fits.BinTableHDU.from_columns(cols, name="W")]).writeto(str(path))

    _, raw = parse_fits_metadata(str(path))

    assert raw["HDUs"][1]["ColumnCount"] == 80 and len(raw["HDUs"][1]["Columns"]) == 50


def test_corrupt_fits_fails_gracefully(tmp_path):
    path = tmp_path / "junk.fits"
    path.write_bytes(b"this is not a FITS file at all" * 100)

    text, raw = parse_fits_metadata(str(path))

    assert "Failed to read FITS file" in text
    assert raw["FilePath"] == str(path)


def test_original_standardized_keys_unchanged_and_all_labelled(synthetic_fits, multi_extension_fits):
    original = {
        "ImageName", "Telescope", "Instrument", "Object", "ObservationDate", "ExposureTime", "Filter",
        "BitsPerPixel", "DimensionX", "DimensionY", "WCS_CTYPE1", "WCS_CTYPE2", "WCS_RefValueX",
        "WCS_RefValueY", "WCS_RefPixelX", "WCS_RefPixelY", "WCS_PixelScaleX", "WCS_PixelScaleY",
        "ReferenceFrame", "Equinox",
    }
    profile = get_profile("Astronomy")
    for path in (synthetic_fits, multi_extension_fits):
        _, raw = parse_fits_metadata(path)
        result = standardize_fits_astronomy_metadata(raw)
        assert original <= set(result)
        for key in result:
            assert key in profile, f"{key} has no label in the Astronomy profile"
        assert all(isinstance(v, str) for v in result.values())   # CSV-friendly, like before
