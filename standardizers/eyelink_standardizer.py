# standardizers/eyelink_standardizer.py
#
# Maps raw EyeLink ASC output to fields named after the BIDS eye-tracking
# extension (BEP020: SamplingFrequency, RecordedEye, ScreenResolution,
# CalibrationType, AverageCalibrationError, ...) and attaches suggestions
# (_Suggestions) for what a curator would still have to supply.

import os

_STD = "BIDS eye-tracking (BEP020) / EyeLink"

# Fraction of samples without a gaze position above which a file is flagged.
# Blinks alone leave under ~10%; in the 334 files of FRDR deposit 1835 the
# median was 22% (participants closing their eyes in the scanner) and a
# quarter of the files were above 45%.
HIGH_MISSING_FRACTION = 0.5
POOR_VALIDATION_ERROR_DEG = 1.0


def _s(code, en, fr, flag=None):
    return {"Code": code, "Standard": _STD, "Message": en, "Message_fr": fr, "Flag": flag}


def _real(value):
    """A header value, or '' when it was blanked out by the depositor."""
    v = (value or "").strip()
    return "" if not v or "removed" in v.lower() else v


def _suggestions(raw, std):
    s = []
    head = raw.get("Header") or {}
    validations = raw.get("Validations") or []
    geometry = raw.get("Geometry") or {}

    if raw.get("UnclosedBlocks"):
        s.append(_s(
            "EYELINK_TRUNCATED",
            "A recording block has no END line: the file ends mid-recording (interrupted conversion or copy).",
            "Un bloc d'enregistrement n'a pas de ligne END : le fichier s'arrête en plein "
            "enregistrement (conversion ou copie interrompue).", "EYELINK_TRUNCATED"))
    if not validations:
        s.append(_s(
            "EYELINK_NO_VALIDATION",
            "No calibration validation is recorded in this file, so CalibrationType and the "
            "validation error cannot be reported. If the participant was calibrated in an "
            "earlier file, say so in the README.",
            "Aucune validation d'étalonnage n'est consignée dans ce fichier : CalibrationType et "
            "l'erreur de validation ne peuvent pas être indiqués. Si le participant a été étalonné "
            "dans un fichier antérieur, précisez-le dans le README."))
    else:
        last = validations[-1]
        if last["Grade"].upper() == "POOR" or last["AvgError"] > POOR_VALIDATION_ERROR_DEG:
            s.append(_s(
                "EYELINK_POOR_VALIDATION",
                f"The last validation is {last['Grade']} ({last['AvgError']}° average error). "
                "Gaze positions may be unreliable: document whether the recording was kept.",
                f"La dernière validation est {last['Grade']} (erreur moyenne de {last['AvgError']}°). "
                "Les positions du regard peuvent être peu fiables : indiquez si l'enregistrement "
                "a été conservé.", "EYELINK_POOR_VALIDATION"))
    frac = raw.get("MissingFraction")
    if frac is not None and frac > HIGH_MISSING_FRACTION:
        s.append(_s(
            "EYELINK_HIGH_MISSING",
            f"{frac * 100:.0f}% of the samples have no gaze position (blinks and tracking loss). "
            "Check the recording before analysis.",
            f"{frac * 100:.0f} % des échantillons n'ont pas de position du regard (clignements et "
            "perte de suivi). Vérifiez l'enregistrement avant l'analyse.", "EYELINK_HIGH_MISSING"))
    rate, observed = std.get("SamplingFrequency"), std.get("ObservedSamplingFrequency")
    if rate and observed and abs(observed - rate) / rate > 0.02:
        s.append(_s(
            "EYELINK_RATE_MISMATCH",
            f"The timestamps give {observed:g} Hz but the header says {rate:g} Hz: samples may be "
            "missing or the recording was resampled.",
            f"Les horodatages donnent {observed:g} Hz alors que l'en-tête indique {rate:g} Hz : "
            "des échantillons manquent peut-être ou l'enregistrement a été rééchantillonné."))

    if std.get("ConvertedFrom") or std.get("RecordedBy"):
        s.append(_s(
            "EYELINK_HEADER_IDENTIFIERS",
            "The header names the original EDF file or the operator "
            f"({std.get('ConvertedFrom') or std.get('RecordedBy')}). EDF file names often contain "
            "participant names or IDs: check them before sharing.",
            "L'en-tête indique le fichier EDF d'origine ou l'opérateur "
            f"({std.get('ConvertedFrom') or std.get('RecordedBy')}). Les noms de fichiers EDF "
            "contiennent souvent le nom ou l'identifiant du participant : vérifiez-les avant de partager.",
            "EYELINK_HEADER_IDENTIFIERS"))
    if not _real(head.get("DATE")):
        s.append(_s(
            "EYELINK_NO_DATE",
            "The header has no conversion/recording date (removed or absent). BIDS needs the "
            "acquisition time: record it in the README or the study spreadsheet.",
            "L'en-tête ne contient aucune date de conversion ou d'enregistrement (supprimée ou "
            "absente). BIDS exige l'heure d'acquisition : consignez-la dans le README ou le "
            "tableur de l'étude."))

    if geometry.get("disttoscreen"):
        s.append(_s(
            "EYELINK_GEOMETRY_UNITS",
            "Screen distance and size come from a message logged by the experiment code, not from "
            "the tracker, and the distance has no unit (the sizes are in inches). BIDS wants "
            "centimetres: confirm the unit before converting.",
            "La distance et la taille de l'écran proviennent d'un message consigné par le code de "
            "l'expérience, pas par le suivi oculaire, et la distance n'a pas d'unité (les tailles "
            "sont en pouces). BIDS exige des centimètres : confirmez l'unité avant de convertir."))
    else:
        s.append(_s(
            "EYELINK_NO_GEOMETRY",
            "No screen distance or size is logged. Without them gaze cannot be converted to "
            "degrees of visual angle: add ScreenDistance, ScreenSize to the README.",
            "Aucune distance ni taille d'écran n'est consignée. Sans elles, le regard ne peut pas "
            "être converti en degrés d'angle visuel : ajoutez ScreenDistance et ScreenSize au README."))

    if not raw.get("EdfCompanion"):
        s.append(_s(
            "EYELINK_ASC_ONLY",
            "This .asc is a text export of a binary EDF recording and the EDF is not in the folder. "
            "Archive the original .edf as well: the export can drop data and cannot be regenerated "
            "without it.",
            "Ce fichier .asc est une exportation texte d'un enregistrement EDF binaire et l'EDF n'est "
            "pas dans le dossier. Archivez aussi le fichier .edf d'origine : l'exportation peut "
            "omettre des données et ne peut pas être refaite sans lui."))
    s.append(_s(
        "EYELINK_NO_STUDY_CONTEXT",
        "The file carries no participant, session or task identifiers beyond its name, and no "
        "stimulus or task description. Supply them in the README (BIDS: sub/ses/task entities, "
        "TaskName, Instructions).",
        "Le fichier ne contient aucun identifiant de participant, de séance ou de tâche en dehors "
        "de son nom, ni description du stimulus ou de la tâche. Fournissez-les dans le README "
        "(BIDS : entités sub/ses/task, TaskName, Instructions)."))
    return s


