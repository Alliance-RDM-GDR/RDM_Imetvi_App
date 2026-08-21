# tests/test_tiff_compression_warning.py
#
# Verifies that tiff_parser detects JPEG compression inside a TIFF container
# and adds a CompressionWarning to the raw_metadata dict.

import numpy as np
import pytest
import tifffile

from metadata_parsers.tiff_parser import parse_tiff_metadata


@pytest.fixture
def jpeg_in_tiff(tmp_path):
    """Creates a TIFF file that stores pixel data with JPEG compression (type 7)."""
    file_path = tmp_path / "jpeg_compressed.tiff"
    data = np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8)
    tifffile.imwrite(str(file_path), data, compression="jpeg", metadata=None)
    return str(file_path)


def test_jpeg_compression_triggers_warning(jpeg_in_tiff):
    text_report, raw_metadata = parse_tiff_metadata(jpeg_in_tiff)

    assert "CompressionWarning" in raw_metadata
    assert "lossy" in raw_metadata["CompressionWarning"].lower()
    assert "CompressionWarning" in text_report


def test_lzw_tiff_has_no_compression_warning(synthetic_tiff):
    _, raw_metadata = parse_tiff_metadata(synthetic_tiff)
    assert "CompressionWarning" not in raw_metadata
