# metadata_parsers/png_parser.py
#
# Extracts metadata from PNG files using Pillow.
# PNG embeds metadata in text chunks (tEXt, iTXt, zTXt) and the
# standard header (dimensions, bit depth, color mode, DPI).

import os
from PIL import Image

_TEXT_FIELDS_OF_INTEREST = {
    "Author", "Comment", "Copyright", "Creation Time", "Description",
    "Disclaimer", "Software", "Source", "Title", "Warning",
    # XMP packet sometimes stored as iTXt chunk
    "XML:com.adobe.xmp",
}


def parse_png_metadata(file_path, application=None):
    text_lines = [f"PNG Metadata Report for {os.path.basename(file_path)}"]
    raw_metadata = {"FilePath": file_path}

    try:
        with Image.open(file_path) as img:
            raw_metadata["Format"] = img.format or "PNG"
            raw_metadata["Mode"] = img.mode          # RGB, RGBA, L, P, etc.
            raw_metadata["ImageWidth"] = img.width
            raw_metadata["ImageHeight"] = img.height

            text_lines.append(f"Format: {raw_metadata['Format']}")
            text_lines.append(f"ColorMode: {img.mode}")
            text_lines.append(f"Width: {img.width} px")
            text_lines.append(f"Height: {img.height} px")

            # Bit depth from mode
            _MODE_DEPTH = {
                "1": 1, "L": 8, "P": 8, "RGB": 8, "RGBA": 8,
                "LA": 8, "I": 32, "F": 32, "I;16": 16,
            }
            raw_metadata["BitDepth"] = _MODE_DEPTH.get(img.mode, "Unknown")
            text_lines.append(f"BitDepth: {raw_metadata['BitDepth']} bit")

            # DPI / resolution
            dpi = img.info.get("dpi")
            if dpi:
                raw_metadata["ResolutionX"] = dpi[0]
                raw_metadata["ResolutionY"] = dpi[1]
                text_lines.append(f"ResolutionX: {dpi[0]} dpi")
                text_lines.append(f"ResolutionY: {dpi[1]} dpi")

            # Text chunks (tEXt / iTXt / zTXt)
            png_info = img.info or {}
            for key, value in png_info.items():
                if key == "dpi":
                    continue
                if isinstance(value, (str, bytes)):
                    str_val = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value
                    raw_metadata[f"TextChunk_{key}"] = str_val
                    text_lines.append(f"TextChunk_{key}: {str_val[:200]}")

            # File size
            try:
                raw_metadata["FileSizeMB"] = round(os.path.getsize(file_path) / 1024 ** 2, 3)
                text_lines.append(f"FileSizeMB: {raw_metadata['FileSizeMB']}")
            except OSError:
                pass

    except Exception as e:
        msg = f"Failed to read PNG file: {str(e)}"
        text_lines.append(msg)
        raw_metadata["Error"] = msg

    return "\n".join(text_lines), raw_metadata
