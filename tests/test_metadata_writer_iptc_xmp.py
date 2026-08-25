# tests/test_metadata_writer_iptc_xmp.py
#
# Verifies that IPTC and XMP fields are written to JPEG files correctly
# without re-encoding the image data.

import shutil
import pytest
from PIL import Image


# ── helpers ──────────────────────────────────────────────────────────────────

def _sample_metadata():
    return {
        "Caption":             "A test caption for curation",
        "Keywords":            "test, curation, metadata",
        "Byline":              "Jane Doe",
        "BylineTitle":         "Archivist",
        "Credit":              "Test Lab",
        "Source":              "USask Archive",
        "IPTCCopyrightNotice": "CC-BY 4.0",
        "City":                "Saskatoon",
        "ProvinceState":       "Saskatchewan",
        "Country":             "Canada",
        "ObjectName":          "Test Image",
        "SpecialInstructions": "Handle with care",
        "XMPRights":           "CC-BY 4.0",
        "XMPUsageTerms":       "Free for research use",
    }


# ── IPTC tests ────────────────────────────────────────────────────────────────

def test_write_iptc_fields_readable_back(synthetic_jpg, tmp_path):
    import logging
    logging.getLogger("iptcinfo").setLevel(logging.ERROR)
    from iptcinfo3 import IPTCInfo
    from utils.metadata_writer import _write_jpg_iptc

    dest = str(tmp_path / "out.jpg")
    shutil.copy2(synthetic_jpg, dest)

    _write_jpg_iptc(dest, _sample_metadata())

    info = IPTCInfo(dest, force=True)
    # iptcinfo3 returns bytes for string fields
    assert info["caption/abstract"] in ("A test caption for curation", b"A test caption for curation")
    assert info["city"] in ("Saskatoon", b"Saskatoon")
    assert info["copyright notice"] in ("CC-BY 4.0", b"CC-BY 4.0")
    kws = [k.decode() if isinstance(k, bytes) else k for k in info["keywords"]]
    assert "test" in kws
    assert "curation" in kws


def test_write_iptc_skips_empty_fields(synthetic_jpg, tmp_path):
    import logging
    logging.getLogger("iptcinfo").setLevel(logging.ERROR)
    from iptcinfo3 import IPTCInfo
    from utils.metadata_writer import _write_jpg_iptc

    dest = str(tmp_path / "out.jpg")
    shutil.copy2(synthetic_jpg, dest)

    _write_jpg_iptc(dest, {"Caption": "Only caption"})

    info = IPTCInfo(dest, force=True)
    assert info["caption/abstract"] in ("Only caption", b"Only caption")
    # city should not be set
    assert not info["city"]


# ── XMP tests ─────────────────────────────────────────────────────────────────

def test_build_xmp_packet_contains_expected_fields():
    from utils.metadata_writer import _build_xmp_packet

    xmp = _build_xmp_packet(_sample_metadata())

    assert "A test caption for curation" in xmp
    assert "Jane Doe" in xmp
    assert "CC-BY 4.0" in xmp
    assert "Free for research use" in xmp
    assert "<rdf:li>test</rdf:li>" in xmp
    assert "<rdf:li>curation</rdf:li>" in xmp


def test_xmp_roundtrip_jpeg(synthetic_jpg, tmp_path):
    """XMP packet survives a write → re-read cycle."""
    from utils.metadata_writer import _write_jpg_xmp

    dest = str(tmp_path / "out.jpg")
    shutil.copy2(synthetic_jpg, dest)

    _write_jpg_xmp(dest, _sample_metadata())

    with open(dest, "rb") as f:
        data = f.read()

    # XMP namespace marker must be present in the file bytes
    assert b"http://ns.adobe.com/xap/1.0/" in data
    # Content from the packet must be present
    assert b"A test caption for curation" in data
    assert b"Jane Doe" in data


def test_xmp_injection_replaces_existing(synthetic_jpg, tmp_path):
    """Writing XMP twice replaces the first packet, not appends."""
    from utils.metadata_writer import _write_jpg_xmp

    dest = str(tmp_path / "out.jpg")
    shutil.copy2(synthetic_jpg, dest)

    _write_jpg_xmp(dest, {"Caption": "First caption"})
    _write_jpg_xmp(dest, {"Caption": "Second caption"})

    with open(dest, "rb") as f:
        data = f.read()

    assert b"Second caption" in data
    assert b"First caption" not in data


def test_xmp_does_not_corrupt_jpeg(synthetic_jpg, tmp_path):
    """After XMP injection the JPEG is still readable by Pillow."""
    from utils.metadata_writer import _write_jpg_xmp

    dest = str(tmp_path / "out.jpg")
    shutil.copy2(synthetic_jpg, dest)
    _write_jpg_xmp(dest, _sample_metadata())

    with Image.open(dest) as img:
        assert img.width == 64
        assert img.height == 48


# ── full write_metadata_to_file integration ───────────────────────────────────

def test_full_write_metadata_to_file_jpeg(synthetic_jpg, tmp_path):
    """write_metadata_to_file runs all three write paths without error."""
    from utils.metadata_writer import write_metadata_to_file

    dest = str(tmp_path / "out.jpg")
    shutil.copy2(synthetic_jpg, dest)

    write_metadata_to_file(dest, _sample_metadata())

    # File must still be a valid JPEG
    with Image.open(dest) as img:
        assert img.format == "JPEG"

    # XMP must be present
    with open(dest, "rb") as f:
        data = f.read()
    assert b"A test caption for curation" in data
