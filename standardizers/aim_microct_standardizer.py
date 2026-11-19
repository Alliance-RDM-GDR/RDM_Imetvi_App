# standardizers/aim_microct_standardizer.py
#
# Maps raw Scanco AIM output to micro-CT fields aligned with REMBI's "Image
# acquisition" and "Image analysis" categories, and attaches standards-based
# suggestions (_Suggestions) a curator can act on.
#
# Matrix size is reported as MatrixSizeX/Y/Z rather than DimensionX/Y: the
# volumes of one deposit are crops of different size by design (and a
# segmentation is a few voxels smaller than its parent image), so DimensionX/Y
# would make almost every file a false DIMENSION_OUTLIER.

import os

from metadata_parsers.aim_parser import parse_vms_date

_STD = "REMBI / Scanco AIM"


def _s(code, en, fr, flag=None):
    return {"Code": code, "Standard": _STD, "Message": en, "Message_fr": fr, "Flag": flag}


def _num(text):
    try:
        return float(str(text).split()[0])
    except (ValueError, IndexError):
        return None


def _scaled(text, factor, ndigits=6):
    v = _num(text)
    return round(v * factor, ndigits) if v is not None else ""


def _count(text):
    """Integer-valued scanner counts ('250') as int, anything else as ''."""
    v = _num(text) if text else None
    return int(v) if v is not None and v == int(v) else (v if v is not None else "")


def _triple(text):
    """'20480 20480 39440' -> [20480.0, 20480.0, 39440.0] (None if not 3 numbers)."""
    try:
        vals = [float(t) for t in str(text).split()]
    except ValueError:
        return None
    return vals if len(vals) == 3 else None


def _vms_basename(path):
    """'dk0:[microct.data.1.2]c0015747.isq;' -> 'c0015747.isq' (VMS path, not portable)."""
    name = str(path).rstrip(";").split("]")[-1].split("/")[-1].split("\\")[-1]
    return name.strip()


