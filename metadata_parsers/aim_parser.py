# metadata_parsers/aim_parser.py
#
# Reads Scanco micro-CT ".aim" volumes — header only, never the voxel data
# (a single scan is 0.5-2 GB). Two on-disk versions occur in the wild and both
# are handled:
#
#   AIM 020  (VMS era, 32-bit):  20-byte pre-header + 140-byte structure, ints,
#            element size as VAX F-floats (mm).
#   AIM 030  ("AIMDATA_V030"):   16-byte tag + 40 + 224-byte structure, int64,
#            element size in nanometres. Used once a scan outgrows 2 GB.
#
# Both are followed by a text "Processing Log" (scanner, calibration, every
# image-processing step applied) and then the voxel block. The log is the
# richest part: acquisition parameters, density calibration, value statistics
# and, for segmentation files, the threshold/filter chain that produced them.
#
# Companion files are read when they sit next to the volume:
#   <stem>.txt  dump of the AIM header written by the reader (cross-checked)
#   <stem>.hx   Amira/Avizo script whose `load -raw` line points at the volume
#
# AIM files are not self-describing about species, specimen preparation or
# instrument model, so those gaps are reported by the standardizer, not guessed.

import os
import re
import struct

AIM_EXTENSIONS = [".aim"]

# Scanco type code -> (label, numpy dtype, bytes per voxel). Other codes are
# reported as "Scanco type 0x...." and treated as not previewable.
_TYPE_INFO = {
    0x00010001: ("char (8-bit)", "uint8", 1),
    0x00020002: ("short (16-bit signed)", "int16", 2),
}

_MONTHS = {m: i for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}

# Statistics keys of a "Parameter name" block, normalized (the "(approx.)"
# suffix of segmentation files is dropped).
_STAT_KEYS = {
    "minimum value": "MinValue", "maximum value": "MaxValue",
    "average value": "MeanValue", "standard deviation": "StdValue",
    "scaled by factor": "ScaleFactor",
    "minimum data value": "MinData", "maximum data value": "MaxData",
    "average data value": "MeanData", "standard data deviation": "StdData",
}


def _vax_f_to_float(raw4):
    """VAX F_floating (VMS) -> Python float. 0.0 for the zero/reserved encoding."""
    w0, w1 = struct.unpack("<2H", raw4)
    exp = (w0 >> 7) & 0xFF
    if exp == 0:
        return 0.0
    frac = ((w0 & 0x7F) << 16) | w1
    value = (0.5 + frac / float(1 << 24)) * 2.0 ** (exp - 128)
    return -value if (w0 & 0x8000) else value


def read_aim_header(file_path):
    """
    Decodes the binary header of an AIM file.
    Returns a dict (Version, Dimensions, Position, ElementSizeMM, TypeCode,
    DataOffset, DataBytes, LogBytes, FileSize, ...) plus the raw log text under
    "LogText". Raises ValueError if the file is not a recognizable AIM.
    """
    file_size = os.path.getsize(file_path)
    with open(file_path, "rb") as f:
        head = f.read(512)
        if head[:4] == b"AIMD":
            if len(head) < 0x108 + 8:
                raise ValueError("file too short for an AIM 030 header")
            pre, struct_size, log_bytes, data_bytes = struct.unpack_from("<4q", head, 0x10)
            header_total = 16 + pre + struct_size
            version = "030"
            type_code = struct.unpack_from("<I", head, 0x44)[0]
            pos = struct.unpack_from("<3q", head, 0x48)
            dim = struct.unpack_from("<3q", head, 0x60)
            el_nm = struct.unpack_from("<3q", head, 0xF0)
            el_mm = tuple(v / 1.0e6 for v in el_nm)
        else:
            if len(head) < 160:
                raise ValueError("file too short for an AIM header")
            pre, struct_size, log_bytes, data_bytes = struct.unpack_from("<4i", head, 0)
            if pre != 20 or struct_size != 140:
                raise ValueError("not an AIM file (unrecognized header)")
            header_total = pre + struct_size
            version = "020"
            type_code = struct.unpack_from("<I", head, 0x28)[0]
            pos = struct.unpack_from("<3i", head, 0x2C)
            dim = struct.unpack_from("<3i", head, 0x38)
            el_mm = tuple(_vax_f_to_float(head[0x80 + 4 * i: 0x84 + 4 * i]) for i in range(3))

        if not (0 <= log_bytes <= (4 << 20)) or any(d <= 0 for d in dim):
            raise ValueError("implausible AIM header values")
        f.seek(header_total)
        log_text = f.read(log_bytes).replace(b"\x00", b"").decode("latin-1")

    return {
        "Version": version,
        "HeaderBytes": header_total,
        "LogBytes": log_bytes,
        "DataOffset": header_total + log_bytes,
        "DataBytes": data_bytes,
        "FileSize": file_size,
        "TypeCode": type_code,
        "Position": [int(v) for v in pos],
        "Dimensions": [int(v) for v in dim],
        "ElementSizeMM": [round(v, 9) for v in el_mm],
        "LogText": log_text,
    }


