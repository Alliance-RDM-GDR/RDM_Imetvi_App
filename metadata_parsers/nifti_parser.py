# metadata_parsers/nifti_parser.py
#
# Reads NIfTI-1/2 images (.nii, .nii.gz) — header only, never the voxel data
# (a resting-state BOLD volume is >100 MB compressed) — and merges the BIDS
# context around them: the JSON sidecar (with BIDS inheritance), .bval/.bvec
# for diffusion images, the filename entities (sub/ses/task/dir/suffix), the
# dataset's dataset_description.json and participants.tsv columns.
#
# participants.tsv *values* are deliberately not read: for human studies the
# rows carry demographics. Only the column names are reported.

import os

import nibabel as nib
import numpy as np

from utils.bids import (
    bids_entities, find_bids_root, find_sidecar, read_json, parse_tsv_header,
    summarize_dataset_description,
)

_SIDECAR_FIELDS = [
    "Manufacturer", "ManufacturersModelName", "DeviceSerialNumber", "StationName",
    "SoftwareVersion", "InstitutionName", "MagneticFieldStrength",
    "ReceiveCoilName", "PulseSequenceType", "ScanningSequence", "SequenceVariant",
    "SequenceName", "PulseSequenceDetails", "EchoTime", "RepetitionTime",
    "InversionTime", "FlipAngle", "PhaseEncodingDirection", "EffectiveEchoSpacing",
    "TotalReadoutTime", "ParallelReductionFactorInPlane", "TaskName",
    "AcquisitionDuration", "NumberOfVolumesDiscardedByScanner",
    "SliceEncodingDirection",
]

_SPATIAL_UNITS = {"meter": 1000.0, "mm": 1.0, "micron": 0.001}


def _read_bval_bvec(base):
    """Summarizes the .bval/.bvec files next to a diffusion image (or None)."""
    bval_path, bvec_path = base + ".bval", base + ".bvec"
    if not (os.path.isfile(bval_path) and os.path.isfile(bvec_path)):
        return None
    try:
        with open(bval_path, "r") as f:
            bvals = [float(x) for x in f.read().split()]
        with open(bvec_path, "r") as f:
            rows = [r.split() for r in f.read().strip().splitlines() if r.strip()]
        n_dirs = len(rows[0]) if rows else 0
        rounded = sorted({int(round(b / 50.0) * 50) for b in bvals})
        return {
            "NumVolumes": len(bvals),
            "BValues": rounded,
            "B0Count": sum(1 for b in bvals if b < 50),
            "BvecRows": len(rows),
            "BvecColumns": n_dirs,
            "Consistent": len(rows) == 3 and n_dirs == len(bvals),
        }
    except (OSError, ValueError):
        return {"Error": "unreadable .bval/.bvec"}


