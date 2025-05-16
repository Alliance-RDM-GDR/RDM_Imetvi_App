# metadata_parsers/czi_parser.py

import czifile
import xml.etree.ElementTree as ET
import os

def parse_czi_metadata(file_path, application="Microscopy"):
    """
    Parse CZI metadata for Microscopy application.
    """
    czi = czifile.CziFile(file_path)
    metadata_xml = czi.metadata()
    root = ET.fromstring(metadata_xml)

    # Prepare extracted fields
    extracted_metadata = {
        "FilePath": file_path,
        "AcquisitionTime": "",
        "PixelSizeX": "",
        "PixelSizeY": "",
        "PixelSizeZ": "",
        "BitDepth": "",
        "DimensionX": "",
        "DimensionY": "",
        "SizeZ": "",
        "SizeT": "",
        "ObjectiveName": "",
        "NA": "",
        "MicroscopeName": "",
        "MicroscopeType": "",
        "DetectorName": "",
        "DetectorModel": "",
        "LightSource": "",
        "Channels": [],
        "ContourType": ""
    }

    # === AcquisitionTime ===
    acq_node = root.find(".//AcquisitionDateAndTime")
    if acq_node is not None:
        extracted_metadata["AcquisitionTime"] = acq_node.text

    # === Dimensions ===
    extracted_metadata["DimensionX"] = root.findtext(".//SizeX", default="")
    extracted_metadata["DimensionY"] = root.findtext(".//SizeY", default="")
    extracted_metadata["SizeZ"] = root.findtext(".//SizeB", default="")  # SizeB → Z slices
    extracted_metadata["SizeT"] = root.findtext(".//SizeT", default="")  # SizeT if available

    # === Pixel Sizes ===
    scale_x = root.findtext(".//Scaling/Items/Distance[@Id='X']/Value")
    scale_y = root.findtext(".//Scaling/Items/Distance[@Id='Y']/Value")
    scale_z = root.findtext(".//Scaling/Items/Distance[@Id='Z']/Value")

    extracted_metadata["PixelSizeX"] = scale_x if scale_x else ""
    extracted_metadata["PixelSizeY"] = scale_y if scale_y else ""
    extracted_metadata["PixelSizeZ"] = scale_z if scale_z else ""

    # === BitDepth ===
    bit_depth = root.findtext(".//ComponentBitCount")
    if bit_depth:
        extracted_metadata["BitDepth"] = bit_depth

    # === Objective Name and NA ===
    objective_node = root.find(".//ChangerElements/Objective")
    if objective_node is not None:
        extracted_metadata["ObjectiveName"] = objective_node.attrib.get("Name", "")
        extracted_metadata["NA"] = root.findtext(".//ChangerElements/Objective/NumericalAperture", default="")

    # === Microscope Name and Type ===
    microscope_node = root.find(".//Microscopes/Microscope")
    if microscope_node is not None:
        extracted_metadata["MicroscopeName"] = microscope_node.attrib.get("Name", "")
        extracted_metadata["MicroscopeType"] = root.findtext(".//Microscopes/Microscope/Type", default="")

    # === Total Magnification from EyepieceSettings ===
    total_mag = root.findtext(".//EyepieceSettings/TotalMagnification")
    if total_mag:
        extracted_metadata["Magnification"] = total_mag

    # === Detector Name and Model ===
    detector_node = root.find(".//Detectors/Detector")
    if detector_node is not None:
        extracted_metadata["DetectorName"] = detector_node.attrib.get("Name", "")
        extracted_metadata["DetectorModel"] = root.findtext(".//Detectors/Detector/Manufacturer/Model", default="")

    # === Light Source ===
    light_node = root.find(".//LightSources/LightSource")
    if light_node is not None:
        extracted_metadata["LightSource"] = light_node.attrib.get("Name", "")

    # === Contour Type (e.g., Rectangle) ===
    contour_node = root.find(".//AllowedScanArea/ContourType")
    if contour_node is not None:
        extracted_metadata["ContourType"] = contour_node.text

    # === Channels and ExposureTimes ===
    channels = []
    channel_nodes = root.findall(".//Information/Image/Dimensions/Channels/Channel")

    for idx, ch in enumerate(channel_nodes):
        fluor = ch.findtext("Fluor", default="")
        excitation = ch.findtext("ExcitationWavelength", default="")
        emission = ch.findtext("EmissionWavelength", default="")
        raw_exposure = ch.findtext("ExposureTime", default="")

        try:
            exposure_sec = str(float(raw_exposure) / 1e9) if raw_exposure else ""
        except:
            exposure_sec = ""

        channel_info = {
            "Name": fluor,
            "ExcitationWavelength": excitation,
            "EmissionWavelength": emission,
            "ExposureTime_sec": exposure_sec
        }
        channels.append(channel_info)

    extracted_metadata["Channels"] = channels

    # Return full report
    text_report = generate_text_summary(file_path, extracted_metadata)
    return text_report, extracted_metadata

def generate_text_summary(file_path, metadata):
    """
    Create a human-readable text report for left panel.
    """
    lines = []
    lines.append(f"CZI Metadata Report for {os.path.basename(file_path)}")
    lines.append(f"AcquisitionTime: {metadata.get('AcquisitionTime', '')}")

    lines.append(f"PixelSizeX: {metadata.get('PixelSizeX', '')}")
    lines.append(f"PixelSizeY: {metadata.get('PixelSizeY', '')}")
    lines.append(f"PixelSizeZ: {metadata.get('PixelSizeZ', '')}")
    lines.append(f"BitDepth: {metadata.get('BitDepth', '')}")

    lines.append(f"MicroscopeName: {metadata.get('MicroscopeName', '')}")
    lines.append(f"MicroscopeType: {metadata.get('MicroscopeType', '')}")
    lines.append(f"ObjectiveName: {metadata.get('ObjectiveName', '')}")
    lines.append(f"NA: {metadata.get('NA', '')}")
    lines.append(f"DetectorName: {metadata.get('DetectorName', '')}")
    lines.append(f"DetectorModel: {metadata.get('DetectorModel', '')}")
    lines.append(f"LightSource: {metadata.get('LightSource', '')}")

    lines.append(f"Magnification: {metadata.get('Magnification', '')}")
    lines.append(f"Channels found: {len(metadata.get('Channels', []))}")

    lines.append(f"ContourType: {metadata.get('ContourType', '')}")

    return "\n".join(lines)
