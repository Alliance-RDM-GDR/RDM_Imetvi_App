# tests/test_hdf5_parser.py

from metadata_parsers.hdf5_parser import parse_hdf5_metadata
from standardizers.hdf5_general_standardizer import standardize_hdf5_general_metadata


def test_parse_hdf5_extracts_structure(synthetic_hdf5):
    text_report, raw_metadata = parse_hdf5_metadata(synthetic_hdf5)

    assert isinstance(text_report, str)
    assert raw_metadata["ObjectCount"] >= 2  # group + datasets
    assert raw_metadata["DatasetCount"] >= 2
    assert raw_metadata["GroupCount"] >= 1
    assert raw_metadata["RootAttributeCount"] == 2
    assert raw_metadata["RootAttr_Conventions"] == "CF-1.8"
    assert raw_metadata["RootAttr_institution"] == "Test University"


def test_parse_hdf5_datasets_have_expected_fields(synthetic_hdf5):
    _, raw_metadata = parse_hdf5_metadata(synthetic_hdf5)
    objects = raw_metadata["Objects"]

    datasets = [o for o in objects if o["Type"] == "Dataset"]
    assert any("10 x 64 x 64" in o["Dimensions"] for o in datasets)
    assert any(o["Compression"] == "gzip" for o in datasets)


def test_standardize_hdf5_maps_root_attrs(synthetic_hdf5):
    _, raw_metadata = parse_hdf5_metadata(synthetic_hdf5)
    result = standardize_hdf5_general_metadata(raw_metadata)

    assert result["Conventions"] == "CF-1.8"
    assert result["institution"] == "Test University"
    assert int(result["DatasetCount"]) >= 2


def test_parse_hdf5_handles_missing_file():
    text_report, raw_metadata = parse_hdf5_metadata("does_not_exist.h5")

    assert "Failed to read HDF5 file" in text_report
    assert raw_metadata["FilePath"] == "does_not_exist.h5"
