# utils/thumbnail.py
#
# Generates a small preview image so a user can visually confirm they're
# looking at the right file. Kept Qt-free (returns PNG-encoded bytes) so
# it can be unit tested without a running QApplication; main.py loads the
# bytes into a QPixmap for display.

import io
import os

from PIL import Image, UnidentifiedImageError

# Formats Pillow can rasterize directly. TIFF here covers plain/OME/GeoTIFF —
# only the first page/frame is previewed for multi-page files.
THUMBNAIL_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}


def supports_thumbnail(file_path):
    return os.path.splitext(file_path)[1].lower() in THUMBNAIL_EXTENSIONS


def generate_thumbnail_bytes(file_path, size=(160, 160)):
    """
    Returns PNG-encoded bytes of a thumbnail for file_path, or None if the
    format isn't rasterizable by Pillow, the file is corrupt/unreadable, or
    the extension isn't in THUMBNAIL_EXTENSIONS (e.g. DICOM, FITS, HDF5,
    NetCDF, LIF, CZI — formats needing a dedicated reader beyond Pillow).
    """
    if not supports_thumbnail(file_path):
        return None

    try:
        with Image.open(file_path) as img:
            img.seek(0)  # first page/frame for multi-page/multi-frame files
            img = img.convert("RGB")
            img.thumbnail(size)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()
    except (OSError, UnidentifiedImageError, ValueError):
        return None
