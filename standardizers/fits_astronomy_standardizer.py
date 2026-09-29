# standardizers/fits_astronomy_standardizer.py

import os


def standardize_fits_astronomy_metadata(raw_metadata):
    """
    Standardizes raw FITS header metadata into an astronomy-specific
    dictionary, surfacing the WCS (World Coordinate System) fields that
    play the same role as CRS/bounding box does for GeoTIFF.
    """

    file_path = raw_metadata.get("FilePath", "")

    dict_report = {
        "ImageName": os.path.basename(file_path),
        "Telescope": str(raw_metadata.get("TELESCOP", "")),
        "Instrument": str(raw_metadata.get("INSTRUME", "")),
        "Object": str(raw_metadata.get("OBJECT", "")),
        "ObservationDate": str(raw_metadata.get("DATE-OBS", "")),
        "ExposureTime": str(raw_metadata.get("EXPTIME", "")),
        "Filter": str(raw_metadata.get("FILTER", "")),
        "BitsPerPixel": str(raw_metadata.get("BITPIX", "")),
        "DimensionX": str(raw_metadata.get("NAXIS1", "")),
        "DimensionY": str(raw_metadata.get("NAXIS2", "")),
        "WCS_CTYPE1": str(raw_metadata.get("CTYPE1", "")),
        "WCS_CTYPE2": str(raw_metadata.get("CTYPE2", "")),
        "WCS_RefValueX": str(raw_metadata.get("CRVAL1", "")),
        "WCS_RefValueY": str(raw_metadata.get("CRVAL2", "")),
        "WCS_RefPixelX": str(raw_metadata.get("CRPIX1", "")),
        "WCS_RefPixelY": str(raw_metadata.get("CRPIX2", "")),
        "WCS_PixelScaleX": str(raw_metadata.get("CDELT1", "")),
        "WCS_PixelScaleY": str(raw_metadata.get("CDELT2", "")),
        "ReferenceFrame": str(raw_metadata.get("RADESYS", "")),
        "Equinox": str(raw_metadata.get("EQUINOX", "")),
    }

    # --- Added fields. Emitted only when the file carries them, so existing
    # consumers of the keys above see no change and files without e.g. a CD
    # matrix don't list empty rows. ---
    def _add(key, value):
        if value is not None and value != "":
            dict_report[key] = str(value)

    _add("Author", raw_metadata.get("AUTHOR"))
    _add("Origin", raw_metadata.get("ORIGIN"))
    _add("Creator", raw_metadata.get("CREATOR"))
    _add("FileCreationDate", raw_metadata.get("DATE"))
    _add("TimeSystem", raw_metadata.get("TIMESYS"))
    _add("ObservationMJD", raw_metadata.get("MJD-OBS"))
    _add("ObservationEndDate", raw_metadata.get("DATE-END"))
    _add("Observer", raw_metadata.get("OBSERVER"))
    _add("ProgramID", raw_metadata.get("PROPOSID"))
    _add("BrightnessUnit", raw_metadata.get("BUNIT"))
    _add("BScale", raw_metadata.get("BSCALE"))
    _add("BZero", raw_metadata.get("BZERO"))
    for key in ("CD1_1", "CD1_2", "CD2_1", "CD2_2", "PC1_1", "PC1_2", "PC2_1", "PC2_2"):
        _add(f"WCS_{key}", raw_metadata.get(key))
    _add("WCS_UnitX", raw_metadata.get("CUNIT1"))
    _add("WCS_UnitY", raw_metadata.get("CUNIT2"))
    _add("WCS_LonPole", raw_metadata.get("LONPOLE"))
    _add("WCS_LatPole", raw_metadata.get("LATPOLE", raw_metadata.get("LATPOL")))

    if "WCSHasCelestial" in raw_metadata:
        dict_report["WCS_Valid"] = "yes" if raw_metadata["WCSHasCelestial"] else "no"
    if "PixelScaleXArcsec" in raw_metadata:
        _add("WCS_PixelScaleXArcsec", f"{raw_metadata['PixelScaleXArcsec']:.6g}")
        _add("WCS_PixelScaleYArcsec", f"{raw_metadata['PixelScaleYArcsec']:.6g}")

    hdus = raw_metadata.get("HDUs")
    if hdus:
        _add("HDUCount", raw_metadata.get("HDUCount"))
        _add("TableCount", raw_metadata.get("TableHDUCount"))
        _add("HDUSummary", "; ".join(_summarize_hdu(h) for h in hdus))
        if raw_metadata.get("IsCompressed"):
            dict_report["Compression"] = raw_metadata.get("CompressionType") or "yes"
    _add("HistoryCardCount", raw_metadata.get("HistoryCardCount") or "")
    _add("CommentCardCount", raw_metadata.get("CommentCardCount") or "")

    return dict_report


def _summarize_hdu(h):
    name = h.get("Name") or "(unnamed)"
    if h["Type"] in ("IMAGE", "COMPRESSED_IMAGE"):
        dims = "x".join(str(n) for n in h.get("Shape", [])) or "empty"
        kind = "compressed image" if h["Type"] == "COMPRESSED_IMAGE" else "image"
        return f"[{h['Index']}] {name}: {kind} {dims}"
    if h["Type"] in ("BINTABLE", "TABLE"):
        return f"[{h['Index']}] {name}: {h['Type'].lower()} {h['Rows']} rows x {h['ColumnCount']} cols"
    return f"[{h['Index']}] {name}: {h['Type']}"
