# metadata_parsers/fits_parser.py

import os

from astropy.io import fits

_HEADER_KEYS_OF_INTEREST = [
    "TELESCOP", "INSTRUME", "OBJECT", "DATE-OBS", "EXPTIME", "FILTER",
    "BITPIX", "NAXIS1", "NAXIS2",
    "CRVAL1", "CRVAL2", "CRPIX1", "CRPIX2", "CDELT1", "CDELT2",
    "CTYPE1", "CTYPE2", "RADESYS", "EQUINOX",
]


def parse_fits_metadata(file_path, application=None):
    """
    Extracts FITS header metadata using astropy.io.fits.

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

    except Exception as e:
        text_lines.append(f"Failed to read FITS file: {str(e)}")

    return "\n".join(text_lines), raw_metadata
