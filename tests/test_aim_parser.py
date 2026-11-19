# tests/test_aim_parser.py
#
# Synthetic Scanco AIM volumes mirroring the layout of FRDR deposit 1925
# (Lost Lagoon stickleback micro-CT): AIM 020 and the 64-bit AIM 030, a
# segmentation, the reader's .txt dump and the Amira .hx script.

import struct
from types import SimpleNamespace

import numpy as np
import pytest

import utils.curation_flags as curation_flags
from main import FORMAT_REGISTRY, MetadataViewer, formats_for_extension, get_standardizer
from metadata_parsers.aim_parser import (
    _vax_f_to_float, decode_rle_runs, parse_aim_log, parse_aim_metadata, parse_vms_date,
    read_aim_header, segmentation_slice,
)
from metadata_profiles.profile_registry import get_profile
from metadata_profiles.required_fields_registry import compute_missing_fields
from metadata_profiles.standards_registry import get_standard_info
from standardizers.aim_microct_standardizer import standardize_aim_microct_metadata
from utils.curation_flags import compute_curation_flags
from utils.thumbnail import generate_thumbnail_bytes

CONTEXT = "Micro-CT (Scanco)"
VAX_0_02 = bytes.fromhex("a33d0ad7")  # 0.02 mm as a VAX F-float, as found in real files
DIMS = (6, 5, 4)


def _line(key, value):
    return f"{key:<30}{value}\n"


def _log(patient="HJ_SB17_LL12_LL01_LL26", segmentation=False):
    text = ["!\n! Processing Log\n!\n", "!" + "-" * 79 + "\n"]
    text += [
        _line("Created by", "ISQ_TO_AIM (IPL)"),
        _line("Time", "22-MAR-2018 17:33:11.72"),
        _line("Original file", "dk0:[microct.data.00019420.00036352]c0015747.isq;"),
        _line("Original Creation-Date", "7-MAR-2018 10:25:53.15"),
        _line("Orig-ISQ-Dim-p", "1024 1024 1972"),
        _line("Orig-ISQ-Dim-um", "20480 20480 39440"),
        "!" + "-" * 79 + "\n",
        _line("Patient Name", patient),
        _line("Index Measurement", "36352"),
        "!" + "-" * 79 + "\n",
        _line("Scanner ID", "2339"), _line("Scanner type", "10"),
        _line("No. samples", "1024"), _line("No. projections per 180", "250"),
        _line("Scan Distance [um]", "20480"), _line("Integration time [us]", "200000"),
        _line("Reconstruction-Alg.", "3"), _line("Energy [V]", "70000"), _line("Intensity [uA]", "114"),
        "!" + "-" * 79 + "\n",
        _line("Mu_Scaling", "4096"),
        _line("Calibration Data", "70 kVp, BH: 1200 mg HA/ccm, Scaling 4096"),
        _line("Density: unit", "mg HA/ccm"), _line("Density: slope", "3.72606995e+02"),
        _line("Density: intercept", "-1.92766998e+02"), _line("HU: mu water", "0.47490"),
        "!" + "-" * 79 + "\n",
        _line("Parameter (before) name", "Linear Attenuation"), _line("Parameter units", "[1/cm]"),
        _line("Minimum data value", "-4778.00000"), _line("Maximum data value", "32767.00000"),
        _line("Average data value", "518.01025"), _line("Standard data deviation", "1167.95435"),
        "!" + "-" * 79 + "\n",
        _line("Procedure:", "D3P_GobjOrAimMaskAimPeel_OW()"),
        _line("Parameter name", "Linear Attenuation"), _line("Parameter units", "[1/cm]"),
        _line("Minimum value", "-1.16650"), _line("Maximum value", "7.99976"),
        _line("Minimum data value", "-4778.00000"), _line("Maximum data value", "32767.00000"),
        _line("Average data value", "890.98431"), _line("Standard data deviation", "1340.37720"),
        "!" + "-" * 79 + "\n",
    ]
    if segmentation:
        text += [
            _line("Procedure:", "D3P_SupGaussThres()"),
            _line("sigma", "0.80000"), _line("support", "1"), _line("Wished Unit of thresholds", "6"),
            _line("low_th_input", "110.00000"), _line("low corresponds to data value", "3604"),
            _line("and low to dens value", "135.08350"), _line("dens in units", "mg HA/ccm"),
            _line("upp_th_input", "1000.00000"), _line("and upp to dens value", "2787.99780"),
            "!" + "-" * 79 + "\n",
            _line("Procedure:", "D3P_Cl_Label_CPP()"),
            "!" + "-" * 79 + "\n",
            _line("Parameter name", "Segmented Objects"), _line("Parameter units", "[object]"),
            _line("Minimum data value", "0.00000"), _line("Maximum data value", "127.00000"),
            _line("Average data value (approx.)", "2.37471"),
            "!" + "-" * 79 + "\n",
        ]
    return "".join(text).encode("latin-1")