def _suggestions(raw, lg):
    s = []
    hx = raw.get("AmiraScriptData") or {}
    dims, offset = raw.get("Dimensions"), raw.get("DataOffset")

    if raw.get("Truncated"):
        s.append(_s(
            "AIM_TRUNCATED",
            f"The file is smaller than its header declares (expected at least "
            f"{raw['DataOffset'] + raw['DataBytes']:,} bytes, found {raw['FileSize']:,}). "
            "It is probably an incomplete copy: re-transfer it and verify it against the manifest.",
            f"Le fichier est plus petit que ce que déclare son en-tête (au moins "
            f"{raw['DataOffset'] + raw['DataBytes']:,} octets attendus, {raw['FileSize']:,} trouvés). "
            "La copie est probablement incomplète : retransférez-la et vérifiez-la avec le manifeste.",
            "AIM_TRUNCATED"))

    ref = hx.get("ReferencedFile")
    if ref:
        if not hx.get("ReferencedExistsIgnoringCase"):
            s.append(_s(
                "AIM_HX_TARGET_MISSING",
                f"The Amira/Avizo script {raw['AmiraScript']} loads '{ref}', which is not in this folder: "
                "the script cannot open the volume.",
                f"Le script Amira/Avizo {raw['AmiraScript']} charge « {ref} », absent de ce dossier : "
                "le script ne peut pas ouvrir le volume.",
                "AIM_HX_BROKEN_LINK"))
        elif not hx.get("ReferencedExactCase"):
            s.append(_s(
                "AIM_HX_CASE_MISMATCH",
                f"The Amira/Avizo script {raw['AmiraScript']} loads '{ref}' but the file is named "
                f"'{os.path.basename(raw['FilePath'])}'. This works on Windows but fails on "
                "case-sensitive file systems (Linux, macOS volumes, some download tools): rename one of them.",
                f"Le script Amira/Avizo {raw['AmiraScript']} charge « {ref} » alors que le fichier s'appelle "
                f"« {os.path.basename(raw['FilePath'])} ». Cela fonctionne sous Windows mais échoue sur les "
                "systèmes de fichiers sensibles à la casse (Linux, volumes macOS, certains outils de "
                "téléchargement) : renommez l'un des deux."))
        if hx.get("Dimensions") and dims and (hx["Dimensions"] != dims or hx.get("HeaderBytes") != offset):
            s.append(_s(
                "AIM_HX_GEOMETRY_MISMATCH",
                f"The Amira/Avizo script declares {hx['Dimensions']} voxels with a {hx.get('HeaderBytes')}-byte "
                f"header, but the AIM header says {dims} voxels and offset {offset}: the volume would be "
                "read incorrectly.",
                f"Le script Amira/Avizo déclare {hx['Dimensions']} voxels avec un en-tête de "
                f"{hx.get('HeaderBytes')} octets, mais l'en-tête AIM indique {dims} voxels et un décalage de "
                f"{offset} : le volume serait mal lu."))

    txt = raw.get("CompanionTxtData") or {}
    diffs = [k for k, cur in (("Dimensions", dims), ("DataOffset", offset),
                              ("ElementSizeMM", raw.get("ElementSizeMM")), ("Position", raw.get("Position")))
             if k in txt and txt[k] != cur and not (k == "ElementSizeMM" and cur and all(
                 abs(a - b) < 1e-6 for a, b in zip(txt[k], cur)))]
    if diffs:
        s.append(_s(
            "AIM_TXT_MISMATCH",
            f"The companion .txt disagrees with the AIM header ({', '.join(diffs)}): the text file belongs "
            "to a different version of this volume.",
            f"Le fichier .txt associé diffère de l'en-tête AIM ({', '.join(diffs)}) : il correspond à une "
            "autre version de ce volume."))

    if raw.get("IsSegmentation") and not raw.get("ParentImage"):
        s.append(_s(
            "AIM_SEG_NO_PARENT",
            "This segmentation has no matching reconstructed volume in the same folder, so it cannot be "
            "related to its grey-value image.",
            "Cette segmentation n'a pas de volume reconstruit correspondant dans le même dossier : "
            "impossible de la relier à son image en niveaux de gris."))

    if lg.get("Scanner type") or lg.get("Scanner ID"):
        s.append(_s(
            "AIM_INSTRUMENT_CODES_ONLY",
            f"The scanner is identified only by numeric codes (type {lg.get('Scanner type', '?')}, "
            f"ID {lg.get('Scanner ID', '?')}). Record the instrument make/model and facility in the dataset "
            "README (REMBI: Image acquisition).",
            f"Le scanner n'est identifié que par des codes numériques (type {lg.get('Scanner type', '?')}, "
            f"ID {lg.get('Scanner ID', '?')}). Indiquez le fabricant/modèle et l'installation dans le "
            "README du jeu de données (REMBI : acquisition d'image)."))

    s.append(_s(
        "AIM_NO_BIOSAMPLE",
        "AIM files carry no species, specimen preparation (fixation, storage, staining), collection "
        "site/date or specimen identifiers beyond a free-text scan label. Supply them in the dataset "
        "README or study record (REMBI: Biosample and Specimen).",
        "Les fichiers AIM ne contiennent ni espèce, ni préparation du spécimen (fixation, conservation, "
        "coloration), ni site/date de collecte, ni identifiants de spécimens au-delà d'une étiquette de "
        "scan en texte libre. Fournissez-les dans le README ou la fiche d'étude (REMBI : Biosample et "
        "Specimen)."))
    return s


