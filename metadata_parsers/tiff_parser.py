# metadata_parsers/tiff_parser.py

import tifffile
import os

def parse_tiff_metadata(file_path, application=None):
    """
    Extracts all TIFF tags and additional metadata for microscopy images.

    Returns:
        - text_report: A string report of raw metadata, line by line.
        - raw_metadata: A dictionary with metadata key-value pairs.
    """
    text_lines = [f"TIFF Metadata Report for {os.path.basename(file_path)}"]
    raw_metadata = {
        "FilePath": file_path
    }

    try:
        with tifffile.TiffFile(file_path) as tif:
            page = tif.pages[0]

            for tag in page.tags.values():
                name = tag.name
                value = tag.value

                # Decode byte strings if needed
                if isinstance(value, bytes):
                    try:
                        value = value.decode("utf-8", errors="replace")
                    except Exception:
                        pass

                # Store full lists/tuples without truncating
                raw_metadata[name] = value
                text_lines.append(f"{name}: {value}")

            # Capture additional useful properties
            raw_metadata["Shape"] = getattr(page, 'shape', None)
            raw_metadata["DataType"] = getattr(page, 'dtype', None)

            text_lines.append(f"Shape: {raw_metadata['Shape']}")
            text_lines.append(f"DataType: {raw_metadata['DataType']}")

            # Extract IJMetadata if available (important for microscopy)
            if "IJMetadata" in page.tags:
                try:
                    ij_metadata = page.tags["IJMetadata"].value
                    if isinstance(ij_metadata, dict):
                        for k, v in ij_metadata.items():
                            raw_metadata[f"IJMetadata|{k}"] = v
                            text_lines.append(f"IJMetadata|{k}: {v}")
                except Exception:
                    pass

            # Some Zeiss CZI-TIFFs also have metadata in ImageDescription
            if "ImageDescription" in raw_metadata:
                image_description = raw_metadata["ImageDescription"]
                if isinstance(image_description, str) and "ImageJ" in image_description:
                    raw_metadata["SoftwareHint"] = "ImageJ-based"
                    text_lines.append("SoftwareHint: ImageJ-based")

            # Detect JPEG compression embedded inside a TIFF container.
            # TIFF Compression tag values 6 (old-JPEG) and 7 (JPEG) indicate
            # lossy compression, which is a data integrity risk for scientific
            # pixel analysis (values are not preserved losslessly).
            compression_val = raw_metadata.get("Compression")
            try:
                compression_int = int(compression_val)
            except (TypeError, ValueError):
                compression_int = None
            if compression_int in (6, 7):
                raw_metadata["CompressionWarning"] = (
                    "JPEG compression detected inside TIFF container (lossy). "
                    "Pixel values may not be preserved exactly — not suitable "
                    "for quantitative scientific analysis without verification."
                )
                text_lines.append(f"⚠ CompressionWarning: {raw_metadata['CompressionWarning']}")

    except Exception as e:
        text_lines.append(f"Failed to read TIFF file: {str(e)}")

    return "\n".join(text_lines), raw_metadata
