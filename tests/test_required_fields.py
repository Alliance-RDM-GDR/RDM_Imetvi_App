# tests/test_required_fields.py

from metadata_profiles.required_fields_registry import (
    REQUIRED_FIELDS_REGISTRY,
    get_required_fields,
    compute_missing_fields,
)


def test_get_required_fields_known_format():
    fields = get_required_fields("TIFF", "Microscopy")
    assert "DimensionX" in fields
    assert "ObjectiveName" in fields


def test_get_required_fields_context_specific_format_without_context_is_empty():
    # TIFF's registry entry is nested per context (Microscopy vs
    # General / EXIF need very different fields) — omitting context_name
    # must not silently fall back to one of them.
    assert get_required_fields("TIFF") == []


def test_get_required_fields_context_specific_format_unknown_context():
    assert get_required_fields("TIFF", "Not A Real Context") == []


def test_get_required_fields_tiff_general_exif_context():
    fields = get_required_fields("TIFF", "General / EXIF")
    assert "CameraMake" in fields
    assert "ObjectiveName" not in fields


def test_get_required_fields_unknown_format_returns_empty():
    assert get_required_fields("HDF5") == []
    assert get_required_fields("SomeMadeUpFormat") == []


def test_compute_missing_fields_all_present():
    meta = {
        "DimensionX": "1024", "DimensionY": "1024",
        "PixelSizeX": "0.2", "PixelSizeY": "0.2",
        "BitDepth": "8", "ObjectiveName": "Plan Apo 20x",
        "NA": "0.75", "Magnification": "20",
    }
    assert compute_missing_fields("TIFF", meta) == []


def test_compute_missing_fields_detects_absent_key():
    meta = {
        "DimensionX": "1024", "DimensionY": "1024",
        "PixelSizeX": "0.2", "PixelSizeY": "0.2",
        "BitDepth": "8",
        # ObjectiveName, NA, Magnification absent
    }
    missing = compute_missing_fields("TIFF", meta, "Microscopy")
    assert set(missing) == {"ObjectiveName", "NA", "Magnification"}


def test_compute_missing_fields_tiff_general_exif_context():
    meta = {
        "DimensionX": "1024", "DimensionY": "1024",
        "AcquisitionDate": "", "CameraMake": "", "CameraModel": "Canon EOS",
    }
    missing = compute_missing_fields("TIFF", meta, "General / EXIF")
    assert set(missing) == {"AcquisitionDate", "CameraMake"}


def test_compute_missing_fields_treats_none_as_missing():
    meta = {"DimensionX": "1024", "DimensionY": None}
    missing = compute_missing_fields("PNG", meta)
    assert "DimensionY" in missing


def test_compute_missing_fields_treats_blank_string_as_missing():
    meta = {
        "DimensionX": "800", "DimensionY": "600",
        "AcquisitionDate": "   ", "CameraMake": "", "CameraModel": "Canon EOS",
    }
    missing = compute_missing_fields("JPG", meta)
    assert "AcquisitionDate" in missing
    assert "CameraMake" in missing
    assert "CameraModel" not in missing


def test_compute_missing_fields_unrequired_format_returns_empty():
    assert compute_missing_fields("HDF5", {"anything": "value"}) == []


def test_all_registered_formats_have_nonempty_field_lists():
    for fmt, fields in REQUIRED_FIELDS_REGISTRY.items():
        assert fields, f"{fmt} has an empty required-fields list"
