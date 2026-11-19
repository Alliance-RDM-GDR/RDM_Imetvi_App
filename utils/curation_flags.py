# utils/curation_flags.py
#
# Curation intelligence adapted from CUR_Res_CurationTools/Scripts/Inspect_Images_Script.R
# and Inspect_LAS_Script.R.
# Flags: DUPLICATE (MD5), CORRUPT (parser error), HAS_GPS_DATA (privacy risk),
#        DIMENSION_OUTLIER (deviates from dataset mode), LOSSY_TIFF (JPEG-in-TIFF),
#        NO_CRS_FOUND (georeferenced context reports no embedded CRS),
#        INCOMPLETE_DUMP / UNDOCUMENTED_VARIABLES / RESTART_RECORDS (simulation output),
#        BIDS_TEMPLATE_METADATA / BIDS_DATASET_INCOMPLETE / NIFTI_NO_SFORM (neuroimaging/BIDS),
#        AIM_TRUNCATED / AIM_HX_BROKEN_LINK (Scanco micro-CT).

import hashlib
import os
from collections import Counter

# Files above this size are not hashed here: this runs on the UI thread for a
# single file, and simulation cubes reach several GB each (minutes of reading).
# Whole-file fixity for such data belongs to the dataset's own manifest.
MAX_MD5_BYTES = 1 << 30

# Per-extension override for formats whose files are routinely large: a Scanco
# micro-CT volume is 0.5-2 GB, so hashing a folder of them would read tens of GB.
MAX_MD5_BYTES_BY_EXT = {".aim": 64 << 20}


def _compute_md5(file_path):
    h = hashlib.md5()
    try:
        limit = MAX_MD5_BYTES_BY_EXT.get(os.path.splitext(file_path)[1].lower(), MAX_MD5_BYTES)
        if os.path.getsize(file_path) > limit:
            return None
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


def _lacks_crs(standardized_metadata):
    """
    True when a context that reports CRS_WKT at all (GeoTIFF, NetCDF, LAS)
    has it empty — i.e. no embedded coordinate reference system. Checking
    for key *presence* first means this never fires for formats that don't
    report CRS_WKT in the first place (e.g. microscopy contexts).
    """
    return "CRS_WKT" in standardized_metadata and not (standardized_metadata.get("CRS_WKT") or "").strip()


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

        # NO_CRS_FOUND — georeferenced context (GeoTIFF/NetCDF/LAS) with no
        # embedded coordinate system; common for LAS/LAZ specifically
        if _lacks_crs(meta):
            flags.append("NO_CRS_FOUND")

        # Simulation output (PPMstar): raw cube blocks are headerless, so a
        # dump missing sibling files or its variables.json can't be used as-is.
        if meta.get("DumpComplete") == "no":
            flags.append("INCOMPLETE_DUMP")
        if meta.get("VariablesDocumented") == "no":
            flags.append("UNDOCUMENTED_VARIABLES")
        if (meta.get("DuplicateDumpRecords") or 0) > 0:
            flags.append("RESTART_RECORDS")

        # Standards-based suggestions (BIDS / NIfTI / OME-NGFF) may raise a
        # curation flag of their own, e.g. BIDS_TEMPLATE_METADATA.
        for sug in meta.get("_Suggestions") or []:
            flag = sug.get("Flag") if isinstance(sug, dict) else None
            if flag and flag not in flags:
                flags.append(flag)

        flags_by_path[file_path] = flags

    return flags_by_path, checksums
