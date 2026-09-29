# metadata_parsers/fits_parser.py

import os
import warnings

from astropy.io import fits

_HEADER_KEYS_OF_INTEREST = [
    "TELESCOP", "INSTRUME", "OBJECT", "DATE-OBS", "EXPTIME", "FILTER",
    "BITPIX", "NAXIS1", "NAXIS2",
    "CRVAL1", "CRVAL2", "CRPIX1", "CRPIX2", "CDELT1", "CDELT2",
    "CTYPE1", "CTYPE2", "RADESYS", "EQUINOX",
]

# Provenance, time, photometric scaling and WCS keys beyond the original set.
# LATPOLE is the FITS-standard spelling; LATPOL is kept because some writers
# truncate it.
_EXTRA_KEYS_OF_INTEREST = [
    "AUTHOR", "ORIGIN", "CREATOR", "DATE", "TIMESYS", "MJD-OBS", "DATE-END",
    "BUNIT", "BSCALE", "BZERO", "OBSERVER", "PROPOSID",
    "CD1_1", "CD1_2", "CD2_1", "CD2_2",
    "PC1_1", "PC1_2", "PC2_1", "PC2_2",
    "CUNIT1", "CUNIT2", "LONPOLE", "LATPOLE", "LATPOL",
]

_BITPIX_DTYPES = {8: "uint8", 16: "int16", 32: "int32", 64: "int64", -32: "float32", -64: "float64"}
_UNSIGNED_BZERO = {16: (32768, "uint16"), 32: (2147483648, "uint32"), 64: (9223372036854775808, "uint64")}

_MAX_COLUMNS_LISTED = 50  # per table HDU; the full count is always recorded


def _dtype_name(header):
    bitpix = header.get("BITPIX")
    if bitpix in _UNSIGNED_BZERO and header.get("BZERO") == _UNSIGNED_BZERO[bitpix][0] \
            and header.get("BSCALE", 1) == 1:
        return _UNSIGNED_BZERO[bitpix][1]
    return _BITPIX_DTYPES.get(bitpix, "")


def _shape(header, prefix="NAXIS"):
    naxis = header.get(prefix, 0) or 0
    return [header.get(f"{prefix}{i}") for i in range(1, naxis + 1)]


def _describe_hdu(index, hdu):
    """One record per HDU, from header cards only — pixel/table data is never read."""
    header = hdu.header
    entry = {"Index": index, "Name": hdu.name or "", "Version": header.get("EXTVER", 1)}

    if isinstance(hdu, fits.CompImageHDU):
        entry["Type"] = "COMPRESSED_IMAGE"
        entry["Shape"] = _shape(header)              # uncompressed image geometry
        entry["DType"] = _dtype_name(header)
        # astropy presents the header of the *uncompressed* image, so ZCMPTYPE
        # is only there on some versions; the HDU attribute is the reliable source.
        entry["Compression"] = str(getattr(hdu, "compression_type", "") or header.get("ZCMPTYPE", ""))
    elif isinstance(hdu, (fits.PrimaryHDU, fits.ImageHDU)):
        entry["Type"] = "IMAGE"
        entry["Shape"] = _shape(header)
        entry["DType"] = _dtype_name(header)
    elif isinstance(hdu, (fits.BinTableHDU, fits.TableHDU)):
        entry["Type"] = "BINTABLE" if isinstance(hdu, fits.BinTableHDU) else "TABLE"
        entry["Rows"] = header.get("NAXIS2", 0)
        columns = []
        for col in hdu.columns:
            columns.append({"Name": col.name or "", "Format": col.format or "", "Unit": col.unit or ""})
        entry["ColumnCount"] = len(columns)
        entry["Columns"] = columns[:_MAX_COLUMNS_LISTED]
    else:
        entry["Type"] = type(hdu).__name__
    return entry


def _science_index(hdus):
    """
    First HDU holding a 2-D+ image: images often live in an extension behind
    an empty primary (multi-extension and Rice/gzip-compressed FITS), and the
    WCS, BUNIT and dimensions then sit in that extension's header.
    """
    for h in hdus:
        if h["Type"] in ("IMAGE", "COMPRESSED_IMAGE") and len(h.get("Shape", [])) >= 2:
            return h["Index"]
    return None


def _wcs_report(header, raw_metadata, text_lines):
    """Celestial-WCS validity and pixel scale. astropy's WCS raises on malformed headers."""
    try:
        from astropy.wcs import WCS
        from astropy.wcs.utils import proj_plane_pixel_scales

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            wcs = WCS(header)
            celestial = wcs.has_celestial
            raw_metadata["WCSHasCelestial"] = bool(celestial)
            if celestial:
                # wcslib normalizes celestial axes to degrees whatever CUNIT says
                scales = proj_plane_pixel_scales(wcs.celestial) * 3600.0
                raw_metadata["PixelScaleXArcsec"] = float(scales[0])
                raw_metadata["PixelScaleYArcsec"] = float(scales[1])
        if celestial:
            text_lines.append(
                f"Celestial WCS: valid, pixel scale {raw_metadata['PixelScaleXArcsec']:.6g} x "
                f"{raw_metadata['PixelScaleYArcsec']:.6g} arcsec/pixel"
            )
        else:
            text_lines.append("Celestial WCS: none found")
    except Exception as e:
        raw_metadata["WCSHasCelestial"] = False
        raw_metadata["WCSError"] = str(e)
        text_lines.append(f"Celestial WCS: could not be built ({e})")


