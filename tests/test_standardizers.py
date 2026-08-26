# tests/test_standardizers.py

from standardizers.jpg_general_standardizer import standardize_jpg_general_metadata
from standardizers.geotiff_remote_sensing_standardizer import standardize_geotiff_remote_sensing_metadata
from standardizers.tiff_microscopy_standardizer import standardize_tiff_microscopy_metadata


def test_standardize_jpg_general_maps_fields():
    raw_metadata = {
        "FilePath": "/path/to/photo.jpg",
        "DateTimeOriginal": "2026:01:01 10:00:00",
        "ImageWidth": 64,
        "ImageLength": 48,
        "Make": "AcmeCam",
        "Model": "Model X",
        "GPSInfo": {
            1: "N", 2: ((52, 1), (0, 1), (0, 1)),
            3: "W", 4: ((106, 1), (0, 1), (0, 1)),
        },
    }

    result = standardize_jpg_general_metadata(raw_metadata)

    assert result["ImageName"] == "photo.jpg"
    assert result["CameraMake"] == "AcmeCam"
    assert result["CameraModel"] == "Model X"
    assert result["DimensionX"] == "64"
    assert result["DimensionY"] == "48"
    assert result["GPSLatitude"] == "52.0"
    assert result["GPSLongitude"] == "-106.0"


def test_standardize_geotiff_remote_sensing_maps_fields():
    raw_metadata = {
        "FilePath": "/path/to/scene.tif",
        "Driver": "GTiff",
        "CRS_EPSG": 4326,
        "CRS_WKT": "GEOGCS[...]",
        "BoundingBox": {"min_x": 0, "min_y": 0, "max_x": 10, "max_y": 10},
        "PixelSizeX": 1.0,
        "PixelSizeY": 1.0,
        "NoDataValue": None,
        "BandCount": 3,
        "BandDescriptions": ["red", "green", "blue"],
        "Width": 100,
        "Height": 100,
        "DataType": "uint16",
        "PixelInterpretation": "Area",
    }

    result = standardize_geotiff_remote_sensing_metadata(raw_metadata)

    assert result["ImageName"] == "scene.tif"
    assert result["CRS_EPSG"] == "4326"
    assert result["BandCount"] == "3"
    assert result["BoundingBox_MaxX"] == "10"
    assert result["DimensionX"] == "100"
    assert result["DataType"] == "uint16"
    assert result["PixelInterpretation"] == "Area"


def test_standardize_tiff_microscopy_handles_missing_fields():
    raw_metadata = {
        "FilePath": "/path/to/image.tif",
        "ImageWidth": 100,
        "ImageLength": 80,
        "BitsPerSample": 16,
    }

    result = standardize_tiff_microscopy_metadata(raw_metadata)

    assert result["ImageName"] == "image.tif"
    assert result["DimensionX"] == "100"
    assert result["DimensionY"] == "80"
    assert result["BitDepth"] == "16"
