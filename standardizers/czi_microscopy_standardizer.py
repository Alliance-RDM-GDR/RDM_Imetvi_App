# standardizers/standardize_czi_microscopy_metadata.py

import os

def standardize_czi_microscopy_metadata(raw_metadata):
    """
    Standardizes raw CZI metadata into a microscopy-specific dictionary compatible with REMBI.
    """

    file_path = raw_metadata.get("FilePath", "")

    dimension_x = raw_metadata.get("DimensionX", "")
    dimension_y = raw_metadata.get("DimensionY", "")
    size_z = raw_metadata.get("SizeZ", "")
    size_t = raw_metadata.get("SizeT", "")

    bit_depth = raw_metadata.get("BitDepth", "")
    pixel_size_x = raw_metadata.get("PixelSizeX", "")
    pixel_size_y = raw_metadata.get("PixelSizeY", "")
    pixel_size_z = raw_metadata.get("PixelSizeZ", "")

    acquisition_time = raw_metadata.get("AcquisitionTime", "")

    objective_name = raw_metadata.get("ObjectiveName", "")
    na = raw_metadata.get("NA", "")
    magnification = raw_metadata.get("Magnification", "")

    microscope_name = raw_metadata.get("MicroscopeName", "")
    microscope_type = raw_metadata.get("MicroscopeType", "")
    detector_name = raw_metadata.get("DetectorName", "")
    detector_model = raw_metadata.get("DetectorModel", "")
    light_source = raw_metadata.get("LightSource", "")
    contour_type = raw_metadata.get("ContourType", "")

    # Handle Channels
    channels_info = []
    channels = raw_metadata.get("Channels", [])
    for ch in channels:
        channel_entry = {
            "Name": ch.get("Name", ""),
            "ExcitationWavelength": ch.get("ExcitationWavelength", ""),
            "EmissionWavelength": ch.get("EmissionWavelength", ""),
            "ExposureTime_sec": ch.get("ExposureTime_sec", "")
        }
        channels_info.append(channel_entry)

    # Compose final standardized dictionary
    dict_report = {
        "ImageName": os.path.basename(file_path),
        "AcquisitionTime": acquisition_time,
        "DimensionX": dimension_x,
        "DimensionY": dimension_y,
        "SizeZ": size_z,
        "SizeT": size_t,
        "DefaultUnitFormat": "microns",
        "ContourType": contour_type,
        "NumChannels": str(len(channels_info)),
        "PixelSizeX": pixel_size_x,
        "PixelSizeY": pixel_size_y,
        "PixelSizeZ": pixel_size_z,
        "BitDepth": bit_depth,
        "ObjectiveName": objective_name,
        "NA": na,
        "Magnification": magnification,
        "Channels": channels_info,
        "MicroscopeName": microscope_name,
        "MicroscopeType": microscope_type,
        "DetectorName": detector_name,
        "DetectorModel": detector_model,
        "LightSource": light_source
    }

    return dict_report
