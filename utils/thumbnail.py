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


def _aim_thumbnail_bytes(file_path, size):
    """
    Preview of a Scanco AIM volume: its middle axial slice, windowed to the
    1st-99.5th percentile of the slice. Reads one slice (~0.5 MB) from the
    volume, never the whole 0.5-2 GB. Returns None for compressed volumes
    (segmentations), unknown voxel types or any read failure.
    """
    try:
        import numpy as np
        from metadata_parsers.aim_parser import read_aim_header, describe_voxel_type

        hdr = read_aim_header(file_path)
        nx, ny, nz = hdr["Dimensions"]
        _, dtype, bpv, compressed = describe_voxel_type(hdr["TypeCode"], hdr["Dimensions"], hdr["DataBytes"])
        if dtype is None or compressed or hdr["FileSize"] < hdr["DataOffset"] + hdr["DataBytes"]:
            return None
        offset = hdr["DataOffset"] + (nz // 2) * nx * ny * bpv
        sl = np.fromfile(file_path, dtype=dtype, count=nx * ny, offset=offset).reshape(ny, nx)
        lo, hi = np.percentile(sl, (1.0, 99.5))
        if hi <= lo:
            hi = lo + 1
        img8 = (np.clip((sl.astype("float64") - lo) / (hi - lo), 0, 1) * 255).astype("uint8")
        img = Image.fromarray(img8)
        img.thumbnail(size)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return None


def generate_thumbnail_bytes(file_path, size=(160, 160)):
    """
    Returns PNG-encoded bytes of a thumbnail for file_path, or None if the
    format isn't rasterizable by Pillow, the file is corrupt/unreadable, or
    the extension isn't in THUMBNAIL_EXTENSIONS (e.g. DICOM, FITS, HDF5,
    NetCDF, LIF, CZI — formats needing a dedicated reader beyond Pillow).
    Scanco .aim volumes are handled separately (middle slice).
    """
    if os.path.splitext(file_path)[1].lower() == ".aim":
        return _aim_thumbnail_bytes(file_path, size)
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
