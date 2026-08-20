# metadata_parsers/dicom_parser.py

import os

import pydicom

# DICOM tags that identify the patient (PHI) are excluded by default. This
# app targets de-identified research datasets — patient identity should be
# handled by institutional anonymization tooling, not read into reports or
# exports here. See PatientName, PatientID, PatientBirthDate, etc.
_PHI_KEYWORDS = {
    "PatientName", "PatientID", "PatientBirthDate", "PatientAddress",
    "PatientTelephoneNumbers", "PatientMotherBirthName", "OtherPatientIDs",
    "OtherPatientNames", "PatientSex", "IssuerOfPatientID",
}

# Research-relevant tags safe to surface: acquisition/equipment context.
_TAGS_OF_INTEREST = [
    "Modality",
    "Manufacturer",
    "ManufacturerModelName",
    "StudyDate",
    "StudyDescription",
    "SeriesDescription",
    "BodyPartExamined",
    "ProtocolName",
    "Rows",
    "Columns",
    "PixelSpacing",
    "SliceThickness",
    "BitsAllocated",
    "BitsStored",
    "PhotometricInterpretation",
    "InstitutionName",
]


def parse_dicom_metadata(file_path, application=None):
    """
    Extracts DICOM metadata, excluding patient-identifying (PHI) fields by
    design. Returns (text_report, raw_metadata) per the parser contract.
    """
    text_lines = [f"DICOM Metadata Report for {os.path.basename(file_path)}"]
    raw_metadata = {
        "FilePath": file_path
    }

    try:
        ds = pydicom.dcmread(file_path, stop_before_pixels=True)

        for tag_name in _TAGS_OF_INTEREST:
            if tag_name in _PHI_KEYWORDS:
                continue
            if hasattr(ds, tag_name):
                value = getattr(ds, tag_name)
                value = str(value)
                raw_metadata[tag_name] = value
                text_lines.append(f"{tag_name}: {value}")

        text_lines.append("Note: patient-identifying fields (PatientName, PatientID, "
                           "PatientBirthDate, etc.) are intentionally excluded from this report.")

    except Exception as e:
        text_lines.append(f"Failed to read DICOM file: {str(e)}")

    return "\n".join(text_lines), raw_metadata
