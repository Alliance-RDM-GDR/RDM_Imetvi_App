# standardizers/jpg_general_standardizer.py

import os


def _gps_to_decimal(gps_ifd):
    """Converts piexif GPS IFD dict to decimal lat/lon strings, if present."""
    try:
        lat_dms = gps_ifd.get(2)
        lat_ref = gps_ifd.get(1)
        lon_dms = gps_ifd.get(4)
        lon_ref = gps_ifd.get(3)
        if not (lat_dms and lon_dms):
            return "", ""

        def dms_to_decimal(dms):
            d, m, s = dms
            return d[0] / d[1] + (m[0] / m[1]) / 60 + (s[0] / s[1]) / 3600

        lat = dms_to_decimal(lat_dms)
        lon = dms_to_decimal(lon_dms)

        if isinstance(lat_ref, bytes):
            lat_ref = lat_ref.decode(errors="replace")
        if isinstance(lon_ref, bytes):
            lon_ref = lon_ref.decode(errors="replace")

        if lat_ref == "S":
            lat = -lat
        if lon_ref == "W":
            lon = -lon

        return str(lat), str(lon)
    except Exception:
        return "", ""


def standardize_jpg_general_metadata(raw_metadata):
    """
    Standardizes raw JPG/EXIF metadata into a general-purpose dictionary
    aligned with EXIF/IPTC conventions.
    """

    file_path = raw_metadata.get("FilePath", "")

    px_size_x = ""
    px_size_y = ""
    if isinstance(raw_metadata.get("XResolution"), tuple):
        ratio = raw_metadata["XResolution"]
        try:
            px_size_x = str(ratio[0] / ratio[1]) if ratio[1] else ""
        except Exception:
            pass
    if isinstance(raw_metadata.get("YResolution"), tuple):
        ratio = raw_metadata["YResolution"]
        try:
            px_size_y = str(ratio[0] / ratio[1]) if ratio[1] else ""
        except Exception:
            pass

    gps_lat, gps_lon = "", ""
    gps_info = raw_metadata.get("GPSInfo")
    if isinstance(gps_info, dict):
        gps_lat, gps_lon = _gps_to_decimal(gps_info)

    keywords = raw_metadata.get("IPTC_keywords", [])
    if isinstance(keywords, list):
        keywords = ", ".join(keywords)

    dict_report = {
        "ImageName": os.path.basename(file_path),
        "AcquisitionDate": raw_metadata.get("DateTimeOriginal", ""),
        "DimensionX": str(raw_metadata.get("ImageWidth", "")),
        "DimensionY": str(raw_metadata.get("ImageLength", "")),
        "CameraMake": raw_metadata.get("Make", ""),
        "CameraModel": raw_metadata.get("Model", ""),
        "Software": raw_metadata.get("Software", ""),
        "Artist": raw_metadata.get("Artist", ""),
        "Copyright": raw_metadata.get("Copyright", ""),
        "Description": raw_metadata.get("ImageDescription", ""),
        "ResolutionX": px_size_x,
        "ResolutionY": px_size_y,
        "GPSLatitude": gps_lat,
        "GPSLongitude": gps_lon,
        # IPTC IIM — provenance and descriptive context (SSH research)
        "Caption": raw_metadata.get("IPTC_caption_abstract", ""),
        "Keywords": keywords,
        "Byline": raw_metadata.get("IPTC_by-line", ""),
        "BylineTitle": raw_metadata.get("IPTC_by-line_title", ""),
        "Credit": raw_metadata.get("IPTC_credit", ""),
        "Source": raw_metadata.get("IPTC_source", ""),
        "IPTCCopyrightNotice": raw_metadata.get("IPTC_copyright_notice", ""),
        "City": raw_metadata.get("IPTC_city", ""),
        "ProvinceState": raw_metadata.get("IPTC_province_state", ""),
        "Country": raw_metadata.get("IPTC_country_primary_location_name", ""),
        "ObjectName": raw_metadata.get("IPTC_object_name", ""),
        "SpecialInstructions": raw_metadata.get("IPTC_special_instructions", ""),
        # XMP — rights and subject keywords
        "XMPUsageTerms": raw_metadata.get("XMP_Rights_UsageTerms", ""),
        "XMPRights": raw_metadata.get("XMP_DC_Rights", ""),
        "XMPSubject": raw_metadata.get("XMP_DC_Subject", ""),
    }

    return dict_report
