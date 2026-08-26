# metadata_profiles/required_fields_registry.py
#
# Declares, per FORMAT_REGISTRY key, which standardized fields a curator
# expects a well-formed capture to have populated. Used to flag gaps at
# ingest time — a field a standard nominally covers (see
# standards_registry.py) but that this particular file happens to be
# missing, e.g. an objective name never entered into the acquisition
# software, or a JPEG saved without a camera model tag.
#
# Keyed by format (not application context) because two formats sharing a
# context can have very different standardized field sets — JPG and PNG
# both land in "General / EXIF" but JPG's fields come from EXIF/IPTC/XMP
# while PNG's come from text chunks, so the same required list wouldn't
# make sense for both.
#
# HDF5 is intentionally absent: its standardized output is a dataset
# inventory (a list, not a fixed set of scalar fields), so "missing field"
# checking doesn't apply the same way — see hdf5_general_standardizer.py.

REQUIRED_FIELDS_REGISTRY = {
    "TIFF": [
        "DimensionX", "DimensionY", "PixelSizeX", "PixelSizeY",
        "BitDepth", "ObjectiveName", "NA", "Magnification",
    ],
    "CZI": [
        "DimensionX", "DimensionY", "PixelSizeX", "PixelSizeY",
        "BitDepth", "ObjectiveName", "NA", "Magnification", "Channels",
    ],
    "OME-TIFF": [
        "DimensionX", "DimensionY", "PixelSizeX", "PixelSizeY",
        "PixelType", "Channels",
    ],
    "GeoTIFF": [
        "CRS_EPSG", "BoundingBox_MinX", "BoundingBox_MinY",
        "BoundingBox_MaxX", "BoundingBox_MaxY",
        "SpatialResolutionX", "SpatialResolutionY", "BandCount",
    ],
    "JPG": [
        "DimensionX", "DimensionY", "AcquisitionDate",
        "CameraMake", "CameraModel",
    ],
    "PNG": [
        "DimensionX", "DimensionY",
    ],
    "DICOM": [
        "Modality", "Manufacturer", "StudyDate",
        "DimensionX", "DimensionY", "PixelSpacingX", "PixelSpacingY",
    ],
    "FITS": [
        "Telescope", "Instrument", "ObservationDate",
        "DimensionX", "DimensionY",
    ],
    "LIF": [
        "DimensionX", "DimensionY", "PixelSizeX", "PixelSizeY",
        "NumChannels", "BitDepth",
    ],
    "NetCDF": [
        "Conventions", "DimensionCount", "VariableCount",
    ],
}


def get_required_fields(format_name):
    """Returns the list of required standardized field names for a format,
    or an empty list if the format has no declared requirements."""
    return REQUIRED_FIELDS_REGISTRY.get(format_name, [])


def compute_missing_fields(format_name, standardized_metadata):
    """
    Returns the subset of get_required_fields(format_name) that is absent
    from standardized_metadata, or present but empty/None/whitespace-only.
    """
    missing = []
    for key in get_required_fields(format_name):
        value = standardized_metadata.get(key)
        if value is None:
            missing.append(key)
        elif isinstance(value, str) and not value.strip():
            missing.append(key)
    return missing
