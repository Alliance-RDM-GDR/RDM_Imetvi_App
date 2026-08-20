# metadata_parsers/ome_tiff_parser.py

import os
import xml.etree.ElementTree as ET

from metadata_parsers.tiff_parser import parse_tiff_metadata

_OME_NAMESPACE_HINT = "openmicroscopy.org/Schemas/OME"


def is_ome_tiff(raw_metadata):
    """Returns True if the TIFF's ImageDescription holds an OME-XML block."""
    description = raw_metadata.get("ImageDescription", "")
    return isinstance(description, str) and _OME_NAMESPACE_HINT in description


def _strip_ns(tag):
    return tag.split("}", 1)[-1] if "}" in tag else tag


def parse_ome_tiff_metadata(file_path, application=None):
    """
    Extracts OME-XML metadata from an OME-TIFF file.
    Falls back to the standard TIFF parser when no OME-XML block is found.

    Returns:
        - text_report: A string report of raw metadata, line by line.
        - raw_metadata: A dictionary with metadata key-value pairs.
    """
    text_lines = [f"OME-TIFF Metadata Report for {os.path.basename(file_path)}"]
    base_text, base_raw = parse_tiff_metadata(file_path, application=application)

    if not is_ome_tiff(base_raw):
        text_lines.append("No OME-XML block found — falling back to standard TIFF metadata.")
        return base_text + "\n" + "\n".join(text_lines), base_raw

    raw_metadata = dict(base_raw)

    try:
        root = ET.fromstring(raw_metadata["ImageDescription"])

        image_node = next((c for c in root if _strip_ns(c.tag) == "Image"), None)
        instrument_node = next((c for c in root if _strip_ns(c.tag) == "Instrument"), None)

        raw_metadata["OME_ImageName"] = image_node.attrib.get("Name", "") if image_node is not None else ""

        acquisition_date = ""
        pixels_node = None
        channels = []
        if image_node is not None:
            for child in image_node:
                tag = _strip_ns(child.tag)
                if tag == "AcquisitionDate":
                    acquisition_date = child.text or ""
                elif tag == "Pixels":
                    pixels_node = child

        raw_metadata["OME_AcquisitionDate"] = acquisition_date

        if pixels_node is not None:
            attrs = pixels_node.attrib
            raw_metadata["OME_SizeX"] = attrs.get("SizeX", "")
            raw_metadata["OME_SizeY"] = attrs.get("SizeY", "")
            raw_metadata["OME_SizeZ"] = attrs.get("SizeZ", "")
            raw_metadata["OME_SizeC"] = attrs.get("SizeC", "")
            raw_metadata["OME_SizeT"] = attrs.get("SizeT", "")
            raw_metadata["OME_PhysicalSizeX"] = attrs.get("PhysicalSizeX", "")
            raw_metadata["OME_PhysicalSizeXUnit"] = attrs.get("PhysicalSizeXUnit", "")
            raw_metadata["OME_PhysicalSizeY"] = attrs.get("PhysicalSizeY", "")
            raw_metadata["OME_PhysicalSizeYUnit"] = attrs.get("PhysicalSizeYUnit", "")
            raw_metadata["OME_Type"] = attrs.get("Type", "")

            for child in pixels_node:
                if _strip_ns(child.tag) == "Channel":
                    channels.append({
                        "Name": child.attrib.get("Name", ""),
                        "SamplesPerPixel": child.attrib.get("SamplesPerPixel", ""),
                        "IlluminationType": child.attrib.get("IlluminationType", ""),
                    })

        raw_metadata["OME_Channels"] = channels

        if instrument_node is not None:
            objective_node = next((c for c in instrument_node if _strip_ns(c.tag) == "Objective"), None)
            if objective_node is not None:
                raw_metadata["OME_ObjectiveModel"] = objective_node.attrib.get("Model", "")
                raw_metadata["OME_ObjectiveMagnification"] = objective_node.attrib.get("NominalMagnification", "")
                raw_metadata["OME_ObjectiveNA"] = objective_node.attrib.get("LensNA", "")
                raw_metadata["OME_ObjectiveImmersion"] = objective_node.attrib.get("Immersion", "")
                raw_metadata["OME_ObjectiveCorrection"] = objective_node.attrib.get("Correction", "")

        for key, value in raw_metadata.items():
            if key.startswith("OME_"):
                text_lines.append(f"{key}: {value}")

    except Exception as e:
        text_lines.append(f"Failed to parse OME-XML: {str(e)}")

    return base_text + "\n" + "\n".join(text_lines), raw_metadata
