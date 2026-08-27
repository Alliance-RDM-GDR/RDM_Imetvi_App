# utils/compliance_summary.py
#
# Aggregates per-file curation state (_MissingFields from
# required_fields_registry.py, _CurationFlags from curation_flags.py)
# across a whole batch into a single readiness snapshot — answers
# "is this dataset ready to deposit?" at a glance, instead of reading
# through every file's Curation tab or scanning every row of the
# per-file curation report CSV.

from collections import Counter


def compute_batch_compliance_summary(sources):
    """
    sources: iterable of (file_path, text_report, standardized_metadata)
             — same shape as MetadataViewer.loaded_files in main.py.

    Returns:
        {
            "total_files": int,
            "fully_compliant": int,             # no missing fields, no curation flags
            "files_with_missing_fields": int,
            "files_with_curation_flags": int,
            "missing_field_counts": Counter,    # {field_key: file_count}
            "curation_flag_counts": Counter,    # {flag_name: file_count}
        }
    """
    total_files = 0
    fully_compliant = 0
    files_with_missing_fields = 0
    files_with_curation_flags = 0
    missing_field_counts = Counter()
    curation_flag_counts = Counter()

    for _, _, meta in sources:
        total_files += 1

        missing = meta.get("_MissingFields") or []
        flags_str = meta.get("_CurationFlags", "") or ""
        flags = [f.strip() for f in flags_str.split(";") if f.strip() and f.strip() != "OK"]

        if missing:
            files_with_missing_fields += 1
            missing_field_counts.update(missing)

        if flags:
            files_with_curation_flags += 1
            curation_flag_counts.update(flags)

        if not missing and not flags:
            fully_compliant += 1

    return {
        "total_files": total_files,
        "fully_compliant": fully_compliant,
        "files_with_missing_fields": files_with_missing_fields,
        "files_with_curation_flags": files_with_curation_flags,
        "missing_field_counts": missing_field_counts,
        "curation_flag_counts": curation_flag_counts,
    }
