# IMetVi — Updates

Human-readable changelog. Entries are grouped by development session and
listed newest first. For the underlying task tracking, see
[`ROADMAP.md`](ROADMAP.md); for how these pieces fit together, see
[`ARCHITECTURE.md`](ARCHITECTURE.md).

---

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
