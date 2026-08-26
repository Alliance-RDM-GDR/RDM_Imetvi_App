# utils/curation_flags.py
#
# Curation intelligence adapted from CUR_Res_CurationTools/Scripts/Inspect_Images_Script.R
# Flags: DUPLICATE (MD5), CORRUPT (parser error), HAS_GPS_DATA (privacy risk),
#        DIMENSION_OUTLIER (deviates from dataset mode), LOSSY_TIFF (JPEG-in-TIFF).

import hashlib
from collections import Counter


def _compute_md5(file_path):
    h = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def _mode(values):
    """Returns the most common non-None value, or None if empty."""
    counts = Counter(v for v in values if v is not None)
    return counts.most_common(1)[0][0] if counts else None


def _has_gps(standardized_metadata):
    for k, v in standardized_metadata.items():
        if "gps" not in k.lower() and k not in {"GPSLatitude", "GPSLongitude", "GPS_Latitude", "GPS_Longitude"}:
            continue
        if v is None:
            continue
        if isinstance(v, str) and not v.strip():
            continue
        return True
    return False


def _dimensions(standardized_metadata):
    """Returns (width_int, height_int) or None if not parseable."""
    for w_key in ("DimensionX", "Width", "ImageWidth", "NAXIS1"):
        for h_key in ("DimensionY", "Height", "ImageLength", "NAXIS2"):
            try:
                w = int(standardized_metadata[w_key])
                h = int(standardized_metadata[h_key])
                return (w, h)
            except (KeyError, TypeError, ValueError):
                continue
    return None


def compute_curation_flags(results):
    """
    Computes per-file curation flags from a batch of parsed results.

    Parameters
    ----------
    results : list of (file_path, text_report, standardized_metadata)

    Returns
    -------
    flags_by_path : dict  {file_path: list[str]}
    checksums     : dict  {file_path: str | None}
    """
    # --- MD5 checksums ---
    checksums = {fp: _compute_md5(fp) for fp, _, _ in results}
    checksum_counts = Counter(v for v in checksums.values() if v)

    # --- Dimension mode (for outlier detection) ---
    dims = [_dimensions(meta) for _, _, meta in results]
    mode_dim = _mode(dims)

    flags_by_path = {}
    for i, (file_path, text_report, meta) in enumerate(results):
        flags = []

        # DUPLICATE — same MD5 as another file in the batch
        cs = checksums.get(file_path)
        if cs and checksum_counts[cs] > 1:
            flags.append("DUPLICATE")

        # CORRUPT — parser reported a read failure
        report_lower = text_report.lower()
        if "failed to read" in report_lower or ("error:" in report_lower and i == 0):
            flags.append("CORRUPT")

        # HAS_GPS_DATA — privacy risk; field present in standardized metadata
        if _has_gps(meta):
            flags.append("HAS_GPS_DATA")

        # DIMENSION_OUTLIER — deviates from dataset-wide mode
        dim = dims[i]
        if mode_dim and dim and dim != mode_dim:
            flags.append("DIMENSION_OUTLIER")

        # LOSSY_TIFF — JPEG compression embedded in TIFF container
        if "CompressionWarning" in meta or (
            meta.get("Compression") in ("6", "7", 6, 7)
        ):
            flags.append("LOSSY_TIFF")

        flags_by_path[file_path] = flags

    return flags_by_path, checksums
