# standardizers/cryoem_standardizer.py
#
# Maps raw cryo-EM output (MRC header, EER tags, EPU sidecar) to fields aligned
# with REMBI's "Image acquisition" category and the EMPIAR / EMDB deposition
# items (voltage, pixel size, dose, detector), and attaches standards-based
# suggestions (_Suggestions) a curator can act on.

import os

_STD = "MRC2014 / EMPIAR / REMBI"


def _s(code, en, fr, flag=None):
    return {"Code": code, "Standard": _STD, "Message": en, "Message_fr": fr, "Flag": flag}


def _round(v, n):
    return round(v, n) if isinstance(v, (int, float)) else ""


def _angstrom_pixel(raw):
    """(value, source) — the MRC cell/size is authoritative, then EPU, then the EER sensor pixel."""
    mrc, epu, eer = raw.get("MRC") or {}, raw.get("EPU") or {}, raw.get("EER") or {}
    if mrc.get("Nx") and mrc.get("CellA"):
        return mrc["CellA"] / mrc["Nx"], "MRC header"
    if epu.get("PixelSizeX_m"):
        return epu["PixelSizeX_m"] * 1e10, "EPU XML"
    px = (eer.get("Acquisition", {}).get("sensorPixelSize.width") or {}).get("value")
    try:
        return float(px) * 1e10, "EER tags"
    except (TypeError, ValueError):
        return None, ""


