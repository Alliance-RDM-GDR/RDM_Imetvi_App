# tests/test_png_parser.py

import numpy as np
import pytest
from PIL import Image

from metadata_parsers.png_parser import parse_png_metadata
from standardizers.png_general_standardizer import standardize_png_general_metadata


@pytest.fixture
def synthetic_png(tmp_path):
    file_path = tmp_path / "synthetic.png"
    img = Image.new("RGB", (80, 60), color="red")
    # Embed text chunks
    from PIL.PngImagePlugin import PngInfo
    info = PngInfo()
    info.add_text("Author", "Test Author")
    info.add_text("Software", "pytest")
    info.add_text("Copyright", "CC-BY 4.0")
    img.save(str(file_path), pnginfo=info, dpi=(96, 96))
    return str(file_path)


@pytest.fixture
def synthetic_png_grayscale(tmp_path):
    file_path = tmp_path / "gray.png"
    img = Image.new("L", (32, 32), color=128)
    img.save(str(file_path))
    return str(file_path)


def test_parse_png_extracts_dimensions(synthetic_png):
    text_report, raw_metadata = parse_png_metadata(synthetic_png)

    assert isinstance(text_report, str)
    assert raw_metadata["ImageWidth"] == 80
    assert raw_metadata["ImageHeight"] == 60
    assert raw_metadata["Mode"] == "RGB"


def test_parse_png_extracts_text_chunks(synthetic_png):
    _, raw_metadata = parse_png_metadata(synthetic_png)

    assert raw_metadata.get("TextChunk_Author") == "Test Author"
    assert raw_metadata.get("TextChunk_Software") == "pytest"
    assert raw_metadata.get("TextChunk_Copyright") == "CC-BY 4.0"


def test_parse_png_grayscale_bit_depth(synthetic_png_grayscale):
    _, raw_metadata = parse_png_metadata(synthetic_png_grayscale)

    assert raw_metadata["Mode"] == "L"
    assert raw_metadata["BitDepth"] == 8


def test_standardize_png_maps_fields(synthetic_png):
    _, raw_metadata = parse_png_metadata(synthetic_png)
    result = standardize_png_general_metadata(raw_metadata)

    assert result["ImageWidth"] == "80"
    assert result["DimensionX"] == "80"
    assert result["Author"] == "Test Author"
    assert result["Copyright"] == "CC-BY 4.0"


def test_parse_png_handles_missing_file():
    text_report, raw_metadata = parse_png_metadata("does_not_exist.png")

    assert "Failed to read PNG file" in text_report
    assert raw_metadata["FilePath"] == "does_not_exist.png"
