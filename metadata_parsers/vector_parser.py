# metadata_parsers/vector_parser.py
#
# Reader for vector GIS data: ESRI Shapefile (.shp with its .shx, .dbf, .prj,
# .cpg companions) and GeoJSON (.geojson). Shapefile files are decoded from
# their fixed binary headers (no GIS library needed, geometry is never read);
# GeoJSON is parsed with the standard library up to a size limit.

import json
import os
import re
import struct
from collections import Counter

VECTOR_EXTENSIONS = [".shp", ".geojson"]

MAX_GEOJSON_BYTES = 128 << 20

SHAPE_TYPES = {
    0: "Null", 1: "Point", 3: "PolyLine", 5: "Polygon", 8: "MultiPoint",
    11: "PointZ", 13: "PolyLineZ", 15: "PolygonZ", 18: "MultiPointZ",
    21: "PointM", 23: "PolyLineM", 25: "PolygonM", 28: "MultiPointM", 31: "MultiPatch",
}
_HAS_Z = {11, 13, 15, 18, 31}
_HAS_M = {11, 13, 15, 18, 21, 23, 25, 28, 31}
DBF_TYPES = {"C": "text", "N": "number", "F": "float", "D": "date", "L": "logical", "M": "memo",
             "I": "integer", "O": "double", "T": "datetime", "@": "timestamp", "+": "autoincrement"}
_SIDECARS = [".sbn", ".sbx", ".qix", ".shp.xml", ".xml", ".qpj", ".cpg", ".prj"]


def _ci_find(names, wanted):
    low = wanted.lower()
    return next((n for n in names if n.lower() == low), "")


def read_shp_header(file_path):
    """Parses the 100-byte .shp main header. Raises ValueError if it is not a shapefile."""
    size = os.path.getsize(file_path)
    with open(file_path, "rb") as f:
        b = f.read(100)
    if len(b) < 100 or struct.unpack(">i", b[:4])[0] != 9994:
        raise ValueError("not a shapefile (file code 9994 missing)")
    length_words = struct.unpack(">i", b[24:28])[0]
    version, shape_type = struct.unpack("<2i", b[28:36])
    xmin, ymin, xmax, ymax, zmin, zmax, mmin, mmax = struct.unpack("<8d", b[36:100])
    out = {
        "ShapeTypeCode": shape_type, "ShapeType": SHAPE_TYPES.get(shape_type, f"unknown ({shape_type})"),
        "Version": version, "DeclaredBytes": length_words * 2, "FileSize": size,
        "BBox": [xmin, ymin, xmax, ymax],
        "Truncated": size < length_words * 2,
    }
    if shape_type in _HAS_Z:
        out["ZRange"] = [zmin, zmax]
    if shape_type in _HAS_M:
        out["MRange"] = [mmin, mmax]
    return out