def _suggestions(raw):
    s = []
    mrc, epu, eer = raw.get("MRC") or {}, raw.get("EPU") or {}, raw.get("EER") or {}
    comp = raw.get("Companions") or {}
    kind = raw.get("Kind")

    if mrc.get("Truncated"):
        s.append(_s(
            "CRYOEM_MRC_TRUNCATED",
            "The MRC file is smaller than its header declares (size x mode + extended header). "
            "The copy is probably incomplete: re-transfer it and compare checksums.",
            "Le fichier MRC est plus petit que ce que déclare son en-tête (taille x mode + en-tête "
            "étendu). La copie est probablement incomplète : retransférez-la et comparez les sommes "
            "de contrôle.", "CRYOEM_TRUNCATED"))
    if mrc and mrc.get("MapId") != "MAP":
        s.append(_s(
            "CRYOEM_MRC_NO_MAP_ID",
            "The MAP identifier is missing from the header. The file predates MRC2014 or is not a "
            "valid MRC file; EMPIAR and EMDB expect MRC2014.",
            "L'identifiant MAP est absent de l'en-tête. Le fichier précède MRC2014 ou n'est pas un "
            "MRC valide ; EMPIAR et EMDB attendent MRC2014."))
    if mrc and mrc.get("Version") not in (20140, 20141):
        s.append(_s(
            "CRYOEM_MRC_VERSION",
            f"MRC version field is {mrc.get('Version')} (MRC2014 writes 20140). Declare the "
            "convention used in the dataset README.",
            f"Le champ de version MRC est {mrc.get('Version')} (MRC2014 écrit 20140). Indiquez la "
            "convention utilisée dans le README du jeu de données."))

    if kind == "MRC" and not comp.get("Xml"):
        s.append(_s(
            "CRYOEM_NO_XML",
            "No EPU .xml sidecar next to this micrograph. The MRC header alone does not record "
            "voltage, dose, defocus, detector or instrument: keep the sidecars with the images.",
            "Aucun fichier .xml EPU à côté de cette micrographie. L'en-tête MRC seul n'indique ni la "
            "tension, ni la dose, ni le défocus, ni le détecteur, ni l'instrument : conservez les "
            "fichiers .xml avec les images.", "CRYOEM_NO_SIDECAR"))
    if raw.get("EPUError"):
        s.append(_s(
            "CRYOEM_XML_UNREADABLE",
            f"The EPU .xml sidecar could not be read ({raw['EPUError']}).",
            f"Le fichier .xml EPU n'a pas pu être lu ({raw['EPUError']}).", "CRYOEM_NO_SIDECAR"))
    if kind == "EER" and not comp.get("Mrc"):
        s.append(_s(
            "CRYOEM_EER_NO_MRC",
            "The motion-corrected/summed .mrc of this movie is not in the folder. Archive the "
            "unaligned movie together with the image EPU saved with it.",
            "Le fichier .mrc (somme/alignement) de ce film n'est pas dans le dossier. Archivez le "
            "film brut avec l'image que EPU a enregistrée."))
    if kind == "MRC" and mrc.get("Nz") == 1 and not comp.get("Eer") and not (eer):
        s.append(_s(
            "CRYOEM_NO_MOVIE",
            "No _EER.eer movie accompanies this micrograph. EMPIAR asks for the raw movies when "
            "they exist; if only summed images are deposited, say so in the README.",
            "Aucun film _EER.eer n'accompagne cette micrographie. EMPIAR demande les films bruts "
            "lorsqu'ils existent ; si seules les images sommées sont déposées, dites-le dans le README."))

    # pixel size must agree across the sources that carry it
    px_mrc = mrc["CellA"] / mrc["Nx"] if mrc.get("Nx") and mrc.get("CellA") else None
    px_epu = epu["PixelSizeX_m"] * 1e10 if epu.get("PixelSizeX_m") else None
    if px_mrc and px_epu and abs(px_mrc - px_epu) / px_epu > 0.01:
        s.append(_s(
            "CRYOEM_PIXEL_MISMATCH",
            f"Pixel size differs between the MRC header ({px_mrc:.4f} Å) and the EPU XML "
            f"({px_epu:.4f} Å). EMPIAR/EMDB need one calibrated value: check which is correct.",
            f"La taille de pixel diffère entre l'en-tête MRC ({px_mrc:.4f} Å) et le XML EPU "
            f"({px_epu:.4f} Å). EMPIAR/EMDB exigent une seule valeur calibrée : vérifiez laquelle "
            "est correcte.", "CRYOEM_PIXEL_MISMATCH"))
    elif mrc and not px_mrc and not px_epu:
        s.append(_s(
            "CRYOEM_NO_PIXEL_SIZE",
            "No pixel size is recorded (cell dimensions are zero and there is no EPU sidecar).",
            "Aucune taille de pixel n'est enregistrée (dimensions de la cellule nulles et aucun "
            "fichier EPU)."))

    if raw.get("GainReferenceName") and not raw.get("GainReferenceFound"):
        s.append(_s(
            "CRYOEM_NO_GAIN",
            f"The movies were recorded with the gain reference '{raw['GainReferenceName']}', which is "
            "not in this folder or its parents. EER movies cannot be processed without it: include "
            "the .gain file in the deposit.",
            f"Les films ont été enregistrés avec la référence de gain « {raw['GainReferenceName']} », "
            "absente de ce dossier et de ses parents. Les films EER ne peuvent pas être traités sans "
            "elle : joignez le fichier .gain au dépôt.", "CRYOEM_NO_GAIN_REF"))

    if epu and not epu.get("SampleName") or (epu and str(epu.get("SampleName")).lower() in ("empty", "none")):
        s.append(_s(
            "CRYOEM_NO_SAMPLE",
            "EPU carries no sample name. Biosample details (macromolecule, source organism, buffer, "
            "grid type and vitrification) must be supplied in the README or EMPIAR entry "
            "(REMBI: Biosample, Specimen preparation).",
            "EPU ne contient pas de nom d'échantillon. Les détails du biospécimen (macromolécule, "
            "organisme source, tampon, type de grille et vitrification) doivent figurer dans le "
            "README ou l'entrée EMPIAR (REMBI : Biosample, Specimen preparation)."))
    else:
        s.append(_s(
            "CRYOEM_NO_SPECIMEN_PREP",
            "Specimen preparation (grid type, vitrification device, blotting) and the cryo-EM "
            "sample are not recorded in the files; supply them in the README or EMPIAR entry "
            "(REMBI: Specimen preparation).",
            "La préparation du spécimen (type de grille, appareil de vitrification, buvardage) et "
            "l'échantillon ne figurent pas dans les fichiers ; fournissez-les dans le README ou "
            "l'entrée EMPIAR (REMBI : Specimen preparation)."))
    return s


