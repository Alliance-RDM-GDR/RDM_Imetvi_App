# standardizers/vector_standardizer.py
#
# Maps raw shapefile / GeoJSON output to ISO 19115-aligned fields (reference
# system, geographic extent, spatial representation type, attribute
# description) using the same key names as the other geospatial contexts
# (CRS_EPSG, CRS_WKT, BoundingBox_*), and attaches suggestions (_Suggestions)
# for what a curator would still have to supply.

import os

from metadata_parsers.vector_parser import _within_lonlat

_STD = "ISO 19115 / ESRI Shapefile / GeoJSON (RFC 7946)"

# Decimal places beyond which a lon/lat coordinate claims sub-millimetre
# precision (1e-9 degree is ~0.1 mm): usually an artefact of floating-point output.
FALSE_PRECISION_DECIMALS = 9
_BBOX_TOLERANCE = 1e-6
_WGS84_NAMES = ("crs84", "epsg:4326", "epsg::4326", "4326")


def _s(code, en, fr, flag=None):
    return {"Code": code, "Standard": _STD, "Message": en, "Message_fr": fr, "Flag": flag}


def _is_wgs84_member(name):
    return any(t in (name or "").lower() for t in _WGS84_NAMES)


def _wgs84_wkt():
    try:
        from rasterio.crs import CRS
        return CRS.from_epsg(4326).to_wkt()
    except Exception:
        return 'GEOGCS["WGS 84"]'


def _bbox_differs(a, b):
    return any(abs(x - y) > _BBOX_TOLERANCE * max(1.0, abs(x), abs(y)) for x, y in zip(a[:4], b[:4]))


