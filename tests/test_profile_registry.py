# tests/test_profile_registry.py

from metadata_profiles.profile_registry import get_profile, format_label, PROFILE_REGISTRY


def test_all_contexts_have_profile():
    expected = [
        "Microscopy", "Microscopy (OME)", "Remote Sensing",
        "General / EXIF", "Medical Imaging", "Astronomy", "General / HDF5",
    ]
    for ctx in expected:
        assert ctx in PROFILE_REGISTRY, f"Missing profile for context: {ctx}"


def test_format_label_returns_human_label_with_unit():
    profile = get_profile("Microscopy")
    assert format_label("DimensionX", profile) == "Image Width (pixels)"
    assert format_label("PixelSizeX", profile) == "Pixel Size X (µm)"
    assert format_label("NA", profile) == "Numerical Aperture"


def test_format_label_falls_back_to_raw_key():
    profile = get_profile("Microscopy")
    assert format_label("SomeUnknownKey", profile) == "SomeUnknownKey"


def test_format_label_geotiff():
    profile = get_profile("Remote Sensing")
    assert format_label("CRS_EPSG", profile) == "CRS (EPSG Code)"
    assert format_label("SpatialResolutionX", profile) == "Spatial Resolution X (CRS units)"


def test_format_label_fits():
    profile = get_profile("Astronomy")
    assert format_label("ExposureTime", profile) == "Exposure Time (sec)"
    assert format_label("WCS_RefValueX", profile) == "WCS Reference Value X (deg)"


def test_format_label_dicom():
    profile = get_profile("Medical Imaging")
    assert format_label("PixelSpacingX", profile) == "Pixel Spacing X (mm)"
    assert format_label("SliceThickness", profile) == "Slice Thickness (mm)"


def test_format_label_jpg_iptc_fields():
    profile = get_profile("General / EXIF")
    assert format_label("Caption", profile) == "Caption / Abstract"
    assert format_label("IPTCCopyrightNotice", profile) == "IPTC Copyright Notice"
    assert format_label("ResolutionX", profile) == "Resolution X (dpi)"


def test_format_label_png_fields():
    profile = get_profile("General / EXIF")
    assert format_label("FileSizeMB", profile) == "File Size (MB)"
    assert format_label("ColorMode", profile) == "Color Mode"


def test_format_label_hdf5():
    profile = get_profile("General / HDF5")
    assert format_label("DatasetCount", profile) == "Datasets"
    assert format_label("RootAttributeCount", profile) == "Root Attributes"
