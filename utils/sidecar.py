# utils/sidecar.py
#
# Writes a standardized metadata sidecar (.json) next to the source image.
# The sidecar uses the same base name as the image, with a .json extension.
# This mirrors the convention used by QGIS, ArcGIS, and common data-deposit
# workflows (FRDR, Archivematica) where the record lives beside the file.

import json
import os

from utils.serialization import make_json_serializable


def sidecar_path_for(image_path):
    """Returns the expected sidecar path for a given image file."""
    base, _ = os.path.splitext(image_path)
    return base + ".json"


def write_sidecar(image_path, standardized_metadata):
    """
    Serializes standardized_metadata to a .json file beside image_path.

    Returns the path of the written file.
    Raises OSError / ValueError on failure.
    """
    out_path = sidecar_path_for(image_path)
    serializable = make_json_serializable(standardized_metadata)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=4, ensure_ascii=False)
    return out_path


def read_sidecar(image_path):
    """
    Reads and returns the sidecar dict for image_path, or None if it does
    not exist or cannot be parsed.
    """
    path = sidecar_path_for(image_path)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
