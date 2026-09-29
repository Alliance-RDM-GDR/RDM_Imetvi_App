# standardizers/omezarr_microscopy_standardizer.py
#
# Maps raw OME-Zarr (OME-NGFF) + BIDS-Microscopy output to REMBI/OME-NGFF
# aligned fields, and attaches standards-based suggestions as _Suggestions.

import os

from utils.bids import zarr_bids_suggestions, dataset_description_suggestions

_TEMPLATE_VALUES = ("name of the dataset", "the license for the dataset")


def _axis_size(shape, axes, name):
    for a, n in zip(axes, shape or []):
        if a.get("Name", "").lower() == name:
            return n
    return ""


def standardize_omezarr_microscopy_metadata(raw_metadata):
    raw = raw_metadata
    axes = raw.get("Axes") or []
    levels = raw.get("Levels") or []
    lv = levels[0] if levels else {}
    shape = lv.get("Shape") or []
    px = raw.get("PixelSizeUM") or {}
    sidecar = raw.get("Sidecar") or {}
    ent = raw.get("BIDSEntities") or {}
    dd = raw.get("DatasetDescription") or {}
    chans = raw.get("Channels") or []

    def r(v):
        return round(v, 6) if isinstance(v, (int, float)) else ""

    d = {
        "ImageName": os.path.basename(raw.get("FilePath", "").rstrip("/\\")),
        "BIDSSubject": ent.get("sub", ""),
        "BIDSSample": ent.get("sample", ""),
        "Modality": "Light-sheet fluorescence microscopy" if raw.get("BIDSSuffix") == "SPIM" else "",
        "NGFFVersion": raw.get("NGFFVersion", ""),
        "DimensionX": _axis_size(shape, axes, "x"),
        "DimensionY": _axis_size(shape, axes, "y"),
        "DimensionZ": _axis_size(shape, axes, "z"),
        "NumChannels": _axis_size(shape, axes, "c") or (len(chans) or ""),
        "NumTimepoints": _axis_size(shape, axes, "t"),
        "PixelSizeX": r(px.get("X")),
        "PixelSizeY": r(px.get("Y")),
        "PixelSizeZ": r(px.get("Z")),
        "PixelType": lv.get("DType", ""),
        "ChunkShape": "x".join(map(str, lv.get("Chunks") or [])),
        "Compression": lv.get("Compressor", ""),
        "PyramidLevels": raw.get("NumLevels", ""),
        "DownsampleFactorXY": raw.get("DownsampleFactorXY", ""),
        "Channels": [{"Name": c.get("Name", "")} for c in chans],
        "Magnification": sidecar.get("Magnification", ""),
        "NA": sidecar.get("NumericalAperture", ""),
        "Immersion": sidecar.get("Immersion", ""),
        "InstrumentModel": sidecar.get("InstrumentModel", ""),
        "SoftwareVersions": sidecar.get("SoftwareVersions", ""),
        "AcquisitionMode": sidecar.get("OtherAcquisitionParameters", ""),
        "SidecarPixelSize": (", ".join(f"{v:g}" for v in sidecar["PixelSize"])
                             + f" {sidecar.get('PixelSizeUnits', '')}")
        if isinstance(sidecar.get("PixelSize"), list) else "",
        "ExcitationWavelength": "" if raw.get("WavelengthAmbiguous") else raw.get("ExcitationWL", ""),
        "EmissionWavelength": "" if raw.get("WavelengthAmbiguous") else raw.get("EmissionWL", ""),
        "ProcessingSoftware": raw.get("GeneratedBy", ""),
        "DatasetName": dd.get("Name", ""),
        "DatasetLicense": dd.get("License", ""),
        "StoredChunkFiles": lv.get("ChunkFiles", ""),
        "StoredSizeMB": round(lv["StoredBytes"] / 1e6, 1) if lv.get("StoredBytes") else "",
    }
    for k in ("DatasetName", "DatasetLicense"):
        if str(d[k]).strip().lower() in _TEMPLATE_VALUES:
            d[k] = ""

    if levels:
        s = []
        if raw.get("DatasetDescriptionFound"):
            s += dataset_description_suggestions(dd)
        s += zarr_bids_suggestions(sidecar if raw.get("SidecarFound") else None,
                                   raw.get("SamplesColumns"), chans, raw.get("UnitsPresent", True))
        d["_Suggestions"] = s
    return d