def describe_voxel_type(type_code, dims, data_bytes):
    """(label, dtype or None, bytes_per_voxel or None, compressed: bool)."""
    voxels = dims[0] * dims[1] * dims[2]
    info = _TYPE_INFO.get(type_code)
    if info:
        label, dtype, bpv = info
        return label, dtype, bpv, data_bytes != voxels * bpv
    return f"Scanco type 0x{type_code:08X}", None, None, data_bytes < voxels


# ── processing log ──────────────────────────────────────────────────────────

def _to_float(text):
    try:
        return float(text.split()[0])
    except (ValueError, IndexError):
        return None


def parse_aim_log(text):
    """
    Splits the processing log into (key, value) pairs grouped in blocks (a block
    ends at a '!----' rule). Keys and values are separated by 2+ spaces.
    Returns {"Fields", "Blocks", "Procedures", "StatGroups"}.
    """
    blocks = [[]]
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("!---"):
            if blocks[-1]:
                blocks.append([])
            continue
        if s.startswith("!"):
            continue
        parts = re.split(r"\s{2,}", s, maxsplit=1)
        blocks[-1].append((parts[0].strip(), parts[1].strip() if len(parts) > 1 else ""))
    blocks = [b for b in blocks if b]

    fields = {}
    for block in blocks:
        for k, v in block:
            fields.setdefault(k, v)

    procedures = []
    for block in blocks:
        name = next((v for k, v in block if k == "Procedure:"), None)
        if name:
            params = {}
            for k, v in block:
                if k != "Procedure:":
                    params.setdefault(k, v)
            procedures.append({"Name": re.sub(r"\(.*$", "", name).strip(), "Parameters": params})

    # Statistics: each "Parameter [(before)] name" line opens a group.
    groups, current = [], None
    for block in blocks:
        for k, v in block:
            if k in ("Parameter name", "Parameter (before) name"):
                current = {"Parameter": v}
                groups.append(current)
            elif k == "Parameter units" and current is not None:
                current["Units"] = v
            elif current is not None:
                norm = re.sub(r"\s*\(approx\.\)", "", k).strip().lower()
                if norm in _STAT_KEYS:
                    current[_STAT_KEYS[norm]] = _to_float(v)
    return {"Fields": fields, "Blocks": blocks, "Procedures": procedures, "StatGroups": groups}


def parse_vms_date(text):
    """'22-MAR-2018 17:33:11.72' -> '2018-03-22T17:33:11' (None if unparseable)."""
    m = re.match(r"(\d{1,2})-([A-Za-z]{3})-(\d{4})\s+(\d{2}):(\d{2}):(\d{2})", text or "")
    if not m or m.group(2).upper() not in _MONTHS:
        return None
    return "%s-%02d-%02dT%s:%s:%s" % (
        m.group(3), _MONTHS[m.group(2).upper()], int(m.group(1)), m.group(4), m.group(5), m.group(6))


# ── companion files ─────────────────────────────────────────────────────────

def _find_companion(dir_names, stem, ext):
    """(exact_name or None, ci_name or None) for <stem><ext> among dir entries."""
    wanted = (stem + ext)
    exact = wanted if wanted in dir_names else None
    ci = next((n for n in dir_names if n.lower() == wanted.lower()), None)
    return exact, ci


