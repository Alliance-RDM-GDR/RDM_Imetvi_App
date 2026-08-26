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
# A format's entry is normally a flat list. When a format supports more
# than one application context (currently just TIFF — see FORMAT_REGISTRY
# in main.py), its entry is instead a {context_name: [fields]} dict, since
# the same format's raw tags map to very different standardized fields
# depending on which context is selected (a TIFF microscopy capture needs
# ObjectiveName/NA; a TIFF used as a general photo/scan doesn't have those
# at all). get_required_fields()/compute_missing_fields() accept an
# optional context_name and handle both shapes transparently.
#
# HDF5 is intentionally absent: its standardized output is a dataset
# inventory (a list, not a fixed set of scalar fields), so "missing field"
# checking doesn't apply the same way — see hdf5_general_standardizer.py.

REQUIRED_FIELDS_REGISTRY = {
    "TIFF": {
        "Microscopy": [
            "DimensionX", "DimensionY", "PixelSizeX", "PixelSizeY",
            "BitDepth", "ObjectiveName", "NA", "Magnification",
        ],
        "General / EXIF": [
            "DimensionX", "DimensionY", "AcquisitionDate",
            "CameraMake", "CameraModel",
        ],
    },
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
        "SpatialResolutionX", "SpatialResolutionY", "BandCount", "DataType",
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


def get_required_fields(format_name, context_name=None):
    """
    Returns the list of required standardized field names for a format, or
    an empty list if the format has no declared requirements. For a format
    whose registry entry is context-specific (currently only TIFF), pass
    context_name to select the right list — an unrecognized or omitted
    context_name returns an empty list for those formats rather than
    guessing which context's requirements apply.
    """
    entry = REQUIRED_FIELDS_REGISTRY.get(format_name, [])
    if isinstance(entry, dict):
        return entry.get(context_name, [])
    return entry


def compute_missing_fields(format_name, standardized_metadata, context_name=None):
    """
    Returns the subset of get_required_fields(format_name, context_name)
    that is absent from standardized_metadata, or present but
    empty/None/whitespace-only.
    """
    missing = []
    for key in get_required_fields(format_name, context_name):
        value = standardized_metadata.get(key)
        if value is None:
            missing.append(key)
        elif isinstance(value, str) and not value.strip():
            missing.append(key)
    return missing
