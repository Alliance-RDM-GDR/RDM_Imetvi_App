# metadata_parsers/las_parser.py
#
# Extracts metadata from LiDAR point cloud files (.las, .laz) via laspy.
# Adapted from CUR_Res_CurationTools/Scripts/Inspect_LAS_Script.R: reads
# only the header/VLRs (fast — does not decompress point data), reporting
# LAS version, point format, point count, 3D bounding box, embedded CRS,
# and generating software.

import os
from collections import Counter

import numpy as np

try:
    import laspy
    _LASPY_AVAILABLE = True
except ImportError:
    _LASPY_AVAILABLE = False

# What each LAS Point Data Format ID stores, per the ASPRS LAS spec.
_POINT_FORMAT_DESCRIPTIONS = {
    0: "Core (no color, no GPS time)",
    1: "Core + GPS time",
    2: "Core + RGB color",
    3: "Core + GPS time + RGB color",
    6: "Core + GPS time (LAS 1.4 extended)",
    7: "Core + GPS time + RGB (LAS 1.4 extended)",
    8: "Core + GPS time + RGB + NIR (LAS 1.4 extended)",
}

# ASPRS standard point classification codes (LAS 1.4, R15). Codes 19-63 are
# reserved and 64-255 are user-definable — both fall back to a generic label.
_CLASSIFICATION_NAMES = {
    0: "Created, never classified",
    1: "Unclassified",
    2: "Ground",
    3: "Low Vegetation",
    4: "Medium Vegetation",
    5: "High Vegetation",
    6: "Building",
    7: "Low Point (Noise)",
    8: "Reserved / Model Key-Point",
    9: "Water",
    10: "Rail",
    11: "Road Surface",
    12: "Reserved (Overlap, legacy)",
    13: "Wire — Guard (Shield)",
    14: "Wire — Conductor (Phase)",
    15: "Transmission Tower",
    16: "Wire-Structure Connector (Insulator)",
    17: "Bridge Deck",
    18: "High Noise",
}

# Points-per-chunk when scanning full point records for analyze_las_point_data()
# — keeps memory bounded on very large point clouds instead of loading every
# point at once.
_POINT_CHUNK_SIZE = 2_000_000


def _point_format_description(fmt_id):
    return _POINT_FORMAT_DESCRIPTIONS.get(fmt_id, f"Format {fmt_id} (see LAS spec)")


def _classification_name(code):
    if code in _CLASSIFICATION_NAMES:
        return _CLASSIFICATION_NAMES[code]
    if 19 <= code <= 63:
        return f"Class {code} (reserved)"
    return f"Class {code} (user-definable)"


def parse_las_metadata(file_path, application=None):
    text_lines = [f"LAS/LAZ Metadata Report for {os.path.basename(file_path)}"]
    raw_metadata = {"FilePath": file_path}

    if not _LASPY_AVAILABLE:
        msg = "laspy is not installed. Run: pip install laspy"
        text_lines.append(msg)
        raw_metadata["Error"] = msg
        return "\n".join(text_lines), raw_metadata

    try:
        with laspy.open(file_path) as f:
            header = f.header

            raw_metadata["FileSizeMB"] = round(os.path.getsize(file_path) / 1024 ** 2, 3)
            raw_metadata["LASVersion"] = f"{header.version.major}.{header.version.minor}"
            raw_metadata["PointFormatID"] = header.point_format.id
            raw_metadata["PointFormatDescription"] = _point_format_description(header.point_format.id)
            raw_metadata["PointCount"] = header.point_count
            raw_metadata["MinX"], raw_metadata["MinY"], raw_metadata["MinZ"] = (float(v) for v in header.mins)
            raw_metadata["MaxX"], raw_metadata["MaxY"], raw_metadata["MaxZ"] = (float(v) for v in header.maxs)
            raw_metadata["GeneratingSoftware"] = header.generating_software or ""
            raw_metadata["CreationDate"] = str(header.creation_date) if header.creation_date else ""

            # CRS: laspy reads whichever VLR the file uses (GeoTIFF-key style
            # or LAS 1.4 OGC WKT) and returns a pyproj CRS — or None if the
            # file has neither, which is common and not itself an error (the
            # coordinate system may be documented separately, e.g. a README).
            crs_wkt = ""
            crs_epsg = None
            try:
                crs = header.parse_crs()
                if crs is not None:
                    crs_wkt = crs.to_wkt()
                    crs_epsg = crs.to_epsg()
            except Exception:
                pass
            raw_metadata["CRS_WKT"] = crs_wkt
            raw_metadata["CRS_EPSG"] = crs_epsg

            text_lines.append(f"LAS Version: {raw_metadata['LASVersion']}")
            text_lines.append(f"Point Format: {raw_metadata['PointFormatDescription']}")
            text_lines.append(f"Point Count: {raw_metadata['PointCount']}")
            text_lines.append(
                f"Extent — X: {raw_metadata['MinX']:.2f} to {raw_metadata['MaxX']:.2f} | "
                f"Y: {raw_metadata['MinY']:.2f} to {raw_metadata['MaxY']:.2f} | "
                f"Z: {raw_metadata['MinZ']:.2f} to {raw_metadata['MaxZ']:.2f}"
            )
            text_lines.append(f"CRS: {crs_wkt[:150] if crs_wkt else 'Not found in header'}")
            text_lines.append(f"Generating Software: {raw_metadata['GeneratingSoftware']}")
            text_lines.append(f"Creation Date: {raw_metadata['CreationDate']}")

    except Exception as e:
        msg = f"Failed to read LAS/LAZ file: {str(e)}"
        text_lines.append(msg)
        raw_metadata["Error"] = msg

    return "\n".join(text_lines), raw_metadata


