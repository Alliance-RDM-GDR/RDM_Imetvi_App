# tests/test_nifti_bids.py
#
# Synthetic BIDS MRI dataset (nibabel + JSON) mirroring the layout of the FRDR
# 1828 deposit: <root>/sub-X/ses-Y/{anat,dwi,func}/ with BrkRaw-style sidecars,
# placeholder values, an empty license and a minimal participants.tsv.

import json

import nibabel as nib
import numpy as np
import pytest

from main import FORMAT_REGISTRY, formats_for_extension, get_standardizer
from metadata_parsers.nifti_parser import parse_nifti_metadata
from metadata_profiles.profile_registry import get_profile
from metadata_profiles.required_fields_registry import compute_missing_fields
from metadata_profiles.standards_registry import get_standard_info
from standardizers.nifti_neuroimaging_standardizer import standardize_nifti_neuroimaging_metadata
from utils.bids import (
    get_extension, strip_extension, bids_entities, find_placeholders, find_sidecar,
)
from utils.curation_flags import compute_curation_flags
from utils.sidecar import sidecar_path_for


def _write_nifti(path, shape, zooms, sform=False, units=True):
    data = np.zeros(shape, dtype=np.int16)
    affine = np.diag(list(zooms[:3]) + [1.0])
    img = nib.Nifti1Image(data, affine)
    img.header.set_zooms(zooms)
    if units:
        img.header.set_xyzt_units("mm", "sec")
    img.set_qform(affine, code=1)
    img.set_sform(affine, code=1 if sform else 0)
    nib.save(img, str(path))


@pytest.fixture
def bids_root(tmp_path):
    root = tmp_path / "MRI_bids"
    (root / "sub-A1" / "ses-baseline" / "func").mkdir(parents=True)
    (root / "sub-A1" / "ses-baseline" / "dwi").mkdir(parents=True)
    (root / "dataset_description.json").write_text(json.dumps(
        {"Name": "LD MRI", "BIDSVersion": "1.9.0", "License": "", "Authors": [""], "DatasetDOI": ""}))
    (root / "participants.tsv").write_text("participant_id\nsub-A1\n")

    func = root / "sub-A1" / "ses-baseline" / "func"
    _write_nifti(func / "sub-A1_ses-baseline_task-resting_bold.nii.gz", (8, 8, 4, 10), (0.3, 0.3, 1.0, 2.0))
    (func / "sub-A1_ses-baseline_task-resting_bold.json").write_text(json.dumps({
        "Manufacturer": "Bruker BioSpin MRI GmbH", "ManufacturersModelName": "BioSpec 70/30",
        "MagneticFieldStrength": 7.05, "EchoTime": 0.03, "RepetitionTime": 2.0, "TaskName": "resting",
        "ReceiveCoilName": "VisuCoilReceiveName", "InversionTime": "VisuAcqInversionTime",
        "Instructions": "Value was not specified", "SliceTiming": [0.0, 0.5, 1.0, 1.5],
    }))

    dwi = root / "sub-A1" / "ses-baseline" / "dwi"
    _write_nifti(dwi / "sub-A1_ses-baseline_dir-fwd_dwi.nii.gz", (8, 8, 4, 4), (0.3, 0.3, 1.0, 9.0), sform=True)
    (dwi / "sub-A1_ses-baseline_dir-fwd_dwi.json").write_text(json.dumps(
        {"Manufacturer": "Bruker", "PhaseEncodingDirection": "j", "TotalReadoutTime": 0.0003}))
    (dwi / "sub-A1_ses-baseline_dir-fwd_dwi.bval").write_text("0 1200 1200 1950\n")
    (dwi / "sub-A1_ses-baseline_dir-fwd_dwi.bvec").write_text("0 1 0 0\n0 0 1 0\n0 0 0 1\n")
    return root


def _std(path):
    _, raw = parse_nifti_metadata(str(path))
    return standardize_nifti_neuroimaging_metadata(raw), raw


def test_compound_extensions():
    assert get_extension("a/b/x.nii.gz") == ".nii.gz"
    assert get_extension("X.NII.GZ") == ".nii.gz"
    assert get_extension("scan.ome.zarr/") == ".ome.zarr"
    assert get_extension("photo.jpg") == ".jpg"
    assert strip_extension("dir/x_T2w.nii.gz") == "dir/x_T2w"


def test_bids_entities():
    assert bids_entities("sub-LD13_ses-baseline_dir-fwd_dwi.nii.gz") == (
        {"sub": "LD13", "ses": "baseline", "dir": "fwd"}, "dwi")
    assert bids_entities("DSURQE_labels_v2.nii.gz") == ({}, "")  # not BIDS


def test_placeholder_detection():
    unresolved, unspecified = find_placeholders({
        "a": "VisuCoilReceiveName", "b": "ACQ_status", "c": "https://x/fillYourID",
        "d": "Value was not specified", "e": {"f": "Author Name 1"}, "g": "real value"})
    assert set(unresolved) == {"a", "b", "c", "e.f"}
    assert unspecified == ["d"]


def test_formats_registered_for_compound_extension():
    assert "NIfTI" in FORMAT_REGISTRY
    assert formats_for_extension(".nii.gz") == ["NIfTI"]
    assert formats_for_extension(".nii") == ["NIfTI"]
    assert get_standardizer("NIfTI", "Neuroimaging (BIDS)") is standardize_nifti_neuroimaging_metadata


