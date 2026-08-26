# IMetVi — Updates

Human-readable changelog. Entries are grouped by development session and
listed newest first. For the underlying task tracking, see
[`ROADMAP.md`](ROADMAP.md); for how these pieces fit together, see
[`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## 2026-08-26 — Fix truncated French button labels (sidebar layout)

The user reported that French button labels ("Écrire les métadonnées
dans le fichier", "Enregistrer les sommes de contrôle", etc.) were
clipped in the sidebar — French routinely runs longer than English and
the sidebar's fixed 200px width was sized for English text.

- `main.py`: moved the thumbnail preview panel from beside the sidebar to
  stacked below it (`left_column_widget`, a `QVBoxLayout` containing the
  sidebar then the preview), freeing horizontal space to widen the
  sidebar from 200px to 260px without shrinking the tab area.
- No behavioral change — same buttons, same groups, same preview toggle;
  only the container layout changed.
- Verified interactively: switched to French, confirmed every sidebar
  label now renders in full ("Écrire les métadonnées dans le fichier",
  "Enregistrer le fichier JSON associé", "Vérifier l'intégrité" all fit
  without clipping), preview panel renders correctly below the sidebar.

## 2026-08-26 — Add General / EXIF context for TIFF; fix context-routing bug

The user pointed out that TIFF is a general-purpose container, not just a
microscopy format — it's equally common for scans, scientific
illustrations, and general photography, and the app should offer more
than "Microscopy" for it.

- Added `standardizers/tiff_general_standardizer.py`, mapping TIFF's
  baseline tags (`DateTime`, `Artist`, `Copyright`, `Make`/`Model`,
  resolution — the EXIF-equivalent fields available without a
  microscopy-specific schema) into the same field names JPG uses, so it
  reuses the existing `General / EXIF` profile and standards-registry
  entry. It does **not** claim IPTC/XMP coverage — this app's TIFF
  parser only reads baseline tags, unlike the JPEG path — so
  `standards_registry.py`'s `General / EXIF` entry was updated to say so
  explicitly rather than implying TIFF gets the same coverage as JPEG.
- **Found and fixed a real routing bug while implementing this.**
  `FORMAT_STANDARDIZERS` was keyed by format name alone
  (`{"TIFF": standardize_tiff_microscopy_metadata, ...}`), so even though
  `FORMAT_REGISTRY["contexts"]` was a list (implying a format could offer
  more than one), the app always used the same standardizer regardless
  of which context was selected in the UI. A separate `CONTEXT_REGISTRY`
  dict existed and looked like it should have handled this — it never
  actually did; nothing in `main.py` ever read it. It's now removed.
  Fixed by re-keying `FORMAT_STANDARDIZERS` as `{format: {context: fn}}`
  and adding `get_standardizer(format_name, context_name)`, used at both
  call sites (`process_file()`, `FolderLoadWorker.run()`).
- `metadata_profiles/required_fields_registry.py` got the same
  (format, context) treatment where needed: TIFF's entry is now a
  `{context: [fields]}` dict (Microscopy needs `ObjectiveName`/`NA`/
  `Magnification`; General / EXIF needs `CameraMake`/`CameraModel`
  instead) — `get_required_fields()`/`compute_missing_fields()` accept an
  optional `context_name` and handle both the old flat-list shape (every
  other format) and the new nested shape.
- 14 new tests: `tests/test_tiff_general_standardizer.py`,
  `tests/test_format_standardizer_routing.py` (pins the routing fix
  directly — including a test that every `FORMAT_REGISTRY` context
  resolves to a real standardizer, to catch the two registries drifting
  out of sync again), and extensions to `tests/test_required_fields.py`.
  Also caught and fixed a real bug in `tiff_general_standardizer.py`'s
  own resolution-parsing helper while writing its tests (a zero
  denominator wasn't handled correctly).
- Verified interactively: loaded the same TIFF under both contexts —
  *Microscopy* showed the full REMBI field set with its own
  missing-fields warning (`Pixel Size X/Y`, `Objective`, `Numerical
  Aperture`, `Magnification`); switching to *General / EXIF* and
  reloading showed camera/date/resolution fields with a completely
  different missing-fields warning (`Acquisition Date`, `Camera Make`,
  `Camera Model`) — confirming the standardizer genuinely changes with
  context, not just the field labels.

## 2026-08-26 — Add GeoTIFF band data type and pixel interpretation (ISO 19115 review)

The user asked whether a GeoTIFF test file's metadata was correct and
sufficient per ISO 19115. Verified the app's output against the file
directly with a standalone `rasterio.open()` inspection (CRS, transform,
resolution, bounds, dtype, band tags) rather than assuming correctness.

- **Correct, verified against ground truth:** CRS (EPSG:2961 — NAD83(CSRS)
  / UTM zone 20N), bounding box, and 1.0 m pixel resolution all matched
  the file exactly; bounding box, resolution, and raster width/height were
  also internally consistent (`(max_x - min_x) / pixel_size == width` and
  the same for height) — a good sign the parser was correct here (unlike
  the CZI unit bug from the same review session).
- **Gap found: band data type was never extracted.** `rasterio` exposes
  it directly (`ds.dtypes`), and every other format in the app (TIFF, CZI,
  LIF) reports a bit depth/data type — GeoTIFF's omission was an
  inconsistency, not a deliberate one. Added `DataType` to
  `metadata_parsers/geotiff_parser.py`, the standardizer, the profile, and
  `REQUIRED_FIELDS_REGISTRY["GeoTIFF"]` (so its absence would now be
  correctly flagged if a file genuinely lacked it).
- **Added: pixel interpretation (`AREA_OR_POINT`).** Whether a coordinate
  refers to a pixel's center or corner (GeoTIFF's `GTRasterTypeGeoKey`)
  matters for sub-pixel georeferencing precision. Added as
  `PixelInterpretation`, informational only (not in the required list)
  since many valid GeoTIFF writers never set this tag.
- Updated `standards_registry.py`'s Remote Sensing "covered" list to
  mention both new fields.
- 3 new/extended tests (`tests/test_geotiff_parser.py`,
  `tests/test_standardizers.py`).
- Verified against the user's actual file: `Band Data Type: float32` and
  `Pixel Interpretation: Area` both now appear in the Recommended Fields
  tab, matching the direct `rasterio` inspection exactly.

## 2026-08-26 — Fix CZI pixel size unit bug and NA sentinel (REMBI review)

The user asked whether a CZI file's metadata was correct and complete
against REMBI. Rather than eyeballing it, dumped and inspected the file's
raw OME/Zeiss XML directly (`czifile.CziFile(...).metadata()`) to confirm
findings against ground truth instead of assumption.

- **🔴 Pixel size understated by 1,000,000×.** Zeiss's
  `Scaling/Items/Distance/Value` is in meters; the sibling
  `<DefaultUnitFormat>µm</DefaultUnitFormat>` is only a display-formatting
  hint, not a claim that `Value` is already in micrometers.
  `metadata_parsers/czi_parser.py` was passing the raw meters value
  straight through into `PixelSizeX/Y/Z`, which the profile labels
  `(µm)` — so a real 4.66 µm/pixel (confirmed against the camera's known
  ~4.65 µm native pixel pitch) displayed as `4.66e-06`. Added
  `_meters_to_micrometers()`, applied at parse time. REMBI requires
  accurate spatial calibration as core Image Acquisition metadata — this
  silently corrupted it for every CZI file.
- **🟠 NA of -1 shown as if real.** Zeiss writes `-1` into
  `NumericalAperture` as its sentinel for "not calibrated" on objectives
  without a defined NA in the instrument database (confirmed: this
  file's `Objective Name` is `Achromat S 1.0x`, a generic objective with
  no catalog NA entry). Added `_clean_numerical_aperture()`, which drops
  any value ≤ 0 (a real NA is always positive). This also makes the D1
  expected-fields check work correctly for NA — it now flags "Numerical
  Aperture" as genuinely missing instead of silently accepting `-1` as
  populated data.
- Confirmed as genuine gaps in the *source file*, not app bugs (verified
  these XML elements are simply absent): `AcquisitionDateAndTime`,
  `SizeZ`/`SizeT` (a single 2D snapshot, no Z-stack/timelapse recorded),
  the channel's fluorophore name, and `MicroscopeName` = `"No Connection"`
  (Zeiss's own placeholder for an unconfigured/disconnected microscope
  stand at acquisition time). These are real REMBI-completeness gaps for
  the researcher to address at the source, not something IMetVi can
  recover after the fact.
- Added `tests/test_czi_parser.py` — no CZI-specific tests existed
  before this (11 new tests: the two helper functions directly, plus the
  standardizer against a representative raw_metadata dict, since czifile
  has no write API for a synthetic fixture, same constraint as LIF).
- Verified against the user's actual file: pixel size now shows `4.6623`
  µm, NA is blank, and the D1 missing-fields banner correctly reads
  "⚠ Missing required fields: Numerical Aperture."

## 2026-08-26 — Fix color bleed across files in Recommended Fields

Found while reviewing a CZI file right after a NetCDF file with several
orange "no standard_name" warnings — the entire Recommended Fields tab
rendered in orange for the unrelated CZI file, not just a warning line.

Root cause: `QTextEdit.append()` with an HTML fragment leaves the
*insertion cursor's* character format at whatever the HTML ended on.
`clear()` wipes the document content but not that lingering format, so if
a colored `<span>` (the missing-fields banner, or a NetCDF variable's "no
standard_name" flag) happened to be the last thing appended, every
subsequent plain-text `append()` — including for a completely different
file loaded afterward — inherited that color, since nothing was resetting
the cursor's format in between.

- `main.py`: added `_reset_text_format()`, a static helper that resets a
  `QTextEdit`'s insertion character format via
  `cursor.setCharFormat(QTextCharFormat())`. Called right after
  `recommended_metadata_display.clear()` (undoes bleed carried over from
  a previous file's render) and immediately after each HTML-colored
  append — the missing-fields banner and each NetCDF variable line
  lacking a `standard_name`.
- Verified interactively by reproducing the exact sequence that surfaced
  it: loaded the NetCDF file (multiple orange-flagged variables, the last
  line of the tab ending in an orange span), then loaded a CZI file —
  confirmed the CZI's Recommended Fields rendered in normal black text.

## 2026-08-26 — Readable NetCDF variable list + CF-compliance flagging

The user tested a real NetCDF (`.adcp.nc`, ADCP ocean current data, 32
variables) and found the Recommended Fields tab's `Variables` line
unreadable — a single wrapped paragraph dumping a Python list repr of
pre-formatted strings like `'LRZAAP01 (m s-1) [upward_sea_water_velocity]'`.
Asked to review it against FAIR/data-documentation practice.

- `standardizers/netcdf_remote_sensing_standardizer.py`: stopped
  flattening `Variables` into display strings at standardization time —
  now kept as a list of dicts (`Name`, `StandardName`, `Units`,
  `LongName`, `Shape`), matching the pattern `Channels`/`Datasets` already
  use elsewhere. This isn't just a display fix: the flattened strings were
  also lossy for JSON/CSV export (FAIR "Reusable" — metadata should stay
  structured, not baked into a sentence).
- `main.py::render_metadata()`: added a `Variables` rendering branch — one
  line per variable (`- Name [standard_name] (units) — long_name  shape:
  [...]`), and flags any variable **missing a CF `standard_name`** with an
  orange `⚠ no standard_name (not CF-mapped)` marker. `standard_name` is
  CF's controlled-vocabulary term (FAIR "Interoperable" — I2: metadata use
  vocabularies that follow FAIR principles); a curator can now spot
  non-CF-compliant variables at a glance instead of having to know the CF
  standard name table by heart.
- Also added a generic fallback for any plain list-of-strings field
  (`CoordinateVariables`, GeoTIFF's `BandDescriptions`, etc.): joined with
  `, ` instead of printed as a Python list repr with quotes and brackets.
- Updated `tests/test_netcdf_parser.py`'s standardizer test for the new
  structured shape (was asserting a substring match on a flattened
  string; now asserts the dict fields directly).
- Verified interactively against the user's actual file: all 32 ADCP
  variables now print one per line, correctly scannable, with 9 of them
  (`time`, `distance`, `VEL_MAGNETIC_EAST/NORTH`, `TEMPPR01`, `filename`,
  `instrument_serial_number`, `instrument_model`, `geographic_area`)
  correctly flagged as lacking a CF `standard_name`.

## 2026-08-26 — Fix three issues found reviewing an OME-TIFF batch

Found while the user tested a 10-file OME-TIFF batch (Huygens-processed
STED microscopy) and asked for a review of the app in that state.

1. **Truncated dropdown text.** `Select Application` showed "Microscopy"
   instead of "Microscopy (OME)" — the combobox's width was fixed at
   whatever its first population needed, and never grew when
   `on_format_changed()` later repopulated it with longer context names
   ("Remote Sensing (NetCDF)", "General / HDF5", etc.). Fixed by setting
   `setSizeAdjustPolicy(QComboBox.AdjustToContents)` on `format_dropdown`,
   `app_dropdown`, and `file_selector_dropdown` (capped at 380px so a very
   long filename can't push the language selector off-screen). The
   underlying selected value was always correct — this was purely visual.

2. **Raw Metadata tab drowned in noise.** TIFF tags with one value per
   image strip (`StripOffsets`, `StripByteCounts`) printed every single
   number — hundreds of them for a 357-strip OME-TIFF — burying the
   actually useful OME-XML content. `metadata_parsers/tiff_parser.py`
   gained `_format_report_value()`: sequences over 8 items now print as
   `(first 8 values, ... N more, M total)` in the *text report* only;
   `raw_metadata` (used by exports and standardizers) keeps the complete,
   untruncated value. Also applied to the `IJMetadata` tag loop.
   `parse_ome_tiff_metadata()` and `parse_geotiff_metadata()`'s TIFF
   fallback inherit the fix for free since both call
   `parse_tiff_metadata()` internally.

3. **Data-loss risk: writing metadata to OME-TIFF (and GeoTIFF).**
   `_write_tiff_metadata()` rewrites a `.tif`/`.tiff` file from its pixel
   array plus a new `ImageDescription` string, discarding every other
   tag — safe for a plain TIFF, but the *Write Metadata to File* button
   was enabled for any `.tif`/`.tiff` regardless of format. For OME-TIFF,
   `ImageDescription` **is** the OME-XML (channel/plane/pixel-size
   structure); for GeoTIFF, georeferencing lives in separate tags
   (`ModelPixelScaleTag`/`ModelTiepointTag`/`GeoKeyDirectoryTag`) that
   also don't survive the rewrite. Either would have silently destroyed
   metadata the app has no way to reconstruct afterward. Fixed by adding
   `UNSAFE_TIFF_WRITE_FORMATS = {"GeoTIFF", "OME-TIFF"}` and
   `is_write_supported(file_path, format_name)` to
   `utils/metadata_writer.py`; `main.py` uses it to disable the button
   (with an explanatory tooltip, bilingual) and re-checks it inside
   `write_metadata()` as defense in depth against a stale button state
   after switching the format dropdown without reloading.

10 new tests across `tests/test_tiff_parser.py` and the new
`tests/test_metadata_writer_safety.py`. Verified interactively: reloaded
the same file as OME-TIFF (button correctly disabled, tooltip shown,
dropdown text no longer truncated, StripOffsets truncated) and as plain
TIFF (button correctly re-enabled).

## 2026-08-26 — Fix HAS_GPS_DATA false positive

- `utils/curation_flags.py::_has_gps()` flagged any file whose
  standardized metadata contained a GPS-named key, regardless of value.
  `standardizers/jpg_general_standardizer.py` always emits
  `GPSLatitude`/`GPSLongitude` keys (empty strings when the source has no
  GPS EXIF block), so every JPG was flagged `HAS_GPS_DATA` even with "No
  EXIF data found" in the Raw Metadata tab.
- Fixed `_has_gps()` to also require the matched value be non-empty
  (skips `None` and blank/whitespace-only strings).
- Added `test_no_gps_flag_when_keys_present_but_empty` and
  `..._but_none` to `tests/test_curation_flags.py` covering the exact
  false-positive shape.
- Verified interactively: a solid-color test JPG with no EXIF now shows
  "✔ OK — no issues detected" instead of the false `HAS_GPS_DATA` flag.

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
