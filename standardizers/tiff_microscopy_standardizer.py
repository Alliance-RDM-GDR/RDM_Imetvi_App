# standardizers/tiff_microscopy_standardizer.py

import os

def standardize_tiff_microscopy_metadata(raw_metadata):
    """
    Standardizes raw TIFF metadata into a microscopy-specific dictionary,
    structured for multi-channel information export.
    """

    file_path = raw_metadata.get("FilePath", "")
    img_width = raw_metadata.get("ImageWidth", "")
    img_length = raw_metadata.get("ImageLength", "")
    bits_per_sample = raw_metadata.get("BitsPerSample", "")

    px_size_x_str = ""
    px_size_y_str = ""
    px_size_z_str = ""

    if isinstance(raw_metadata.get("XResolution"), tuple):
        try:
            xres_num, xres_den = raw_metadata["XResolution"]
            px_size_x = xres_den / xres_num if xres_num else None
            px_size_x_str = str(px_size_x) if px_size_x is not None else ""
        except Exception:
            pass

    if isinstance(raw_metadata.get("YResolution"), tuple):
        try:
            yres_num, yres_den = raw_metadata["YResolution"]
            px_size_y = yres_den / yres_num if yres_num else None
            px_size_y_str = str(px_size_y) if px_size_y is not None else ""
        except Exception:
            pass

    extracted_fields = {}
    text_sources = []

    if isinstance(raw_metadata.get("ImageDescription"), str):
        text_sources.append(raw_metadata["ImageDescription"])
    if isinstance(raw_metadata.get("IJMetadata"), dict):
        for key, value in raw_metadata["IJMetadata"].items():
            if isinstance(value, str):
                text_sources.append(value)

    for text_block in text_sources:
        lines = text_block.splitlines()
        for line in lines:
            if '=' in line:
                parts = line.split('=', 1)
                key = parts[0].strip()
                value = parts[1].strip()
                extracted_fields[key] = value

    objective_name = (
        extracted_fields.get("Scaling|AutoScaling|ObjectiveName")
        or extracted_fields.get("Information|Instrument|Objective|Name")
        or extracted_fields.get("Information|Instrument|Objective|Manufacturer|Model")
        or ""
    )

    na = extracted_fields.get("Information|Instrument|Objective|LensNA", "")
    magnification = (
        extracted_fields.get("Information|Image|Magnification")
        or extracted_fields.get("Scaling|AutoScaling|OptovarMagnification")
        or ""
    )

    microscope_name = extracted_fields.get("Information|Instrument|Microscope|Name", "")
    microscope_type = extracted_fields.get("Information|Instrument|Microscope|Type", "")
    detector_name = extracted_fields.get("Information|Instrument|Detector|Name", "")
    detector_model = extracted_fields.get("Information|Instrument|Detector|Manufacturer|Model", "")
    light_source = extracted_fields.get("Information|Instrument|LightSource|Name #1", "")
    contour_type = extracted_fields.get("Experiment|AcquisitionBlock|RegionsSetup|SampleHolder|AllowedScanArea|ContourType", "")
    acquisition_time = extracted_fields.get("Information|Image|T|StartTime", "")

    channels_value = extracted_fields.get("channels", "")
    try:
        num_channels = int(channels_value)
    except Exception:
        num_channels = 0

    # Prepare dynamic channel fields
    channel_fields = {}
    for i in range(1, num_channels + 1):
        channel_name = extracted_fields.get(f"Experiment|AcquisitionBlock|MultiTrackSetup|Track|Channel|FluorescenceDye|ShortName #{i}", "")
        exposure_raw = extracted_fields.get(f"Information|Image|Channel|ExposureTime #{i}", "")
        try:
            exposure_sec = str(float(exposure_raw) / 1e9)  # From nanoseconds to seconds
        except Exception:
            exposure_sec = ""

        if channel_name:
            channel_fields[f"Channel_{i}_Name"] = channel_name
            channel_fields[f"Channel_{i}_Exposure"] = exposure_sec

    # Compose final dictionary
    dict_report = {
        "ImageName": os.path.basename(file_path),
        "AcquisitionTime": acquisition_time,
        "DimensionX": str(img_width) if img_width else "",
        "DimensionY": str(img_length) if img_length else "",
        "SizeZ": extracted_fields.get("SizeZ", ""),
        "SizeT": extracted_fields.get("SizeT", ""),
        "DefaultUnitFormat": extracted_fields.get("unit", ""),
        "ContourType": contour_type,
        "NumChannels": str(num_channels) if num_channels else "",
        "PixelSizeX": px_size_x_str,
        "PixelSizeY": px_size_y_str,
        "PixelSizeZ": px_size_z_str,
        "BitDepth": str(bits_per_sample) if bits_per_sample else "",
        "ObjectiveName": objective_name,
        "NA": na,
        "Magnification": magnification,
        "MicroscopeName": microscope_name,
        "MicroscopeType": microscope_type,
        "DetectorName": detector_name,
        "DetectorModel": detector_model,
        "LightSource": light_source
    }

    # Merge dynamic channel info into report
    dict_report.update(channel_fields)

    return dict_report
