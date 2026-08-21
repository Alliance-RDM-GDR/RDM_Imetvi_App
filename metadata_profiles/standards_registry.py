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
            "resolution, band count and descriptions, no-data value.",
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
            "location (city/province/country), special instructions.",
            "XMP: usage terms / rights statement, subject keywords (when present).",
        ],
        "not_covered": [
            "Controlled-vocabulary subject classification (e.g. AAT, LCSH) — "
            "IPTC keywords are free text as written by the photographer/archivist.",
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
    "Astronomy": {
        "standard_name": "FITS (Flexible Image Transport System)",
        "reference_url": "https://fits.gsfc.nasa.gov/fits_standard.html",
        "secondary_url": "https://docs.astropy.org/en/stable/io/fits/",
        "secondary_label": "astropy.io.fits documentation",
        "covered": [
            "Header cards: telescope, instrument, object, observation date, "
            "exposure time, filter, dimensions.",
            "WCS (World Coordinate System): reference value/pixel, pixel scale, "
            "coordinate type, reference frame, equinox.",
        ],
        "not_covered": [
            "Extension HDUs beyond the primary header (e.g. multi-extension "
            "FITS with per-extension WCS) are not currently parsed.",
        ],
    },
}


def get_standard_info(context_name):
    """Returns the standards registry entry for a context, or None."""
    return STANDARDS_REGISTRY.get(context_name)


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
