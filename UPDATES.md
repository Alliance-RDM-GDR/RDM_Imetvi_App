# IMetVi — Updates

Human-readable changelog. Entries are grouped by development session and
listed newest first. For the underlying task tracking, see
[`ROADMAP.md`](ROADMAP.md); for how these pieces fit together, see
[`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## 2026-08-26 — Expected-fields checking (D1)

- Added `metadata_profiles/required_fields_registry.py`:
  `REQUIRED_FIELDS_REGISTRY` declares, per format (TIFF, CZI, OME-TIFF,
  GeoTIFF, JPG, PNG, DICOM, FITS, LIF, NetCDF), the standardized fields a
  well-formed capture is expected to have. Keyed by format rather than
  application context, since JPG and PNG share the `General / EXIF`
  context but have unrelated field sets (EXIF/IPTC/XMP vs. PNG text
  chunks). HDF5 has no entry — its output is a dataset inventory, not a
  fixed scalar field set. `compute_missing_fields()` treats a field as
  missing if it's absent from the dict, `None`, or a blank/whitespace
  string.
- `main.py`: both `process_file()` (single file) and
  `FolderLoadWorker.run()` (batch) attach `_MissingFields` alongside the
  existing `_CurationFlags`/`_MD5Checksum`. `render_metadata()` shows any
  gaps in bold red at the top of the Recommended Fields tab (human
  labels via `format_label()`, not raw keys). `export_curation_report()`
  gained a `MissingFields` column (semicolon-joined).
- Added a `missing_fields_label` key to both `i18n/strings_en.py` and
  `strings_fr.py` so the red warning line stays bilingual.
- 8 new tests (`tests/test_required_fields.py`).
- Verified interactively: a JPG with no camera/date EXIF showed "⚠
  Missing required fields: Acquisition Date, Camera Make, Camera Model"
  in red, correctly using human-readable labels.

## 2026-08-26 — Bilingual EN/FR interface (C4)

- Added `i18n/strings_en.py` and `i18n/strings_fr.py`: flat `{key:
  template}` dicts covering every static UI string — window title,
  sidebar group titles, button labels, tooltips, tab titles, placeholder
  text, dialog titles, and every `QMessageBox` message. `i18n/__init__.py`
  exposes `tr(key, **kwargs)` (falls back to English, then the raw key —
  never crashes on a missing translation), `set_language()`,
  `get_language()`.
- Added a `Language: EN | FR` dropdown to the top bar. Switching it calls
  `MetadataViewer.retranslate_ui()`, which re-applies `tr()` to every
  persistent widget, and re-renders the currently displayed file (via a
  newly stored `self.current_display_text_report`) so the Curation tab's
  dynamically built summary and the "File: …" header update too, not just
  future loads.
- Deliberately out of scope: metadata field labels
  (`metadata_profiles/*_profile.py`) and standards-coverage text
  (`standards_registry.py`) — those describe the extracted data itself,
  live across ~10 separate profile files, and are a larger effort than
  covering UI chrome.
- `tests/test_i18n.py` (9 tests) asserts `strings_en.py` and
  `strings_fr.py` have identical key sets, so a key added to one and
  forgotten in the other fails a test instead of silently falling back to
  English in the French UI.
- Verified interactively: switched EN→FR→EN with a file loaded, confirmed
  every sidebar/tab/dialog string and the dynamic Curation summary
  translated correctly in both directions.

## 2026-08-26 — Grouped action sidebar

- Replaced the single horizontal row of action buttons (Load File through
  Verify Integrity) with a left-hand sidebar of titled `QGroupBox`
  sections: **File** (Load File, Load Folder), **Export** (Export as
  JSON/CSV, Export Curation Report), **Write-back** (Write Metadata to
  File, Save Sidecar JSON), **Integrity** (Save Checksums, Verify
  Integrity), **View** (Hide/Show Preview).
- No behavioral change — every button keeps its existing handler,
  tooltip, and enabled/disabled state logic; only the layout container
  changed, from `button_layout` (a `QHBoxLayout` inside `layout`) to
  `sidebar_widget` (a fixed-width `QVBoxLayout` of group boxes inside
  `content_layout`, alongside the thumbnail preview and tab widget).
- Verified interactively: sidebar renders with grouped titles, buttons
  enable correctly after loading a file, no regressions in the existing
  109-test suite.

## 2026-08-26 — Thumbnail preview panel (C3)

- Added `utils/thumbnail.py`: `generate_thumbnail_bytes()` rasterizes JPG,
  PNG, and TIFF (first page/frame for multi-page files) via Pillow and
  returns PNG-encoded bytes, kept Qt-free so it's unit-testable without a
  running `QApplication`. Returns `None` for non-rasterizable formats
  (DICOM, FITS, HDF5, NetCDF, LIF, CZI) and for corrupt/missing files.
- Added a collapsible preview panel to `main.py`: a fixed-size `QLabel`
  left of the tab widget shows the thumbnail (scaled, aspect-preserved)
  or, for formats Pillow can't rasterize, the file extension as a generic
  placeholder. A **Hide Preview** / **Show Preview** toggle button
  collapses the panel.
- While testing this feature interactively (per project convention —
  UI changes get exercised in the running app, not just unit tests),
  found and fixed a pre-existing bug: the Curation tab called
  `self.curation_display.setOpenLinks(False)`, but `setOpenLinks` belongs
  to `QTextBrowser`, not `QTextEdit` — every file load crashed the
  Curation tab render with `AttributeError`. Removed the call entirely
  (`QTextEdit` doesn't auto-navigate HTML links without extra wiring
  anyway, so nothing needed replacing it).
- 9 new tests (`tests/test_thumbnail.py`).

## 2026-08-25 — NetCDF / CF Conventions support (B3)

- Added `metadata_parsers/netcdf_parser.py` (via `netCDF4`),
  `standardizers/netcdf_remote_sensing_standardizer.py`, and
  `metadata_profiles/netcdf_remote_sensing_profile.py`.
- Extracts CF global attributes (`Conventions`, `institution`, `title`,
  `history`, `source`), the dimension inventory, and per-variable CF
  attributes (`units`, `long_name`, `standard_name`), detecting common
  coordinate variables (lat/lon/time/depth/level).
- Registered as a new `Remote Sensing (NetCDF)` context — kept separate
  from GeoTIFF's `Remote Sensing` context because NetCDF exposes spatial
  reference as coordinate variables rather than a fixed CRS/BoundingBox
  tag, so the field sets genuinely differ even though both target ISO
  19115.
- `.nc4` is now claimed by both `HDF5` and `NetCDF` in `FORMAT_REGISTRY`
  (NetCDF4 files are HDF5-backed) — same pattern as TIFF/OME-TIFF/GeoTIFF
  sharing `.tif`/`.tiff`; the format dropdown disambiguates. The HDF5
  parser still reports `.nc4` structurally (groups/datasets/compression)
  without CF semantics; the NetCDF parser is what interprets those.
- Unlike LIF, `netCDF4` can write files, so tests use real synthetic `.nc`
  fixtures rather than mocks — 8 new tests
  (`tests/test_netcdf_parser.py`).
- Added `netCDF4>=1.6` to `requirements.txt`.

## 2026-08-25 — Cross-session integrity verification (A4)

- Added `utils/integrity.py`: `compute_md5()`, `save_checksums()` /
  `load_checksums()` persist a `{filename: md5}` record as `checksums.json`
  in a batch's folder; `verify_checksums()` diffs a stored record against a
  current scan and classifies each file as `OK`, `MODIFIED`, `MISSING`, or
  `NEW`.
- Added **Save Checksums** and **Verify Integrity** buttons to `main.py`,
  enabled whenever a batch or single file is loaded. Verification results
  open in a scrollable dialog with per-status counts and a list of
  anomalies.
- This is distinct from the curation layer's `DUPLICATE` flag, which only
  compares files within a single loaded batch — `checksums.json` persists
  across sessions, so a curator can confirm a dataset wasn't altered
  between visits.
- 11 new tests (`tests/test_integrity.py`); full suite at 92 tests passing.

## 2026-08-25 — Sidecar JSON export (A3)

- Added `utils/sidecar.py`: `write_sidecar()` serializes standardized
  metadata to `<basename>.json` next to the source image (never touching
  the original file); `read_sidecar()` reads it back.
- Added **Save Sidecar JSON** button to `main.py`; prompts for
  confirmation before overwriting an existing sidecar.
- Matches the co-located-record convention used by QGIS, ArcGIS, and
  repository deposit workflows (FRDR, Archivematica).
- 8 new tests (`tests/test_sidecar.py`).

## 2026-08-25 — Leica LIF format support (B1)

- Added `metadata_parsers/lif_parser.py` (via `readlif`),
  `standardizers/lif_microscopy_standardizer.py`, and
  `metadata_profiles/lif_microscopy_profile.py`.
- Extracts per-series dimensions (X/Y/Z/T/M), channel count, pixel size
  (inverted from readlif's px/µm `scale`), bit depth per channel, and
  confocal acquisition settings (numerical aperture, magnification,
  objective, zoom, pinhole size) from the `ATLConfocalSettingDefinition`
  block. Mosaic tile count/position is reported when present.
- Registered as a new `Microscopy (Leica)` context in
  `profile_registry.py` and `standards_registry.py`, REMBI-aligned like
  the TIFF/CZI/OME-TIFF microscopy contexts.
- `readlif` has no write API, so tests mock the `LifFile`/`LifImage`
  objects for the happy path and use a real missing-file case for the
  error path — 9 new tests (`tests/test_lif_parser.py`).
- Added `readlif>=0.6.6` to `requirements.txt` (was missing after initial
  install).

## Earlier — Curation workflow, human-readable labels, tabbed UI

*(Reconstructed from commit history; predates this changelog.)*

- **Three-tab layout** (`Raw Metadata` / `Recommended Fields` / `Curation`)
  replacing the original two-panel view.
- **Human-readable labels with units** in the Recommended Fields tab via
  `metadata_profiles/profile_registry.py::format_label()`, falling back to
  the raw key name for anything not yet in a profile.
- **IPTC and XMP write support** for JPEG, extending
  `utils/metadata_writer.py` (previously EXIF-only) — IPTC via
  `iptcinfo3`, XMP via manual APP1 packet injection to avoid the
  Windows-hostile `libexempi` dependency of `python-xmp-toolkit`.
- **Curation report export** (`Export Curation Report` button): a
  dedicated CSV — one row per file, `CurationFlags` and technical columns
  only — compatible with `CUR_Res_CurationTools`'s report shape.
- **PNG format support**: `metadata_parsers/png_parser.py`,
  `standardizers/png_general_standardizer.py`, sharing the
  `General / EXIF` context with JPG.
- **HDF5 format support**: `metadata_parsers/hdf5_parser.py` reports
  group/dataset hierarchy, dtypes, compression filters, and root
  attributes; flags `EXTERNAL_LINK`, `PROPRIETARY_COMPRESSION`,
  `NOT_SELF_DESCRIBING` as curation risks specific to generic containers.
- **Curation flags module** (`utils/curation_flags.py`): `DUPLICATE`
  (MD5), `CORRUPT`, `HAS_GPS_DATA`, `DIMENSION_OUTLIER`, `LOSSY_TIFF`,
  adapted from `CUR_Res_CurationTools/Scripts/Inspect_Images_Script.R`.
- **JPEG-in-TIFF detection**: `tiff_parser.py` flags TIFF files using
  internal JPEG compression (Compression tag 6/7) as lossy, since this
  contradicts the archival-quality assumption usually made about TIFF.
- **Multi-format metadata support and disciplinary standards
  integration**: added DICOM (`Medical Imaging`, with patient-identifying
  fields intentionally excluded — see `dicom_parser.py`), FITS
  (`Astronomy`), OME-TIFF (`Microscopy (OME)`), GeoTIFF
  (`Remote Sensing`); introduced `metadata_profiles/standards_registry.py`
  to document, per context, what the app actually captures relative to
  the target standard (REMBI, ISO 19115, DICOM PS3.3, FITS) vs. what must
  be supplied separately.
- Initial functional app: TIFF and CZI microscopy metadata extraction,
  REMBI-aligned standardization, JSON/CSV export.

---

## How to add an entry

When a development session lands a feature (or the user confirms a task
as complete against `ROADMAP.md`), add a new dated section at the top of
this file — newest first — summarizing:

- What was added/changed, in plain language (not a diff).
- Why, if the motivation isn't obvious from the description.
- New files created and their one-line purpose.
- Test count delta, if tests were added.

Keep entries scoped to what a curator or future contributor would want to
know — not every intermediate step taken to get there.