def _read_txt_companion(path):
    """Cross-check values from the reader's header dump (<stem>.txt)."""
    out = {}
    try:
        with open(path, "r", errors="replace") as f:
            text = f.read()
    except OSError:
        return None
    m = re.search(r"Image Data starts at byte offset\s+(\d+)", text)
    if m:
        out["DataOffset"] = int(m.group(1))
    for key, name in (("dim", "Dimensions"), ("pos", "Position")):
        m = re.search(r"^!>\s+%s\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)" % key, text, re.M)
        if m:
            out[name] = [int(m.group(i)) for i in (1, 2, 3)]
    m = re.search(r"^!>\s+element size in mm\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)", text, re.M)
    if m:
        out["ElementSizeMM"] = [float(m.group(i)) for i in (1, 2, 3)]
    return out


def _read_hx(path, dir_names):
    """Parses the `load -raw` line of an Amira/Avizo script."""
    try:
        with open(path, "r", errors="replace") as f:
            text = f.read()
    except OSError:
        return None
    m = re.search(r"^\s*load\s+-raw\s+(.+)$", text, re.M)
    if not m:
        return {"LoadFound": False}
    tokens = [t.strip('"') for t in re.findall(r'"[^"]*"|\S+', m.group(1))]
    hx = {"LoadFound": True}
    try:
        target = tokens[0]
        hx["ReferencedPath"] = target
        hx["ReferencedFile"] = re.split(r"[\\/]", target)[-1]
        hx["Endian"], hx["Layout"], hx["DataType"] = tokens[1], tokens[2], tokens[3]
        hx["Components"] = int(tokens[4])
        hx["Dimensions"] = [int(tokens[5]), int(tokens[6]), int(tokens[7])]
        hx["BoundingBoxMM"] = [float(t) for t in tokens[8:14]]
        if "-header" in tokens:
            hx["HeaderBytes"] = int(tokens[tokens.index("-header") + 1])
    except (IndexError, ValueError):
        hx["Malformed"] = True
    ref = hx.get("ReferencedFile")
    if ref:
        hx["ReferencedExactCase"] = ref in dir_names
        hx["ReferencedExistsIgnoringCase"] = any(n.lower() == ref.lower() for n in dir_names)
    return hx


# ── main entry point ────────────────────────────────────────────────────────

