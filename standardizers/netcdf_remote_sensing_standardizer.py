# standardizers/netcdf_remote_sensing_standardizer.py

import os


def standardize_netcdf_remote_sensing_metadata(raw_metadata):
    """
    Standardizes raw NetCDF/CF metadata into an ISO 19115-aligned dictionary,
    matching the remote sensing context shared with GeoTIFF.
    """

    file_path = raw_metadata.get("FilePath", "")
    variables = raw_metadata.get("Variables", []) or []
    coord_vars = raw_metadata.get("CoordinateVariables", []) or []

    # Kept as structured dicts (Name/Units/StandardName/Shape), not flattened
    # to display strings — the CF standard_name is the controlled-vocabulary
    # term a curator or downstream tool needs intact for FAIR interoperability/
    # reuse (JSON and CSV exports both benefit from real fields here instead
    # of a pre-formatted sentence baked at standardization time).
    variable_entries = [
        {
            "Name": v.get("Name", ""),
            "StandardName": v.get("StandardName", ""),
            "Units": v.get("Units", ""),
            "LongName": v.get("LongName", ""),
            "Shape": v.get("Shape", []),
        }
        for v in variables
    ]

    dict_report = {
        "ImageName": os.path.basename(file_path),
        "Conventions": raw_metadata.get("Conventions", ""),
        "Institution": raw_metadata.get("institution", ""),
        "Title": raw_metadata.get("title", ""),
        "ProcessingHistory": raw_metadata.get("history", ""),
        "Source": raw_metadata.get("source", ""),
        "DimensionCount": str(raw_metadata.get("DimensionCount", "")),
        "VariableCount": str(raw_metadata.get("VariableCount", "")),
        "CoordinateVariables": coord_vars,
        "Variables": variable_entries,
    }

    return dict_report
