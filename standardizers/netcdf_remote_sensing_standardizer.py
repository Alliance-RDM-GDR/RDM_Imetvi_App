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

    var_summaries = [
        f"{v['Name']}"
        + (f" ({v['Units']})" if v.get("Units") else "")
        + (f" [{v['StandardName']}]" if v.get("StandardName") else "")
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
        "Variables": var_summaries,
    }

    return dict_report
