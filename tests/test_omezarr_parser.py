# tests/test_omezarr_parser.py
#
# Synthetic OME-Zarr (zarr v2, OME-NGFF 0.4) in a BIDS-Microscopy layout, read
# both from a .zarr folder and from an uncompressed .tar, like the FRDR 1828
# light-sheet deposits (SPIMprep output).

import json
import tarfile

import pytest

from main import FORMAT_REGISTRY, formats_for_extension, get_standardizer
from metadata_parsers.omezarr_parser import parse_omezarr_metadata
from metadata_profiles.profile_registry import get_profile
from metadata_profiles.required_fields_registry import compute_missing_fields
from standardizers.omezarr_microscopy_standardizer import standardize_omezarr_microscopy_metadata
from utils.curation_flags import compute_curation_flags

ZATTRS = {"multiscales": [{
    "version": "0.4",
    "axes": [{"name": "c", "type": "channel"},
             {"name": "z", "type": "space", "unit": "millimeter"},
             {"name": "y", "type": "space", "unit": "millimeter"},
             {"name": "x", "type": "space", "unit": "millimeter"}],
    "datasets": [{"path": "2", "coordinateTransformations": [
        {"type": "scale", "scale": [1, 0.003, 0.0065, 0.0065]}]}],
}], "omero": {"channels": [{"label": "AAV", "color": "FFFFFF"}, {"label": "gfap", "color": "FFFFFF"}]}}
ZARRAY = {"shape": [2, 8, 16, 16], "chunks": [1, 1, 16, 16], "dtype": "<u2",
          "compressor": {"id": "blosc", "cname": "lz4"}, "zarr_format": 2}
SIDECAR = {"PixelSize": [1.625, 1.625, 3.0], "PixelSizeUnits": "um", "Magnification": 4.0,
           "NumericalAperture": 0.1, "Immersion": "Oil RI 1.52", "InstrumentModel": "Ultramicroscope Expert",
           "SoftwareVersions": "Imspector Pro 8.0.3",
           "ExtraMetadata": {"ExcitationWL": {"ExcitationWL": "488"}, "EmissionWL": {"EmissionWL": "525"}}}
TEMPLATE_DD = {"Name": "Name of the dataset", "BIDSVersion": "v1.9.0", "DatasetType": "raw",
               "License": "The license for the dataset", "Authors": ["Author Name 1", "Author Name 2"],
               "GeneratedBy": [{"Name": "SPIMprep"}, {"Version": "0.1.0"}]}
SAMPLES_TSV = "participant_id\tsample_id\tsample_type\nsub-A1\tsample-brain\ttissue\n"
ZNAME = "sub-A1_sample-brain_acq-imaris_SPIM"


def _build(root):
    """Lays out <root>/BIDS/... and returns (bids_dir, zarr_dir)."""
    bids = root / "A1_gfap_bids"
    micr = bids / "sub-A1" / "micr"
    zarr = micr / f"{ZNAME}.ome.zarr"
    (zarr / "2").mkdir(parents=True, exist_ok=True)
    (zarr / ".zgroup").write_text('{"zarr_format": 2}')
    (zarr / ".zattrs").write_text(json.dumps(ZATTRS))
    (zarr / "2" / ".zarray").write_text(json.dumps(ZARRAY))
    for i in range(4):
        (zarr / "2" / f"0.{i}.0.0").write_bytes(b"x" * 100)
    (micr / f"{ZNAME}.json").write_text(json.dumps(SIDECAR))
    (bids / "dataset_description.json").write_text(json.dumps(TEMPLATE_DD))
    (bids / "samples.tsv").write_text(SAMPLES_TSV)
    (bids / "README.md").write_text("# README")
    return bids, zarr


@pytest.fixture
def bids_tar(tmp_path):
    bids, _ = _build(tmp_path)
    tar_path = tmp_path / "A1_gfap_bids.tar"
    with tarfile.open(tar_path, "w") as tf:
        tf.add(bids, arcname="A1_gfap_bids")
    return tar_path


@pytest.fixture
def zarr_dir(tmp_path):
    return _build(tmp_path)[1]


def test_format_registered():
    assert "OME-Zarr" in FORMAT_REGISTRY
    assert formats_for_extension(".tar") == ["OME-Zarr"]
    assert formats_for_extension(".ome.zarr") == ["OME-Zarr"]
    assert get_standardizer("OME-Zarr", "Microscopy (OME-Zarr)") is standardize_omezarr_microscopy_metadata


def test_tar_is_read_without_extraction(bids_tar, tmp_path):
    text, raw = parse_omezarr_metadata(str(bids_tar))
    assert raw["Container"] == "tar"
    assert raw["NGFFVersion"] == "0.4"
    assert [c["Name"] for c in raw["Channels"]] == ["AAV", "gfap"]
    lv = raw["Levels"][0]
    assert lv["Shape"] == [2, 8, 16, 16] and lv["ChunkFiles"] == 4 and lv["StoredBytes"] == 400
    assert lv["Compressor"] == "lz4" and lv["DType"] == "<u2"
    # nothing got extracted next to the archive
    assert sorted(p.name for p in tmp_path.iterdir() if p.name.endswith("_bids")) == ["A1_gfap_bids"]


