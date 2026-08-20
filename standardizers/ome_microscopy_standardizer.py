# standardizers/ome_microscopy_standardizer.py

import os


def standardize_ome_microscopy_metadata(raw_metadata):
    """
    Standardizes raw OME-XML metadata into a microscopy-specific dictionary.
    Falls back to whatever plain-TIFF fields are present (e.g. ImageWidth)
    when the file had no OME-XML block — see ome_tiff_parser.is_ome_tiff.
    """

    file_path = raw_metadata.get("FilePath", "")

    channels_info = [
        {
            "Name": ch.get("Name", ""),
            "SamplesPerPixel": ch.get("SamplesPerPixel", ""),
            "IlluminationType": ch.get("IlluminationType", ""),
        }
        for ch in raw_metadata.get("OME_Channels", [])
    ]

    dict_report = {
        "ImageName": raw_metadata.get("OME_ImageName") or os.path.basename(file_path),
        "AcquisitionDate": raw_metadata.get("OME_AcquisitionDate", ""),
        "DimensionX": raw_metadata.get("OME_SizeX") or str(raw_metadata.get("ImageWidth", "")),
        "DimensionY": raw_metadata.get("OME_SizeY") or str(raw_metadata.get("ImageLength", "")),
        "SizeZ": raw_metadata.get("OME_SizeZ", ""),
        "SizeC": raw_metadata.get("OME_SizeC", ""),
        "SizeT": raw_metadata.get("OME_SizeT", ""),
        "PixelType": raw_metadata.get("OME_Type", ""),
        "PixelSizeX": raw_metadata.get("OME_PhysicalSizeX", ""),
        "PixelSizeXUnit": raw_metadata.get("OME_PhysicalSizeXUnit", ""),
        "PixelSizeY": raw_metadata.get("OME_PhysicalSizeY", ""),
        "PixelSizeYUnit": raw_metadata.get("OME_PhysicalSizeYUnit", ""),
        "ObjectiveModel": raw_metadata.get("OME_ObjectiveModel", ""),
        "ObjectiveMagnification": raw_metadata.get("OME_ObjectiveMagnification", ""),
        "ObjectiveNA": raw_metadata.get("OME_ObjectiveNA", ""),
        "ObjectiveImmersion": raw_metadata.get("OME_ObjectiveImmersion", ""),
        "ObjectiveCorrection": raw_metadata.get("OME_ObjectiveCorrection", ""),
        "Channels": channels_info,
    }

    return dict_report
