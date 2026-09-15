# metadata_parsers/las_parser.py
#
# Extracts metadata from LiDAR point cloud files (.las, .laz) via laspy.
# Adapted from CUR_Res_CurationTools/Scripts/Inspect_LAS_Script.R: reads
# only the header/VLRs (fast — does not decompress point data), reporting
# LAS version, point format, point count, 3D bounding box, embedded CRS,
# and generating software.

import os

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


def _point_format_description(fmt_id):
    return _POINT_FORMAT_DESCRIPTIONS.get(fmt_id, f"Format {fmt_id} (see LAS spec)")


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
