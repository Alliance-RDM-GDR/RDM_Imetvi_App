# metadata_parsers/cryoem_parser.py
#
# Header-only reader for cryo-EM data collected with Thermo Fisher EPU:
#   .mrc / .mrcs  MRC2014 image or stack (1024-byte header + extended header)
#   .eer          Falcon 4/4i electron-event movie (BigTIFF; only tags are read)
# plus the files EPU writes next to them: the .xml sidecar (acquisition and
# microscope settings), the .jpg preview, the _EER.eer movie and the .gain
# reference. Pixel data is never read here.

import os
import struct
import xml.etree.ElementTree as ET

CRYOEM_EXTENSIONS = [".mrc", ".mrcs", ".eer"]

MRC_MODES = {
    0: ("int8", 1), 1: ("int16", 2), 2: ("float32", 4), 3: ("complex int16", 4),
    4: ("complex float32", 8), 6: ("uint16", 2), 12: ("float16", 2), 101: ("uint4", 0.5),
}
_MAX_XML_BYTES = 4 << 20  # EPU sidecars are ~15 KB; refuse anything absurd


def _local(tag):
    return tag.split("}")[-1]


def read_mrc_header(file_path):
    """Parses the fixed 1024-byte MRC2014 header. Raises on a file too short or without a valid mode."""
    size = os.path.getsize(file_path)
    with open(file_path, "rb") as f:
        raw = f.read(1024)
    if len(raw) < 1024:
        raise ValueError("file is shorter than the 1024-byte MRC header")

    machst = raw[212:214]
    endian = ">" if machst in (b"\x11\x11",) else "<"

    def i(off, n=1):
        return struct.unpack(endian + "%di" % n, raw[off:off + 4 * n])

    def f(off, n=1):
        return struct.unpack(endian + "%df" % n, raw[off:off + 4 * n])

    nx, ny, nz, mode = i(0, 4)
    if mode not in MRC_MODES or min(nx, ny, nz) < 0:
        raise ValueError(f"not a valid MRC header (mode {mode}, size {nx}x{ny}x{nz})")
    nsymbt = i(92)[0]
    dmin, dmax, dmean = f(76, 3)
    nlabl = max(0, min(10, i(220)[0]))
    labels = []
    for k in range(nlabl):
        s = raw[224 + 80 * k:224 + 80 * (k + 1)].decode("latin-1").rstrip("\x00 ").strip()
        if s:
            labels.append(s)
    dtype, bpv = MRC_MODES[mode]
    data_bytes = int(nx * ny * nz * bpv)
    nsymbt = max(nsymbt, 0)
    return {
        "Nx": nx, "Ny": ny, "Nz": nz, "Mode": mode, "DataType": dtype, "BytesPerVoxel": bpv,
        "CellA": f(40)[0], "CellB": f(44)[0], "CellC": f(48)[0],
        "Dmin": dmin, "Dmax": dmax, "Dmean": dmean, "Rms": f(216)[0],
        "ExtendedHeaderBytes": nsymbt,
        "ExtendedHeaderType": raw[104:108].decode("latin-1").strip("\x00 "),
        "Version": i(108)[0],
        "MapId": raw[208:212].decode("latin-1").strip("\x00 "),
        "MachineStamp": machst.hex(),
        "ByteOrder": "big-endian" if endian == ">" else "little-endian",
        "Labels": labels,
        "DataBytes": data_bytes,
        "DataOffset": 1024 + nsymbt,
        "FileSize": size,
        "Truncated": size < 1024 + nsymbt + data_bytes,
    }