def standardize_aim_microct_metadata(raw_metadata):
    raw = raw_metadata
    dims = raw.get("Dimensions") or []
    el = raw.get("ElementSizeMM") or []
    pos = raw.get("Position") or []
    lg = raw.get("Log") or {}
    is_seg = bool(raw.get("IsSegmentation"))
    stored = raw.get("StoredStatistics") or {}
    seg = raw.get("Segmentation") or {}
    bpv = raw.get("BytesPerVoxel")
    fov_um = _triple(lg.get("Orig-ISQ-Dim-um"))

    def at(seq, i, f=lambda v: v):
        return f(seq[i]) if len(seq) > i else ""

    d = {
        "ImageName": os.path.basename(raw.get("FilePath", "")),
        "FileRole": ("Segmentation (labelled objects)" if is_seg else "Reconstructed volume") if dims else "",
        "AIMVersion": raw.get("Version", ""),
        "MatrixSizeX": at(dims, 0), "MatrixSizeY": at(dims, 1), "MatrixSizeZ": at(dims, 2),
        "VoxelSizeX": at(el, 0, lambda v: round(v * 1000, 6)),
        "VoxelSizeY": at(el, 1, lambda v: round(v * 1000, 6)),
        "VoxelSizeZ": at(el, 2, lambda v: round(v * 1000, 6)),
        "PhysicalSizeX": round(dims[0] * el[0], 4) if len(dims) > 2 and len(el) > 2 else "",
        "PhysicalSizeY": round(dims[1] * el[1], 4) if len(dims) > 2 and len(el) > 2 else "",
        "PhysicalSizeZ": round(dims[2] * el[2], 4) if len(dims) > 2 and len(el) > 2 else "",
        "OffsetX": at(pos, 0), "OffsetY": at(pos, 1), "OffsetZ": at(pos, 2),
        "VoxelType": raw.get("VoxelType", ""),
        "BitDepth": bpv * 8 if bpv else "",
        "StoredCompressed": ("yes" if raw.get("Compressed") else "no") if dims else "",
        "ScannerType": lg.get("Scanner type", ""),
        "ScannerID": lg.get("Scanner ID", ""),
        "TubeVoltage": _scaled(lg.get("Energy [V]"), 1e-3),
        "TubeCurrent": _num(lg.get("Intensity [uA]")) if _num(lg.get("Intensity [uA]")) is not None else "",
        "IntegrationTime": _scaled(lg.get("Integration time [us]"), 1e-3),
        "ProjectionsPer180": _count(lg.get("No. projections per 180")),
        "DetectorSamples": _count(lg.get("No. samples")),
        "ScanDistance": _scaled(lg.get("Scan Distance [um]"), 1e-3),
        "SourceFieldOfViewX": round(fov_um[0] / 1000, 4) if fov_um else "",
        "SourceFieldOfViewY": round(fov_um[1] / 1000, 4) if fov_um else "",
        "ReconstructionAlgorithm": lg.get("Reconstruction-Alg.", ""),
        "AcquisitionDate": parse_vms_date(lg.get("Original Creation-Date", "")) or "",
        "ConversionDate": parse_vms_date(lg.get("Time", "")) or "",
        "SpecimenLabel": lg.get("Patient Name", ""),
        "SourceScanFile": _vms_basename(lg.get("Original file", "")),
        "SourceMeasurementIndex": lg.get("Index Measurement", ""),
        "CalibrationDescription": lg.get("Calibration Data", ""),
        "DensityUnit": lg.get("Density: unit", ""),
        "DensitySlope": _num(lg.get("Density: slope")) if lg.get("Density: slope") else "",
        "DensityIntercept": _num(lg.get("Density: intercept")) if lg.get("Density: intercept") else "",
        "MuScaling": _num(lg.get("Mu_Scaling")) if lg.get("Mu_Scaling") else "",
        "MuWater": _num(lg.get("HU: mu water")) if lg.get("HU: mu water") else "",
        "ProcessingSteps": " > ".join(p["Name"] for p in raw.get("Procedures") or []),
        "ParentImage": raw.get("ParentImage", ""),
        "CompanionTxt": raw.get("CompanionTxt", ""),
        "AmiraScript": raw.get("AmiraScript", ""),
    }

    # Value statistics describe grey values for a volume but object labels for a
    # segmentation, so they are only reported where they mean something.
    if not is_seg and stored:
        d.update({
            "DataMin": stored.get("MinData") if stored.get("MinData") is not None else "",
            "DataMax": stored.get("MaxData") if stored.get("MaxData") is not None else "",
            "DataMean": stored.get("MeanData") if stored.get("MeanData") is not None else "",
            "DataStdDev": stored.get("StdData") if stored.get("StdData") is not None else "",
            "AttenuationMin": stored.get("MinValue") if stored.get("MinValue") is not None else "",
            "AttenuationMax": stored.get("MaxValue") if stored.get("MaxValue") is not None else "",
        })
    if is_seg and seg:
        d.update({
            "SegmentationSigma": seg.get("Sigma") if seg.get("Sigma") is not None else "",
            "SegmentationSupport": seg.get("Support") if seg.get("Support") is not None else "",
            "LowThresholdDensity": seg.get("LowThresholdDensity") if seg.get("LowThresholdDensity") is not None else "",
            "UpperThresholdDensity": seg.get("UpperThresholdDensity") if seg.get("UpperThresholdDensity") is not None else "",
            "LowThresholdDataValue": seg.get("LowThresholdDataValue") if seg.get("LowThresholdDataValue") is not None else "",
        })

    if dims:
        d["_Suggestions"] = _suggestions(raw, lg)
    return d
