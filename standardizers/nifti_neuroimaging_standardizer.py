# standardizers/nifti_neuroimaging_standardizer.py
#
# Maps raw NIfTI/BIDS-MRI output to BIDS-aligned fields and attaches the
# standards-based suggestions (BIDS 1.9.0, NIfTI-1, ARRIVE 2.0) as _Suggestions.
#
# Matrix size is reported as MatrixSizeX/Y/Z rather than DimensionX/Y: a BIDS
# session mixes T2w (128x128), DWI and BOLD (64x64) by design, and
# DimensionX/Y would make every other modality a false DIMENSION_OUTLIER.

import os

from utils.bids import (
    dataset_description_suggestions, participants_suggestions, sidecar_suggestions,
    nifti_geometry_suggestions,
)

_DATATYPE_LABEL = {"anat": "Anatomical MRI", "dwi": "Diffusion MRI", "func": "Functional MRI",
                   "fmap": "Field map", "perf": "Perfusion MRI"}
_TEMPLATE_LICENSE = "the license for the dataset"


def _dim(shape, i):
    return shape[i] if len(shape) > i else ""


def standardize_nifti_neuroimaging_metadata(raw_metadata):
    raw = raw_metadata
    shape = raw.get("Shape") or []
    zooms = raw.get("VoxelSizes") or []
    sidecar = raw.get("Sidecar") or {}
    ent = raw.get("BIDSEntities") or {}
    dd = raw.get("DatasetDescription") or {}
    dwi = raw.get("Diffusion") or {}
    suffix = raw.get("BIDSSuffix", "")
    datatype = raw.get("BIDSDatatype", "")
    dwi_ok = bool(dwi) and "Error" not in dwi
    n_vol = shape[3] if len(shape) > 3 else (1 if shape else "")

    def zoom(i):
        return round(zooms[i], 6) if len(zooms) > i else ""

    d = {
        "ImageName": os.path.basename(raw.get("FilePath", "")),
        "BIDSSubject": ent.get("sub", ""),
        "BIDSSession": ent.get("ses", ""),
        "BIDSTask": ent.get("task", "") or sidecar.get("TaskName", ""),
        "BIDSSuffix": suffix,
        "BIDSDatatype": datatype,
        "ImagingType": _DATATYPE_LABEL.get(datatype, ""),
        "MatrixSizeX": _dim(shape, 0),
        "MatrixSizeY": _dim(shape, 1),
        "MatrixSizeZ": _dim(shape, 2),
        "NumVolumes": n_vol,
        "VoxelSizeX": zoom(0),
        "VoxelSizeY": zoom(1),
        "VoxelSizeZ": zoom(2),
        "TimeStep": zoom(3) if len(zooms) > 3 else "",
        "SpatialUnit": raw.get("SpatialUnit", ""),
        "DataType": raw.get("DataType", ""),
        "Orientation": raw.get("Orientation", ""),
        "QformCode": raw.get("QformCode", ""),
        "SformCode": raw.get("SformCode", ""),
        "Manufacturer": sidecar.get("Manufacturer", ""),
        "ManufacturerModel": sidecar.get("ManufacturersModelName", ""),
        "MagneticFieldStrength": sidecar.get("MagneticFieldStrength", ""),
        "SoftwareVersion": sidecar.get("SoftwareVersion", ""),
        "InstitutionName": sidecar.get("InstitutionName", ""),
        "PulseSequence": sidecar.get("PulseSequenceDetails", "") or sidecar.get("SequenceName", ""),
        "ScanningSequence": sidecar.get("ScanningSequence", ""),
        "EchoTime": sidecar.get("EchoTime", ""),
        "RepetitionTime": sidecar.get("RepetitionTime", ""),
        "FlipAngle": sidecar.get("FlipAngle", ""),
        "PhaseEncodingDirection": sidecar.get("PhaseEncodingDirection", ""),
        "TotalReadoutTime": sidecar.get("TotalReadoutTime", ""),
        "AcquisitionDuration": sidecar.get("AcquisitionDuration", ""),
        "SliceCount": raw.get("SliceTimingCount", ""),
        "BValues": dwi.get("BValues", "") if dwi_ok else "",
        "B0Count": dwi.get("B0Count", "") if dwi_ok else "",
        "DatasetName": dd.get("Name", ""),
        "BIDSVersion": dd.get("BIDSVersion", ""),
        "DatasetLicense": dd.get("License", ""),
    }
    # template text must not be presented as real dataset metadata
    if str(d["DatasetLicense"]).strip().lower().startswith(_TEMPLATE_LICENSE):
        d["DatasetLicense"] = ""

    if shape:
        s = []
        in_bids = bool(raw.get("BIDSRoot"))
        if raw.get("DatasetDescriptionFound"):
            s += dataset_description_suggestions(dd)
            s += participants_suggestions(raw.get("ParticipantsColumns"))
        elif ent.get("sub") or in_bids:
            s += dataset_description_suggestions(None)
        if ent.get("sub") or in_bids:
            s += sidecar_suggestions(
                sidecar if raw.get("SidecarFound") else None, suffix,
                has_bval_bvec=(dwi_ok if suffix == "dwi" else None),
                sidecar_found=bool(raw.get("SidecarFound")),
            )
        s += nifti_geometry_suggestions(raw.get("SformCode", 1), raw.get("QformCode", 1),
                                        raw.get("SpatialUnit", "mm"))
        d["_Suggestions"] = s
    return d