def standardize_cryoem_metadata(raw_metadata):
    raw = raw_metadata
    mrc, epu, eer = raw.get("MRC") or {}, raw.get("EPU") or {}, raw.get("EER") or {}
    if not (mrc or eer):
        return {"ImageName": os.path.basename(raw.get("FilePath", ""))}
    acq = eer.get("Acquisition", {})
    comp = raw.get("Companions") or {}
    px, px_src = _angstrom_pixel(raw)

    def eer_val(name):
        v = (acq.get(name) or {}).get("value")
        try:
            return float(v)
        except (TypeError, ValueError):
            return v or ""

    dose_a2 = epu["Dose_e_m2"] / 1e20 if epu.get("Dose_e_m2") else ""
    exposure = epu.get("ExposureTime_s") or (eer_val("exposureTime") if acq else "")
    defocus = epu.get("AppliedDefocus_m")
    if defocus is None:
        defocus = epu.get("Defocus_m")

    if raw.get("Kind") == "EER":
        file_type = "EER electron-event movie"
        w, h, n = eer.get("Width", ""), eer.get("Height", ""), eer.get("FrameCount", "")
        dtype = "EER encoded"
    else:
        file_type = "MRC2014 micrograph" if mrc.get("Nz") == 1 else "MRC2014 stack/volume"
        w, h, n, dtype = mrc["Nx"], mrc["Ny"], mrc["Nz"], mrc["DataType"]

    d = {
        "ImageName": os.path.basename(raw.get("FilePath", "")),
        "FileType": file_type,
        "ImageWidth": w, "ImageHeight": h, "FrameCount": n if raw.get("Kind") == "EER" else (eer.get("FrameCount") or ""),
        "SectionCount": mrc.get("Nz", ""),
        "DataType": dtype,
        "ByteOrder": mrc.get("ByteOrder", ""),
        "MRCVersion": mrc.get("Version", ""),
        "ExtendedHeaderType": mrc.get("ExtendedHeaderType", "") if mrc else "",
        "PixelSize": _round(px, 5) if px else "",
        "PixelSizeSource": px_src,
        "DataMin": _round(mrc.get("Dmin"), 4) if mrc else "",
        "DataMax": _round(mrc.get("Dmax"), 4) if mrc else "",
        "DataMean": _round(mrc.get("Dmean"), 4) if mrc else "",
        "AccelerationVoltage": _round((epu.get("AccelerationVoltage_V") or 0) / 1000, 3) if epu.get("AccelerationVoltage_V") else "",
        "ElectronSource": epu.get("GunSource") or "",
        "NominalMagnification": epu.get("NominalMagnification") or "",
        "Defocus": _round(defocus * 1e6, 3) if defocus is not None else "",
        "TotalDose": _round(dose_a2, 3) if dose_a2 != "" else "",
        "DoseRate": _round(epu.get("DoseRate_e_px_s"), 4) if epu.get("DoseRate_e_px_s") else "",
        "ExposureTime": _round(exposure, 4) if exposure != "" else "",
        "FrameRate": _round(epu.get("FrameRate"), 2) if epu.get("FrameRate") else "",
        "Detector": epu.get("CommercialName") or (acq.get("commercialName") or {}).get("value", "") if (epu or acq) else "",
        "DetectorSerial": epu.get("CameraSerial") or (acq.get("serialNumber") or {}).get("value", "") if (epu or acq) else "",
        "ElectronCounting": epu.get("ElectronCounted") or "",
        "EnergyFilterSlit": _round(epu.get("SlitWidth_eV"), 2) if epu.get("SlitInserted") == "true" and epu.get("SlitWidth_eV") is not None else "",
        "C2Aperture": epu.get("C2Aperture_um") if epu.get("C2Aperture_um") is not None else "",
        "ObjectiveAperture": "" if str(epu.get("ObjectiveAperture")).lower() in ("none", "") else epu.get("ObjectiveAperture", ""),
        "PhasePlate": epu.get("PhasePlateUsed") or "",
        "ColumnMode": epu.get("ColumnMode") or "",
        "ProbeMode": epu.get("ProbeMode") or "",
        "SpotSize": epu.get("SpotIndex") if epu.get("SpotIndex") is not None else "",
        "Microscope": epu.get("InstrumentModel") or "",
        "AcquisitionSoftware": " ".join(x for x in (epu.get("Software"), epu.get("SoftwareVersion")) if x),
        "AcquisitionDate": epu.get("AcquisitionDateTime") or (acq.get("timestamp") or {}).get("value", ""),
        "StageX": _round(epu.get("StageX_m") * 1e6, 3) if epu.get("StageX_m") is not None else "",
        "StageY": _round(epu.get("StageY_m") * 1e6, 3) if epu.get("StageY_m") is not None else "",
        "StageTilt": _round(epu.get("StageTiltA_rad") * 57.29578, 3) if epu.get("StageTiltA_rad") is not None else "",
        "GainReference": raw.get("GainReferenceName", ""),
        "GainReferenceFound": "yes" if raw.get("GainReferenceFound") else ("no" if raw.get("GainReferenceName") else ""),
        "CompanionXml": comp.get("Xml", ""),
        "CompanionMrc": comp.get("Mrc", ""),
        "CompanionMovie": comp.get("Eer", ""),
        "CompanionPreview": comp.get("Jpg", ""),
        "HeaderLabels": " | ".join(mrc.get("Labels") or []),
    }
    d["_Suggestions"] = _suggestions(raw)
    return d