def analyze_las_point_data(file_path):
    """
    Reads the full point records (in bounded-size chunks, so memory stays
    flat regardless of point count) to compute statistics the header alone
    cannot provide: point classification breakdown, scan angle range, GPS
    time range (only for point formats that store it), and a flight-line
    count (distinct point_source_id values).

    This is deliberately NOT part of parse_las_metadata() / the standard
    load path — decompressing and scanning every point is much slower than
    the header-only read, so it's offered as a separate, on-demand action
    (main.py's "Analyze Point Classification" button) rather than run
    automatically on every file load or folder batch.

    Sensor model and flying height are NOT included: neither the LAS/LAZ
    header nor its point records store acquisition-platform parameters —
    those live in external flight/mission logs, not in the point cloud
    file itself, so there's nothing here to extract.

    Returns a dict, or {"Error": <message>} on failure.
    """
    if not _LASPY_AVAILABLE:
        return {"Error": "laspy is not installed. Run: pip install laspy"}

    try:
        classification_counts = Counter()
        scan_angle_min = scan_angle_max = None
        gps_time_min = gps_time_max = None
        flight_line_ids = set()
        has_gps_time = False

        with laspy.open(file_path) as f:
            dim_names = {d.name for d in f.header.point_format.dimensions}
            has_gps_time = "gps_time" in dim_names
            scan_angle_field = "scan_angle" if "scan_angle" in dim_names else "scan_angle_rank"
            gps_time_type = f.header.global_encoding.gps_time_type if hasattr(f.header, "global_encoding") else None

            for chunk in f.chunk_iterator(_POINT_CHUNK_SIZE):
                # classification (and, on legacy point formats, scan_angle_rank)
                # come back as SubFieldView / packed-field wrappers rather than
                # plain ndarrays — np.asarray() normalizes either case.
                classification_counts.update(np.asarray(chunk.classification).tolist())

                angles = getattr(chunk, scan_angle_field, None)
                if angles is not None and len(angles) > 0:
                    angles = np.asarray(angles)
                    chunk_min, chunk_max = float(angles.min()), float(angles.max())
                    scan_angle_min = chunk_min if scan_angle_min is None else min(scan_angle_min, chunk_min)
                    scan_angle_max = chunk_max if scan_angle_max is None else max(scan_angle_max, chunk_max)

                if has_gps_time and len(chunk.gps_time) > 0:
                    gps_time = np.asarray(chunk.gps_time)
                    chunk_min, chunk_max = float(gps_time.min()), float(gps_time.max())
                    gps_time_min = chunk_min if gps_time_min is None else min(gps_time_min, chunk_min)
                    gps_time_max = chunk_max if gps_time_max is None else max(gps_time_max, chunk_max)

                flight_line_ids.update(np.asarray(chunk.point_source_id).tolist())

        return {
            "ClassificationCounts": {
                _classification_name(code): count
                for code, count in classification_counts.items()
            },
            "ScanAngleMin": scan_angle_min,
            "ScanAngleMax": scan_angle_max,
            "HasGPSTime": has_gps_time,
            "GPSTimeMin": gps_time_min,
            "GPSTimeMax": gps_time_max,
            "GPSTimeType": (
                ("GPS Week Time" if gps_time_type == 0 else "Standard GPS Time (Adjusted)")
                if has_gps_time and gps_time_type is not None
                else None
            ),
            "FlightLineCount": len(flight_line_ids),
        }

    except Exception as e:
        return {"Error": f"Failed to analyze LAS/LAZ point data: {str(e)}"}
