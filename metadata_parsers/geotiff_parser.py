# metadata_parsers/geotiff_parser.py

import os

from metadata_parsers.tiff_parser import parse_tiff_metadata


def is_geotiff(file_path):
    """Returns True if the TIFF file has CRS/geotransform information."""
    try:
        import rasterio
        with rasterio.open(file_path) as ds:
            return ds.crs is not None
    except Exception:
        return False


def parse_geotiff_metadata(file_path, application=None):
    """
    Extracts geospatial metadata from a GeoTIFF using rasterio.
    Falls back to the regular TIFF parser when no CRS/geotransform is found.

    Returns:
        - text_report: A string report of raw metadata, line by line.
        - raw_metadata: A dictionary with metadata key-value pairs.
    """
    text_lines = [f"GeoTIFF Metadata Report for {os.path.basename(file_path)}"]
    raw_metadata = {
        "FilePath": file_path
    }

    try:
        import rasterio

        with rasterio.open(file_path) as ds:
            if ds.crs is None:
                text_lines.append("No CRS found — falling back to standard TIFF parser.")
                fallback_text, fallback_raw = parse_tiff_metadata(file_path, application=application)
                return fallback_text + "\n" + "\n".join(text_lines), fallback_raw

            crs = ds.crs
            bounds = ds.bounds
            transform = ds.transform

            raw_metadata["Driver"] = ds.driver
            raw_metadata["CRS_EPSG"] = crs.to_epsg()
            raw_metadata["CRS_WKT"] = crs.to_wkt()
            raw_metadata["BoundingBox"] = {
                "min_x": bounds.left,
                "min_y": bounds.bottom,
                "max_x": bounds.right,
                "max_y": bounds.top,
            }
            raw_metadata["PixelSizeX"] = abs(transform.a)
            raw_metadata["PixelSizeY"] = abs(transform.e)
            raw_metadata["NoDataValue"] = ds.nodata
            raw_metadata["BandCount"] = ds.count
            raw_metadata["BandDescriptions"] = list(ds.descriptions)
            raw_metadata["Width"] = ds.width
            raw_metadata["Height"] = ds.height

            for key, value in raw_metadata.items():
                if key == "FilePath":
                    continue
                text_lines.append(f"{key}: {value}")

    except Exception as e:
        text_lines.append(f"Failed to read GeoTIFF file: {str(e)}")
        text_lines.append("Falling back to standard TIFF parser.")
        fallback_text, fallback_raw = parse_tiff_metadata(file_path, application=application)
        return fallback_text + "\n" + "\n".join(text_lines), fallback_raw

    return "\n".join(text_lines), raw_metadata
