# tests/test_czi_parser.py
#
# czifile has no write API for building a synthetic .czi fixture, so unit
# behavior is exercised directly against the pure-Python helper functions
# that do the unit conversion and sentinel handling — the parts that were
# silently wrong (pixel size off by 1e6, NA=-1 shown as if it were real).
# Standardizer tests use a representative raw_metadata dict instead of a
# real file, same approach as test_standardizers.py.

from metadata_parsers.czi_parser import _meters_to_micrometers, _clean_numerical_aperture
from standardizers.czi_microscopy_standardizer import standardize_czi_microscopy_metadata


# ── _meters_to_micrometers ───────────────────────────────────────────────────

def test_meters_to_micrometers_converts_zeiss_scaling_value():
    # Real value from a Zeiss CZI file's Scaling/Items/Distance[@Id='X']/Value
    # (stored in meters despite the sibling DefaultUnitFormat hint of "µm").
    result = _meters_to_micrometers("4.6623081780420383E-06")
    assert abs(float(result) - 4.6623081780420383) < 1e-6


def test_meters_to_micrometers_empty_input():
    assert _meters_to_micrometers("") == ""
    assert _meters_to_micrometers(None) == ""


def test_meters_to_micrometers_invalid_input():
    assert _meters_to_micrometers("not-a-number") == ""


# ── _clean_numerical_aperture ────────────────────────────────────────────────

def test_clean_numerical_aperture_keeps_valid_value():
    assert _clean_numerical_aperture("1.45") == "1.45"
    assert _clean_numerical_aperture("0.75") == "0.75"


def test_clean_numerical_aperture_drops_zeiss_sentinel():
    # Zeiss writes -1 for objectives with no NA registered in the instrument
    # database (seen on generic objectives like "Achromat S 1.0x").
    assert _clean_numerical_aperture("-1") == ""


def test_clean_numerical_aperture_drops_zero_and_other_nonpositive():
    assert _clean_numerical_aperture("0") == ""
    assert _clean_numerical_aperture("-0.5") == ""


def test_clean_numerical_aperture_empty_input():
    assert _clean_numerical_aperture("") == ""
    assert _clean_numerical_aperture(None) == ""


def test_clean_numerical_aperture_invalid_input():
    assert _clean_numerical_aperture("not-a-number") == ""


# ── standardize_czi_microscopy_metadata ──────────────────────────────────────

def _sample_raw_metadata(**overrides):
    base = {
        "FilePath": "sample.czi",
        "AcquisitionTime": "2024-01-01T12:00:00",
        "DimensionX": "1392",
        "DimensionY": "1038",
        "SizeZ": "5",
        "SizeT": "1",
        "BitDepth": "8",
        "PixelSizeX": "4.662308178042038",
        "PixelSizeY": "4.662308178042038",
        "PixelSizeZ": "1.0",
        "ObjectiveName": "Plan-Apochromat 20x",
        "NA": "0.8",
        "Magnification": "20",
        "MicroscopeName": "Axio Observer",
        "MicroscopeType": "Inverted",
        "DetectorName": "AxioCam IC",
        "DetectorModel": "AxioCamICc1",
        "LightSource": "HXP 120",
        "ContourType": "Rectangle",
        "Channels": [
            {"Name": "GFP", "ExcitationWavelength": "488", "EmissionWavelength": "509", "ExposureTime_sec": "0.19"},
        ],
    }
    base.update(overrides)
    return base


def test_standardize_czi_maps_corrected_pixel_size():
    result = standardize_czi_microscopy_metadata(_sample_raw_metadata())
    assert result["PixelSizeX"] == "4.662308178042038"


def test_standardize_czi_preserves_empty_na_from_sentinel_cleanup():
    # NA already cleaned to "" by the parser before reaching the
    # standardizer — verify the standardizer doesn't reintroduce a bogus
    # value and just passes the (already-clean) absence through.
    result = standardize_czi_microscopy_metadata(_sample_raw_metadata(NA=""))
    assert result["NA"] == ""


def test_standardize_czi_maps_rembi_fields():
    result = standardize_czi_microscopy_metadata(_sample_raw_metadata())

    assert result["ImageName"] == "sample.czi"
    assert result["DimensionX"] == "1392"
    assert result["SizeZ"] == "5"
    assert result["NumChannels"] == "1"
    assert result["ObjectiveName"] == "Plan-Apochromat 20x"
    assert result["NA"] == "0.8"
    assert result["Channels"][0]["Name"] == "GFP"