def encode_rle(mask):
    """Reference encoder for a segmentation block: alternating bg/fg runs, bg first."""
    flat = np.asarray(mask, dtype=bool).ravel()
    changes = np.flatnonzero(np.diff(flat.astype(np.int8))) + 1
    bounds = np.concatenate(([0], changes, [flat.size]))
    runs = list(np.diff(bounds))
    if flat[0]:
        runs.insert(0, 0)  # the stream always starts with a background run
    body = bytearray()
    for r in runs:
        r = int(r)
        while r >= 255:
            body.append(255)
            r -= 254
        body.append(r)
    block = bytearray(4) + bytes([0, 127]) + body
    struct.pack_into("<i", block, 0, len(block))
    return bytes(block)


def default_mask(dims=DIMS):
    mask = np.zeros(dims[::-1], dtype=bool)  # (z, y, x), x fastest
    mask[1:3, 1:4, 2:5] = True
    return mask


def write_aim(path, version="020", dims=DIMS, type_code=0x00020002, segmentation=False,
              patient="HJ_SB17_LL12_LL01_LL26", pos=(3, 2, 1), mask=None):
    """Writes a minimal AIM; returns the data offset. Short voxels = running index."""
    log = _log(patient, segmentation)
    n = dims[0] * dims[1] * dims[2]
    if segmentation:
        data = encode_rle(default_mask(dims) if mask is None else mask)
    else:
        data = (np.arange(n, dtype="<i2") * 7).tobytes()
    if version == "020":
        hdr = bytearray(160)
        struct.pack_into("<4i", hdr, 0, 20, 140, len(log), len(data))
        struct.pack_into("<I", hdr, 0x28, type_code)
        struct.pack_into("<3i", hdr, 0x2C, *pos)
        struct.pack_into("<3i", hdr, 0x38, *dims)
        hdr[0x80:0x8C] = VAX_0_02 * 3
    else:
        hdr = bytearray(280)
        hdr[:16] = b"AIMDATA_V030   \x00"
        struct.pack_into("<4q", hdr, 0x10, 40, 224, len(log), len(data))
        struct.pack_into("<I", hdr, 0x44, type_code)
        struct.pack_into("<3q", hdr, 0x48, *pos)
        struct.pack_into("<3q", hdr, 0x60, *dims)
        struct.pack_into("<3q", hdr, 0xF0, 20000, 20000, 20000)
    path.write_bytes(bytes(hdr) + log + data)
    return len(hdr) + len(log)


def write_txt(path, offset, dims=DIMS, pos=(3, 2, 1)):
    path.write_text(
        f"!%  Image Data starts at byte offset {offset}\n"
        f"!> dim {dims[0]:>20} {dims[1]:>7} {dims[2]:>7}\n"
        f"!> pos {pos[0]:>20} {pos[1]:>7} {pos[2]:>7}\n"
        "!> element size in mm             0.0200  0.0200  0.0200\n")


def write_hx(path, target, offset, dims=DIMS):
    path.write_text(
        "# Amira-Script-Object v3.0\n"
        f'load -raw ${{SCRIPTDIR}}/{target} little xfastest short 1 {dims[0]} {dims[1]} {dims[2]} '
        f'0 "0.1" 0 "0.08" 0 "0.06" -header {offset}\n')


def _std(path):
    text, raw = parse_aim_metadata(str(path), application=CONTEXT)
    return text, raw, standardize_aim_microct_metadata(raw)


def _codes(meta):
    return {s["Code"] for s in meta["_Suggestions"]}


