# standardizers/geotiff_remote_sensing_standardizer.py

import os


def standardize_geotiff_remote_sensing_metadata(raw_metadata):
    """
    Standardizes raw GeoTIFF metadata (from rasterio) into an ISO 19115-aligned
    dictionary for remote sensing / geospatial context.
    """

    file_path = raw_metadata.get("FilePath", "")
    bbox = raw_metadata.get("BoundingBox", {}) or {}

    dict_report = {
        "ImageName": os.path.basename(file_path),
        "Driver": raw_metadata.get("Driver", ""),
        "CRS_EPSG": str(raw_metadata.get("CRS_EPSG", "")) if raw_metadata.get("CRS_EPSG") is not None else "",
        "CRS_WKT": raw_metadata.get("CRS_WKT", ""),
        "BoundingBox_MinX": str(bbox.get("min_x", "")),
        "BoundingBox_MinY": str(bbox.get("min_y", "")),
        "BoundingBox_MaxX": str(bbox.get("max_x", "")),
        "BoundingBox_MaxY": str(bbox.get("max_y", "")),
        "SpatialResolutionX": str(raw_metadata.get("PixelSizeX", "")),
        "SpatialResolutionY": str(raw_metadata.get("PixelSizeY", "")),
        "NoDataValue": str(raw_metadata.get("NoDataValue", "")) if raw_metadata.get("NoDataValue") is not None else "",
        "BandCount": str(raw_metadata.get("BandCount", "")),
        "BandDescriptions": raw_metadata.get("BandDescriptions", []),
        "DimensionX": str(raw_metadata.get("Width", "")),
        "DimensionY": str(raw_metadata.get("Height", "")),
        "DataType": raw_metadata.get("DataType", ""),
        "PixelInterpretation": raw_metadata.get("PixelInterpretation", ""),
    }

    return dict_report