def _suggestions(raw, std):
    s = []
    kind = raw.get("Kind")
    stem = os.path.splitext(os.path.basename(raw.get("FilePath", "")))[0]
    bbox = [std.get(k) for k in ("BoundingBox_MinX", "BoundingBox_MinY", "BoundingBox_MaxX", "BoundingBox_MaxY")]

    if kind == "Shapefile":
        comp = raw.get("Companions") or {}
        missing = [e for e in (".shx", ".dbf") if not comp.get(e)]
        if missing:
            s.append(_s(
                "VECTOR_SHP_INCOMPLETE",
                f"The shapefile is missing its {' and '.join(missing)} file(s). A shapefile needs .shp, "
                ".shx and .dbf together; GIS software cannot open it without them.",
                f"Il manque {' et '.join(missing)} au shapefile. Un shapefile exige .shp, .shx et .dbf "
                "ensemble ; les logiciels SIG ne peuvent pas l'ouvrir sans eux.", "SHAPEFILE_INCOMPLETE"))
        if raw["SHP"]["Truncated"] or (raw.get("DBF") or {}).get("Truncated"):
            s.append(_s(
                "VECTOR_TRUNCATED",
                "The .shp or .dbf is smaller than its header declares: the copy is probably incomplete. "
                "Re-transfer it and compare checksums.",
                "Le .shp ou le .dbf est plus petit que ce que déclare son en-tête : la copie est "
                "probablement incomplète. Retransférez-la et comparez les sommes de contrôle.",
                "SHAPEFILE_TRUNCATED"))
        dbf = raw.get("DBF")
        if dbf and "ShxRecords" in raw and raw["ShxRecords"] != dbf["Records"]:
            s.append(_s(
                "VECTOR_COUNT_MISMATCH",
                f"The .shx indexes {raw['ShxRecords']} geometries but the .dbf holds {dbf['Records']} "
                "attribute rows: the files do not belong together or one was edited on its own.",
                f"Le .shx indexe {raw['ShxRecords']} géométries mais le .dbf contient {dbf['Records']} "
                "lignes d'attributs : les fichiers ne vont pas ensemble ou l'un a été modifié seul.",
                "VECTOR_COUNT_MISMATCH"))
        if not comp.get(".prj"):
            s.append(_s(
                "VECTOR_NO_PRJ",
                "No .prj file: the coordinate reference system is unknown, so the coordinates cannot be "
                "placed on a map reliably. Add the .prj (ISO 19115: referenceSystemInfo).",
                "Aucun fichier .prj : le système de référence est inconnu, donc les coordonnées ne "
                "peuvent pas être placées de façon fiable sur une carte. Ajoutez le .prj "
                "(ISO 19115 : referenceSystemInfo)."))
        elif not std.get("CRS_EPSG"):
            s.append(_s(
                "VECTOR_NO_EPSG",
                "The .prj does not match any EPSG code. Record the CRS as an EPSG code (or its full "
                "definition) in the README so it can be identified unambiguously.",
                "Le .prj ne correspond à aucun code EPSG. Consignez le SCR sous forme de code EPSG "
                "(ou de sa définition complète) dans le README afin de pouvoir l'identifier sans ambiguïté."))
        if dbf and not comp.get(".cpg") and dbf["LanguageDriver"] == 0:
            s.append(_s(
                "VECTOR_NO_CPG",
                "No .cpg file and no language driver in the .dbf: the text encoding of the attributes is "
                "not stated and accents may be misread. Add a .cpg (for example UTF-8).",
                "Aucun fichier .cpg ni pilote de langue dans le .dbf : l'encodage des attributs n'est pas "
                "indiqué et les accents peuvent être mal lus. Ajoutez un .cpg (par exemple UTF-8)."))
        if dbf and any(len(f["Name"]) >= 10 for f in dbf["Fields"]):
            s.append(_s(
                "VECTOR_FIELD_NAMES_TRUNCATED",
                "Some attribute names use all 10 characters of the .dbf limit and may have been "
                "truncated. Document the full names in a data dictionary.",
                "Certains noms d'attributs utilisent les 10 caractères permis par le .dbf et ont peut-être "
                "été tronqués. Documentez les noms complets dans un dictionnaire de données."))
        if not raw.get("Sidecars") or not any(n.lower().endswith(".shp.xml") for n in raw["Sidecars"]):
            s.append(_s(
                "VECTOR_NO_ISO_METADATA",
                "No .shp.xml metadata record. A shapefile cannot hold title, abstract, lineage, "
                "contact or licence: provide an ISO 19115 record or describe them in the README.",
                "Aucune fiche de métadonnées .shp.xml. Un shapefile ne peut pas contenir de titre, de "
                "résumé, de généalogie, de contact ni de licence : fournissez une fiche ISO 19115 ou "
                "décrivez-les dans le README."))
    else:
        g = raw["GeoJSON"]
        if g.get("TooLarge"):
            return s
        member = g.get("CrsMember", "")
        if member:
            s.append(_s(
                "GEOJSON_LEGACY_CRS",
                f"The file declares a 'crs' member ({member}). RFC 7946 removed it and requires "
                "WGS 84 longitude/latitude: remove it if the data is WGS 84, otherwise reproject.",
                f"Le fichier déclare un membre « crs » ({member}). La RFC 7946 l'a supprimé et exige "
                "des longitudes/latitudes WGS 84 : retirez-le si les données sont en WGS 84, sinon reprojetez."))
        wgs84 = not member or _is_wgs84_member(member)
        if wgs84 and g.get("BBox") and not _within_lonlat(g["BBox"]):
            s.append(_s(
                "GEOJSON_COORDS_OUT_OF_RANGE",
                "The coordinates fall outside longitude/latitude range although the file is WGS 84 "
                "(or declares no CRS): they are probably projected. Reproject before sharing.",
                "Les coordonnées sortent de la plage longitude/latitude alors que le fichier est en WGS 84 "
                "(ou ne déclare aucun SCR) : elles sont probablement projetées. Reprojetez avant de partager.",
                "VECTOR_COORDS_OUT_OF_RANGE"))
        if g.get("MaxDecimals", 0) > FALSE_PRECISION_DECIMALS:
            s.append(_s(
                "VECTOR_FALSE_PRECISION",
                f"Coordinates are written with up to {g['MaxDecimals']} decimals, implying sub-millimetre "
                "precision the data does not have. Rounding to 6-7 decimals (~10 cm) shrinks the file.",
                f"Les coordonnées sont écrites avec jusqu'à {g['MaxDecimals']} décimales, ce qui laisse "
                "croire à une précision submillimétrique que les données n'ont pas. Arrondir à 6-7 décimales "
                "(~10 cm) réduit la taille du fichier."))
        if g.get("EmptyGeometries"):
            s.append(_s(
                "VECTOR_EMPTY_GEOMETRY",
                f"{g['EmptyGeometries']} feature(s) have no geometry.",
                f"{g['EmptyGeometries']} entité(s) n'ont aucune géométrie."))
        if g.get("Name") and g["Name"].lower() != stem.lower():
            s.append(_s(
                "VECTOR_NAME_MISMATCH",
                f"The layer name inside the file ('{g['Name']}') differs from the file name ('{stem}'). "
                "Check that the file is the one described, especially if the name carries a size or date.",
                f"Le nom de couche dans le fichier (« {g['Name']} ») diffère du nom du fichier (« {stem} »). "
                "Vérifiez qu'il s'agit bien du fichier décrit, surtout si le nom contient une taille ou une date."))
        s.append(_s(
            "VECTOR_NO_ISO_METADATA",
            "GeoJSON has no place for title, abstract, lineage, contact or licence. Provide an ISO 19115 "
            "record or describe them in the README.",
            "GeoJSON n'a aucun emplacement pour le titre, le résumé, la généalogie, le contact ou la licence. "
            "Fournissez une fiche ISO 19115 ou décrivez-les dans le README."))

    twin = raw.get("Twin")
    if twin and isinstance(bbox[0], (int, float)) and twin.get("BBox") and _bbox_differs(bbox, twin["BBox"]):
        s.append(_s(
            "VECTOR_TWIN_MISMATCH",
            f"{raw['TwinFile']} has the same name but a different extent: the two versions of this layer "
            "do not match. Say which one is authoritative.",
            f"{raw['TwinFile']} porte le même nom mais couvre une étendue différente : les deux versions de "
            "cette couche ne concordent pas. Indiquez laquelle fait foi.", "VECTOR_TWIN_MISMATCH"))
    return s