@pytest.fixture
def sample(tmp_path):
    """ll01.aim + ll01.txt + ll01.hx (script names the file in upper case, as the real deposit does)."""
    off = write_aim(tmp_path / "ll01.aim")
    write_txt(tmp_path / "ll01.txt", off)
    write_hx(tmp_path / "ll01.hx", "LL01.AIM", off)
    return tmp_path / "ll01.aim"


# ── registration ────────────────────────────────────────────────────────────

def test_aim_is_registered():
    assert "AIM" in FORMAT_REGISTRY
    assert formats_for_extension(".aim") == ["AIM"]
    assert FORMAT_REGISTRY["AIM"]["contexts"] == [CONTEXT]
    assert get_standardizer("AIM", CONTEXT) is standardize_aim_microct_metadata
    assert get_standard_info(CONTEXT)["standard_name"]


# ── binary header ───────────────────────────────────────────────────────────

def test_vax_float_decoding():
    assert _vax_f_to_float(VAX_0_02) == pytest.approx(0.02, rel=1e-6)
    assert _vax_f_to_float(bytes.fromhex("80400000")) == pytest.approx(1.0)
    assert _vax_f_to_float(bytes.fromhex("80c00000")) == pytest.approx(-1.0)
    assert _vax_f_to_float(bytes(4)) == 0.0


def test_header_v020(tmp_path):
    off = write_aim(tmp_path / "a.aim")
    h = read_aim_header(str(tmp_path / "a.aim"))
    assert h["Version"] == "020" and h["DataOffset"] == off
    assert h["Dimensions"] == list(DIMS) and h["Position"] == [3, 2, 1]
    assert h["ElementSizeMM"] == pytest.approx([0.02] * 3, rel=1e-6)
    assert h["DataBytes"] == DIMS[0] * DIMS[1] * DIMS[2] * 2


def test_header_v030(tmp_path):
    off = write_aim(tmp_path / "a.aim", version="030")
    h = read_aim_header(str(tmp_path / "a.aim"))
    assert h["Version"] == "030" and h["DataOffset"] == off == 280 + h["LogBytes"]
    assert h["Dimensions"] == list(DIMS) and h["ElementSizeMM"] == pytest.approx([0.02] * 3)


def test_not_an_aim_is_rejected(tmp_path):
    p = tmp_path / "x.aim"
    p.write_bytes(b"this is not an AIM file" * 20)
    with pytest.raises(ValueError):
        read_aim_header(str(p))


# ── parsing ─────────────────────────────────────────────────────────────────

def test_parse_volume_fields(sample):
    text, raw = parse_aim_metadata(str(sample))
    assert raw["Dimensions"] == list(DIMS) and raw["VoxelType"] == "short (16-bit signed)"
    assert raw["Compressed"] is False and raw["Truncated"] is False
    assert raw["IsSegmentation"] is False
    assert raw["Log"]["Patient Name"] == "HJ_SB17_LL12_LL01_LL26"
    assert raw["Log"]["Calibration Data"].startswith("70 kVp")
    assert [p["Name"] for p in raw["Procedures"]] == ["D3P_GobjOrAimMaskAimPeel_OW"]
    assert raw["OriginalStatistics"]["MeanData"] == pytest.approx(518.01025)
    assert raw["StoredStatistics"]["MeanData"] == pytest.approx(890.98431)  # after masking
    assert raw["CompanionTxt"] == "ll01.txt" and raw["AmiraScript"] == "ll01.hx"
    assert "Matrix: 6 x 5 x 4 voxels" in text and "20 x 20 x 20 um" in text


def test_parse_v030_volume(tmp_path):
    write_aim(tmp_path / "big.aim", version="030")
    _, raw = parse_aim_metadata(str(tmp_path / "big.aim"))
    assert raw["Version"] == "030" and raw["Dimensions"] == list(DIMS) and raw["Truncated"] is False


def test_log_parser_handles_odd_keys():
    log = parse_aim_log("Gobj: ** FALSE ** Rel. Vol. of set AIM  0.52183364390\n"
                        "           dens in units      mg HA/ccm\n")
    assert log["Fields"]["Gobj: ** FALSE ** Rel. Vol. of set AIM"] == "0.52183364390"
    assert log["Fields"]["dens in units"] == "mg HA/ccm"


