# Image Metadata Viewer (IMetVi)

**IMetVi** is a cross-format desktop application for extracting,
standardizing, displaying, exporting, and curating scientific image
metadata. It targets researchers, librarians, and research technicians
working with microscopy, remote sensing, medical, astronomical, and
general-purpose image files in Canadian academic institutions.

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for how the codebase is
organized, [`ROADMAP.md`](ROADMAP.md) for planned/in-progress work, and
[`UPDATES.md`](UPDATES.md) for a chronological changelog.

## Features

- 🖼️ **Supported formats**, each mapped to a discipline-aligned standard:

  | Format | Extensions | Standard |
  |---|---|---|
  | TIFF | `.tif` `.tiff` | REMBI (microscopy) or EXIF (general photo/scan/illustration) |
  | CZI (Zeiss) | `.czi` | REMBI (microscopy) |
  | OME-TIFF | `.tif` `.tiff` | OME-XML |
  | GeoTIFF | `.tif` `.tiff` | ISO 19115 (geospatial) |
  | JPG / JPEG | `.jpg` `.jpeg` | EXIF + IPTC + XMP |
  | PNG | `.png` | EXIF-style general fields |
  | DICOM | `.dcm` | DICOM PS3.3 (patient-identifying fields excluded by design) |
  | FITS | `.fits` `.fit` | FITS / WCS (astronomy) |
  | HDF5 | `.h5` `.hdf5` `.nc4` | Generic container inspection |
  | LIF (Leica) | `.lif` | REMBI (microscopy) |
  | NetCDF | `.nc` `.nc4` | ISO 19115 via CF Conventions |
  | LAS/LAZ (LiDAR) | `.las` `.laz` | ISO 19115 / ASPRS LAS |

  Formats sharing an extension (TIFF / OME-TIFF / GeoTIFF all use
  `.tif`/`.tiff`; HDF5 / NetCDF both cover `.nc4`) are selected explicitly
  via the format dropdown, which auto-suggests a match on load. TIFF is a
  general-purpose container, not just a microscopy format — the
  **Select Application** dropdown offers both *Microscopy* and
  *General / EXIF* for it, so a scanned figure or illustration gets
  EXIF-style fields (camera, date, resolution) instead of REMBI
  microscopy fields.

- 🛰️ **LAS/LAZ point classification analysis** (on demand) — beyond the
  header fields every LAS/LAZ file shows on load, a **LiDAR** sidebar
  action reads the full point records to report point classification
  breakdown (ground/vegetation/building/water/etc.), scan angle range,
  GPS time range, and flight-line count. Kept separate from the normal
  load path since it's slower (reads every point); sensor model and
  flying height are not stored in LAS/LAZ files at all, so the app says
  so rather than guessing. The sidebar section only appears when the
  loaded file's format is LAS — it stays out of the way for every other
  format instead of sitting there greyed out.

- 📁 Load a single file or an entire folder (batch loading runs off the UI
  thread with a progress bar).
- 🇨🇦 **Bilingual EN/FR interface** — a language selector switches every
  button, label, tooltip, dialog, and error/success message between
  English and French, including the dynamically rendered Curation
  summary. (Extracted metadata field labels and standards documentation
  text are not yet translated — see [`ARCHITECTURE.md`](ARCHITECTURE.md).)
- 💬 **Tooltips on every sidebar action** — hover any button to see what
  it does before clicking it.
- 🌳 **Readable CRS WKT** — a CRS's WKT definition (often 1000+ characters
  on one line) is shown indented by nesting depth in the Recommended
  Fields tab instead of one unbroken wall of text. The value exported to
  JSON/CSV/sidecar files is unaffected — this only changes the on-screen
  display.
- 🖼️ **Collapsible thumbnail preview** — confirms visually which file is
  loaded (JPG/PNG/TIFF, first page for multi-page TIFF); other formats
  show a generic extension placeholder.
- 🧾 **Three-tab metadata view**:
  - *Raw Metadata* — everything the parser extracted, unfiltered.
  - *Recommended Fields* — standardized, discipline-aligned fields with
    human-readable labels and units.
  - *Curation* — automated flags and integrity info for this file.