def parse_fits_metadata(file_path, application=None):
    """
    Extracts FITS metadata using astropy.io.fits: primary-header keys (with
    fallback to the science extension when the primary HDU holds no image),
    an inventory of every HDU, and a celestial-WCS check.

    Returns:
        - text_report: A string report of raw metadata, line by line.
        - raw_metadata: A dictionary with metadata key-value pairs.
    """
    text_lines = [f"FITS Metadata Report for {os.path.basename(file_path)}"]
    raw_metadata = {
        "FilePath": file_path
    }

    try:
        with fits.open(file_path) as hdul:
            header = hdul[0].header

            for key in _HEADER_KEYS_OF_INTEREST:
                if key in header:
                    value = header[key]
                    raw_metadata[key] = value
                    text_lines.append(f"{key}: {value}")

            # --- HDU inventory ---
            try:
                hdus = [_describe_hdu(i, h) for i, h in enumerate(hdul)]
                raw_metadata["HDUCount"] = len(hdus)
                raw_metadata["HDUs"] = hdus
                raw_metadata["TableHDUCount"] = sum(1 for h in hdus if h["Type"] in ("BINTABLE", "TABLE"))
                raw_metadata["IsCompressed"] = any(h["Type"] == "COMPRESSED_IMAGE" for h in hdus)
                sci = _science_index(hdus)
                raw_metadata["ScienceHDUIndex"] = sci
                if raw_metadata["IsCompressed"]:
                    raw_metadata["CompressionType"] = next(
                        h["Compression"] for h in hdus if h["Type"] == "COMPRESSED_IMAGE")

                text_lines.append(f"HDUs: {len(hdus)}")
                for h in hdus:
                    if h["Type"] in ("IMAGE", "COMPRESSED_IMAGE"):
                        dims = "x".join(str(n) for n in h["Shape"]) or "empty"
                        extra = f", {h['DType']}" if h["DType"] else ""
                        extra += f", {h['Compression']}" if h.get("Compression") else ""
                        text_lines.append(f"  [{h['Index']}] {h['Name']} {h['Type']} {dims}{extra}")
                    elif h["Type"] in ("BINTABLE", "TABLE"):
                        cols = ", ".join(
                            c["Name"] + (f" [{c['Unit']}]" if c["Unit"] else "") for c in h["Columns"])
                        more = h["ColumnCount"] - len(h["Columns"])
                        text_lines.append(
                            f"  [{h['Index']}] {h['Name']} {h['Type']} {h['Rows']} rows, "
                            f"{h['ColumnCount']} columns: {cols}" + (f", ... (+{more})" if more > 0 else ""))
                    else:
                        text_lines.append(f"  [{h['Index']}] {h['Name']} {h['Type']}")

                # Keys the primary header lacks come from the science extension;
                # BITPIX/NAXISn describe the image, so an empty primary must not
                # win (its BITPIX 8 / no NAXIS1 would misdescribe the data).
                sci_header = hdul[sci].header if sci not in (None, 0) else header
                if sci not in (None, 0):
                    raw_metadata["KeysFromExtension"] = sci
                    if not header.get("NAXIS"):
                        for key in ("BITPIX", "NAXIS1", "NAXIS2"):
                            if key in sci_header:
                                raw_metadata[key] = sci_header[key]
                    for key in _HEADER_KEYS_OF_INTEREST:
                        if key not in raw_metadata and key in sci_header:
                            raw_metadata[key] = sci_header[key]
                            text_lines.append(f"{key}: {sci_header[key]} (from HDU {sci})")
            except Exception as e:
                sci_header = header
                text_lines.append(f"HDU inventory failed: {str(e)}")

            # --- Additional astronomy keys ---
            for key in _EXTRA_KEYS_OF_INTEREST:
                for h in (header, sci_header):
                    if key in h:
                        raw_metadata[key] = h[key]
                        text_lines.append(f"{key}: {h[key]}")
                        break

            # --- Commentary cards (counted, not stored: they can be huge) ---
            n_history = len(header["HISTORY"]) if "HISTORY" in header else 0
            n_comment = len(header["COMMENT"]) if "COMMENT" in header else 0
            raw_metadata["HistoryCardCount"] = n_history
            raw_metadata["CommentCardCount"] = n_comment
            text_lines.append(f"HISTORY cards: {n_history}   COMMENT cards: {n_comment}")

            # --- WCS ---
            _wcs_report(sci_header, raw_metadata, text_lines)

    except Exception as e:
        text_lines.append(f"Failed to read FITS file: {str(e)}")

    return "\n".join(text_lines), raw_metadata
