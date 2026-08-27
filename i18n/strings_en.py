# i18n/strings_en.py
#
# English UI strings. Keys are grouped by where they appear in main.py.
# Placeholders use str.format() syntax, e.g. "{filename}".

STRINGS_EN = {
    # --- Window / top bar ---
    "window_title": "Image Metadata Viewer",
    "label_select_format": "Select Format:",
    "label_select_application": "Select Application:",
    "btn_standards_info": "Metadata Standard Info",
    "label_select_file": "Select File:",
    "label_language": "Language:",

    # --- Sidebar: File ---
    "group_file": "File",
    "btn_load_file": "Load File",
    "btn_load_folder": "Load Folder",

    # --- Sidebar: Export ---
    "group_export": "Export",
    "btn_export_json": "Export as JSON",
    "btn_export_csv": "Export as CSV",
    "btn_export_curation": "Export Curation Report",
    "btn_batch_compliance": "Batch Compliance Summary",
    "tooltip_batch_compliance": "Aggregates missing-field and curation-flag counts across all loaded files — how ready is this dataset overall?",

    # --- Sidebar: Write-back ---
    "group_write": "Write-back",
    "btn_write_metadata": "Write Metadata to File",
    "btn_save_sidecar": "Save Sidecar JSON",
    "tooltip_save_sidecar": "Save metadata as a .json file beside the image (same folder, same base name).",

    # --- Sidebar: Integrity ---
    "group_integrity": "Integrity",
    "btn_save_checksums": "Save Checksums",
    "tooltip_save_checksums": "Write checksums.json for the loaded files' folder, for later integrity checks.",
    "btn_verify_integrity": "Verify Integrity",
    "tooltip_verify_integrity": "Compare current file checksums against a saved checksums.json.",

    # --- Sidebar: View ---
    "group_view": "View",
    "btn_hide_preview": "Hide Preview",
    "btn_show_preview": "Show Preview",
    "label_no_preview": "No Preview",

    # --- Tabs ---
    "tab_raw_metadata": "Raw Metadata",
    "tab_recommended_fields": "Recommended Fields",
    "tab_curation": "Curation",
    "placeholder_raw_metadata": "Raw metadata will appear here",
    "placeholder_recommended_fields": "Recommended / standardized fields will appear here",
    "placeholder_curation": "Curation flags and integrity info will appear here",

    # --- Standards info dialog ---
    "dialog_title_metadata_standard": "Metadata Standard — {context}",
    "text_no_standards_doc": "No standards documentation is registered for '{context}' yet.",
    "text_covers": "What this app extracts for this standard:",
    "text_not_covered": "Not covered by file metadata (must be supplied separately):",
    "btn_close": "Close",

    # --- File / folder dialogs ---
    "dialog_select_file": "Select File",
    "dialog_select_folder": "Select Folder",
    "msg_no_files_found_title": "No Files Found",
    "msg_no_files_found_text": "No supported image files were found in this folder.",

    # --- Batch loading progress ---
    "progress_loading_files": "Loading files...",
    "progress_cancel": "Cancel",
    "progress_batch_loading_title": "Batch Loading",
    "progress_processing": "Processing {filename} ({current}/{total})",

    # --- Metadata editor dialog ---
    "dialog_title_edit_metadata": "Edit Metadata Before Writing",
    "text_edit_metadata_note": (
        "Edit the values below, then click Save to write them into the file. "
        "Fields with multiple sub-values (shown greyed out) are structured "
        "and not editable here."
    ),

    # --- Write metadata ---
    "dialog_title_write_metadata": "Write Metadata to File",
    "confirm_overwrite_metadata": "This will overwrite metadata in:\n{path}\n\nThis action cannot be undone. Continue?",
    "msg_write_metadata_success": "Metadata written to file successfully.",
    "msg_write_metadata_failed": "Failed to write metadata: {error}",
    "tooltip_write_metadata_unsafe": (
        "Writing is disabled for this format: it would overwrite structural "
        "metadata (OME-XML channel/plane structure, or GeoTIFF "
        "georeferencing) that cannot be reconstructed from the pixel data."
    ),
    "msg_write_unsafe_format": (
        "Writing metadata to this format is disabled because it would "
        "overwrite structural metadata (OME-XML or GeoTIFF georeferencing) "
        "that cannot be recovered afterward."
    ),

    # --- Curation report export ---
    "dialog_save_curation_report": "Save Curation Report",
    "msg_curation_report_success": "Curation report saved successfully.",
    "msg_curation_report_failed": "Failed to save curation report: {error}",

    # --- Integrity ---
    "msg_checksums_success": "Checksums saved for {count} file(s):\n{path}",
    "msg_checksums_failed": "Failed to save checksums: {error}",
    "msg_no_checksums_title": "No Checksums Found",
    "msg_no_checksums_text": "No checksums.json found in this folder.\nUse 'Save Checksums' first to create a baseline.",
    "dialog_title_integrity_result": "Integrity Verification Result",

    # --- Sidecar ---
    "dialog_title_save_sidecar": "Save Sidecar JSON",
    "confirm_overwrite_sidecar": "A sidecar file already exists:\n{path}\n\nOverwrite it?",
    "msg_sidecar_success": "Sidecar saved:\n{path}",
    "msg_sidecar_failed": "Failed to save sidecar: {error}",

    # --- JSON / CSV export ---
    "dialog_save_json": "Save JSON",
    "msg_json_success": "JSON file saved successfully.",
    "msg_json_failed": "Failed to save JSON: {error}",
    "dialog_save_csv": "Save CSV",
    "msg_csv_success": "CSV file saved successfully.",
    "msg_csv_failed": "Failed to save CSV: {error}",

    # --- Batch compliance summary dialog ---
    "dialog_title_batch_compliance": "Batch Compliance Summary",
    "compliance_summary_header": "{compliant} / {total} files fully compliant (no missing required fields, no curation flags)",
    "compliance_missing_fields_header": "Missing required fields, by frequency:",
    "compliance_curation_flags_header": "Curation flags, by frequency:",
    "compliance_files_count": "{count} file(s)",
    "compliance_all_clear": "All files are fully compliant — no missing required fields or curation flags.",

    # --- Generic dialog titles ---
    "msg_success_title": "Success",
    "msg_error_title": "Error",

    # --- Metadata display content ---
    "label_file": "File:",
    "text_metadata_extraction_failed": "Metadata extraction failed.",
    "text_error_prefix": "Error: {error}",

    # --- Recommended Fields tab: missing required fields ---
    "missing_fields_label": "Missing required fields:",

    # --- Curation tab rendering ---
    "curation_summary_title": "Curation Summary — {filename}",
    "curation_flags_label": "Flags:",
    "curation_ok_text": "OK — no issues detected",
    "curation_md5_label": "MD5 Checksum:",
    "curation_compression_warning_label": "Compression Warning:",
    "curation_standard_label": "Metadata Standard:",
    "curation_reference_label": "Reference:",
}