def standardize_eyelink_metadata(raw_metadata):
    raw = raw_metadata
    name = os.path.basename(raw.get("FilePath", ""))
    if "Header" not in raw:  # not an EyeLink file, or unreadable
        return {"ImageName": name}
    head, cfg = raw["Header"], raw.get("Config") or {}
    counts, geo = raw["Counts"], raw.get("Geometry") or {}
    vals, cals = raw.get("Validations") or [], raw.get("Calibrations") or []
    disp = cfg.get("DisplayCoords") or []
    retrace = cfg.get("RetraceInterval_ms")
    tracking = {"CR": "Pupil-CR", "P": "Pupil"}.get(cfg.get("Tracking"), cfg.get("Tracking") or "")
    source = (head.get("SOURCE") or head.get("VERSION") or "").upper()

    d = {
        "ImageName": name,
        "FileFormat": "EyeLink ASCII (edf2asc)",
        "EyeTrackerManufacturer": "SR Research" if "EYELINK" in source or "EYELINK" in (head.get("VERSION") or "").upper() else "",
        "EyeTrackerModel": head.get("VERSION", ""),
        "SoftwareVersion": head.get("Tracker software", ""),
        "CameraModel": head.get("CAMERA", ""),
        "SerialNumber": head.get("SERIAL NUMBER", ""),
        "SamplingFrequency": cfg.get("Rate") or "",
        "ObservedSamplingFrequency": raw.get("ObservedRate") or "",
        "RecordedEye": "+".join(e.capitalize() for e in raw.get("Eyes") or []),
        "TrackingMethod": tracking,
        "SampleFilter": cfg.get("Filter", ""),
        "SampleType": cfg.get("SampleType", ""),
        "PupilMeasure": cfg.get("PupilMeasure", ""),
        "PupilFitMethod": cfg.get("PupilFitMethod", ""),
        "ScreenResolutionX": int(disp[2] - disp[0] + 1) if len(disp) == 4 and None not in disp else "",
        "ScreenResolutionY": int(disp[3] - disp[1] + 1) if len(disp) == 4 and None not in disp else "",
        "ScreenRefreshRate": round(1000.0 / retrace, 2) if retrace else "",
        "ScreenDistance": geo.get("disttoscreen", ""),
        "ScreenWidth": round(geo["swidthinches"] * 2.54, 2) if geo.get("swidthinches") else "",
        "ScreenHeight": round(geo["sheightinches"] * 2.54, 2) if geo.get("sheightinches") else "",
        "PixelsPerDegree": round(geo["PPD"], 3) if geo.get("PPD") else "",
        "SampleCount": counts["Samples"],
        "RecordingBlocks": raw["Blocks"],
        "RecordedDuration": raw["RecordedSeconds"],
        "MissingSamples": round(raw["MissingFraction"] * 100, 2) if raw.get("MissingFraction") is not None else "",
        "FixationCount": counts["Fixations"],
        "SaccadeCount": counts["Saccades"],
        "BlinkCount": counts["Blinks"],
        "TrialCount": counts["Trials"],
        "InputEventCount": counts["InputEvents"],
        "CalibrationCount": len(cals) or len(vals),
        "CalibrationType": (vals[-1]["Type"] if vals else (cals[-1]["Type"] if cals else "")),
        "CalibrationGrade": vals[-1]["Grade"] if vals else "",
        "AverageCalibrationError": vals[-1]["AvgError"] if vals else "",
        "MaximalCalibrationError": vals[-1]["MaxError"] if vals else "",
        "TrialVariables": ", ".join(raw.get("TrialVariables") or []),
        "ConvertedFrom": _real(head.get("CONVERTED FROM")),
        "RecordedBy": _real(head.get("RECORDED BY")),
        "ConversionDate": _real(head.get("DATE")),
        "EdfCompanion": raw.get("EdfCompanion", ""),
    }
    d["_Suggestions"] = _suggestions(raw, d)
    return d
