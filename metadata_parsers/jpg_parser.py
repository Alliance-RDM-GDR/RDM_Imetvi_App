# metadata_parsers/jpg_parser.py

import logging
import os
import re

from PIL import Image
import piexif
from iptcinfo3 import IPTCInfo

# Map piexif tag names we care about to their EXIF IFD group
_TAGS_OF_INTEREST = [
    ("0th", "Make"),
    ("0th", "Model"),
    ("0th", "Software"),
    ("0th", "Artist"),
    ("0th", "Copyright"),
    ("0th", "ImageDescription"),
    ("0th", "XResolution"),
    ("0th", "YResolution"),
    ("Exif", "DateTimeOriginal"),
    ("Exif", "PixelXDimension"),
    ("Exif", "PixelYDimension"),
]

# IPTC IIM fields relevant to SSH (social sciences and humanities) research:
# provenance, rights, and descriptive context that EXIF does not carry.
_IPTC_FIELDS_OF_INTEREST = [
    "caption/abstract",
    "keywords",
    "by-line",
    "by-line title",
    "credit",
    "source",
    "copyright notice",
    "city",
    "province/state",
    "country/primary location name",
    "object name",
    "special instructions",
]

# Minimal XMP fields read directly from the embedded XMP packet via regex,
# since iptcinfo3 only covers legacy IPTC IIM, not XMP/RDF.
_XMP_PATTERNS = {
    "XMP_Rights_UsageTerms": r"<xmpRights:UsageTerms>.*?<rdf:li[^>]*>(.*?)</rdf:li>",
    "XMP_DC_Rights": r"<dc:rights>.*?<rdf:li[^>]*>(.*?)</rdf:li>",
    "XMP_DC_Subject": r"<dc:subject>.*?<rdf:li[^>]*>(.*?)</rdf:li>",
}

# iptcinfo3 logs verbosely (e.g. "could not determine file type") to its own
# logger; silence it so it does not spam stdout for files without IPTC data.
logging.getLogger("iptcinfo").setLevel(logging.ERROR)


def _decode(value):
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", errors="replace").strip("\x00").strip()
        except Exception:
            return str(value)
    return value


def _ratio_to_float(value):
    try:
        num, den = value
        return num / den if den else None
    except Exception:
        return None


def parse_jpg_metadata(file_path, application=None):
    """
    Extracts EXIF metadata from a JPG/JPEG file using Pillow + piexif.

    Returns:
        - text_report: A string report of raw metadata, line by line.
        - raw_metadata: A dictionary with metadata key-value pairs.
    """
    text_lines = [f"JPG Metadata Report for {os.path.basename(file_path)}"]
    raw_metadata = {
        "FilePath": file_path
    }

    try:
        with Image.open(file_path) as img:
            raw_metadata["ImageWidth"] = img.width
            raw_metadata["ImageLength"] = img.height
            raw_metadata["Format"] = img.format
            raw_metadata["Mode"] = img.mode
            text_lines.append(f"ImageWidth: {img.width}")
            text_lines.append(f"ImageLength: {img.height}")
            text_lines.append(f"Format: {img.format}")
            text_lines.append(f"Mode: {img.mode}")

            exif_bytes = img.info.get("exif")

        if exif_bytes:
            try:
                exif_dict = piexif.load(exif_bytes)
            except Exception:
                exif_dict = {}

            for ifd_name, tag_name in _TAGS_OF_INTEREST:
                ifd = exif_dict.get(ifd_name, {}) if exif_dict else {}
                tag_id = piexif.TAGS.get(ifd_name, {})
                tag_id = next((tid for tid, info in tag_id.items() if info["name"] == tag_name), None)
                if tag_id is not None and tag_id in ifd:
                    value = _decode(ifd[tag_id])
                    raw_metadata[tag_name] = value
                    text_lines.append(f"{tag_name}: {value}")

            # GPS info
            gps_ifd = exif_dict.get("GPS", {}) if exif_dict else {}
            if gps_ifd:
                raw_metadata["GPSInfo"] = gps_ifd
                text_lines.append(f"GPSInfo: {gps_ifd}")
        else:
            text_lines.append("No EXIF data found.")

        # === IPTC IIM ===
        try:
            iptc_info = IPTCInfo(file_path, force=True)
            for field in _IPTC_FIELDS_OF_INTEREST:
                value = iptc_info[field]
                if not value:
                    continue
                if isinstance(value, list):
                    value = [_decode(v) for v in value]
                else:
                    value = _decode(value)
                key = "IPTC_" + field.replace("/", "_").replace(" ", "_")
                raw_metadata[key] = value
                text_lines.append(f"{key}: {value}")
        except Exception:
            pass

        # === XMP (minimal, regex-based extraction from the raw XMP packet) ===
        try:
            with open(file_path, "rb") as f:
                raw_bytes = f.read()
            xmp_match = re.search(rb"<x:xmpmeta.*?</x:xmpmeta>", raw_bytes, re.DOTALL)
            if xmp_match:
                xmp_text = xmp_match.group(0).decode("utf-8", errors="replace")
                for key, pattern in _XMP_PATTERNS.items():
                    m = re.search(pattern, xmp_text, re.DOTALL)
                    if m:
                        value = m.group(1).strip()
                        raw_metadata[key] = value
                        text_lines.append(f"{key}: {value}")
        except Exception:
            pass

    except Exception as e:
        text_lines.append(f"Failed to read JPG file: {str(e)}")

    return "\n".join(text_lines), raw_metadata