def read_shx_count(file_path):
    """Number of records an .shx index declares (its size minus the 100-byte header, over 8)."""
    return max(0, (os.path.getsize(file_path) - 100) // 8)


def read_dbf_header(file_path):
    """Reads the dBase header and field descriptors of a shapefile's .dbf (no records)."""
    with open(file_path, "rb") as f:
        head = f.read(32)
        if len(head) < 32:
            raise ValueError(".dbf is shorter than its 32-byte header")
        records = struct.unpack("<I", head[4:8])[0]
        header_len, record_len = struct.unpack("<2H", head[8:12])
        fields = []
        while True:
            d = f.read(32)
            if len(d) < 32 or d[0] == 0x0D:
                break
            name = d[:11].split(b"\x00")[0].decode("latin-1")
            ftype = chr(d[11])
            fields.append({"Name": name, "Type": ftype, "TypeName": DBF_TYPES.get(ftype, ftype),
                           "Length": d[16], "Decimals": d[17]})
            if len(fields) > 2000:
                break
    year, month, day = head[1], head[2], head[3]
    return {
        "Version": head[0], "Records": records, "HeaderBytes": header_len, "RecordBytes": record_len,
        "LastUpdate": f"{1900 + year:04d}-{month:02d}-{day:02d}" if 1 <= month <= 12 and 1 <= day <= 31 else "",
        "LanguageDriver": head[29], "Fields": fields,
        "Truncated": os.path.getsize(file_path) < header_len + records * record_len,
    }


def describe_wkt(wkt):
    """CRS name, kind (geographic/projected), unit and EPSG code (when rasterio can match it) from a WKT string."""
    wkt = (wkt or "").strip()
    if not wkt:
        return {"Name": "", "Kind": "", "Unit": "", "EPSG": None}
    name = re.match(r'\s*\w+\["([^"]*)"', wkt)
    kind = "projected" if re.match(r"\s*(PROJCS|PROJCRS|PROJECTEDCRS)", wkt, re.I) else (
        "geographic" if re.match(r"\s*(GEOGCS|GEOGCRS|GEOGRAPHICCRS)", wkt, re.I) else "")
    units = re.findall(r'(?:UNIT|LENGTHUNIT|ANGLEUNIT)\["([^"]+)"', wkt, re.I)
    epsg = None
    try:
        from rasterio.crs import CRS
        epsg = CRS.from_wkt(wkt).to_epsg()
    except Exception:
        pass
    return {"Name": name.group(1) if name else "", "Kind": kind, "Unit": units[-1] if units else "", "EPSG": epsg}


def _walk_positions(coords, acc):
    """Accumulates min/max per axis and a position count over arbitrarily nested GeoJSON coordinates."""
    if not coords:
        return
    if isinstance(coords[0], (int, float)):
        if len(coords) >= 2:
            acc["n"] += 1
            for i in range(min(len(coords), 3)):
                v = coords[i]
                if acc["min"][i] is None or v < acc["min"][i]:
                    acc["min"][i] = v
                if acc["max"][i] is None or v > acc["max"][i]:
                    acc["max"][i] = v
            if len(coords) > 2:
                acc["z"] = True
        return
    for c in coords:
        if isinstance(c, list):
            _walk_positions(c, acc)


def _geometries(geom):
    if not isinstance(geom, dict):
        return
    if geom.get("type") == "GeometryCollection":
        for g in geom.get("geometries") or []:
            yield from _geometries(g)
    else:
        yield geom


def read_geojson(file_path):
    """Parses a GeoJSON file into a summary: type, CRS member, geometry types, bbox and attribute table schema."""
    size = os.path.getsize(file_path)
    out = {"FileSize": size}
    if size > MAX_GEOJSON_BYTES:
        out["TooLarge"] = True
        return out
    with open(file_path, "rb") as f:
        blob = f.read()
    text = blob.decode("utf-8-sig", errors="replace")
    data = json.loads(text)
    if not isinstance(data, dict) or "type" not in data:
        raise ValueError("not a GeoJSON object")
    out["Type"] = data["type"]
    out["Name"] = data.get("name", "") if isinstance(data.get("name"), str) else ""
    crs = data.get("crs")
    out["CrsMember"] = ((crs or {}).get("properties") or {}).get("name", "") if isinstance(crs, dict) else ""
    out["HasBBoxMember"] = "bbox" in data

    if data["type"] == "FeatureCollection":
        features = [x for x in data.get("features") or [] if isinstance(x, dict)]
    elif data["type"] == "Feature":
        features = [data]
    else:
        features = [{"type": "Feature", "geometry": data, "properties": None}]
    out["FeatureCount"] = len(features)

    geom_types, prop_types, prop_nulls = Counter(), {}, Counter()
    acc = {"n": 0, "min": [None] * 3, "max": [None] * 3, "z": False}
    empty = 0
    id_count = 0
    for ft in features:
        if "id" in ft:
            id_count += 1
        geoms = list(_geometries(ft.get("geometry")))
        if not geoms:
            empty += 1
        for g in geoms:
            geom_types[g.get("type", "?")] += 1
            _walk_positions(g.get("coordinates") or [], acc)
        props = ft.get("properties")
        if isinstance(props, dict):
            for k, v in props.items():
                t = ("null" if v is None else "boolean" if isinstance(v, bool) else
                     "number" if isinstance(v, (int, float)) else "string" if isinstance(v, str) else "object")
                prop_types.setdefault(k, set()).add(t)
                if v is None:
                    prop_nulls[k] += 1
    out.update({
        "GeometryTypes": dict(geom_types), "EmptyGeometries": empty, "PositionCount": acc["n"],
        "HasZ": acc["z"], "FeaturesWithId": id_count,
        "Properties": {k: sorted(v) for k, v in prop_types.items()}, "PropertyNulls": dict(prop_nulls),
    })
    if acc["n"]:
        out["BBox"] = [acc["min"][0], acc["min"][1], acc["max"][0], acc["max"][1]]
    # decimals written for the first coordinates (a GPS fix is ~1e-6 deg, 15 decimals is false precision)
    decimals = [len(m) for m in re.findall(r"-?\d+\.(\d+)", text[:200000])]
    out["MaxDecimals"] = max(decimals) if decimals else 0
    return out


def _within_lonlat(bbox):
    return bool(bbox) and -180.0 <= bbox[0] <= 180.0 and -180.0 <= bbox[2] <= 180.0 \
        and -90.0 <= bbox[1] <= 90.0 and -90.0 <= bbox[3] <= 90.0


def parse_vector_metadata(file_path, application=None):
    """
    Reads a shapefile (.shp plus companions) or a GeoJSON file. Returns
    (text_report, raw_metadata) per the parser contract; a read failure is
    reported in the text and never raised.
    """
    fname = os.path.basename(file_path)
    ext = os.path.splitext(fname)[1].lower()
    stem = os.path.splitext(fname)[0]
    dirpath = os.path.dirname(os.path.abspath(file_path))
    text = [f"Vector GIS Metadata Report for {fname}"]
    raw = {"FilePath": file_path, "Kind": "GeoJSON" if ext == ".geojson" else "Shapefile"}
    try:
        names = os.listdir(dirpath)
    except OSError:
        names = []

    try:
        if raw["Kind"] == "Shapefile":
            raw["SHP"] = read_shp_header(file_path)
            comp = {e: _ci_find(names, stem + e) for e in (".shx", ".dbf", ".prj", ".cpg")}
            raw["Companions"] = comp
            raw["Sidecars"] = [n for e in (".sbn", ".sbx", ".qix", ".shp.xml") for n in [_ci_find(names, stem + e)] if n]
            if comp[".shx"]:
                raw["ShxRecords"] = read_shx_count(os.path.join(dirpath, comp[".shx"]))
            if comp[".dbf"]:
                try:
                    raw["DBF"] = read_dbf_header(os.path.join(dirpath, comp[".dbf"]))
                except Exception as e:
                    raw["DBFError"] = str(e)
            if comp[".prj"]:
                with open(os.path.join(dirpath, comp[".prj"]), "r", encoding="utf-8", errors="replace") as f:
                    raw["PrjWKT"] = f.read(20000).strip()
                raw["CRS"] = describe_wkt(raw["PrjWKT"])
            if comp[".cpg"]:
                with open(os.path.join(dirpath, comp[".cpg"]), "r", encoding="ascii", errors="replace") as f:
                    raw["Encoding"] = f.read(64).strip()
            twin = _ci_find(names, stem + ".geojson")
            if twin:
                raw["TwinFile"] = twin
                try:
                    raw["Twin"] = read_geojson(os.path.join(dirpath, twin))
                except Exception:
                    pass
        else:
            raw["GeoJSON"] = read_geojson(file_path)
            twin = _ci_find(names, stem + ".shp")
            if twin:
                raw["TwinFile"] = twin
                try:
                    raw["Twin"] = read_shp_header(os.path.join(dirpath, twin))
                except Exception:
                    pass
    except Exception as e:
        text.append(f"Failed to read {raw['Kind']} file: {e}")
        return "\n".join(text), raw

    if raw["Kind"] == "Shapefile":
        h = raw["SHP"]
        text.append(f"Shapefile: {h['ShapeType']} geometry, {raw.get('ShxRecords', '?')} record(s) per .shx, "
                    f"{h['FileSize']:,} bytes")
        text.append("Extent: " + ", ".join(f"{v:.6g}" for v in h["BBox"]))
        if h["Truncated"]:
            text.append("WARNING: .shp is smaller than its header declares (incomplete copy?).")
        crs = raw.get("CRS")
        text.append("CRS: " + (f"{crs['Name']} ({crs['Kind'] or 'unknown kind'}"
                               + (f", EPSG:{crs['EPSG']}" if crs["EPSG"] else "") + ")" if crs else ".prj missing"))
        dbf = raw.get("DBF")
        if dbf:
            text.append(f"Attributes: {dbf['Records']} record(s), {len(dbf['Fields'])} field(s): "
                        + ", ".join(f["Name"] for f in dbf["Fields"][:12]))
        else:
            text.append("Attributes: .dbf " + ("unreadable" if raw.get("DBFError") else "missing"))
        text.append("Companions: " + (", ".join(v for v in raw["Companions"].values() if v) or "none")
                    + (f" | encoding {raw['Encoding']}" if raw.get("Encoding") else ""))
    else:
        g = raw["GeoJSON"]
        if g.get("TooLarge"):
            text.append(f"GeoJSON is {g['FileSize']:,} bytes: too large to parse here, only the size is reported.")
        else:
            text.append(f"GeoJSON {g['Type']}: {g['FeatureCount']} feature(s), geometry "
                        + (", ".join(f"{k} x{v}" for k, v in g["GeometryTypes"].items()) or "none")
                        + f", {g['PositionCount']:,} positions")
            if g.get("BBox"):
                text.append("Extent: " + ", ".join(f"{v:.6g}" for v in g["BBox"][:4]))
            text.append("CRS: " + (g["CrsMember"] or "none declared (GeoJSON default WGS 84)"))
            text.append("Properties: " + (", ".join(g["Properties"]) or "none"))
    if raw.get("TwinFile"):
        text.append(f"Same-name file: {raw['TwinFile']}")
    return "\n".join(text), raw
