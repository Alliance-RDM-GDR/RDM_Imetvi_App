# metadata_parsers/lif_parser.py
#
# Extracts metadata from Leica Image File (.lif) containers using readlif.
# A single .lif file can hold multiple image series; each is reported
# as a sub-entry in SeriesList and also flattened as top-level keys
# for the first (or only) series so that the standardizer has direct access.

import os

try:
    from readlif.reader import LifFile
    _READLIF_AVAILABLE = True
except ImportError:
    _READLIF_AVAILABLE = False


def parse_lif_metadata(file_path, application=None):
    text_lines = [f"LIF Metadata Report for {os.path.basename(file_path)}"]
    raw_metadata = {"FilePath": file_path}

    if not _READLIF_AVAILABLE:
        msg = "readlif is not installed. Run: pip install readlif"
        text_lines.append(msg)
        raw_metadata["Error"] = msg
        return "\n".join(text_lines), raw_metadata

    try:
        lif = LifFile(file_path)
        series_list = list(lif.get_iter_image())

        raw_metadata["SeriesCount"] = len(series_list)
        raw_metadata["FileSizeMB"]  = round(os.path.getsize(file_path) / 1024 ** 2, 3)

        text_lines.append(f"Series count: {len(series_list)}")
        text_lines.append(f"File size: {raw_metadata['FileSizeMB']} MB")

        all_series = []
        for idx, img in enumerate(series_list):
            series = _extract_series(img, idx)
            all_series.append(series)

            text_lines.append(f"\n--- Series {idx + 1}: {series['Name']} ---")
            text_lines.append(f"  Dimensions (X×Y×Z×T×M): "
                              f"{series['SizeX']}×{series['SizeY']}×"
                              f"{series['SizeZ']}×{series['SizeT']}×{series['SizeM']}")
            text_lines.append(f"  Channels: {series['NumChannels']}")
            text_lines.append(f"  Bit depth: {series['BitDepth']}")
            text_lines.append(f"  Pixel size X: {series['PixelSizeX_um']} µm")
            text_lines.append(f"  Pixel size Y: {series['PixelSizeY_um']} µm")
            if series.get("PixelSizeZ_um"):
                text_lines.append(f"  Pixel size Z: {series['PixelSizeZ_um']} µm")
            if series.get("NA"):
                text_lines.append(f"  Numerical Aperture: {series['NA']}")
            if series.get("Magnification"):
                text_lines.append(f"  Magnification: {series['Magnification']}×")
            if series.get("IsMosaic"):
                text_lines.append(f"  Mosaic tiles: {series['MosaicTiles']}")

        raw_metadata["SeriesList"] = all_series

        # Flatten the first series to top-level keys so the standardizer
        # can access them directly without iterating SeriesList.
        if all_series:
            for k, v in all_series[0].items():
                raw_metadata[k] = v

    except Exception as e:
        msg = f"Failed to read LIF file: {str(e)}"
        text_lines.append(msg)
        raw_metadata["Error"] = msg

    return "\n".join(text_lines), raw_metadata


def _extract_series(img, idx):
    """Extracts metadata from a single LifImage series into a plain dict."""
    series = {"SeriesIndex": idx, "Name": img.name or f"Series_{idx}"}

    # Dimensions: readlif dims namedtuple has x, y, z, t, m fields
    dims = img.dims
    series["SizeX"]   = getattr(dims, "x", 0)
    series["SizeY"]   = getattr(dims, "y", 0)
    series["SizeZ"]   = getattr(dims, "z", 1)
    series["SizeT"]   = getattr(dims, "t", 1)
    series["SizeM"]   = getattr(dims, "m", 1)
    series["NumChannels"] = int(img.channels)

    # Bit depth — tuple per channel; report first channel's value
    bd = img.bit_depth
    if bd and len(bd) > 0:
        series["BitDepth"] = int(bd[0])
        series["BitDepthAllChannels"] = [int(b) for b in bd]
    else:
        series["BitDepth"] = None

    # Pixel size: scale is px/µm → invert for µm/px
    scale = img.scale  # (scale_x, scale_y, scale_z, scale_t) or None per axis
    def _px_to_um(s):
        try:
            return round(1.0 / float(s), 6) if s and float(s) != 0 else None
        except (TypeError, ValueError, ZeroDivisionError):
            return None

    series["PixelSizeX_um"] = _px_to_um(scale[0]) if scale and len(scale) > 0 else None
    series["PixelSizeY_um"] = _px_to_um(scale[1]) if scale and len(scale) > 1 else None
    series["PixelSizeZ_um"] = _px_to_um(scale[2]) if scale and len(scale) > 2 else None

    # Confocal settings (Leica ATLConfocalSettingDefinition)
    settings = img.settings or {}
    series["NA"]           = settings.get("NumericalAperture")
    series["Magnification"]= settings.get("Magnification")
    series["Objective"]    = settings.get("ObjectiveName") or settings.get("Objective")
    series["Zoom"]         = settings.get("Zoom")
    series["PinholeSize"]  = settings.get("PinholeSize")

    # Mosaic / tile info
    mosaic = img.mosaic_position
    series["IsMosaic"]   = bool(mosaic and len(mosaic) > 0)
    series["MosaicTiles"]= len(mosaic) if mosaic else 0

    return series
