# utils/metadata_writer.py

import json
import os

import piexif
import tifffile

from utils.serialization import make_json_serializable

SUPPORTED_WRITE_EXTENSIONS = (".jpg", ".jpeg", ".tif", ".tiff")

# Formats whose .tif/.tiff container holds structural metadata that
# _write_tiff_metadata() would destroy: it rewrites the file from the pixel
# array plus a new ImageDescription string only, dropping every other tag.
#   - GeoTIFF: georeferencing lives in ModelPixelScaleTag/ModelTiepointTag/
#     GeoKeyDirectoryTag — none of those survive the rewrite.
#   - OME-TIFF: the OME-XML (channel/plane/pixel-size structure) IS the
#     ImageDescription tag this function overwrites with plain JSON.
# Both are excluded from write support entirely rather than attempting a
# tag-preserving merge, which would need format-specific reconstruction
# logic (re-deriving GeoTIFF's GeoKeys, re-serializing valid OME-XML).
UNSAFE_TIFF_WRITE_FORMATS = {"GeoTIFF", "OME-TIFF"}


def is_write_supported(file_path, format_name=None):
    """
    Returns True if write_metadata_to_file() can safely handle file_path
    under the given format context.

    False when the extension isn't handled at all, or when format_name is
    one of UNSAFE_TIFF_WRITE_FORMATS — writing would silently destroy
    structural metadata that can't be reconstructed from the pixel data
    alone (see the comment above).
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in SUPPORTED_WRITE_EXTENSIONS:
        return False
    if format_name in UNSAFE_TIFF_WRITE_FORMATS:
        return False
    return True

# ── IPTC field mapping: standardized key → iptcinfo3 field name ──────────────
_IPTC_FIELD_MAP = {
    "Caption":              "caption/abstract",
    "ObjectName":           "object name",
    "Byline":               "by-line",
    "BylineTitle":          "by-line title",
    "Credit":               "credit",
    "Source":               "source",
    "IPTCCopyrightNotice":  "copyright notice",
    "City":                 "city",
    "ProvinceState":        "province/state",
    "Country":              "country/primary location name",
    "SpecialInstructions":  "special instructions",
}

# ── JPEG binary constants ─────────────────────────────────────────────────────
_SOI          = b"\xff\xd8"
_EOI          = b"\xff\xd9"
_APP1_MARKER  = b"\xff\xe1"
_XMP_MARKER   = b"http://ns.adobe.com/xap/1.0/\x00"


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def write_metadata_to_file(file_path, standardized_metadata):
    """
    Writes standardized metadata back into the image file.

    - JPG/JPEG: writes EXIF tags (piexif) + IPTC IIM fields (iptcinfo3)
      + an XMP packet (injected directly into the JPEG byte stream),
      all without re-encoding the image.
    - TIFF/TIF: writes the standardized metadata as a JSON string into
      the ImageDescription tag via tifffile (re-saves in place).

    Raises ValueError for unsupported extensions, re-raises I/O errors.
    """
    ext = os.path.splitext(file_path)[1].lower()

    if ext in (".jpg", ".jpeg"):
        _write_jpg_exif(file_path, standardized_metadata)
        _write_jpg_iptc(file_path, standardized_metadata)
        _write_jpg_xmp(file_path, standardized_metadata)
    elif ext in (".tif", ".tiff"):
        _write_tiff_metadata(file_path, standardized_metadata)
    else:
        raise ValueError(f"Writing metadata is not supported for files of type '{ext}'.")


# ─────────────────────────────────────────────────────────────────────────────
# JPEG — EXIF (piexif)
# ─────────────────────────────────────────────────────────────────────────────

def _write_jpg_exif(file_path, standardized_metadata):
    try:
        exif_dict = piexif.load(file_path)
    except Exception:
        exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}

    description = json.dumps(make_json_serializable(standardized_metadata))
    exif_dict.setdefault("0th", {})
    exif_dict["0th"][piexif.ImageIFD.ImageDescription] = description.encode("utf-8")

    if standardized_metadata.get("CameraMake"):
        exif_dict["0th"][piexif.ImageIFD.Make] = str(standardized_metadata["CameraMake"]).encode("utf-8")
    if standardized_metadata.get("CameraModel"):
        exif_dict["0th"][piexif.ImageIFD.Model] = str(standardized_metadata["CameraModel"]).encode("utf-8")
    if standardized_metadata.get("Software"):
        exif_dict["0th"][piexif.ImageIFD.Software] = str(standardized_metadata["Software"]).encode("utf-8")
    if standardized_metadata.get("AcquisitionDate"):
        exif_dict.setdefault("Exif", {})
        exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = str(standardized_metadata["AcquisitionDate"]).encode("utf-8")

    piexif.insert(piexif.dump(exif_dict), file_path)


# ─────────────────────────────────────────────────────────────────────────────
# JPEG — IPTC IIM (iptcinfo3)
# ─────────────────────────────────────────────────────────────────────────────

def _write_jpg_iptc(file_path, standardized_metadata):
    """Writes IPTC IIM fields to the JPEG using iptcinfo3."""
    import logging
    logging.getLogger("iptcinfo").setLevel(logging.ERROR)

    try:
        from iptcinfo3 import IPTCInfo
    except ImportError:
        return  # iptcinfo3 not installed — skip silently

    try:
        info = IPTCInfo(file_path, force=True)
    except Exception:
        return

    for std_key, iptc_field in _IPTC_FIELD_MAP.items():
        val = standardized_metadata.get(std_key)
        if val:
            info[iptc_field] = str(val)

    # Keywords: iptcinfo3 expects a list
    keywords_raw = standardized_metadata.get("Keywords", "")
    if isinstance(keywords_raw, str) and keywords_raw.strip():
        info["keywords"] = [k.strip() for k in keywords_raw.split(",") if k.strip()]
    elif isinstance(keywords_raw, list) and keywords_raw:
        info["keywords"] = [str(k) for k in keywords_raw]

    try:
        info.save_as(file_path)
    except Exception:
        pass  # Don't crash the overall write if IPTC save fails


# ─────────────────────────────────────────────────────────────────────────────
# JPEG — XMP (injected directly into JPEG byte stream)
# ─────────────────────────────────────────────────────────────────────────────

def _write_jpg_xmp(file_path, standardized_metadata):
    """Builds an XMP packet from standardized metadata and injects it into the JPEG."""
    xmp_string = _build_xmp_packet(standardized_metadata)
    _inject_xmp_into_jpeg(file_path, xmp_string)


def _build_xmp_packet(meta):
    """Returns a valid XMP/RDF XML string covering dc: and xmpRights: namespaces."""

    def _esc(s):
        """XML-escape a string value."""
        return (str(s)
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;"))

    caption   = _esc(meta.get("Caption", ""))
    creator   = _esc(meta.get("Byline") or meta.get("Author") or "")
    rights    = _esc(meta.get("XMPRights") or meta.get("IPTCCopyrightNotice") or "")
    usage     = _esc(meta.get("XMPUsageTerms") or "")
    credit    = _esc(meta.get("Credit") or "")
    source    = _esc(meta.get("Source") or "")

    keywords_raw = meta.get("Keywords") or meta.get("XMPSubject") or ""
    if isinstance(keywords_raw, str):
        keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()]
    elif isinstance(keywords_raw, list):
        keywords = [str(k) for k in keywords_raw]
    else:
        keywords = []

    subject_items = "\n".join(f"          <rdf:li>{_esc(k)}</rdf:li>" for k in keywords)
    subject_block = (
        f"\n      <dc:subject>\n        <rdf:Bag>\n{subject_items}\n        </rdf:Bag>\n      </dc:subject>"
        if keywords else ""
    )

    return (
        "<?xpacket begin='﻿' id='W5M0MpCehiHzreSzNTczkc9d'?>\n"
        "<x:xmpmeta xmlns:x='adobe:ns:meta/'>\n"
        "  <rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>\n"
        "    <rdf:Description rdf:about=''\n"
        "        xmlns:dc='http://purl.org/dc/elements/1.1/'\n"
        "        xmlns:xmpRights='http://ns.adobe.com/xap/1.0/rights/'\n"
        "        xmlns:photoshop='http://ns.adobe.com/photoshop/1.0/'>\n"
        f"      <dc:description><rdf:Alt><rdf:li xml:lang='x-default'>{caption}</rdf:li></rdf:Alt></dc:description>\n"
        f"      <dc:creator><rdf:Seq><rdf:li>{creator}</rdf:li></rdf:Seq></dc:creator>\n"
        f"      <dc:rights><rdf:Alt><rdf:li xml:lang='x-default'>{rights}</rdf:li></rdf:Alt></dc:rights>\n"
        f"      <xmpRights:UsageTerms><rdf:Alt><rdf:li xml:lang='x-default'>{usage}</rdf:li></rdf:Alt></xmpRights:UsageTerms>\n"
        f"      <photoshop:Credit>{credit}</photoshop:Credit>\n"
        f"      <photoshop:Source>{source}</photoshop:Source>"
        f"{subject_block}\n"
        "    </rdf:Description>\n"
        "  </rdf:RDF>\n"
        "</x:xmpmeta>\n"
        "<?xpacket end='w'?>"
    )


def _inject_xmp_into_jpeg(file_path, xmp_string):
    """
    Replaces any existing XMP APP1 segment in the JPEG and inserts the new one
    right after the SOI marker — no image data is re-encoded.
    """
    with open(file_path, "rb") as f:
        data = f.read()

    if not data.startswith(_SOI):
        raise ValueError("Not a valid JPEG file.")

    # Build new XMP APP1 segment
    xmp_bytes    = xmp_string.encode("utf-8")
    payload      = _XMP_MARKER + xmp_bytes
    seg_len      = len(payload) + 2            # length field includes itself
    new_segment  = _APP1_MARKER + seg_len.to_bytes(2, "big") + payload

    # Strip any pre-existing XMP APP1 segment, then prepend the new one
    cleaned = _remove_xmp_app1(data)
    result  = cleaned[:2] + new_segment + cleaned[2:]

    with open(file_path, "wb") as f:
        f.write(result)


def _remove_xmp_app1(data):
    """Returns JPEG bytes with any existing XMP APP1 segment removed."""
    out = bytearray(data[:2])   # copy SOI
    i   = 2
    while i < len(data) - 1:
        if data[i] != 0xFF:
            out.extend(data[i:])
            break
        marker = data[i:i + 2]
        # EOI or standalone markers (no length field)
        if marker == _EOI or (0xD0 <= data[i + 1] <= 0xD7) or data[i + 1] in (0x01, 0xD8):
            out.extend(data[i:])
            break
        if i + 3 >= len(data):
            out.extend(data[i:])
            break
        seg_len = int.from_bytes(data[i + 2:i + 4], "big")
        seg_end = i + 2 + seg_len
        # Drop APP1 segments that carry the XMP namespace marker
        if marker == _APP1_MARKER and data[i + 4: i + 4 + len(_XMP_MARKER)] == _XMP_MARKER:
            i = seg_end
        else:
            out.extend(data[i:seg_end])
            i = seg_end
    return bytes(out)


# ─────────────────────────────────────────────────────────────────────────────
# TIFF — ImageDescription tag (tifffile)
# ─────────────────────────────────────────────────────────────────────────────

def _write_tiff_metadata(file_path, standardized_metadata):
    description = json.dumps(make_json_serializable(standardized_metadata))
    with tifffile.TiffFile(file_path) as tif:
        image_data = tif.asarray()
    tifffile.imwrite(file_path, image_data, description=description)