- ℹ️ **Metadata Standard Info** dialog — for the active context, shows
  what the target standard requires and honestly reports what is (and
  isn't) captured from the file itself.
- 🚩 **Curation flags**, computed per batch:
  - `DUPLICATE` — identical MD5 checksum to another file in the batch
  - `CORRUPT` — parser reported a read failure
  - `HAS_GPS_DATA` — GPS metadata present (privacy/consent flag)
  - `DIMENSION_OUTLIER` — dimensions deviate from the batch's most common size
  - `LOSSY_TIFF` — TIFF using internal JPEG compression
  - `NO_CRS_FOUND` — a georeferenced format (GeoTIFF/NetCDF/LAS) with no embedded coordinate system
- ⚠️ **Missing required fields** — each format declares the standardized
  fields a well-formed capture is expected to have; gaps are shown in red
  at the top of the Recommended Fields tab and exported as a
  `MissingFields` column in the curation report
- ✍️ **Write metadata back into the file** (JPEG: EXIF + IPTC + XMP; TIFF:
  `ImageDescription`), with an editable form and an overwrite confirmation.
  Disabled (with an explanatory tooltip) for GeoTIFF and OME-TIFF, where
  writing would destroy georeferencing or the OME-XML structure — see
  [`ARCHITECTURE.md`](ARCHITECTURE.md).
- 📎 **Save Sidecar JSON** — writes `<basename>.json` beside the source
  image without touching the original (QGIS/ArcGIS/repository convention).
- 🔒 **Cross-session integrity verification** — `Save Checksums` persists
  a `checksums.json` manifest per folder; `Verify Integrity` re-scans and
  reports `OK` / `MODIFIED` / `MISSING` / `NEW` per file.
- 📋 **Batch Compliance Summary** — aggregates missing-required-field and
  curation-flag counts across a whole loaded batch into one dataset-wide
  readiness snapshot ("N / M files fully compliant", ranked by which
  fields/flags are most common), so you can judge deposit-readiness
  without reading every file's Curation tab individually.
- 💾 **Export**:
  - Standardized metadata as JSON or CSV (single file or full batch)
  - Dedicated **Curation Report** CSV (one row per file, curation-focused
    columns, compatible with `CUR_Res_CurationTools` report shape)

## Screenshot

> ![IMetVi GUI](docs/AppImage.png)
> *Recommended Fields view for a loaded LAS file — note the CRS (WKT) field
> indented for readability, and the LiDAR sidebar section that only appears
> for this format*

---

## Installation

### Requirements

- Python 3.8+
- Tested on Windows 10/11
- Recommended: run within a conda or venv environment

### Dependencies

```bash
pip install -r requirements.txt
```

### Launch the App

```bash
python main.py
```

### Run the tests

```bash
python -m pytest -q
```

---

## License
This project is licensed under the MIT License. See LICENSE for details.

---

## Acknowledgements

- TIFF handling: [tifffile](https://github.com/cgohlke/tifffile)
- Zeiss CZI reader: [czifile](https://github.com/cgohlke/czifile)
- Leica LIF reader: [readlif](https://github.com/nimne/readlif)
- EXIF read/write: [Pillow](https://python-pillow.org/) + [piexif](https://piexif.readthedocs.io/)
- IPTC read/write: [iptcinfo3](https://github.com/jkelleyrtp/iptcinfo3)
- GeoTIFF / geospatial: [rasterio](https://rasterio.readthedocs.io/)
- HDF5: [h5py](https://www.h5py.org/)
- NetCDF: [netCDF4](https://unidata.github.io/netcdf4-python/)
- LiDAR / LAS-LAZ: [laspy](https://laspy.readthedocs.io/) + [pyproj](https://pyproj4.github.io/pyproj/)
- DICOM: [pydicom](https://pydicom.github.io/)
- FITS: [astropy](https://www.astropy.org/)
- REMBI Guidelines: https://doi.org/10.1038/s41592-021-01166-8
- OME-XML spec: https://www.openmicroscopy.org/ome-files/
- ISO 19115 (geospatial metadata): https://www.iso.org/standard/53798.html
- IPTC standard: https://www.iptc.org/std/photometadata/specification/
- ASPRS LAS specification: https://www.asprs.org/divisions-committees/lidar-division/laser-las-file-format-exchange-activities
