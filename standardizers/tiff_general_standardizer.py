# standardizers/tiff_general_standardizer.py
#
# Standardizes a plain TIFF's baseline tags for the "General / EXIF"
# context — TIFF used for general photographs, scans, or illustrations
# (e.g. a figure exported for a paper) rather than a microscopy capture.
#
# TIFF's baseline tags (DateTime, Artist, Copyright, Make/Model,
# resolution) are the EXIF-equivalent fields available without a
# microscopy-specific schema. This app's TIFF parser does not extract
# IPTC or XMP blocks (unlike the JPEG path), so those fields are simply
# absent here rather than populated — see standards_registry.py's
# "General / EXIF" entry for the documented coverage caveat.

import os


def _resolution_value(value):
    """XResolution/YResolution arrive from tifffile as a (numerator, denominator) rational tuple."""
    if isinstance(value, tuple) and len(value) == 2:
        if not value[1]:
            return ""
        try:
            return str(value[0] / value[1])
        except (TypeError, ZeroDivisionError):
            return ""
    return str(value) if value else ""


def standardize_tiff_general_metadata(raw_metadata):
    file_path = raw_metadata.get("FilePath", "")

    return {
        "ImageName": os.path.basename(file_path),
        "AcquisitionDate": raw_metadata.get("DateTime", ""),
        "DimensionX": str(raw_metadata.get("ImageWidth", "")),
        "DimensionY": str(raw_metadata.get("ImageLength", "")),
        "CameraMake": raw_metadata.get("Make", ""),
        "CameraModel": raw_metadata.get("Model", ""),
        "Software": raw_metadata.get("Software", ""),
        "Artist": raw_metadata.get("Artist", ""),
        "Copyright": raw_metadata.get("Copyright", ""),
        "Description": raw_metadata.get("ImageDescription", ""),
        "ResolutionX": _resolution_value(raw_metadata.get("XResolution")),
        "ResolutionY": _resolution_value(raw_metadata.get("YResolution")),
    }
