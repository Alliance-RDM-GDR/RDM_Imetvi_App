# tests/test_geotiff_parser.py

from metadata_parsers.geotiff_parser import is_geotiff, parse_geotiff_metadata


def test_non_georeferenced_tiff_is_not_geotiff(synthetic_tiff):
    assert is_geotiff(synthetic_tiff) is False


def test_parse_geotiff_falls_back_to_tiff_parser(synthetic_tiff):
    text_report, raw_metadata = parse_geotiff_metadata(synthetic_tiff)

    assert isinstance(text_report, str)
    assert raw_metadata["ImageWidth"] == 32
    assert raw_metadata["ImageLength"] == 32


def test_parse_geotiff_with_real_crs(tmp_path):
    rasterio = __import__("rasterio")
    from rasterio.transform import from_origin

    file_path = tmp_path / "geo.tif"
    transform = from_origin(0, 10, 1, 1)

    import numpy as np

    data = np.zeros((10, 10), dtype=np.uint8)
    with rasterio.open(
        str(file_path), "w",
        driver="GTiff", height=10, width=10, count=1,
        dtype=data.dtype, crs="EPSG:4326", transform=transform,
    ) as dst:
        dst.write(data, 1)

    assert is_geotiff(str(file_path)) is True

    text_report, raw_metadata = parse_geotiff_metadata(str(file_path))
    assert raw_metadata["CRS_EPSG"] == 4326
    assert raw_metadata["BandCount"] == 1
    assert raw_metadata["PixelSizeX"] == 1
    assert raw_metadata["PixelSizeY"] == 1