def read_eer_header(file_path):
    """Reads the BigTIFF tags of an EER movie (acquisition XML in tag 65001) without touching frame data."""
    import tifffile
    out = {"FileSize": os.path.getsize(file_path)}
    with tifffile.TiffFile(file_path) as tf:
        out["FrameCount"] = len(tf.pages)
        page = tf.pages[0]
        out["Width"], out["Height"] = int(page.imagewidth), int(page.imagelength)
        out["Compression"] = int(page.compression)
        tag = page.tags.get(65001)
        items = {}
        if tag is not None:
            value = tag.value
            if isinstance(value, bytes):
                value = value.decode("utf-8", "replace")
            if len(value) <= _MAX_XML_BYTES:
                for el in ET.fromstring(value):
                    name = el.get("name")
                    if name:
                        items[name] = {"value": (el.text or "").strip(), "unit": el.get("unit", "")}
        out["Acquisition"] = items
        frame_tag = page.tags.get(65002)
        if frame_tag is not None:
            v = frame_tag.value
            v = v.decode("utf-8", "replace") if isinstance(v, bytes) else v
            try:
                out["FrameEncoding"] = {e.get("name"): (e.text or "").strip() for e in ET.fromstring(v)}
            except ET.ParseError:
                pass
    return out


def _num(text):
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def read_epu_xml(file_path):
    """Extracts the acquisition, optics, camera and instrument fields of an EPU MicroscopeImage XML."""
    if os.path.getsize(file_path) > _MAX_XML_BYTES:
        raise ValueError("XML sidecar is unexpectedly large")
    root = ET.parse(file_path).getroot()
    if _local(root.tag) != "MicroscopeImage":
        raise ValueError("not an EPU MicroscopeImage file")

    flat = {}

    def walk(el, path):
        name = _local(el.tag)
        if name in ("CustomData", "CameraSpecificInput", "ReferenceTransformation"):
            return
        children = list(el)
        here = path + "/" + name
        if not children:
            text = (el.text or "").strip()
            if text and el.get("{http://www.w3.org/2001/XMLSchema-instance}nil") != "true":
                flat[here] = text
        else:
            for c in children:
                walk(c, here)

    walk(root, "")
    custom = {}
    for el in root.iter():
        if _local(el.tag) == "CustomData":
            for kv in el:
                key = value = None
                for part in kv:
                    if _local(part.tag) == "Key":
                        key = part.text
                    elif _local(part.tag) == "Value":
                        value = (part.text or "").strip()
                if key:
                    custom[key] = value
            break

    def g(suffix):
        return flat.get("/MicroscopeImage/" + suffix)

    cam = "microscopeData/acquisition/camera/"
    det = "Detectors[%s]." % (g(cam + "Name") or "")
    return {
        "PixelSizeX_m": _num(g("SpatialScale/pixelSize/x/numericValue")),
        "PixelSizeY_m": _num(g("SpatialScale/pixelSize/y/numericValue")),
        "AcquisitionDateTime": g("microscopeData/acquisition/acquisitionDateTime"),
        "Software": g("microscopeData/core/ApplicationSoftware"),
        "SoftwareVersion": g("microscopeData/core/ApplicationSoftwareVersion"),
        "InstrumentModel": g("microscopeData/instrument/InstrumentModel"),
        "InstrumentID": g("microscopeData/instrument/InstrumentID"),
        "AccelerationVoltage_V": _num(g("microscopeData/gun/AccelerationVoltage")),
        "GunSource": g("microscopeData/gun/Sourcetype"),
        "NominalMagnification": _num(g("microscopeData/optics/TemMagnification/NominalMagnification")),
        "ColumnMode": g("microscopeData/optics/ColumnOperatingMode"),
        "ProbeMode": g("microscopeData/optics/ProbeMode"),
        "SpotIndex": _num(g("microscopeData/optics/SpotIndex")),
        "EFTEM": g("microscopeData/optics/EFTEMOn"),
        "SlitInserted": g("microscopeData/optics/EnergyFilter/EnergySelectionSlitInserted"),
        "SlitWidth_eV": _num(g("microscopeData/optics/EnergyFilter/EnergySelectionSlitWidth")),
        "Defocus_m": _num(g("microscopeData/optics/Defocus")),
        "CameraName": g(cam + "Name"),
        "ExposureTime_s": _num(g(cam + "ExposureTime")),
        "ReadoutWidth": _num(g(cam + "ReadoutArea/width")),
        "ReadoutHeight": _num(g(cam + "ReadoutArea/height")),
        "BinningX": _num(g(cam + "Binning/x")),
        "StageX_m": _num(g("microscopeData/stage/Position/X")),
        "StageY_m": _num(g("microscopeData/stage/Position/Y")),
        "StageZ_m": _num(g("microscopeData/stage/Position/Z")),
        "StageTiltA_rad": _num(g("microscopeData/stage/Position/A")),
        "SampleName": g("microscopeData/sample/ID") or g("name"),
        "CommercialName": custom.get(det + "CommercialName") or custom.get("DetectorCommercialName"),
        "CameraSerial": custom.get(det + "CameraSerialNumber"),
        "ElectronCounted": custom.get(det + "ElectronCounted"),
        "FrameRate": _num(custom.get(det + "FrameRate")),
        "DoseRate_e_px_s": _num(custom.get(det + "DoseRate")),
        "TotalDose_e_px": _num(custom.get(det + "TotalDose")),
        "Dose_e_m2": _num(custom.get("Dose")),
        "AppliedDefocus_m": _num(custom.get("AppliedDefocus")),
        "C2Aperture_um": _num(custom.get("Aperture[C2].Name")),
        "ObjectiveAperture": custom.get("Aperture[OBJ].Name"),
        "PhasePlateUsed": custom.get("PhasePlateUsed"),
        "GainReference": custom.get(det + "EerGainReference") or custom.get(det + "GainReference"),
        "CountsToElectrons": _num(custom.get(det + "CountsToElectrons")),
    }


