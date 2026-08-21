# standardizers/hdf5_general_standardizer.py


def standardize_hdf5_general_metadata(raw_metadata):
    """
    Maps raw HDF5 structural metadata to a standardized summary dict.
    HDF5 is a container format, so standardization focuses on structure
    rather than domain-specific fields.
    """
    std = {}

    std["FilePath"] = raw_metadata.get("FilePath", "")
    std["ObjectCount"] = str(raw_metadata.get("ObjectCount", ""))
    std["DatasetCount"] = str(raw_metadata.get("DatasetCount", ""))
    std["GroupCount"] = str(raw_metadata.get("GroupCount", ""))
    std["RootAttributeCount"] = str(raw_metadata.get("RootAttributeCount", ""))

    # Collect root-level global attributes (e.g. Conventions, institution)
    for k, v in raw_metadata.items():
        if k.startswith("RootAttr_"):
            label = k[len("RootAttr_"):]
            std[label] = str(v)

    # Summarize datasets as a list of dicts for display and JSON export
    objects = raw_metadata.get("Objects", [])
    std["Datasets"] = [
        {
            "Path": o["Path"],
            "Type": o["Type"],
            "Dimensions": o.get("Dimensions", ""),
            "DataType": o.get("DataType", ""),
            "Compression": o.get("Compression", ""),
            "Risk": o.get("Risk", ""),
        }
        for o in objects
    ]

    # Compression risk summary
    risky = [o for o in objects if o.get("Risk")]
    if risky:
        std["CurationRisks"] = "; ".join(
            f"{o['Path']}: {o['Risk']}" for o in risky
        )

    return std
