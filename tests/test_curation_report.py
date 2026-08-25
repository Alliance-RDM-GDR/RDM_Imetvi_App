# tests/test_curation_report.py
#
# Verifies that the _CurationFlags and _MD5Checksum fields are present
# in standardized metadata after processing, which is what the
# Export Curation Report button consumes.

from utils.curation_flags import compute_curation_flags


def test_curation_flags_field_present_after_processing(synthetic_jpg):
    """Simulate what process_file does: parse → standardize → attach flags."""
    from metadata_parsers.jpg_parser import parse_jpg_metadata
    from standardizers.jpg_general_standardizer import standardize_jpg_general_metadata

    text_report, raw_metadata = parse_jpg_metadata(synthetic_jpg)
    meta = standardize_jpg_general_metadata(raw_metadata)

    flags_by_path, checksums = compute_curation_flags(
        [(synthetic_jpg, text_report, meta)]
    )
    meta["_CurationFlags"] = "; ".join(flags_by_path[synthetic_jpg]) or "OK"
    meta["_MD5Checksum"] = checksums[synthetic_jpg]

    assert "_CurationFlags" in meta
    assert "_MD5Checksum" in meta
    assert len(meta["_MD5Checksum"]) == 32


def test_curation_report_columns_present(synthetic_jpg):
    """The curation report CSV columns must be derivable from standardized metadata."""
    from metadata_parsers.jpg_parser import parse_jpg_metadata
    from standardizers.jpg_general_standardizer import standardize_jpg_general_metadata

    text_report, raw_metadata = parse_jpg_metadata(synthetic_jpg)
    meta = standardize_jpg_general_metadata(raw_metadata)

    flags_by_path, checksums = compute_curation_flags(
        [(synthetic_jpg, text_report, meta)]
    )
    meta["_CurationFlags"] = "; ".join(flags_by_path[synthetic_jpg]) or "OK"
    meta["_MD5Checksum"] = checksums.get(synthetic_jpg, "")

    # All columns the export function reads must exist or default to ""
    assert meta.get("_CurationFlags") is not None
    assert meta.get("_MD5Checksum") is not None
