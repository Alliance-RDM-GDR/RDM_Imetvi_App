# tests/test_lif_parser.py
#
# Uses unittest.mock to simulate a readlif LifFile object since creating
# a valid binary LIF file without Leica's acquisition software is impractical.
# The graceful-error path is tested against a real (missing) file.

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from metadata_parsers.lif_parser import parse_lif_metadata, _extract_series
from standardizers.lif_microscopy_standardizer import standardize_lif_microscopy_metadata


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_mock_image(
    name="Series 1",
    dims=(512, 512, 10, 3, 1),
    channels=2,
    scale=(5.0, 5.0, 2.0, 1.0),  # px/µm
    bit_depth=(8, 8),
    settings=None,
    mosaic_position=None,
):
    """Returns a MagicMock that mimics a LifImage object."""
    img = MagicMock()
    img.name = name
    # dims namedtuple: x, y, z, t, m
    img.dims = SimpleNamespace(x=dims[0], y=dims[1], z=dims[2], t=dims[3], m=dims[4])
    img.channels = channels
    img.scale = scale
    img.bit_depth = bit_depth
    img.settings = settings or {
        "NumericalAperture": "0.75",
        "Magnification": "20",
        "Zoom": "1.0",
    }
    img.mosaic_position = mosaic_position or []
    return img


# ── _extract_series unit tests ────────────────────────────────────────────────

def test_extract_series_dimensions():
    img = _make_mock_image(dims=(1024, 512, 5, 2, 1))
    series = _extract_series(img, 0)

    assert series["SizeX"] == 1024
    assert series["SizeY"] == 512
    assert series["SizeZ"] == 5
    assert series["SizeT"] == 2
    assert series["NumChannels"] == 2


def test_extract_series_pixel_size_inversion():
    # scale = 4.0 px/µm → pixel size = 0.25 µm/px
    img = _make_mock_image(scale=(4.0, 4.0, 2.0, 1.0))
    series = _extract_series(img, 0)

    assert abs(series["PixelSizeX_um"] - 0.25) < 1e-6
    assert abs(series["PixelSizeY_um"] - 0.25) < 1e-6
    assert abs(series["PixelSizeZ_um"] - 0.5) < 1e-6


def test_extract_series_bit_depth():
    img = _make_mock_image(bit_depth=(16, 16))
    series = _extract_series(img, 0)

    assert series["BitDepth"] == 16
    assert series["BitDepthAllChannels"] == [16, 16]


def test_extract_series_settings():
    img = _make_mock_image(settings={
        "NumericalAperture": "0.8",
        "Magnification": "40",
        "Zoom": "2.5",
        "PinholeSize": "1.0",
    })
    series = _extract_series(img, 0)

    assert series["NA"] == "0.8"
    assert series["Magnification"] == "40"
    assert series["Zoom"] == "2.5"
    assert series["PinholeSize"] == "1.0"


def test_extract_series_mosaic():
    tiles = [(0, 0, 100.0, 200.0), (1, 0, 200.0, 200.0)]
    img = _make_mock_image(mosaic_position=tiles)
    series = _extract_series(img, 0)

    assert series["IsMosaic"] is True
    assert series["MosaicTiles"] == 2


# ── parse_lif_metadata integration (mocked LifFile) ──────────────────────────

def test_parse_lif_metadata_single_series(tmp_path):
    fake_file = str(tmp_path / "fake.lif")
    # Create a dummy file so os.path.getsize won't fail
    open(fake_file, "wb").close()

    mock_img = _make_mock_image(name="Confocal Z-stack")
    mock_lif = MagicMock()
    mock_lif.get_iter_image.return_value = [mock_img]

    with patch("metadata_parsers.lif_parser.LifFile", return_value=mock_lif):
        text_report, raw_metadata = parse_lif_metadata(fake_file)

    assert "Confocal Z-stack" in text_report
    assert raw_metadata["Name"] == "Confocal Z-stack"
    assert raw_metadata["SeriesCount"] == 1
    assert raw_metadata["SizeX"] == 512
    assert isinstance(raw_metadata["SeriesList"], list)
    assert len(raw_metadata["SeriesList"]) == 1


def test_parse_lif_metadata_multiple_series(tmp_path):
    fake_file = str(tmp_path / "multi.lif")
    open(fake_file, "wb").close()

    imgs = [
        _make_mock_image(name="Series A", dims=(256, 256, 1, 1, 1)),
        _make_mock_image(name="Series B", dims=(512, 512, 20, 5, 1)),
    ]
    mock_lif = MagicMock()
    mock_lif.get_iter_image.return_value = imgs

    with patch("metadata_parsers.lif_parser.LifFile", return_value=mock_lif):
        _, raw_metadata = parse_lif_metadata(fake_file)

    assert raw_metadata["SeriesCount"] == 2
    assert len(raw_metadata["SeriesList"]) == 2
    # Top-level keys reflect the first series
    assert raw_metadata["SizeX"] == 256


# ── standardizer ─────────────────────────────────────────────────────────────

def test_standardize_lif_maps_rembi_fields(tmp_path):
    fake_file = str(tmp_path / "fake.lif")
    open(fake_file, "wb").close()

    mock_img = _make_mock_image(
        name="Widefield 20x",
        dims=(1024, 1024, 15, 1, 1),
        scale=(5.0, 5.0, 2.0, 1.0),
        bit_depth=(8, 8),
        settings={"NumericalAperture": "0.75", "Magnification": "20"},
    )
    mock_lif = MagicMock()
    mock_lif.get_iter_image.return_value = [mock_img]

    with patch("metadata_parsers.lif_parser.LifFile", return_value=mock_lif):
        _, raw_metadata = parse_lif_metadata(fake_file)

    result = standardize_lif_microscopy_metadata(raw_metadata)

    assert result["ImageName"] == "Widefield 20x"
    assert result["DimensionX"] == "1024"
    assert result["SizeZ"] == "15"
    assert result["NumChannels"] == "2"
    assert result["NA"] == "0.75"
    assert result["Magnification"] == "20"
    assert abs(float(result["PixelSizeX"]) - 0.2) < 1e-5


# ── graceful error handling ───────────────────────────────────────────────────

def test_parse_lif_handles_missing_file():
    text_report, raw_metadata = parse_lif_metadata("does_not_exist.lif")

    assert "Failed to read LIF file" in text_report
    assert raw_metadata["FilePath"] == "does_not_exist.lif"