def parse_nifti_metadata(file_path, application=None):
    """
    Extracts NIfTI header fields plus BIDS sidecar/dataset context.
    Returns (text_report, raw_metadata) per the parser contract.
    """
    fname = os.path.basename(file_path)
    text_lines = [f"NIfTI / BIDS Metadata Report for {fname}"]
    raw = {"FilePath": file_path}

    try:
        img = nib.load(file_path)
        hdr = img.header
        shape = tuple(int(s) for s in img.shape)
        zooms = tuple(float(z) for z in hdr.get_zooms())
        space_unit, time_unit = hdr.get_xyzt_units()
        affine = img.affine
        raw.update({
            "NiftiVersion": 2 if isinstance(hdr, nib.Nifti2Header) else 1,
            "Shape": list(shape),
            "VoxelSizes": list(zooms),
            "SpatialUnit": space_unit,
            "TimeUnit": time_unit,
            "DataType": str(img.get_data_dtype()),
            "Orientation": "".join(nib.aff2axcodes(affine)),
            "QformCode": int(hdr["qform_code"]),
            "SformCode": int(hdr["sform_code"]),
            "Description": hdr["descrip"].tobytes().split(b"\x00")[0].decode("latin-1").strip()
            if "descrip" in hdr else "",
            "IntentCode": int(hdr["intent_code"]),
            "SclSlope": float(hdr["scl_slope"]) if np.isfinite(hdr["scl_slope"]) else None,
            "SclInter": float(hdr["scl_inter"]) if np.isfinite(hdr["scl_inter"]) else None,
        })
        text_lines += [
            f"Shape: {' x '.join(map(str, shape))}",
            f"Voxel size: {' x '.join(f'{z:g}' for z in zooms[:3])} {space_unit}"
            + (f"; time step {zooms[3]:g} {time_unit}" if len(zooms) > 3 else ""),
            f"Data type: {raw['DataType']}",
            f"Orientation: {raw['Orientation']}",
            f"qform_code: {raw['QformCode']}  sform_code: {raw['SformCode']}",
        ]
    except Exception as e:
        text_lines.append(f"Failed to read NIfTI file: {e}")
        return "\n".join(text_lines), raw

    entities, suffix = bids_entities(file_path)
    root = find_bids_root(file_path)
    raw["BIDSEntities"] = entities
    raw["BIDSSuffix"] = suffix
    parent = os.path.basename(os.path.dirname(os.path.abspath(file_path)))
    raw["BIDSDatatype"] = parent if parent in ("anat", "dwi", "func", "fmap", "perf") else ""
    if entities.get("sub"):
        text_lines.append(
            "BIDS entities: " + ", ".join(f"{k}-{v}" for k, v in entities.items()) + f" | suffix: {suffix}"
        )

    # ── sidecar (with BIDS inheritance) ─────────────────────────────────────
    sidecar_path = find_sidecar(file_path, root)
    sidecar = read_json(sidecar_path) if sidecar_path else None
    raw["SidecarFound"] = sidecar is not None
    if sidecar is not None:
        raw["SidecarPath"] = sidecar_path
        raw["Sidecar"] = sidecar
        for k in _SIDECAR_FIELDS:
            if k in sidecar and sidecar[k] not in ("", None):
                text_lines.append(f"{k}: {sidecar[k]}")
        st = sidecar.get("SliceTiming")
        if isinstance(st, list) and st:
            raw["SliceTimingCount"] = len(st)
            text_lines.append(f"SliceTiming: {len(st)} values ({min(st):g}-{max(st):g})")
    else:
        text_lines.append("No JSON sidecar found for this image.")

    # ── diffusion gradients ─────────────────────────────────────────────────
    if suffix == "dwi":
        base = file_path[: -len(".nii.gz")] if file_path.lower().endswith(".nii.gz") \
            else os.path.splitext(file_path)[0]
        dwi = _read_bval_bvec(base)
        raw["Diffusion"] = dwi
        if dwi and "Error" not in dwi:
            text_lines.append(
                f"Diffusion: {dwi['NumVolumes']} volumes, b-values {dwi['BValues']}, "
                f"{dwi['B0Count']} b=0 volume(s)"
                + ("" if dwi["Consistent"] else "  [bvec/bval size mismatch]")
            )
        elif dwi is None:
            text_lines.append("Diffusion: .bval/.bvec files not found next to the image.")

    # ── dataset-level BIDS context ──────────────────────────────────────────
    raw["BIDSRoot"] = root or ""
    if root:
        dd = read_json(os.path.join(root, "dataset_description.json"))
        raw["DatasetDescription"] = summarize_dataset_description(dd)
        raw["DatasetDescriptionFound"] = dd is not None
        pt = os.path.join(root, "participants.tsv")
        if os.path.isfile(pt):
            try:
                with open(pt, "r", encoding="utf-8") as f:
                    cols, n = parse_tsv_header(f.read())
                raw["ParticipantsColumns"] = cols
                raw["ParticipantsCount"] = n
            except OSError:
                raw["ParticipantsColumns"] = None
        else:
            raw["ParticipantsColumns"] = None
        if dd:
            text_lines.append(
                f"BIDS dataset: {dd.get('Name', '')!s} (BIDS {dd.get('BIDSVersion', '?')}, "
                f"license: {dd.get('License') or 'not set'})"
            )
    else:
        raw["DatasetDescriptionFound"] = False
        text_lines.append("Not inside a BIDS dataset (no dataset_description.json found above this file).")

    return "\n".join(text_lines), raw
