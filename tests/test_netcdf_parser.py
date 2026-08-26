# tests/test_netcdf_parser.py

import netCDF4
import numpy as np

from metadata_parsers.netcdf_parser import parse_netcdf_metadata
from standardizers.netcdf_remote_sensing_standardizer import standardize_netcdf_remote_sensing_metadata


def _make_cf_netcdf(path, with_coords=True):
    ds = netCDF4.Dataset(path, "w", format="NETCDF4")
    ds.Conventions = "CF-1.8"
    ds.institution = "University of Saskatchewan"
    ds.title = "Synthetic test dataset"
    ds.history = "Created by test suite"
    ds.source = "test_netcdf_parser.py"

    ds.createDimension("time", 3)
    ds.createDimension("lat", 4)
    ds.createDimension("lon", 5)

    if with_coords:
        lat_var = ds.createVariable("lat", "f4", ("lat",))
        lat_var.units = "degrees_north"
        lat_var.standard_name = "latitude"
        lat_var.long_name = "Latitude"
        lat_var[:] = np.linspace(49.0, 52.0, 4)

        lon_var = ds.createVariable("lon", "f4", ("lon",))
        lon_var.units = "degrees_east"
        lon_var.standard_name = "longitude"
        lon_var[:] = np.linspace(-106.0, -103.0, 5)

    temp_var = ds.createVariable("temperature", "f4", ("time", "lat", "lon"))
    temp_var.units = "K"
    temp_var.standard_name = "air_temperature"
    temp_var.long_name = "Air Temperature"
    temp_var[:] = np.zeros((3, 4, 5))

    ds.close()


def test_parse_netcdf_global_attributes(tmp_path):
    nc_path = str(tmp_path / "sample.nc")
    _make_cf_netcdf(nc_path)

    text_report, raw_metadata = parse_netcdf_metadata(nc_path)

    assert raw_metadata["Conventions"] == "CF-1.8"
    assert raw_metadata["institution"] == "University of Saskatchewan"
    assert raw_metadata["title"] == "Synthetic test dataset"
    assert "CF-1.8" in text_report


def test_parse_netcdf_dimensions(tmp_path):
    nc_path = str(tmp_path / "sample.nc")
    _make_cf_netcdf(nc_path)

    _, raw_metadata = parse_netcdf_metadata(nc_path)

    assert raw_metadata["DimensionCount"] == 3
    assert raw_metadata["Dimensions"]["time"] == 3
    assert raw_metadata["Dimensions"]["lat"] == 4
    assert raw_metadata["Dimensions"]["lon"] == 5


def test_parse_netcdf_variables_and_cf_attrs(tmp_path):
    nc_path = str(tmp_path / "sample.nc")
    _make_cf_netcdf(nc_path)

    _, raw_metadata = parse_netcdf_metadata(nc_path)

    var_names = {v["Name"] for v in raw_metadata["Variables"]}
    assert "temperature" in var_names
    assert "lat" in var_names
    assert "lon" in var_names

    temp_var = next(v for v in raw_metadata["Variables"] if v["Name"] == "temperature")
    assert temp_var["Units"] == "K"
    assert temp_var["StandardName"] == "air_temperature"
    assert temp_var["Shape"] == [3, 4, 5]


def test_parse_netcdf_detects_coordinate_variables(tmp_path):
    nc_path = str(tmp_path / "sample.nc")
    _make_cf_netcdf(nc_path, with_coords=True)

    _, raw_metadata = parse_netcdf_metadata(nc_path)

    assert "lat" in raw_metadata["CoordinateVariables"]
    assert "lon" in raw_metadata["CoordinateVariables"]


def test_parse_netcdf_no_coordinate_variables(tmp_path):
    nc_path = str(tmp_path / "no_coords.nc")
    _make_cf_netcdf(nc_path, with_coords=False)

    _, raw_metadata = parse_netcdf_metadata(nc_path)

    assert raw_metadata["CoordinateVariables"] == []


def test_parse_netcdf_handles_missing_file():
    text_report, raw_metadata = parse_netcdf_metadata("does_not_exist.nc")

    assert "Failed to read NetCDF file" in text_report
    assert "Error" in raw_metadata


def test_standardize_netcdf_maps_iso19115_fields(tmp_path):
    nc_path = str(tmp_path / "sample.nc")
    _make_cf_netcdf(nc_path)

    _, raw_metadata = parse_netcdf_metadata(nc_path)
    result = standardize_netcdf_remote_sensing_metadata(raw_metadata)

    assert result["Conventions"] == "CF-1.8"
    assert result["Institution"] == "University of Saskatchewan"
    assert result["Title"] == "Synthetic test dataset"
    assert result["ProcessingHistory"] == "Created by test suite"
    assert "lat" in result["CoordinateVariables"]

    # Variables stay structured (dicts), not flattened to display strings —
    # downstream JSON/CSV exports and the Recommended Fields renderer both
    # rely on this to keep the CF standard_name as a real, reusable field.
    temp_var = next(v for v in result["Variables"] if v["Name"] == "temperature")
    assert temp_var["StandardName"] == "air_temperature"
    assert temp_var["Units"] == "K"
    assert temp_var["LongName"] == "Air Temperature"
    assert temp_var["Shape"] == [3, 4, 5]


def test_standardize_netcdf_handles_missing_globals():
    raw_metadata = {
        "FilePath": "some/path/minimal.nc",
        "Conventions": "",
        "institution": "",
        "title": "",
        "history": "",
        "source": "",
        "DimensionCount": 0,
        "VariableCount": 0,
        "CoordinateVariables": [],
        "Variables": [],
    }

    result = standardize_netcdf_remote_sensing_metadata(raw_metadata)

    assert result["ImageName"] == "minimal.nc"
    assert result["Conventions"] == ""
    assert result["Variables"] == []
