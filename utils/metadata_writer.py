# utils/metadata_writer.py

import json
import os

import piexif
import tifffile

from utils.serialization import make_json_serializable

SUPPORTED_WRITE_EXTENSIONS = (".jpg", ".jpeg", ".tif", ".tiff")


def write_metadata_to_file(file_path, standardized_metadata):
    """
    Writes standardized metadata back into the image file.

    - JPG/JPEG: writes EXIF tags (Make, Model, Software, ImageDescription,
      DateTimeOriginal) via piexif, without re-encoding the image.
    - TIFF/TIF: writes the standardized metadata as a JSON string into the
      ImageDescription tag via tifffile, by re-saving the file in place.

    Raises ValueError for unsupported extensions, and re-raises any
    underlying I/O error so the caller can report it to the user.
    """
    ext = os.path.splitext(file_path)[1].lower()

    if ext in (".jpg", ".jpeg"):
        _write_jpg_metadata(file_path, standardized_metadata)
    elif ext in (".tif", ".tiff"):
        _write_tiff_metadata(file_path, standardized_metadata)
    else:
        raise ValueError(f"Writing metadata is not supported for files of type '{ext}'.")


def _write_jpg_metadata(file_path, standardized_metadata):
    try:
        exif_dict = piexif.load(file_path)
    except Exception:
        exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}

    description = json.dumps(make_json_serializable(standardized_metadata))

    exif_dict.setdefault("0th", {})
    exif_dict["0th"][piexif.ImageIFD.ImageDescription] = description.encode("utf-8")

    if standardized_metadata.get("CameraMake"):
        exif_dict["0th"][piexif.ImageIFD.Make] = str(standardized_metadata["CameraMake"]).encode("utf-8")
    if standardized_metadata.get("CameraModel"):
        exif_dict["0th"][piexif.ImageIFD.Model] = str(standardized_metadata["CameraModel"]).encode("utf-8")
    if standardized_metadata.get("Software"):
        exif_dict["0th"][piexif.ImageIFD.Software] = str(standardized_metadata["Software"]).encode("utf-8")

    if standardized_metadata.get("AcquisitionDate"):
        exif_dict.setdefault("Exif", {})
        exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = str(standardized_metadata["AcquisitionDate"]).encode("utf-8")

    exif_bytes = piexif.dump(exif_dict)
    piexif.insert(exif_bytes, file_path)


def _write_tiff_metadata(file_path, standardized_metadata):
    description = json.dumps(make_json_serializable(standardized_metadata))

    with tifffile.TiffFile(file_path) as tif:
        image_data = tif.asarray()

    tifffile.imwrite(file_path, image_data, description=description)