def test_parse_bold_header_and_sidecar(bids_root):
    path = bids_root / "sub-A1" / "ses-baseline" / "func" / "sub-A1_ses-baseline_task-resting_bold.nii.gz"
    text, raw = parse_nifti_metadata(str(path))
    assert raw["Shape"] == [8, 8, 4, 10]
    assert raw["SformCode"] == 0 and raw["QformCode"] == 1
    assert raw["BIDSEntities"]["sub"] == "A1" and raw["BIDSSuffix"] == "bold"
    assert raw["BIDSDatatype"] == "func"
    assert raw["SidecarFound"] is True
    assert "EchoTime: 0.03" in text


def test_standardized_fields_and_units(bids_root):
    path = bids_root / "sub-A1" / "ses-baseline" / "func" / "sub-A1_ses-baseline_task-resting_bold.nii.gz"
    d, _ = _std(path)
    assert d["BIDSSubject"] == "A1" and d["BIDSSession"] == "baseline" and d["BIDSTask"] == "resting"
    assert (d["MatrixSizeX"], d["MatrixSizeY"], d["MatrixSizeZ"], d["NumVolumes"]) == (8, 8, 4, 10)
    assert d["VoxelSizeX"] == pytest.approx(0.3) and d["TimeStep"] == pytest.approx(2.0)
    assert d["ManufacturerModel"] == "BioSpec 70/30"
    assert d["ImagingType"] == "Functional MRI"
    assert "DimensionX" not in d  # would cause false DIMENSION_OUTLIER across modalities
    profile = get_profile("Neuroimaging (BIDS)")
    assert all(k in profile for k in d if not k.startswith("_"))


def test_suggestions_cover_dataset_and_sidecar_gaps(bids_root):
    path = bids_root / "sub-A1" / "ses-baseline" / "func" / "sub-A1_ses-baseline_task-resting_bold.nii.gz"
    d, _ = _std(path)
    codes = {s["Code"] for s in d["_Suggestions"]}
    assert {"BIDS_LICENSE_MISSING", "BIDS_AUTHORS_MISSING", "BIDS_DOI_MISSING",
            "ARRIVE_PARTICIPANT_DESCRIPTORS", "BIDS_SIDECAR_UNRESOLVED",
            "BIDS_SIDECAR_UNSPECIFIED", "NIFTI_NO_SFORM"} <= codes
    for s in d["_Suggestions"]:
        assert s["Message"] and s["Message_fr"] and s["Standard"]


def test_suggestions_raise_curation_flags(bids_root):
    path = bids_root / "sub-A1" / "ses-baseline" / "func" / "sub-A1_ses-baseline_task-resting_bold.nii.gz"
    d, raw = _std(path)
    flags, _ = compute_curation_flags([(str(path), "", d)])
    f = flags[str(path)]
    assert "BIDS_TEMPLATE_METADATA" in f and "BIDS_DATASET_INCOMPLETE" in f and "NIFTI_NO_SFORM" in f


def test_dwi_reads_bvals_and_has_no_missing_required(bids_root):
    path = bids_root / "sub-A1" / "ses-baseline" / "dwi" / "sub-A1_ses-baseline_dir-fwd_dwi.nii.gz"
    d, raw = _std(path)
    assert d["BValues"] == [0, 1200, 1950] and d["B0Count"] == 1
    assert raw["Diffusion"]["Consistent"] is True
    codes = {s["Code"] for s in d["_Suggestions"]}
    assert "NIFTI_NO_SFORM" not in codes  # sform set on this one
    assert "BIDS_DWI_NO_BVAL_BVEC" not in codes
    assert compute_missing_fields("NIfTI", d, "Neuroimaging (BIDS)") == []


def test_bold_missing_repetition_time_is_flagged(bids_root):
    func = bids_root / "sub-A1" / "ses-baseline" / "func"
    p = func / "sub-A1_ses-baseline_task-resting_bold.json"
    side = json.loads(p.read_text())
    del side["RepetitionTime"]
    p.write_text(json.dumps(side))
    d, _ = _std(func / "sub-A1_ses-baseline_task-resting_bold.nii.gz")
    assert "BIDS_SIDECAR_REQUIRED_MISSING" in {s["Code"] for s in d["_Suggestions"]}


def test_non_bids_nifti_gets_no_bids_noise(tmp_path):
    p = tmp_path / "atlas_labels_v2.nii.gz"
    _write_nifti(p, (6, 6, 6), (0.04, 0.04, 0.04), sform=True, units=False)
    d, raw = _std(p)
    codes = {s["Code"] for s in d["_Suggestions"]}
    assert codes == {"NIFTI_UNITS_UNSET"}
    assert raw["SidecarFound"] is False and d["BIDSSuffix"] == ""


def test_sidecar_inheritance(tmp_path):
    root = tmp_path / "ds"
    (root / "sub-A" / "func").mkdir(parents=True)
    (root / "dataset_description.json").write_text("{}")
    (root / "task-rest_bold.json").write_text(json.dumps({"RepetitionTime": 2.0}))
    img = root / "sub-A" / "func" / "sub-A_task-rest_bold.nii.gz"
    _write_nifti(img, (4, 4, 2, 3), (1, 1, 1, 2))
    assert find_sidecar(str(img), str(root)) == str(root / "task-rest_bold.json")


def test_corrupt_nifti_reports_failure(tmp_path):
    p = tmp_path / "broken.nii.gz"
    p.write_bytes(b"not a nifti")
    text, raw = parse_nifti_metadata(str(p))
    assert "failed to read" in text.lower()


def test_standards_entry_and_write_sidecar_never_overwrites_bids_json():
    info = get_standard_info("Neuroimaging (BIDS)")
    assert "BIDS" in info["standard_name"] and info["covered"] and info["not_covered"]
    assert sidecar_path_for("/d/sub-A_T2w.nii.gz") == "/d/sub-A_T2w.imetvi.json"
