# tests/test_compliance_summary.py

from utils.compliance_summary import compute_batch_compliance_summary


def _source(path, missing=None, flags="OK"):
    meta = {"_MissingFields": missing or [], "_CurationFlags": flags}
    return (path, "", meta)


def test_all_files_fully_compliant():
    sources = [
        _source("a.tif"),
        _source("b.tif"),
    ]
    summary = compute_batch_compliance_summary(sources)

    assert summary["total_files"] == 2
    assert summary["fully_compliant"] == 2
    assert summary["files_with_missing_fields"] == 0
    assert summary["files_with_curation_flags"] == 0
    assert summary["missing_field_counts"] == {}
    assert summary["curation_flag_counts"] == {}


def test_counts_missing_fields_across_files():
    sources = [
        _source("a.tif", missing=["NA", "ObjectiveName"]),
        _source("b.tif", missing=["NA"]),
        _source("c.tif"),
    ]
    summary = compute_batch_compliance_summary(sources)

    assert summary["files_with_missing_fields"] == 2
    assert summary["missing_field_counts"]["NA"] == 2
    assert summary["missing_field_counts"]["ObjectiveName"] == 1
    assert summary["fully_compliant"] == 1


def test_counts_curation_flags_across_files():
    sources = [
        _source("a.jpg", flags="HAS_GPS_DATA"),
        _source("b.jpg", flags="HAS_GPS_DATA; DIMENSION_OUTLIER"),
        _source("c.jpg", flags="OK"),
    ]
    summary = compute_batch_compliance_summary(sources)

    assert summary["files_with_curation_flags"] == 2
    assert summary["curation_flag_counts"]["HAS_GPS_DATA"] == 2
    assert summary["curation_flag_counts"]["DIMENSION_OUTLIER"] == 1
    assert summary["fully_compliant"] == 1


def test_file_with_both_missing_fields_and_flags_is_not_compliant():
    sources = [_source("a.tif", missing=["NA"], flags="DUPLICATE")]
    summary = compute_batch_compliance_summary(sources)

    assert summary["fully_compliant"] == 0
    assert summary["files_with_missing_fields"] == 1
    assert summary["files_with_curation_flags"] == 1


def test_empty_batch():
    summary = compute_batch_compliance_summary([])

    assert summary["total_files"] == 0
    assert summary["fully_compliant"] == 0
    assert summary["missing_field_counts"] == {}
    assert summary["curation_flag_counts"] == {}


def test_missing_curation_flags_key_treated_as_ok():
    # A file processed without curation flags attached at all (e.g. a
    # minimal/mocked metadata dict) shouldn't be misread as non-compliant.
    sources = [("a.tif", "", {"_MissingFields": []})]
    summary = compute_batch_compliance_summary(sources)

    assert summary["fully_compliant"] == 1
