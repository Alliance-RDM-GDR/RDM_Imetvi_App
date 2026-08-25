# standardizers/lif_microscopy_standardizer.py
#
# Maps raw LIF metadata → REMBI-aligned standardized fields.
# Uses the first series' top-level keys (flattened by lif_parser).
# SeriesList is preserved for JSON export and multi-series display.


def standardize_lif_microscopy_metadata(raw_metadata):
    std = {}

    std["FilePath"]     = raw_metadata.get("FilePath", "")
    std["ImageName"]    = raw_metadata.get("Name", "")
    std["SeriesCount"]  = str(raw_metadata.get("SeriesCount", ""))
    std["FileSizeMB"]   = str(raw_metadata.get("FileSizeMB", ""))

    # Dimensions
    std["DimensionX"]   = str(raw_metadata.get("SizeX", ""))
    std["DimensionY"]   = str(raw_metadata.get("SizeY", ""))
    std["SizeZ"]        = str(raw_metadata.get("SizeZ", ""))
    std["SizeT"]        = str(raw_metadata.get("SizeT", ""))
    std["NumChannels"]  = str(raw_metadata.get("NumChannels", ""))

    # Pixel size
    px_x = raw_metadata.get("PixelSizeX_um")
    px_y = raw_metadata.get("PixelSizeY_um")
    px_z = raw_metadata.get("PixelSizeZ_um")
    std["PixelSizeX"]   = str(px_x) if px_x is not None else ""
    std["PixelSizeY"]   = str(px_y) if px_y is not None else ""
    std["PixelSizeZ"]   = str(px_z) if px_z is not None else ""

    # Bit depth
    std["BitDepth"]     = str(raw_metadata.get("BitDepth", ""))

    # Objective / optics
    std["NA"]           = str(raw_metadata.get("NA", "") or "")
    std["Magnification"]= str(raw_metadata.get("Magnification", "") or "")
    std["Objective"]    = str(raw_metadata.get("Objective", "") or "")
    std["Zoom"]         = str(raw_metadata.get("Zoom", "") or "")
    std["PinholeSize"]  = str(raw_metadata.get("PinholeSize", "") or "")

    # Mosaic
    if raw_metadata.get("IsMosaic"):
        std["MosaicTiles"] = str(raw_metadata.get("MosaicTiles", ""))

    # Full series list preserved for multi-series LIF files
    all_series = raw_metadata.get("SeriesList", [])
    if all_series:
        std["SeriesList"] = all_series

    return std