def test_vms_date():
    assert parse_vms_date("22-MAR-2018 17:33:11.72") == "2018-03-22T17:33:11"
    assert parse_vms_date("7-MAR-2018 10:25:53.15") == "2018-03-07T10:25:53"
    assert parse_vms_date("garbage") is None


def test_segmentation_file(tmp_path):
    write_aim(tmp_path / "ll01.aim")
    write_aim(tmp_path / "ll01_seg.aim", type_code=0x00150001, segmentation=True)
    text, raw, d = _std(tmp_path / "ll01_seg.aim")
    assert raw["IsSegmentation"] is True and raw["Compressed"] is True
    assert raw["ParentImage"] == "ll01.aim"
    assert raw["Segmentation"]["LowThresholdDensity"] == pytest.approx(135.0835)
    assert d["FileRole"] == "Segmentation (labelled objects)"
    assert d["LowThresholdDensity"] == pytest.approx(135.0835) and d["SegmentationSigma"] == 0.8
    assert "DataMean" not in d  # label statistics are not grey values
    assert "Segmentation: D3P_GobjOrAimMaskAimPeel_OW > D3P_SupGaussThres" in text
    assert "AIM_SEG_NO_PARENT" not in _codes(d)


def test_segmented_volume_is_computed(tmp_path):
    write_aim(tmp_path / "ll01_seg.aim", type_code=0x00150001, segmentation=True)
    text, raw, d = _std(tmp_path / "ll01_seg.aim")
    expected = int(default_mask().sum())  # 2 x 3 x 3 = 18 voxels
    assert raw["SegmentationDecoded"] is True and raw["SegmentedVoxels"] == expected == 18
    assert d["SegmentedVoxels"] == 18
    assert d["SegmentedVolume"] == pytest.approx(18 * 0.02 ** 3)  # mm3
    assert d["SegmentedFraction"] == pytest.approx(100 * 18 / (6 * 5 * 4))
    assert "Segmented volume: 18 voxels" in text


def test_volume_fields_absent_for_grey_value_volumes(sample):
    _, raw, d = _std(sample)
    assert raw["SegmentationDecoded"] is False
    assert "SegmentedVolume" not in d


def test_undecodable_segmentation_is_reported_not_guessed(tmp_path):
    p = tmp_path / "ll01_seg.aim"
    write_aim(p, type_code=0x00150001, segmentation=True)
    off = read_aim_header(str(p))["DataOffset"]
    blob = bytearray(p.read_bytes())
    blob[off + 10] ^= 0x7F  # corrupt a run length so the total no longer adds up
    p.write_bytes(bytes(blob))
    text, raw, d = _std(p)
    assert raw["SegmentationDecoded"] is False and "SegmentedVolume" not in d
    assert "not decoded" in text


@pytest.mark.parametrize("fg_run", [0, 1, 253, 254, 255, 256, 508, 509, 1000])
def test_rle_run_lengths_around_the_escape_boundary(fg_run):
    flat = np.zeros(2000, dtype=bool)
    flat[300:300 + fg_run] = True
    decoded = decode_rle_runs(encode_rle(flat), flat.size)
    assert decoded is not None
    runs, bg, fg = decoded
    assert (bg, fg) == (0, 127) and int(runs.sum()) == flat.size
    assert int(runs[1::2].sum()) == fg_run


def test_rle_rejects_bad_blocks():
    good = encode_rle(default_mask())
    n = 6 * 5 * 4
    assert decode_rle_runs(good, n) is not None
    assert decode_rle_runs(good, n + 1) is None            # runs do not add up
    assert decode_rle_runs(good[:-1], n) is None            # size field disagrees
    assert decode_rle_runs(b"\x03\x00\x00\x00", n) is None  # too short
    assert decode_rle_runs(good[:-1] + b"\xff", n) is None  # unterminated last run


def test_segmentation_slice_matches_the_mask():
    mask = default_mask()
    decoded = decode_rle_runs(encode_rle(mask), mask.size)
    for z in range(DIMS[2]):
        assert np.array_equal(segmentation_slice(decoded, list(DIMS), z), mask[z])


def test_segmentation_without_parent_is_suggested(tmp_path):
    write_aim(tmp_path / "ll09_seg.aim", type_code=0x00150001, segmentation=True)
    _, _, d = _std(tmp_path / "ll09_seg.aim")
    assert "AIM_SEG_NO_PARENT" in _codes(d)


