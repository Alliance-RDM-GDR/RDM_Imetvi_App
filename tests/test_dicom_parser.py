# tests/test_dicom_parser.py

from metadata_parsers.dicom_parser import _PHI_KEYWORDS, parse_dicom_metadata
from standardizers.dicom_medical_standardizer import standardize_dicom_medical_metadata


def test_parse_dicom_excludes_phi_fields(synthetic_dicom):
    text_report, raw_metadata = parse_dicom_metadata(synthetic_dicom)

    for phi_field in _PHI_KEYWORDS:
        assert phi_field not in raw_metadata
        assert "Doe" not in text_report
        assert "12345" not in text_report
        assert "19900101" not in text_report


def test_parse_dicom_extracts_research_fields(synthetic_dicom):
    _, raw_metadata = parse_dicom_metadata(synthetic_dicom)

    assert raw_metadata["Modality"] == "MR"
    assert raw_metadata["Manufacturer"] == "AcmeScan"
    assert raw_metadata["BodyPartExamined"] == "BRAIN"
    assert raw_metadata["Rows"] == "256"
    assert raw_metadata["Columns"] == "256"


def test_standardize_dicom_medical_maps_fields(synthetic_dicom):
    _, raw_metadata = parse_dicom_metadata(synthetic_dicom)
    result = standardize_dicom_medical_metadata(raw_metadata)

    assert result["Modality"] == "MR"
    assert result["DimensionX"] == "256"
    assert result["DimensionY"] == "256"
    assert result["PixelSpacingX"] == "0.5"
    assert result["SliceThickness"] == "1.0"
    assert not any("Doe" in str(v) for v in result.values())