def test_pixel_size_normalized_to_micrometers_and_downsample_factor(bids_tar):
    _, raw = parse_omezarr_metadata(str(bids_tar))
    assert raw["PixelSizeUM"] == pytest.approx({"Z": 3.0, "Y": 6.5, "X": 6.5})
    assert raw["DownsampleFactorXY"] == pytest.approx(4.0)


def test_directory_matches_tar(bids_tar, zarr_dir):
    _, from_tar = parse_omezarr_metadata(str(bids_tar))
    _, from_dir = parse_omezarr_metadata(str(zarr_dir))
    assert from_dir["Container"] == "directory"
    for key in ("NGFFVersion", "Channels", "PixelSizeUM", "DownsampleFactorXY", "SidecarFound"):
        assert from_dir[key] == from_tar[key], key
    assert from_dir["DatasetDescriptionFound"] is True  # found on disk around the .zarr
    assert from_dir["SamplesColumns"] == ["participant_id", "sample_id", "sample_type"]


def test_standardized_fields(bids_tar):
    d = standardize_omezarr_microscopy_metadata(parse_omezarr_metadata(str(bids_tar))[1])
    assert (d["DimensionX"], d["DimensionY"], d["DimensionZ"], d["NumChannels"]) == (16, 16, 8, 2)
    assert (d["PixelSizeX"], d["PixelSizeZ"]) == (6.5, 3.0)
    assert d["BIDSSubject"] == "A1" and d["BIDSSample"] == "brain"
    assert d["Modality"] == "Light-sheet fluorescence microscopy"
    assert d["NA"] == 0.1 and d["Magnification"] == 4.0
    assert d["Channels"] == [{"Name": "AAV"}, {"Name": "gfap"}]
    assert compute_missing_fields("OME-Zarr", d, "Microscopy (OME-Zarr)") == []
    profile = get_profile("Microscopy (OME-Zarr)")
    assert all(k in profile for k in d if not k.startswith("_"))


def test_template_dataset_description_is_blanked_and_flagged(bids_tar):
    d = standardize_omezarr_microscopy_metadata(parse_omezarr_metadata(str(bids_tar))[1])
    assert d["DatasetName"] == "" and d["DatasetLicense"] == ""
    codes = {s["Code"] for s in d["_Suggestions"]}
    assert {"BIDS_TEMPLATE_DATASET_DESCRIPTION", "REMBI_BIOSAMPLE_MISSING",
            "REMBI_ACQUISITION_RECOMMENDED"} <= codes
    for s in d["_Suggestions"]:
        assert s["Message"] and s["Message_fr"]
    flags, _ = compute_curation_flags([(str(bids_tar), "", d)])
    assert "BIDS_TEMPLATE_METADATA" in flags[str(bids_tar)]


def test_ambiguous_wavelength_not_attributed_to_a_channel(bids_tar):
    _, raw = parse_omezarr_metadata(str(bids_tar))
    assert raw["WavelengthAmbiguous"] is True
    d = standardize_omezarr_microscopy_metadata(raw)
    assert d["ExcitationWavelength"] == "" and d["EmissionWavelength"] == ""


def test_single_channel_wavelength_is_kept(tmp_path):
    zattrs = json.loads(json.dumps(ZATTRS))
    zattrs["omero"]["channels"] = [{"label": "cfos"}]
    bids, zarr = _build(tmp_path)
    (zarr / ".zattrs").write_text(json.dumps(zattrs))
    d = standardize_omezarr_microscopy_metadata(parse_omezarr_metadata(str(zarr))[1])
    assert d["ExcitationWavelength"] == "488" and d["EmissionWavelength"] == "525"


def test_zarr_v3_metadata(tmp_path):
    z = tmp_path / "img.ome.zarr"
    (z / "0").mkdir(parents=True)
    ome = {"version": "0.5", "multiscales": [{
        "axes": [{"name": "y", "type": "space", "unit": "micrometer"},
                 {"name": "x", "type": "space", "unit": "micrometer"}],
        "datasets": [{"path": "0", "coordinateTransformations": [{"type": "scale", "scale": [0.5, 0.5]}]}]}]}
    (z / "zarr.json").write_text(json.dumps(
        {"zarr_format": 3, "node_type": "group", "attributes": {"ome": ome}}))
    (z / "0" / "zarr.json").write_text(json.dumps({
        "zarr_format": 3, "node_type": "array", "shape": [32, 32], "data_type": "uint8",
        "chunk_grid": {"name": "regular", "configuration": {"chunk_shape": [16, 16]}},
        "codecs": [{"name": "bytes"}, {"name": "zstd"}]}))
    _, raw = parse_omezarr_metadata(str(z))
    assert raw["Levels"][0]["ZarrFormat"] == 3 and raw["Levels"][0]["Compressor"] == "zstd"
    assert raw["PixelSizeUM"] == pytest.approx({"Y": 0.5, "X": 0.5})


def test_tar_without_zarr_and_missing_file_fail_gracefully(tmp_path):
    empty = tmp_path / "other.tar"
    with tarfile.open(empty, "w") as tf:
        (tmp_path / "a.txt").write_text("hi")
        tf.add(tmp_path / "a.txt", arcname="a.txt")
    text, _ = parse_omezarr_metadata(str(empty))
    assert "failed to read" in text.lower()
    text, _ = parse_omezarr_metadata(str(tmp_path / "missing.tar"))
    assert "failed to read" in text.lower()