# ── standardizer ────────────────────────────────────────────────────────────

def test_standardized_fields_and_units(sample):
    _, _, d = _std(sample)
    assert (d["MatrixSizeX"], d["MatrixSizeY"], d["MatrixSizeZ"]) == DIMS
    assert d["VoxelSizeX"] == pytest.approx(20.0) and d["PhysicalSizeX"] == pytest.approx(0.12)
    assert d["BitDepth"] == 16 and d["StoredCompressed"] == "no"
    assert d["TubeVoltage"] == pytest.approx(70.0) and d["TubeCurrent"] == pytest.approx(114.0)
    assert d["IntegrationTime"] == pytest.approx(200.0)
    assert d["ProjectionsPer180"] == 250 and isinstance(d["ProjectionsPer180"], int)
    assert d["AcquisitionDate"] == "2018-03-07T10:25:53"
    assert d["SourceScanFile"] == "c0015747.isq"
    assert d["SpecimenLabel"] == "HJ_SB17_LL12_LL01_LL26"
    assert d["DensitySlope"] == pytest.approx(372.606995)
    assert d["DataMean"] == pytest.approx(890.98431)
    # would make crops of different size false DIMENSION_OUTLIERs
    assert "DimensionX" not in d and "DimensionY" not in d


def test_every_standardized_key_has_a_label(sample, tmp_path):
    write_aim(tmp_path / "s_seg.aim", type_code=0x00150001, segmentation=True)
    profile = get_profile(CONTEXT)
    for path in (sample, tmp_path / "s_seg.aim"):
        _, _, d = _std(path)
        assert all(k in profile for k in d if not k.startswith("_")), path.name


def test_required_fields_complete_for_normal_file(sample):
    _, _, d = _std(sample)
    assert compute_missing_fields("AIM", d, CONTEXT) == []
    assert compute_missing_fields("AIM", {}, CONTEXT)  # an empty record is flagged


def test_biosample_and_instrument_suggestions_have_french(sample):
    _, _, d = _std(sample)
    assert {"AIM_NO_BIOSAMPLE", "AIM_INSTRUMENT_CODES_ONLY"} <= _codes(d)
    assert all(s["Message"] and s["Message_fr"] for s in d["_Suggestions"])


# ── companion files ─────────────────────────────────────────────────────────

def test_hx_case_mismatch_is_suggested_but_not_flagged(sample):
    text, raw, d = _std(sample)
    assert raw["AmiraScriptData"]["ReferencedFile"] == "LL01.AIM"
    assert raw["AmiraScriptData"]["ReferencedExactCase"] is False
    assert raw["AmiraScriptData"]["ReferencedExistsIgnoringCase"] is True
    assert "AIM_HX_CASE_MISMATCH" in _codes(d)
    flags, _ = compute_curation_flags([(str(sample), text, d)])
    assert flags[str(sample)] == []


def test_hx_with_matching_case_is_clean(tmp_path):
    off = write_aim(tmp_path / "ll01.aim")
    write_hx(tmp_path / "ll01.hx", "ll01.aim", off)
    _, _, d = _std(tmp_path / "ll01.aim")
    assert not {"AIM_HX_CASE_MISMATCH", "AIM_HX_TARGET_MISSING", "AIM_HX_GEOMETRY_MISMATCH"} & _codes(d)


def test_hx_pointing_at_a_missing_file_raises_flag(tmp_path):
    off = write_aim(tmp_path / "ll01.aim")
    write_hx(tmp_path / "ll01.hx", "other_scan.aim", off)
    text, _, d = _std(tmp_path / "ll01.aim")
    assert "AIM_HX_TARGET_MISSING" in _codes(d)
    flags, _ = compute_curation_flags([(str(tmp_path / "ll01.aim"), text, d)])
    assert "AIM_HX_BROKEN_LINK" in flags[str(tmp_path / "ll01.aim")]


def test_hx_geometry_mismatch(tmp_path):
    off = write_aim(tmp_path / "ll01.aim")
    write_hx(tmp_path / "ll01.hx", "ll01.aim", off + 12)
    _, _, d = _std(tmp_path / "ll01.aim")
    assert "AIM_HX_GEOMETRY_MISMATCH" in _codes(d)


