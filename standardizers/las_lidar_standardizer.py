# standardizers/las_lidar_standardizer.py

import os


def standardize_las_lidar_metadata(raw_metadata):
    """
    Standardizes raw LAS/LAZ metadata into an ISO 19115-aligned dictionary
    for the point cloud / LiDAR remote sensing context. CRS fields mirror
    GeoTIFF's naming (CRS_EPSG/CRS_WKT/BoundingBox_*) since both target the
    same standard, but CRS is treated as optional here — unlike GeoTIFF,
    a LAS file with no embedded CRS is common and still a valid, useful
    point cloud (see curation_flags.py's NO_CRS_FOUND check).
    """

    file_path = raw_metadata.get("FilePath", "")
    crs_epsg = raw_metadata.get("CRS_EPSG")

    return {
        "ImageName": os.path.basename(file_path),
        "LASVersion": raw_metadata.get("LASVersion", ""),
        "PointFormatDescription": raw_metadata.get("PointFormatDescription", ""),
        "PointCount": str(raw_metadata.get("PointCount", "")),
        "CRS_EPSG": str(crs_epsg) if crs_epsg is not None else "",
        "CRS_WKT": raw_metadata.get("CRS_WKT", ""),
        "BoundingBox_MinX": str(raw_metadata.get("MinX", "")),
        "BoundingBox_MinY": str(raw_metadata.get("MinY", "")),
        "BoundingBox_MinZ": str(raw_metadata.get("MinZ", "")),
        "BoundingBox_MaxX": str(raw_metadata.get("MaxX", "")),
        "BoundingBox_MaxY": str(raw_metadata.get("MaxY", "")),
        "BoundingBox_MaxZ": str(raw_metadata.get("MaxZ", "")),
        "GeneratingSoftware": raw_metadata.get("GeneratingSoftware", ""),
        "CreationDate": raw_metadata.get("CreationDate", ""),
        "FileSizeMB": str(raw_metadata.get("FileSizeMB", "")),
    }
