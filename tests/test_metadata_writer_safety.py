# tests/test_metadata_writer_safety.py
#
# _write_tiff_metadata() rewrites a .tif/.tiff file from its pixel array
# plus a new ImageDescription string, discarding every other tag. That
# silently destroys GeoTIFF georeferencing (ModelPixelScaleTag/
# ModelTiepointTag/GeoKeyDirectoryTag) and OME-TIFF's OME-XML structure
# (both live outside, or ARE, the tag this function overwrites).
# is_write_supported() is the policy gate main.py uses to keep those
# formats out of the write-back path entirely.

from utils.metadata_writer import is_write_supported, UNSAFE_TIFF_WRITE_FORMATS


def test_plain_tiff_is_supported():
    assert is_write_supported("sample.tif", "TIFF") is True
    assert is_write_supported("sample.tiff", "TIFF") is True


def test_jpg_is_supported_regardless_of_format_name():
    assert is_write_supported("sample.jpg", "General / EXIF") is True
    assert is_write_supported("sample.jpeg", None) is True


def test_geotiff_is_not_supported():
    assert is_write_supported("sample.tif", "GeoTIFF") is False


def test_ome_tiff_is_not_supported():
    assert is_write_supported("sample.ome.tiff", "OME-TIFF") is False


def test_unsupported_extension_is_not_supported():
    assert is_write_supported("sample.czi", "CZI") is False
    assert is_write_supported("sample.png", "PNG") is False


def test_missing_format_name_defaults_to_extension_check():
    # No format context supplied (e.g. called before a format is known) —
    # falls back to the plain extension check, same as the pre-existing
    # SUPPORTED_WRITE_EXTENSIONS behavior.
    assert is_write_supported("sample.tif") is True
    assert is_write_supported("sample.dcm") is False


def test_unsafe_formats_registry_matches_known_risks():
    assert UNSAFE_TIFF_WRITE_FORMATS == {"GeoTIFF", "OME-TIFF"}