def test_txt_that_disagrees_with_header(tmp_path):
    off = write_aim(tmp_path / "ll01.aim")
    write_txt(tmp_path / "ll01.txt", off, dims=(9, 9, 9))
    _, _, d = _std(tmp_path / "ll01.aim")
    assert "AIM_TXT_MISMATCH" in _codes(d)


def test_matching_txt_is_clean(sample):
    _, _, d = _std(sample)
    assert "AIM_TXT_MISMATCH" not in _codes(d)


# ── integrity ───────────────────────────────────────────────────────────────

def test_truncated_file_is_flagged(tmp_path):
    p = tmp_path / "ll01.aim"
    write_aim(p)
    p.write_bytes(p.read_bytes()[:-30])
    text, raw, d = _std(p)
    assert raw["Truncated"] is True and "WARNING" in text
    flags, _ = compute_curation_flags([(str(p), text, d)])
    assert "AIM_TRUNCATED" in flags[str(p)]


def test_corrupt_file_reports_failure_and_corrupt_flag(tmp_path):
    p = tmp_path / "bad.aim"
    p.write_bytes(b"\x00" * 64)
    text, raw = parse_aim_metadata(str(p))
    assert "Failed to read AIM file" in text
    d = standardize_aim_microct_metadata(raw)
    assert d["ImageName"] == "bad.aim" and "_Suggestions" not in d
    flags, _ = compute_curation_flags([(str(p), text, d)])
    assert "CORRUPT" in flags[str(p)]


def test_large_volumes_are_not_md5_hashed(tmp_path, monkeypatch):
    p = tmp_path / "ll01.aim"
    write_aim(p)
    assert curation_flags._compute_md5(str(p))  # tiny file: hashed
    monkeypatch.setitem(curation_flags.MAX_MD5_BYTES_BY_EXT, ".aim", 10)
    assert curation_flags._compute_md5(str(p)) is None


# ── thumbnail and folder discovery ──────────────────────────────────────────

def test_thumbnail_is_the_middle_slice(sample):
    png = generate_thumbnail_bytes(str(sample))
    assert png and png[:8] == b"\x89PNG\r\n\x1a\n"


def test_segmentation_thumbnail_is_its_mask(tmp_path):
    write_aim(tmp_path / "s_seg.aim", type_code=0x00150001, segmentation=True)
    png = generate_thumbnail_bytes(str(tmp_path / "s_seg.aim"))
    assert png and png[:8] == b"\x89PNG\r\n\x1a\n"


def test_no_thumbnail_for_undecodable_or_corrupt_volumes(tmp_path):
    p = tmp_path / "s_seg.aim"
    write_aim(p, type_code=0x00150001, segmentation=True)
    blob = bytearray(p.read_bytes())
    blob[read_aim_header(str(p))["DataOffset"] + 10] ^= 0x7F
    p.write_bytes(bytes(blob))
    (tmp_path / "bad.aim").write_bytes(b"\x00" * 64)
    assert generate_thumbnail_bytes(str(p)) is None
    assert generate_thumbnail_bytes(str(tmp_path / "bad.aim")) is None


def test_nested_sample_folders_are_found_and_format_selected(tmp_path):
    for name in ("LL_01", "LL_02"):
        (tmp_path / name).mkdir()
        write_aim(tmp_path / name / (name.replace("_", "").lower() + ".aim"))
        (tmp_path / name / "notes.txt").write_text("not an image")
    chosen = {"format": "TIFF"}
    stub = SimpleNamespace(
        format_dropdown=SimpleNamespace(currentText=lambda: chosen["format"]),
        select_format_for_extension=lambda p: chosen.update(format="AIM"),
    )
    found = MetadataViewer.collect_nested_files(stub, str(tmp_path))
    assert [p.replace("\\", "/").split("/")[-1] for p in found] == ["ll01.aim", "ll02.aim"]
    assert chosen["format"] == "AIM"


def test_nested_search_with_nothing_supported_returns_empty(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "readme.md").write_text("x")
    stub = SimpleNamespace(format_dropdown=SimpleNamespace(currentText=lambda: "TIFF"),
                           select_format_for_extension=lambda p: None)
    assert MetadataViewer.collect_nested_files(stub, str(tmp_path)) == []
