# tests/test_integrity.py

import json
import os

from utils.integrity import (
    compute_md5,
    checksums_path_for_folder,
    save_checksums,
    load_checksums,
    verify_checksums,
)


def test_compute_md5_known_content(tmp_path):
    f = tmp_path / "sample.bin"
    f.write_bytes(b"hello world")

    # md5("hello world") is a well-known fixed value
    assert compute_md5(str(f)) == "5eb63bbbe01eeed093cb22bb8f5acdc3"


def test_compute_md5_missing_file_returns_none(tmp_path):
    assert compute_md5(str(tmp_path / "ghost.bin")) is None


def test_checksums_path_for_folder(tmp_path):
    assert checksums_path_for_folder(str(tmp_path)) == str(tmp_path / "checksums.json")


def test_save_and_load_checksums_roundtrip(tmp_path):
    checksums = {"a.tif": "abc123", "b.jpg": "def456"}
    out_path = save_checksums(str(tmp_path), checksums)

    assert os.path.isfile(out_path)
    loaded = load_checksums(str(tmp_path))
    assert loaded == checksums


def test_load_checksums_returns_none_when_absent(tmp_path):
    assert load_checksums(str(tmp_path)) is None


def test_load_checksums_returns_none_on_corrupt_json(tmp_path):
    path = checksums_path_for_folder(str(tmp_path))
    with open(path, "w") as f:
        f.write("{not valid")

    assert load_checksums(str(tmp_path)) is None


def test_verify_checksums_all_ok():
    stored = {"a.tif": "abc", "b.tif": "def"}
    current = {"a.tif": "abc", "b.tif": "def"}

    result = verify_checksums(stored, current)
    assert result == {"a.tif": "OK", "b.tif": "OK"}


def test_verify_checksums_detects_modification():
    stored = {"a.tif": "abc"}
    current = {"a.tif": "xyz"}

    result = verify_checksums(stored, current)
    assert result == {"a.tif": "MODIFIED"}


def test_verify_checksums_detects_missing_file():
    stored = {"a.tif": "abc", "b.tif": "def"}
    current = {"a.tif": "abc"}

    result = verify_checksums(stored, current)
    assert result == {"a.tif": "OK", "b.tif": "MISSING"}


def test_verify_checksums_detects_new_file():
    stored = {"a.tif": "abc"}
    current = {"a.tif": "abc", "c.tif": "new"}

    result = verify_checksums(stored, current)
    assert result == {"a.tif": "OK", "c.tif": "NEW"}


def test_verify_checksums_mixed_scenario():
    stored = {"a.tif": "abc", "b.tif": "def", "c.tif": "ghi"}
    current = {"a.tif": "abc", "b.tif": "CHANGED", "d.tif": "new"}

    result = verify_checksums(stored, current)
    assert result == {
        "a.tif": "OK",
        "b.tif": "MODIFIED",
        "c.tif": "MISSING",
        "d.tif": "NEW",
    }
