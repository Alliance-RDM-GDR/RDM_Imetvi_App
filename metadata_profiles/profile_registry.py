# metadata_profiles/profile_registry.py
#
# Maps each application context name to its display profile dict.
# A profile dict maps raw standardized keys → {"label": str, "unit": str|None}.
# render_metadata() in main.py consults this to show human-readable labels.

from metadata_profiles.tiff_microscopy_profile import REMBI_TIFF_MICROSCOPY_PROFILE
from metadata_profiles.ome_microscopy_profile import OME_MICROSCOPY_PROFILE
from metadata_profiles.geotiff_remote_sensing_profile import GEOTIFF_REMOTE_SENSING_PROFILE
from metadata_profiles.jpg_general_profile import JPG_GENERAL_PROFILE
from metadata_profiles.dicom_medical_profile import DICOM_MEDICAL_PROFILE
from metadata_profiles.fits_astronomy_profile import FITS_ASTRONOMY_PROFILE

# HDF5 and PNG profiles are compact enough to define inline here.
HDF5_GENERAL_PROFILE = {
    "FilePath":           {"label": "File Path",               "unit": None},
    "ObjectCount":        {"label": "Total Objects",           "unit": None},
    "DatasetCount":       {"label": "Datasets",                "unit": None},
    "GroupCount":         {"label": "Groups",                  "unit": None},
    "RootAttributeCount": {"label": "Root Attributes",         "unit": None},
    "Datasets":           {"label": "Dataset Inventory",       "unit": None},
    "CurationRisks":      {"label": "Curation Risks",          "unit": None},
    # Common CF-Convention root attributes
    "Conventions":        {"label": "Conventions",             "unit": None},
    "institution":        {"label": "Institution",             "unit": None},
    "title":              {"label": "Title",                   "unit": None},
    "history":            {"label": "Processing History",      "unit": None},
    "source":             {"label": "Source",                  "unit": None},
}

PNG_GENERAL_PROFILE = {
    "FilePath":    {"label": "File Path",     "unit": None},
    "ImageWidth":  {"label": "Image Width",   "unit": "pixels"},
    "ImageHeight": {"label": "Image Height",  "unit": "pixels"},
    "DimensionX":  {"label": "Image Width",   "unit": "pixels"},
    "DimensionY":  {"label": "Image Height",  "unit": "pixels"},
    "ColorMode":   {"label": "Color Mode",    "unit": None},
    "BitDepth":    {"label": "Bit Depth",     "unit": "bit"},
    "ResolutionX": {"label": "Resolution X",  "unit": "dpi"},
    "ResolutionY": {"label": "Resolution Y",  "unit": "dpi"},
    "FileSizeMB":  {"label": "File Size",     "unit": "MB"},
    "Author":      {"label": "Author",        "unit": None},
    "Copyright":   {"label": "Copyright",     "unit": None},
    "CreationTime":{"label": "Creation Time", "unit": None},
    "Software":    {"label": "Software",      "unit": None},
    "Description": {"label": "Description",   "unit": None},
    "Comment":     {"label": "Comment",       "unit": None},
    "Title":       {"label": "Title",         "unit": None},
    "Source":      {"label": "Source",        "unit": None},
}

PROFILE_REGISTRY = {
    "Microscopy":       REMBI_TIFF_MICROSCOPY_PROFILE,
    "Microscopy (OME)": OME_MICROSCOPY_PROFILE,
    "Remote Sensing":   GEOTIFF_REMOTE_SENSING_PROFILE,
    "General / EXIF":   JPG_GENERAL_PROFILE,
    "Medical Imaging":  DICOM_MEDICAL_PROFILE,
    "Astronomy":        FITS_ASTRONOMY_PROFILE,
    "General / HDF5":   HDF5_GENERAL_PROFILE,
}

# PNG shares the General / EXIF context; PNG-specific keys are added here
# so they also resolve to human labels when a PNG is loaded.
PROFILE_REGISTRY["General / EXIF"] = {**JPG_GENERAL_PROFILE, **PNG_GENERAL_PROFILE}


def get_profile(context_name):
    """Returns the profile dict for a context, or an empty dict if not registered."""
    return PROFILE_REGISTRY.get(context_name, {})


def format_label(key, profile):
    """
    Returns a display string for a metadata key using the profile.
    Format: "Human Label (unit)" when unit is present, "Human Label" otherwise.
    Falls back to the raw key name if not in the profile.
    """
    entry = profile.get(key)
    if not entry:
        return key
    label = entry.get("label", key)
    unit  = entry.get("unit")
    return f"{label} ({unit})" if unit else label