def _ci_find(names, wanted):
    low = wanted.lower()
    for n in names:
        if n.lower() == low:
            return n
    return ""


def _acquisition_stem(path):
    stem = os.path.splitext(os.path.basename(path))[0]
    return stem[:-4] if stem.upper().endswith("_EER") else stem


def _find_gain(dirpath, reference):
    """Looks for the gain reference named in the acquisition metadata in this folder and up to four parents."""
    if not reference:
        return ""
    base = os.path.basename(reference.replace("\\", "/"))
    wanted = [base, base + ".gain"] if not base.lower().endswith(".gain") else [base]
    here = os.path.abspath(dirpath)
    for _ in range(5):
        try:
            names = os.listdir(here)
        except OSError:
            names = []
        for w in wanted:
            hit = _ci_find(names, w)
            if hit:
                return os.path.join(here, hit)
        parent = os.path.dirname(here)
        if parent == here:
            break
        here = parent
    return ""


def parse_cryoem_metadata(file_path, application=None):
    """
    Reads an MRC or EER header plus its EPU sidecars. Returns
    (text_report, raw_metadata) per the parser contract; a read failure is
    reported in the text and never raised.
    """
    fname = os.path.basename(file_path)
    ext = os.path.splitext(fname)[1].lower()
    text = [f"Cryo-EM Metadata Report for {fname}"]
    raw = {"FilePath": file_path, "Kind": "EER" if ext == ".eer" else "MRC"}
    dirpath = os.path.dirname(os.path.abspath(file_path))

    try:
        if ext == ".eer":
            raw["EER"] = read_eer_header(file_path)
        else:
            raw["MRC"] = read_mrc_header(file_path)
    except Exception as e:
        text.append(f"Failed to read {raw['Kind']} file: {e}")
        return "\n".join(text), raw

    # the other files of the same acquisition
    try:
        names = os.listdir(dirpath)
    except OSError:
        names = []
    stem = _acquisition_stem(file_path)
    companions = {
        "Mrc": _ci_find(names, stem + ".mrc"),
        "Eer": _ci_find(names, stem + "_EER.eer"),
        "Xml": _ci_find(names, stem + ".xml"),
        "Jpg": _ci_find(names, stem + ".jpg"),
    }
    raw["Companions"] = companions
    if raw["Kind"] == "MRC" and companions["Eer"]:
        try:
            raw["EER"] = read_eer_header(os.path.join(dirpath, companions["Eer"]))
        except Exception as e:
            raw["EERError"] = str(e)
    if companions["Xml"]:
        try:
            raw["EPU"] = read_epu_xml(os.path.join(dirpath, companions["Xml"]))
        except Exception as e:
            raw["EPUError"] = str(e)
    ref = (raw.get("EPU") or {}).get("GainReference") or \
        ((raw.get("EER") or {}).get("Acquisition", {}).get("eerGainReference") or {}).get("value", "")
    raw["GainReferenceName"] = os.path.basename(ref.replace("\\", "/")) if ref else ""
    raw["GainReferenceFound"] = os.path.basename(_find_gain(dirpath, ref)) if ref else ""

    # report
    mrc, eer, epu = raw.get("MRC"), raw.get("EER"), raw.get("EPU")
    if mrc:
        text.append(f"MRC: {mrc['Nx']} x {mrc['Ny']} x {mrc['Nz']} {mrc['DataType']} (mode {mrc['Mode']}), "
                    f"{mrc['ByteOrder']}, version {mrc['Version'] or 'not set'}, "
                    f"extended header {mrc['ExtendedHeaderBytes']:,} bytes ({mrc['ExtendedHeaderType'] or 'none'})")
        if mrc["Nx"]:
            text.append(f"Pixel size from cell: {mrc['CellA'] / mrc['Nx']:.4f} A")
        text.append(f"Data block: {mrc['DataBytes']:,} bytes at offset {mrc['DataOffset']:,} (file {mrc['FileSize']:,} bytes)")
        if mrc["Truncated"]:
            text.append("WARNING: file is smaller than its header declares (incomplete copy?).")
        if mrc["MapId"] != "MAP":
            text.append("WARNING: MAP identifier missing (pre-2014 MRC or not an MRC file).")
    if eer:
        acq = eer.get("Acquisition", {})
        text.append(f"EER movie: {eer['FrameCount']:,} frames of {eer['Width']} x {eer['Height']}, "
                    f"exposure {acq.get('exposureTime', {}).get('value', '?')} s, "
                    f"{eer['FileSize']:,} bytes")
    if epu:
        v = (epu["AccelerationVoltage_V"] or 0) / 1000
        text.append(f"Instrument: {epu['InstrumentModel'] or '?'}  |  {epu['Software'] or '?'} {epu['SoftwareVersion'] or ''}  |  {v:g} kV")
        text.append(f"Camera: {epu['CommercialName'] or epu['CameraName'] or '?'}  |  magnification {epu['NominalMagnification'] or '?'}x")
        if epu["PixelSizeX_m"]:
            text.append(f"Pixel size (EPU): {epu['PixelSizeX_m'] * 1e10:.4f} A")
        if epu["Dose_e_m2"]:
            text.append(f"Total dose: {epu['Dose_e_m2'] / 1e20:.2f} e/A2")
    present = [k for k, v in (("mrc", companions["Mrc"]), ("eer", companions["Eer"]),
                              ("xml", companions["Xml"]), ("jpg", companions["Jpg"])) if v]
    if raw["GainReferenceFound"]:
        gain_text = raw["GainReferenceFound"]
    elif raw["GainReferenceName"]:
        gain_text = raw["GainReferenceName"] + " (not found)"
    else:
        gain_text = "none declared"
    text.append("Acquisition files: " + (", ".join(present) or "none") + f"  |  gain reference: {gain_text}")
    for key in ("EERError", "EPUError"):
        if raw.get(key):
            text.append(f"{key[:-5]} sidecar could not be read: {raw[key]}")
    return "\n".join(text), raw
