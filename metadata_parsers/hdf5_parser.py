# metadata_parsers/hdf5_parser.py
#
# Extracts structural metadata from HDF5 container files (.h5, .hdf5, .nc4).
# Adapted from CUR_Res_CurationTools/Scripts/Inspect_hdf5_Script.R:
#   - Maps internal group/dataset hierarchy
#   - Reports compression filters, data types, and dimensions per dataset
#   - Flags external links (file is not self-contained)
#   - Reports root-level attributes (global metadata)

import os

try:
    import h5py
    _H5PY_AVAILABLE = True
except ImportError:
    _H5PY_AVAILABLE = False

_MAX_ATTR_KEYS = 5  # number of attribute key names shown per dataset


def parse_hdf5_metadata(file_path, application=None):
    text_lines = [f"HDF5 Metadata Report for {os.path.basename(file_path)}"]
    raw_metadata = {"FilePath": file_path}

    if not _H5PY_AVAILABLE:
        msg = "h5py is not installed. Run: pip install h5py"
        text_lines.append(msg)
        raw_metadata["Error"] = msg
        return "\n".join(text_lines), raw_metadata

    try:
        with h5py.File(file_path, "r") as f:
            # --- Root-level attributes (global metadata) ---
            root_attrs = {}
            for k, v in f.attrs.items():
                root_attrs[k] = str(v)
                raw_metadata[f"RootAttr_{k}"] = str(v)
                text_lines.append(f"Root Attribute — {k}: {v}")

            raw_metadata["RootAttributeCount"] = len(root_attrs)

            # --- Walk all groups and datasets ---
            objects = []

            def _visitor(name, obj):
                if isinstance(obj, h5py.ExternalLink):
                    objects.append({
                        "Path": name,
                        "Type": "ExternalLink",
                        "Dimensions": "N/A",
                        "DataType": "N/A",
                        "Compression": "N/A",
                        "Attributes": "",
                        "Risk": "EXTERNAL_LINK — file may not be self-contained",
                    })
                    return

                entry = {
                    "Path": name,
                    "Type": "Dataset" if isinstance(obj, h5py.Dataset) else "Group",
                    "Dimensions": "N/A",
                    "DataType": "N/A",
                    "Compression": "None",
                    "Attributes": "",
                    "Risk": "",
                }

                if isinstance(obj, h5py.Dataset):
                    entry["Dimensions"] = " x ".join(str(s) for s in obj.shape) or "scalar"
                    entry["DataType"] = str(obj.dtype)
                    if obj.compression:
                        entry["Compression"] = obj.compression
                        # Flag proprietary compressors that may not be widely supported
                        if obj.compression.lower() in ("szip", "lzf"):
                            entry["Risk"] = f"PROPRIETARY_COMPRESSION ({obj.compression})"

                attr_keys = list(obj.attrs.keys())
                entry["Attributes"] = ", ".join(attr_keys[:_MAX_ATTR_KEYS])
                if len(attr_keys) == 0:
                    entry["Risk"] = (entry["Risk"] + "; NOT_SELF_DESCRIBING").lstrip("; ")

                objects.append(entry)

            f.visititems(_visitor)

            raw_metadata["Objects"] = objects
            raw_metadata["ObjectCount"] = len(objects)

            dataset_count = sum(1 for o in objects if o["Type"] == "Dataset")
            group_count = sum(1 for o in objects if o["Type"] == "Group")
            raw_metadata["DatasetCount"] = dataset_count
            raw_metadata["GroupCount"] = group_count

            text_lines.append(
                f"\nStructure: {group_count} group(s), {dataset_count} dataset(s)"
            )
            for obj in objects:
                risk_note = f"  ⚠ {obj['Risk']}" if obj["Risk"] else ""
                text_lines.append(
                    f"  [{obj['Type']}] {obj['Path']} | "
                    f"Dims: {obj['Dimensions']} | "
                    f"Type: {obj['DataType']} | "
                    f"Compression: {obj['Compression']}"
                    f"{risk_note}"
                )

    except Exception as e:
        msg = f"Failed to read HDF5 file: {str(e)}"
        text_lines.append(msg)
        raw_metadata["Error"] = msg

    return "\n".join(text_lines), raw_metadata