def parse_aim_metadata(file_path, application=None):
    """
    Extracts Scanco AIM header fields, processing-log content and companion
    .txt/.hx information. Returns (text_report, raw_metadata) per the parser
    contract; a read failure is reported in the text (never raised).
    """
    fname = os.path.basename(file_path)
    text_lines = [f"Scanco AIM Micro-CT Metadata Report for {fname}"]
    raw = {"FilePath": file_path}

    try:
        hdr = read_aim_header(file_path)
    except Exception as e:
        text_lines.append(f"Failed to read AIM file: {e}")
        return "\n".join(text_lines), raw

    label, dtype, bpv, compressed = describe_voxel_type(hdr["TypeCode"], hdr["Dimensions"], hdr["DataBytes"])
    log = parse_aim_log(hdr.pop("LogText"))
    raw.update(hdr)
    raw.update({
        "VoxelType": label, "NumpyDtype": dtype, "BytesPerVoxel": bpv, "Compressed": compressed,
        "Log": log["Fields"],
        "Procedures": log["Procedures"],
        "OriginalStatistics": log["StatGroups"][0] if log["StatGroups"] else None,
        "StoredStatistics": log["StatGroups"][-1] if log["StatGroups"] else None,
        # a volume smaller than its header promises is an incomplete copy
        "Truncated": hdr["FileSize"] < hdr["DataOffset"] + hdr["DataBytes"],
    })

    stem = os.path.splitext(fname)[0]
    is_seg_name = stem.lower().endswith("_seg")
    stored = raw["StoredStatistics"] or {}
    raw["IsSegmentation"] = is_seg_name or stored.get("Parameter") == "Segmented Objects"

    # segmentation recipe, from the thresholding procedure's parameters
    thres = next((p for p in log["Procedures"] if "Thres" in p["Name"]), None)
    if thres:
        p = thres["Parameters"]
        raw["Segmentation"] = {
            "Procedures": [x["Name"] for x in log["Procedures"]],
            "Sigma": _to_float(p.get("sigma", "")),
            "Support": _to_float(p.get("support", "")),
            "LowThresholdInput": _to_float(p.get("low_th_input", "")),
            "UpperThresholdInput": _to_float(p.get("upp_th_input", "")),
            "ThresholdUnitCode": _to_float(p.get("Wished Unit of thresholds", "")),
            "LowThresholdDataValue": _to_float(p.get("low corresponds to data value", "")),
            "UpperThresholdDataValue": _to_float(p.get("upp corresponds to data value", "")),
            "LowThresholdDensity": _to_float(p.get("and low to dens value", "")),
            "UpperThresholdDensity": _to_float(p.get("and upp to dens value", "")),
            "DensityUnit": p.get("dens in units", ""),
        }

    # companion files
    try:
        dir_names = set(os.listdir(os.path.dirname(os.path.abspath(file_path))))
    except OSError:
        dir_names = set()
    dirpath = os.path.dirname(os.path.abspath(file_path))
    txt_exact, txt_ci = _find_companion(dir_names, stem, ".txt")
    raw["CompanionTxt"] = txt_exact or txt_ci or ""
    raw["CompanionTxtData"] = _read_txt_companion(os.path.join(dirpath, raw["CompanionTxt"])) if raw["CompanionTxt"] else None
    hx_exact, hx_ci = _find_companion(dir_names, stem, ".hx")
    raw["AmiraScript"] = hx_exact or hx_ci or ""
    raw["AmiraScriptData"] = _read_hx(os.path.join(dirpath, raw["AmiraScript"]), dir_names) if raw["AmiraScript"] else None
    raw["ParentImage"] = ""
    if is_seg_name:
        parent = _find_companion(dir_names, stem[: -len("_seg")], ".aim")
        raw["ParentImage"] = parent[0] or parent[1] or ""

    # ── report ──────────────────────────────────────────────────────────────
    dims, el = raw["Dimensions"], raw["ElementSizeMM"]
    text_lines += [
        f"AIM version: {raw['Version']}  |  role: " + ("segmentation (labelled objects)" if raw["IsSegmentation"] else "reconstructed volume"),
        f"Matrix: {' x '.join(map(str, dims))} voxels  |  voxel size: {' x '.join(f'{v * 1000:g}' for v in el)} um",
        f"Physical size: {' x '.join(f'{d * e:.2f}' for d, e in zip(dims, el))} mm",
        f"Voxel type: {label}" + ("  [compressed]" if compressed else ""),
        f"Data block: {raw['DataBytes']:,} bytes at offset {raw['DataOffset']:,}  (file {raw['FileSize']:,} bytes)",
    ]
    if raw["Truncated"]:
        text_lines.append("WARNING: file is smaller than its header declares (incomplete copy?).")
    lg = raw["Log"]
    for key in ("Patient Name", "Original Creation-Date", "Scanner type", "Scanner ID", "Energy [V]",
                "Intensity [uA]", "Integration time [us]", "No. projections per 180", "Calibration Data"):
        if lg.get(key):
            text_lines.append(f"{key}: {lg[key]}")
    if raw.get("Segmentation"):
        sg = raw["Segmentation"]
        text_lines.append("Segmentation: " + " > ".join(sg["Procedures"]))
        text_lines.append(f"  sigma {sg['Sigma']}, support {sg['Support']}, thresholds "
                          f"{sg['LowThresholdInput']}-{sg['UpperThresholdInput']} "
                          f"(low = {sg['LowThresholdDensity']} {sg['DensityUnit']})")
    elif log["Procedures"]:
        text_lines.append("Processing: " + " > ".join(p["Name"] for p in log["Procedures"]))
    text_lines.append(f"Companion .txt: {raw['CompanionTxt'] or 'none'}  |  Amira script: {raw['AmiraScript'] or 'none'}")
    hx = raw["AmiraScriptData"]
    if hx and hx.get("ReferencedFile"):
        text_lines.append(f"Amira script loads: {hx['ReferencedFile']}")
    if raw["ParentImage"]:
        text_lines.append(f"Segmentation of: {raw['ParentImage']}")

    return "\n".join(text_lines), raw
