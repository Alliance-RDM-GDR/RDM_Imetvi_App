# utils/wkt_display.py
#
# Formats a CRS WKT string for on-screen display. The raw single-line WKT
# stored in metadata (and used for JSON/CSV export, write-back, etc.) is
# left untouched everywhere else — this only produces a reader-friendly,
# indented version for the UI.

from pyproj import CRS
from pyproj.exceptions import CRSError


def pretty_wkt(wkt):
    """Returns an indented, multi-line version of a WKT string for display.

    Falls back to the original string unchanged if it can't be parsed
    (e.g. a malformed or non-standard WKT variant) rather than raising.
    """
    if not wkt:
        return wkt
    try:
        return CRS.from_wkt(wkt).to_wkt(pretty=True)
    except CRSError:
        return wkt
