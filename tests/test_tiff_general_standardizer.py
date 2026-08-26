# tests/test_tiff_general_standardizer.py

from standardizers.tiff_general_standardizer import standardize_tiff_general_metadata


def test_standardize_tiff_general_maps_baseline_tags():
    raw_metadata = {
        "FilePath": "/path/to/figure1.tif",
        "DateTime": "2024:03:15 10:30:00",
        "ImageWidth": 2000,
        "ImageLength": 1500,
        "Make": "Canon",
        "Model": "EOS R5",
        "Software": "Adobe Photoshop",
        "Artist": "Jane Doe",
        "Copyright": "CC-BY 4.0",
        "ImageDescription": "Figure 1: sample cross-section",
        "XResolution": (300, 1),
        "YResolution": (300, 1),
    }

    result = standardize_tiff_general_metadata(raw_metadata)

    assert result["ImageName"] == "figure1.tif"
    assert result["AcquisitionDate"] == "2024:03:15 10:30:00"
    assert result["DimensionX"] == "2000"
    assert result["DimensionY"] == "1500"
    assert result["CameraMake"] == "Canon"
    assert result["CameraModel"] == "EOS R5"
    assert result["Software"] == "Adobe Photoshop"
    assert result["Artist"] == "Jane Doe"
    assert result["Copyright"] == "CC-BY 4.0"
    assert result["Description"] == "Figure 1: sample cross-section"
    assert result["ResolutionX"] == "300.0"
    assert result["ResolutionY"] == "300.0"


def test_standardize_tiff_general_handles_missing_fields():
    raw_metadata = {"FilePath": "scan.tif", "ImageWidth": 800, "ImageLength": 600}

    result = standardize_tiff_general_metadata(raw_metadata)

    assert result["ImageName"] == "scan.tif"
    assert result["DimensionX"] == "800"
    assert result["CameraMake"] == ""
    assert result["ResolutionX"] == ""


def test_standardize_tiff_general_handles_rational_resolution_zero_denominator():
    raw_metadata = {"FilePath": "x.tif", "XResolution": (300, 0)}
    result = standardize_tiff_general_metadata(raw_metadata)
    assert result["ResolutionX"] == ""


def test_standardize_tiff_general_handles_plain_numeric_resolution():
    # Some TIFF writers store resolution as a plain float, not a rational tuple
    raw_metadata = {"FilePath": "x.tif", "XResolution": 96.0}
    result = standardize_tiff_general_metadata(raw_metadata)
    assert result["ResolutionX"] == "96.0"
