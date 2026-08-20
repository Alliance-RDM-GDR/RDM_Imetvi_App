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

    return dict_report
