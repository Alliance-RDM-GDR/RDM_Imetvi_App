# tests/test_sidecar.py

import json
import os

import numpy as np

from utils.sidecar import write_sidecar, read_sidecar, sidecar_path_for


def test_sidecar_path_same_base_different_extension(tmp_path):
    img = str(tmp_path / "image.tif")
    assert sidecar_path_for(img) == str(tmp_path / "image.json")


def test_sidecar_path_jpeg(tmp_path):
    img = str(tmp_path / "photo.jpeg")
    assert sidecar_path_for(img) == str(tmp_path / "photo.json")


def test_write_sidecar_creates_file(tmp_path):
    img = str(tmp_path / "sample.tif")
    meta = {"ImageWidth": 1024, "ImageHeight": 512, "BitDepth": 8}

    out = write_sidecar(img, meta)

    assert os.path.isfile(out)
    assert out == str(tmp_path / "sample.json")


def test_write_sidecar_content_roundtrip(tmp_path):
    img = str(tmp_path / "sample.tif")
    meta = {
        "ImageWidth": 512,
        "Author": "Test Author",
        "Keywords": ["confocal", "z-stack"],
    }

    write_sidecar(img, meta)
    loaded = json.loads(open(str(tmp_path / "sample.json"), encoding="utf-8").read())

    assert loaded["ImageWidth"] == 512
    assert loaded["Author"] == "Test Author"
    assert loaded["Keywords"] == ["confocal", "z-stack"]


def test_write_sidecar_handles_numpy_types(tmp_path):
    img = str(tmp_path / "array.tif")
    meta = {
        "DimensionX": np.int64(1024),
        "PixelSizeX": np.float32(0.125),
    }

    write_sidecar(img, meta)
    loaded = json.loads(open(str(tmp_path / "array.json"), encoding="utf-8").read())

    assert loaded["DimensionX"] == 1024
    assert abs(loaded["PixelSizeX"] - 0.125) < 1e-4


def test_read_sidecar_returns_none_when_missing(tmp_path):
    img = str(tmp_path / "ghost.tif")
    assert read_sidecar(img) is None


def test_read_sidecar_returns_dict_when_present(tmp_path):
    img = str(tmp_path / "sample.tif")
    meta = {"Standard": "REMBI", "Version": "1.0"}
    write_sidecar(img, meta)

    result = read_sidecar(img)
    assert result == meta


def test_read_sidecar_returns_none_on_corrupt_json(tmp_path):
    img = str(tmp_path / "broken.tif")
    sidecar = str(tmp_path / "broken.json")
    with open(sidecar, "w") as f:
        f.write("not valid json {{{")

    assert read_sidecar(img) is None
