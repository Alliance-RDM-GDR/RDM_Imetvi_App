# standardizers/dicom_medical_standardizer.py

import os


def standardize_dicom_medical_metadata(raw_metadata):
    """
    Standardizes raw DICOM metadata into a research-oriented dictionary.
    Patient-identifying fields are never present in raw_metadata — see
    metadata_parsers/dicom_parser.py's PHI exclusion list.
    """

    file_path = raw_metadata.get("FilePath", "")

    pixel_spacing = raw_metadata.get("PixelSpacing", "")
    spacing_x, spacing_y = "", ""
    if pixel_spacing:
        try:
            parts = pixel_spacing.strip("[]").replace("'", "").split(",")
            spacing_x, spacing_y = parts[0].strip(), parts[1].strip()
        except Exception:
            pass

    dict_report = {
        "ImageName": os.path.basename(file_path),
        "Modality": raw_metadata.get("Modality", ""),
        "Manufacturer": raw_metadata.get("Manufacturer", ""),
        "ManufacturerModel": raw_metadata.get("ManufacturerModelName", ""),
        "StudyDate": raw_metadata.get("StudyDate", ""),
        "StudyDescription": raw_metadata.get("StudyDescription", ""),
        "SeriesDescription": raw_metadata.get("SeriesDescription", ""),
        "BodyPartExamined": raw_metadata.get("BodyPartExamined", ""),
        "ProtocolName": raw_metadata.get("ProtocolName", ""),
        "DimensionX": raw_metadata.get("Columns", ""),
        "DimensionY": raw_metadata.get("Rows", ""),
        "PixelSpacingX": spacing_x,
        "PixelSpacingY": spacing_y,
        "SliceThickness": raw_metadata.get("SliceThickness", ""),
        "BitsAllocated": raw_metadata.get("BitsAllocated", ""),
        "BitsStored": raw_metadata.get("BitsStored", ""),
        "PhotometricInterpretation": raw_metadata.get("PhotometricInterpretation", ""),
        "InstitutionName": raw_metadata.get("InstitutionName", ""),
    }

    return dict_report
