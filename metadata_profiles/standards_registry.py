# metadata_profiles/standards_registry.py

# Documents which disciplinary metadata standard each application context
# targets, what this app actually captures from the image file relative to
# that standard, and where to find the standard's official reference.
#
# Coverage is reported honestly: most disciplinary standards include fields
# (e.g. REMBI's Biosample/Specimen categories) that are never embedded by
# acquisition software in the image file itself — those have to be supplied
# by the researcher through a separate record (ELN, repository submission
# form, etc.), and this app cannot extract what isn't in the file.
from i18n import get_language
from metadata_profiles.standards_fr import STANDARDS_FR

STANDARDS_REGISTRY = {
    "Microscopy": {
        "standard_name": "REMBI (Recommended Metadata for Biological Images)",
        "reference_url": "https://doi.org/10.1038/s41592-021-01166-8",
        "secondary_url": "https://www.ebi.ac.uk/bioimage-archive/rembi/",
        "secondary_label": "BioImage Archive — REMBI guidance",
        "covered": [
            "Image Acquisition: objective, numerical aperture, magnification, "
            "microscope, detector, light source, channel names/exposure, "
            "pixel size, image dimensions, bit depth, acquisition time.",
        ],
        "not_covered": [
            "Biosample (organism, strain, genotype, growth conditions) — not "
            "embedded by acquisition software; must be supplied separately.",
            "Specimen (fixation, staining, embedding, sectioning) — same as above.",
            "Image Analysis (segmentation method, software, parameters) — only "
            "present if explicitly written into the file by analysis software.",
        ],
    },
    "Microscopy (OME)": {
        "standard_name": "OME-XML / OME-TIFF",
        "reference_url": "https://www.openmicroscopy.org/ome-files/",
        "secondary_url": "https://docs.openmicroscopy.org/ome-model/latest/",
        "secondary_label": "OME Data Model specification",
        "covered": [
            "Pixels element: dimensions, physical pixel size + units, pixel type.",
            "Channel elements: name, samples per pixel, illumination type.",
            "Instrument/Objective: model, magnification, NA, immersion, correction.",
        ],
        "not_covered": [
            "StructuredAnnotations (free-form experiment notes) — only parsed "
            "if present; not all OME-TIFF exporters populate them.",
            "Biosample/Specimen fields, same caveat as REMBI above.",
        ],
    },
    "Remote Sensing": {
        "standard_name": "ISO 19115 (Geographic Information — Metadata)",
        "reference_url": "https://www.iso.org/standard/53798.html",
        "secondary_url": "https://www.fgdc.gov/metadata/iso-standards",
        "secondary_label": "FGDC — ISO geospatial metadata overview",
        "covered": [
            "Spatial reference: CRS (EPSG code, WKT), bounding box, pixel "
            "resolution, band count and descriptions, no-data value, band "
            "data type, pixel interpretation (area vs. point, when set).",
        ],
        "not_covered": [
            "Lineage/provenance (processing history), distribution and "
            "responsible-party fields — ISO 19115 categories not present in "
            "raw GeoTIFF tags; typically supplied via a separate .xml sidecar "
            "or catalog record (e.g. in QGIS/ArcGIS metadata tools).",
        ],
    },
    "General / EXIF": {
        "standard_name": "EXIF (CIPA DC-008) + IPTC Photo Metadata",
        "reference_url": "https://www.iptc.org/std/photometadata/specification/",
        "secondary_url": "https://www.cipa.jp/std/documents/e/DC-008-Translation-2019-E.pdf",
        "secondary_label": "CIPA DC-008 (EXIF 2.32) specification",
        "covered": [
            "EXIF: camera make/model, software, acquisition date, resolution, GPS.",
            "IPTC IIM: caption, keywords, byline/credit, copyright notice, "
            "location (city/province/country), special instructions. "
            "JPEG only — see note below.",
            "XMP: usage terms / rights statement, subject keywords (when present). "
            "JPEG only — see note below.",
        ],
        "not_covered": [
            "Controlled-vocabulary subject classification (e.g. AAT, LCSH) — "
            "IPTC keywords are free text as written by the photographer/archivist.",
            "IPTC and XMP for TIFF: this app's TIFF parser only reads baseline "
            "TIFF tags (the EXIF-equivalent fields — date, artist, copyright, "
            "make/model, resolution). IPTC IIM and XMP blocks are parsed for "
            "JPEG only; a TIFF's IPTC/XMP data, if present, is not extracted.",
        ],
    },
    "Neuroimaging (BIDS)": {
        "standard_name": "BIDS 1.9.0 (Brain Imaging Data Structure) — MRI, with NIfTI-1 and ARRIVE 2.0",
        "reference_url": "https://bids-specification.readthedocs.io/en/v1.9.0/",
        "secondary_url": "https://nifti.nimh.nih.gov/nifti-1",
        "secondary_label": "NIfTI-1 header specification (also: ARRIVE 2.0 guidelines, arriveguidelines.org)",
        "covered": [
            "Image geometry from the NIfTI header: matrix size, voxel size and "
            "units, volume count and time step, data type, orientation, "
            "qform/sform codes. Header only — voxel data is never read.",
            "BIDS filename entities (sub, ses, task, dir) and suffix "
            "(T2w, dwi, bold); datatype folder (anat, dwi, func).",
            "Acquisition parameters from the JSON sidecar (with BIDS inheritance): "
            "scanner, field strength, sequence, TE/TR, flip angle, phase "
            "encoding, readout time, slice timing, task.",
            "Diffusion gradients: b-values and b=0 volume count from .bval/.bvec.",
            "Dataset context: dataset_description.json (name, BIDS version, "
            "license, authors, DOI) and participants.tsv column names.",
            "Suggestions: missing license/authors/DOI, template or unresolved "
            "converter placeholders, missing required sidecar fields for the "
            "image type, missing animal descriptors, and a missing sform.",
        ],
        "not_covered": [
            "Animal-study details (species, strain, sex, age, injury model, "
            "anesthesia, group allocation): BIDS has no small-animal MRI "
            "extension and scanners do not embed them. Add them to "
            "participants.tsv and follow ARRIVE 2.0.",
            "participants.tsv values are deliberately not read (they can hold "
            "human demographics); only column names are reported.",
            "Full BIDS validation (every entity/file-naming rule, "
            "cross-file consistency): use the official bids-validator for "
            "that. This app reports the metadata gaps a curator acts on.",
            "Voxel data: image statistics, motion or SNR quality metrics "
            "(use MRIQC) are outside this header-only inspection.",
        ],
    },
    "Microscopy (OME-Zarr)": {
        "standard_name": "OME-NGFF 0.4 (OME-Zarr) with BIDS Microscopy (BEP031) and REMBI",
        "reference_url": "https://ngff.openmicroscopy.org/0.4/",
        "secondary_url": "https://bids-specification.readthedocs.io/en/stable/appendices/microscopy.html",
        "secondary_label": "BIDS Microscopy specification (also: REMBI, doi:10.1038/s41592-021-01166-8)",
        "covered": [
            "OME-NGFF: axes (names, types, units), multiscale pyramid levels, "
            "scale transforms (pixel size normalized to µm), channel labels "
            "(omero), array shape, chunking, data type, compression. Zarr v2 "
            "and v3 metadata are both read.",
            "BIDS Microscopy JSON sidecar: acquired pixel size and units, "
            "magnification, numerical aperture, immersion, instrument "
            "model, acquisition software.",
            "Downsampling factor between the acquired pixel size (sidecar) "
            "and the stored pyramid level.",
            "Dataset context: dataset_description.json, samples.tsv columns, "
            "conversion software (GeneratedBy). Works on a .zarr folder or "
            "directly inside an uncompressed BIDS .tar, without extracting it.",
            "Suggestions: template dataset_description, missing required "
            "sidecar fields, missing REMBI Biosample/Specimen information, "
            "unnamed channels, axes without units.",
        ],
        "not_covered": [
            "Biosample and Specimen (REMBI): organism, strain, genotype, "
            "treatment/group, clearing protocol, antibodies/reporters are not "
            "stored in the image; supply them in samples.tsv/samples.json or "
            "the study record.",
            "Per-channel excitation/emission: light-sheet sidecars often "
            "carry a single wavelength pair for a multi-channel image; it is "
            "then withheld rather than attributed to a wrong channel.",
            "Pixel values, and pyramid levels that were not deposited "
            "(only the levels listed in the metadata exist in the file).",
            "Labels/segmentation (OME-NGFF labels), plates/wells and "
            "transformations other than scale.",
        ],
    },
    "Micro-CT (Scanco)": {
        "standard_name": "REMBI (Recommended Metadata for Biological Images) — Scanco micro-CT (AIM)",
        "reference_url": "https://doi.org/10.1038/s41592-021-01166-8",
        "secondary_url": "https://www.ebi.ac.uk/bioimage-archive/rembi/",
        "secondary_label": "BioImage Archive — REMBI guidance",
        "covered": [
            "Image acquisition: voxel size and matrix size, physical extent, voxel "
            "type, X-ray tube voltage and current, integration time, projections, "
            "scanner type/ID codes, acquisition date, source scan file, "
            "calibration (density unit, slope/intercept, µ scaling). Both AIM "
            "versions are read (020 and the 64-bit 030 used for scans over 2 GB). "
            "Header only — voxel data is never read.",
            "Image analysis: the processing chain recorded in the AIM log and, for "
            "segmentation files, the Gaussian filter and threshold values (in "
            "density units), plus the link to the parent grey-value volume.",
            "Companion files: the .txt header dump (cross-checked against the "
            "AIM header) and the Amira/Avizo .hx script (target file, matrix size "
            "and header offset checked against the volume).",
            "Suggestions: truncated files, Amira scripts that point to a missing or "
            "differently-cased file, instrument identified only by codes, missing "
            "Biosample/Specimen information.",
        ],
        "not_covered": [
            "Biosample and Specimen (species, collection site/date, fixation, "
            "storage, staining): AIM files hold only a free-text scan label; these "
            "must be supplied in the README or study record.",
            "Instrument make/model: the scanner is identified by numeric codes only "
            "(the code tables are not published in the file).",
            "Voxel values: histograms, bone/tissue volume or density measures are "
            "outside this header-only inspection; the statistics reported come "
            "from the file's own processing log.",
            "Segmentations: only the foreground size (voxels, mm³, % of the matrix) "
            "is computed from the run-length block. Per-object counts, the tissue "
            "volume needed for BV/TV, and morphometry are analysis, not metadata, "
            "and are left to the analysis software.",
        ],
    },
    "Cryo-EM": {
        "standard_name": "MRC2014 / EMPIAR / REMBI — cryo-EM (Thermo Fisher EPU)",
        "reference_url": "https://www.ccpem.ac.uk/mrc_format/mrc2014.php",
        "secondary_url": "https://www.ebi.ac.uk/empiar/deposition/",
        "secondary_label": "EMPIAR — deposition requirements",
        "covered": [
            "Image acquisition: image size, pixel size (Å, checked between the MRC "
            "header and the EPU XML), accelerating voltage, nominal magnification, "
            "applied defocus, total dose (e⁻/Å²), dose rate, exposure time, frame "
            "count and rate, detector model and serial number, electron counting, "
            "energy-filter slit, apertures, microscope and acquisition software.",
            "MRC2014 header: mode, byte order, version, extended-header type "
            "(FEI1/FEI2) and the expected versus actual file size. EER movies are "
            "read from their BigTIFF tags only.",
            "The files of one acquisition (.mrc, _EER.eer, .xml, .jpg) and the gain "
            "reference named in the metadata (searched in the folder and its "
            "parents). Header only — image data is never read.",
            "Suggestions: truncated files, missing XML sidecar, movie or gain "
            "reference, pixel-size mismatch, and absent biosample / specimen "
            "preparation information.",
        ],
        "not_covered": [
            "Biosample and Specimen preparation (macromolecule, source organism, "
            "buffer, grid type, vitrification): EPU does not store them; supply them "
            "in the README or the EMPIAR entry.",
            "Image quality: CTF fit, motion, ice thickness and particle counts are "
            "processing results, not acquisition metadata.",
            "The FEI extended header values: the XML sidecar carries the same "
            "settings in a documented form and is used instead.",
            "EMDB map and half-map headers, tomography tilt series and other "
            "microscope vendors' sidecars.",
        ],
    },
    "Eye Tracking": {
        "standard_name": "BIDS eye-tracking extension (BEP020) — SR Research EyeLink",
        "reference_url": "https://bids.neuroimaging.io/extensions/beps/bep_020.html",
        "secondary_url": "https://www.sr-research.com/support/",
        "secondary_label": "SR Research — EyeLink support",
        "covered": [
            "Recording: sampling frequency (header and observed from timestamps), "
            "recorded eye, tracking method, filter level, sample type, pupil "
            "measure and fit, tracker model, software, camera and serial number.",
            "Display: screen resolution and refresh rate from the tracker, and the "
            "distance, size and pixels per degree when the experiment code logged "
            "them.",
            "Quality: calibration type and count, grade and average/maximal "
            "validation error (degrees) of the last validation, share of missing "
            "samples, and counts of samples, blocks, fixations, saccades, blinks, "
            "trials and input events.",
            "Suggestions: no validation, poor validation, many missing samples, "
            "truncated file, rate mismatch, identifiers left in the header, "
            "missing screen geometry, no original EDF. The file is read in one "
            "pass; samples are counted, never stored.",
        ],
        "not_covered": [
            "Participant, session, task and stimulus descriptions: the ASC holds none "
            "beyond what the experiment code logged as messages.",
            "Conversion to BIDS (_eyetrack.tsv.gz and its .json sidecar): BEP020 is "
            "still a proposal; this app reports the fields, it does not write them.",
            "Gaze data quality beyond the tracker's own validation (precision, "
            "data loss per trial, drift): analysis, not metadata.",
            "Other trackers (Tobii, Pupil Labs) and binary EDF files.",
        ],
    },
    "Vector GIS": {
        "standard_name": "ISO 19115 — ESRI Shapefile and GeoJSON (RFC 7946)",
        "reference_url": "https://www.iso.org/standard/53798.html",
        "secondary_url": "https://datatracker.ietf.org/doc/html/rfc7946",
        "secondary_label": "GeoJSON — RFC 7946",
        "covered": [
            "Reference system: the .prj definition (name, geographic or projected, "
            "unit, EPSG code when one matches) for a shapefile; the 'crs' member or "
            "the WGS 84 default for GeoJSON.",
            "Geographic extent and spatial representation: bounding box, geometry "
            "type, feature count, Z and M values.",
            "Attribute description: field names, types and widths from the .dbf "
            "header, or the property names and value types in GeoJSON; text "
            "encoding from the .cpg.",
            "Consistency: the .shp, .shx and .dbf of a shapefile agree on size and "
            "record count, and a .shp and .geojson with the same name agree on "
            "extent. Geometry is never read from a shapefile.",
            "Suggestions: missing .shx/.dbf/.prj/.cpg, truncated files, "
            "coordinates outside lon/lat range, legacy 'crs' member, false "
            "precision, layer name that differs from the file name, no ISO record.",
        ],
        "not_covered": [
            "Title, abstract, lineage, purpose, contacts and licence (ISO 19115 "
            "identification and lineage): neither format can hold them; supply an "
            "ISO record or describe them in the README.",
            "Geometry validity (self-intersections, ring orientation, duplicate "
            "vertices) and topology: analysis in GIS software, not metadata.",
            "Attribute meaning and units: field names are read, their definitions "
            "are not.",
            "GeoPackage, KML, file geodatabases and GeoJSON files over 128 MB.",
        ],
    },
    "Medical Imaging": {
        "standard_name": "DICOM (Digital Imaging and Communications in Medicine)",
        "reference_url": "https://www.dicomstandard.org/",
        "secondary_url": "https://dicom.nema.org/medical/dicom/current/output/html/part03.html",
        "secondary_label": "DICOM PS3.3 — Information Object Definitions",
        "covered": [
            "Acquisition context: modality, manufacturer/model, study/series "
            "description, body part, protocol, pixel spacing, slice thickness.",
        ],
        "not_covered": [
            "Patient-identifying fields are intentionally excluded by this app "
            "(PatientName, PatientID, PatientBirthDate, etc.) — see "
            "metadata_parsers/dicom_parser.py. Use institutional de-identification "
            "tooling if patient-level data is required for your workflow.",
        ],
    },
    "Microscopy (Leica)": {
        "standard_name": "REMBI (Recommended Metadata for Biological Images) — Leica LIF",
        "reference_url": "https://doi.org/10.1038/s41592-021-01166-8",
        "secondary_url": "https://www.leica-microsystems.com/science-lab/life-science/lif-file-format/",
        "secondary_label": "Leica — LIF file format overview",
        "covered": [
            "Image Acquisition: image name, series count, dimensions (X/Y/Z/T), "
            "number of channels, pixel size (µm/pixel in X/Y/Z), bit depth per channel.",
            "Optics: numerical aperture, magnification, objective name, "
            "digital zoom, pinhole size (from ATLConfocalSettingDefinition block).",
            "Mosaic: tile count and positions (when present).",
        ],
        "not_covered": [
            "Channel names and excitation/emission wavelengths — stored in a "
            "separate XML block not yet parsed by readlif; use Fiji/Bio-Formats "
            "for full channel metadata.",
            "Acquisition date/time — not consistently embedded in the LIF XML.",
            "Biosample and Specimen fields — same caveat as REMBI/TIFF above.",
        ],
    },
    "General / HDF5": {
        "standard_name": "HDF5 (Hierarchical Data Format, version 5)",
        "reference_url": "https://www.hdfgroup.org/solutions/hdf5/",
        "secondary_url": "https://docs.h5py.org/",
        "secondary_label": "h5py documentation",
        "covered": [
            "Container structure: groups, datasets, dimensions, data types, "
            "compression filters (gzip, szip, lzf, etc.).",
            "Root-level global attributes (e.g. Conventions, institution).",
            "Per-dataset attribute key names (up to 5 per dataset).",
            "Curation risk flags: EXTERNAL_LINK, PROPRIETARY_COMPRESSION, "
            "NOT_SELF_DESCRIBING.",
        ],
        "not_covered": [
            "Domain-specific semantics (what the datasets represent) — "
            "HDF5 is a generic container; field meaning depends on the "
            "scientific community's conventions (e.g. CF Conventions for "
            "climate/earth science, OME-Zarr for bioimaging).",
            "Full attribute values per dataset — only key names are listed "
            "to avoid overwhelming the report.",
        ],
    },
    "Remote Sensing (NetCDF)": {
        "standard_name": "ISO 19115 (Geographic Information — Metadata) via CF Conventions",
        "reference_url": "https://www.iso.org/standard/53798.html",
        "secondary_url": "https://cfconventions.org/",
        "secondary_label": "CF Conventions for Climate and Forecast metadata",
        "covered": [
            "Global attributes: Conventions version, institution, title, "
            "processing history, source.",
            "Dimensions and variable inventory: name, shape, data type, "
            "units, long_name, standard_name.",
            "Coordinate variables (lat/lon/time/depth/level) when present "
            "under CF-conventional names.",
        ],
        "not_covered": [
            "Spatial reference details (CRS, bounding box, pixel resolution) "
            "as reported for GeoTIFF — NetCDF stores these as grid_mapping "
            "variables and coordinate values rather than fixed tags; not yet "
            "parsed into a structured CRS/BoundingBox field.",
            "Lineage/provenance and distribution fields beyond the free-text "
            "'history' and 'source' global attributes.",
        ],
    },
    "Remote Sensing (LiDAR)": {
        "standard_name": "ISO 19115 (Geographic Information — Metadata) / ASPRS LAS",
        "reference_url": "https://www.iso.org/standard/53798.html",
        "secondary_url": "https://www.asprs.org/divisions-committees/lidar-division/laser-las-file-format-exchange-activities",
        "secondary_label": "ASPRS — LAS specification",
        "covered": [
            "LAS version, point data format (what each point record stores — "
            "XYZ only, +GPS time, +RGB color, +near-infrared), point count, "
            "3D bounding box (X/Y/Z min-max), generating software, creation date.",
            "Spatial reference: CRS (EPSG code, WKT), read from the header's "
            "GeoTIFF-key or LAS 1.4 WKT projection tag, when present.",
        ],
        "not_covered": [
            "CRS is frequently absent from LAS/LAZ headers even in otherwise "
            "well-formed files — this is common practice, not necessarily an "
            "error, but means the coordinate system must be confirmed from "
            "project documentation (e.g. a README) rather than assumed. "
            "Flagged as a NO_CRS_FOUND curation risk when missing.",
            "Point classification scheme, flight/acquisition parameters "
            "(sensor, flying height, scan angle), and point density are not "
            "summarized — those require reading the full point records, not "
            "just the header, and are outside this app's header-only, "
            "fast-inspection design.",
        ],
    },
    "Astrophysical Simulation": {
        "standard_name": "IVOA Simulation Data Model (SimDM) — descriptive core only",
        "reference_url": "https://www.ivoa.net/documents/SimDM/",
        "secondary_url": "https://doi.org/10.1038/sdata.2016.18",
        "secondary_label": "FAIR Guiding Principles (Wilkinson et al. 2016)",
        "covered": [
            "Run identity: code, run label, run ID, dump number, simulated time.",
            "Numerical setup read from the output: hydrodynamic grid, boundary "
            "radii, number of fluids, heating/burning switches, MPI layout.",
            "Time integration: time step, Courant number, run history with "
            "restart detection, maximum Mach number.",
            "Data layout of raw 3-D cubes (sub-cube geometry, completeness) and, "
            "when a variables.json is present, variable names and units.",
            "Initial stratification (setup file): stellar model, radial range, "
            "base-state constants.",
        ],
        "not_covered": [
            "Authors, licence, DOI, funding and citation: these live in the "
            "dataset README/release.json, not in the simulation files, and must "
            "be supplied at deposit.",
            "Code version and physics options beyond the flags a data release "
            "ships (PPMstar is proprietary; its full configuration is withheld).",
            "Cube data values (ranges, NaN masks, spherical averages): cubes "
            "are sized, never read — they reach 2.3 GB per file.",
            "Cube variable names and units when no variables.json sits within "
            "four folders of the cube: raw float32 blocks are headerless.",
            "Whole-file checksums: use the Integrity > Verify Manifest action "
            "against the dataset's MANIFEST.sha256.",
        ],
    },
    "Astronomy": {
        "standard_name": "FITS (Flexible Image Transport System)",
        "reference_url": "https://fits.gsfc.nasa.gov/fits_standard.html",
        "secondary_url": "https://docs.astropy.org/en/stable/io/fits/",
        "secondary_label": "astropy.io.fits documentation",
        "covered": [
            "Header cards: telescope, instrument, object, observation date "
            "(DATE-OBS, MJD-OBS, DATE-END), exposure time, filter, dimensions, "
            "author/origin/creator, observer, proposal ID, time system, BUNIT, "
            "BSCALE/BZERO.",
            "WCS (World Coordinate System): reference value/pixel, pixel scale, "
            "CD or PC matrix, axis units, pole angles, coordinate type, reference "
            "frame, equinox; plus a check that astropy can build a celestial WCS "
            "and the resulting pixel scale in arcsec/pixel.",
            "HDU inventory: every HDU's type (image, binary/ASCII table, "
            "compressed image), name, image shape and dtype, or table row and "
            "column count with column names and units.",
            "Images stored in an extension (multi-extension or compressed FITS): "
            "dimensions, BITPIX, WCS and missing header keys are read from the "
            "first 2-D image extension when the primary HDU is empty.",
            "Number of HISTORY and COMMENT cards.",
        ],
        "not_covered": [
            "Header keys of extensions other than the first 2-D image HDU (e.g. "
            "per-detector WCS in a mosaic with several image extensions).",
            "Pixel values and table contents: only headers are read, so image "
            "statistics, saturation and table row data are not summarized.",
            "The text of HISTORY/COMMENT cards, and instrument-specific keywords "
            "(e.g. HST, JWST, Gemini conventions) beyond the common set.",
            "Non-celestial WCS (spectral, time) axes and distortion terms (SIP, "
            "TPV) beyond the validity check.",
        ],
    },
}


def get_standard_info(context_name):
    """Returns the standards registry entry for a context, or None.

    In French, the human-readable strings come from standards_fr.py; URLs
    and anything not translated there stay as in the English entry.
    """
    info = STANDARDS_REGISTRY.get(context_name)
    if info and get_language() == "FR":
        return {**info, **STANDARDS_FR.get(context_name, {})}
    return info


def get_reference_summary(context_name):
    """
    Returns a compact {"Standard": ..., "URL": ...} dict suitable for
    embedding in exported/written metadata, or None if the context is
    not registered.
    """
    info = STANDARDS_REGISTRY.get(context_name)
    if not info:
        return None
    return {
        "Standard": info["standard_name"],
        "URL": info["reference_url"],
    }
