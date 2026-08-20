# tests/test_ome_tiff_parser.py

from metadata_parsers.ome_tiff_parser import is_ome_tiff, parse_ome_tiff_metadata
from standardizers.ome_microscopy_standardizer import standardize_ome_microscopy_metadata


def test_plain_tiff_is_not_ome(synthetic_tiff):
    from metadata_parsers.tiff_parser import parse_tiff_metadata

    _, raw_metadata = parse_tiff_metadata(synthetic_tiff)
    assert is_ome_tiff(raw_metadata) is False


def test_parse_ome_tiff_extracts_expected_keys(synthetic_ome_tiff):
    _, raw_metadata = parse_ome_tiff_metadata(synthetic_ome_tiff)

    assert raw_metadata["OME_ImageName"] == "TestImage"
    assert raw_metadata["OME_SizeX"] == "10"
    assert raw_metadata["OME_SizeC"] == "2"
    assert raw_metadata["OME_PhysicalSizeX"] == "0.5"
    assert raw_metadata["OME_ObjectiveModel"] == "Plan-Apo 20x"
    assert len(raw_metadata["OME_Channels"]) == 2
    assert raw_metadata["OME_Channels"][0]["Name"] == "DAPI"


def test_standardize_ome_microscopy_maps_fields(synthetic_ome_tiff):
    _, raw_metadata = parse_ome_tiff_metadata(synthetic_ome_tiff)
    result = standardize_ome_microscopy_metadata(raw_metadata)

    assert result["ImageName"] == "TestImage"
    assert result["DimensionX"] == "10"
    assert result["SizeC"] == "2"
    assert result["ObjectiveMagnification"] == "20.0"
    assert len(result["Channels"]) == 2