def standardize_vector_metadata(raw_metadata):
    raw = raw_metadata
    name = os.path.basename(raw.get("FilePath", ""))
    if raw.get("Kind") == "Shapefile" and "SHP" in raw:
        h, crs = raw["SHP"], raw.get("CRS") or {}
        dbf = raw.get("DBF") or {}
        fields = dbf.get("Fields") or []
        d = {
            "ImageName": name, "DataFormat": "ESRI Shapefile", "GeometryType": h["ShapeType"],
            "FeatureCount": raw.get("ShxRecords", ""),
            "CRS_EPSG": crs.get("EPSG") or "", "CRS_WKT": raw.get("PrjWKT", ""),
            "CRS_Name": crs.get("Name", ""), "CRS_Kind": crs.get("Kind", ""), "CRS_Unit": crs.get("Unit", ""),
            "BoundingBox_MinX": h["BBox"][0], "BoundingBox_MinY": h["BBox"][1],
            "BoundingBox_MaxX": h["BBox"][2], "BoundingBox_MaxY": h["BBox"][3],
            "HasZ": "yes" if "ZRange" in h else "no", "HasM": "yes" if "MRange" in h else "no",
            "AttributeFieldCount": len(fields) if dbf else "",
            "AttributeFields": ", ".join(f"{f['Name']} ({f['TypeName']} {f['Length']})" for f in fields),
            "CharacterEncoding": raw.get("Encoding", ""),
            "LastUpdate": dbf.get("LastUpdate", ""),
            "CompanionFiles": ", ".join(v for v in (raw.get("Companions") or {}).values() if v),
            "MetadataRecord": next((n for n in raw.get("Sidecars") or [] if n.lower().endswith(".shp.xml")), ""),
            "SameNameFile": raw.get("TwinFile", ""),
        }
    elif raw.get("Kind") == "GeoJSON" and "GeoJSON" in raw and not raw["GeoJSON"].get("TooLarge"):
        g = raw["GeoJSON"]
        bbox = g.get("BBox") or [None] * 4
        member = g.get("CrsMember", "")
        wgs84 = not member or _is_wgs84_member(member)
        types = g.get("GeometryTypes") or {}
        props = g.get("Properties") or {}
        d = {
            "ImageName": name, "DataFormat": "GeoJSON", "LayerName": g.get("Name", ""),
            "GeometryType": ", ".join(sorted(types)), "FeatureCount": g["FeatureCount"],
            "CRS_EPSG": 4326 if wgs84 else "",
            "CRS_WKT": _wgs84_wkt() if wgs84 else member,
            "CRS_Name": member or "WGS 84 (GeoJSON default)",
            "CRS_Kind": "geographic" if wgs84 else "",
            "CRS_Unit": "degree" if wgs84 else "",
            "BoundingBox_MinX": bbox[0] if bbox[0] is not None else "",
            "BoundingBox_MinY": bbox[1] if bbox[1] is not None else "",
            "BoundingBox_MaxX": bbox[2] if bbox[2] is not None else "",
            "BoundingBox_MaxY": bbox[3] if bbox[3] is not None else "",
            "HasZ": "yes" if g.get("HasZ") else "no",
            "AttributeFieldCount": len(props),
            "AttributeFields": ", ".join(f"{k} ({'/'.join(v)})" for k, v in props.items()),
            "CoordinateDecimals": g.get("MaxDecimals", ""),
            "SameNameFile": raw.get("TwinFile", ""),
        }
    else:
        return {"ImageName": name, "DataFormat": raw.get("Kind", "")}
    d["_Suggestions"] = _suggestions(raw, d)
    return d
