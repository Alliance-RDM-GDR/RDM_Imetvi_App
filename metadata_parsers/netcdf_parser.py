# metadata_parsers/netcdf_parser.py
#
# Extracts CF Conventions metadata from NetCDF files (.nc, .nc4).
# HDF5 parser already covers .nc4 structurally (it is HDF5-backed), but
# does not interpret CF attribute semantics (units, standard_name,
# coordinate variables) — this parser reads those directly via netCDF4.

import os

try:
    import netCDF4
    _NETCDF4_AVAILABLE = True
except ImportError:
    _NETCDF4_AVAILABLE = False

# CF coordinate variable names commonly used for spatial/temporal axes
_COORD_CANDIDATES = ("lat", "latitude", "lon", "longitude", "time", "depth", "level")


def parse_netcdf_metadata(file_path, application=None):
    text_lines = [f"NetCDF Metadata Report for {os.path.basename(file_path)}"]
    raw_metadata = {"FilePath": file_path}

    if not _NETCDF4_AVAILABLE:
        msg = "netCDF4 is not installed. Run: pip install netCDF4"
        text_lines.append(msg)
        raw_metadata["Error"] = msg
        return "\n".join(text_lines), raw_metadata

    try:
        with netCDF4.Dataset(file_path, "r") as ds:
            # --- Global attributes ---
            global_attrs = {name: str(getattr(ds, name)) for name in ds.ncattrs()}
            raw_metadata["Conventions"] = global_attrs.get("Conventions", "")
            raw_metadata["institution"] = global_attrs.get("institution", "")
            raw_metadata["title"] = global_attrs.get("title", "")
            raw_metadata["history"] = global_attrs.get("history", "")
            raw_metadata["source"] = global_attrs.get("source", "")
            raw_metadata["GlobalAttributes"] = global_attrs

            text_lines.append(f"Conventions: {raw_metadata['Conventions'] or '(not declared)'}")
            if raw_metadata["title"]:
                text_lines.append(f"Title: {raw_metadata['title']}")
            if raw_metadata["institution"]:
                text_lines.append(f"Institution: {raw_metadata['institution']}")

            # --- Dimensions ---
            dimensions = {name: (len(dim) if not dim.isunlimited() else "unlimited")
                          for name, dim in ds.dimensions.items()}
            raw_metadata["Dimensions"] = dimensions
            raw_metadata["DimensionCount"] = len(dimensions)

            text_lines.append(f"\nDimensions ({len(dimensions)}):")
            for name, size in dimensions.items():
                text_lines.append(f"  {name}: {size}")

            # --- Variables and their CF attributes ---
            variables = []
            coord_vars = []
            for name, var in ds.variables.items():
                entry = {
                    "Name": name,
                    "Dimensions": list(var.dimensions),
                    "Shape": list(var.shape),
                    "DataType": str(var.dtype),
                    "Units": getattr(var, "units", ""),
                    "LongName": getattr(var, "long_name", ""),
                    "StandardName": getattr(var, "standard_name", ""),
                }
                variables.append(entry)
                if name.lower() in _COORD_CANDIDATES:
                    coord_vars.append(name)

            raw_metadata["Variables"] = variables
            raw_metadata["VariableCount"] = len(variables)
            raw_metadata["CoordinateVariables"] = coord_vars

            text_lines.append(f"\nVariables ({len(variables)}):")
            for v in variables:
                unit_note = f" [{v['Units']}]" if v["Units"] else ""
                std_note = f" (standard_name: {v['StandardName']})" if v["StandardName"] else ""
                text_lines.append(
                    f"  {v['Name']}{unit_note} — dims: {v['Dimensions']}, "
                    f"shape: {v['Shape']}, dtype: {v['DataType']}{std_note}"
                )

            if coord_vars:
                text_lines.append(f"\nCoordinate variables detected: {', '.join(coord_vars)}")

    except Exception as e:
        msg = f"Failed to read NetCDF file: {str(e)}"
        text_lines.append(msg)
        raw_metadata["Error"] = msg

    return "\n".join(text_lines), raw_metadata
