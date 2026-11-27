# tests/test_vector_parser.py
#
# Synthetic shapefiles and GeoJSON mirroring FRDR deposit 1811 (a study-area
# polygon published as study_corridor_250m.shp and .geojson): .shp/.shx/.dbf/
# .prj/.cpg written byte by byte, so no GIS library is needed.

import json
import struct

import pytest

from main import FORMAT_REGISTRY, formats_for_extension, get_standardizer
from metadata_parsers.vector_parser import (
    describe_wkt, parse_vector_metadata, read_dbf_header, read_geojson, read_shp_header,
)
from metadata_profiles.profile_registry import get_profile
from metadata_profiles.required_fields_registry import compute_missing_fields
from metadata_profiles.standards_registry import get_standard_info
from standardizers.vector_standardizer import standardize_vector_metadata
from utils.curation_flags import compute_curation_flags

CONTEXT = "Vector GIS"
BBOX = (105.28, 21.0, 105.63, 21.5)
WKT = ('GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],'
       'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]')
UTM_WKT = ('PROJCS["WGS_1984_UTM_Zone_48N",GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",'
           'SPHEROID["WGS_1984",6378137.0,298.257223563]],PRIMEM["Greenwich",0.0],'
           'UNIT["Degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],'
           'PARAMETER["False_Easting",500000.0],PARAMETER["False_Northing",0.0],'
           'PARAMETER["Central_Meridian",105.0],PARAMETER["Scale_Factor",0.9996],'
           'PARAMETER["Latitude_Of_Origin",0.0],UNIT["Meter",1.0]]')


def _write_shp(path, shape_type=5, bbox=BBOX, content_bytes=200):
    length_words = (100 + content_bytes) // 2
    h = struct.pack(">7i", 9994, 0, 0, 0, 0, 0, length_words)
    h += struct.pack("<2i", 1000, shape_type) + struct.pack("<8d", *bbox, 0, 0, 0, 0)
    path.write_bytes(h + b"\x00" * content_bytes)


def _write_shx(path, records=1):
    path.write_bytes(struct.pack(">7i", 9994, 0, 0, 0, 0, 0, (100 + 8 * records) // 2) + b"\x00" * 72
                     + b"\x00" * (8 * records))


def _write_dbf(path, records=1, fields=(("name", "C", 80),), language=0):
    rec_len = 1 + sum(f[2] for f in fields)
    head = bytearray(32)
    head[0] = 3
    head[1:4] = bytes([126, 9, 26])
    struct.pack_into("<I", head, 4, records)
    struct.pack_into("<2H", head, 8, 32 + 32 * len(fields) + 1, rec_len)
    head[29] = language
    desc = b""
    for name, ftype, length in fields:
        d = bytearray(32)
        d[:len(name)] = name.encode()
        d[11] = ord(ftype)
        d[16] = length
        desc += bytes(d)
    path.write_bytes(bytes(head) + desc + b"\x0d" + b"".join(b" " + b"x" * (rec_len - 1) for _ in range(records)))


def _shapefile(tmp_path, stem="layer", prj=WKT, cpg="UTF-8", records=1, dbf_records=None, fields=(("name", "C", 80),), **kw):
    _write_shp(tmp_path / f"{stem}.shp", **kw)
    _write_shx(tmp_path / f"{stem}.shx", records)
    _write_dbf(tmp_path / f"{stem}.dbf", dbf_records if dbf_records is not None else records, fields)
    if prj:
        (tmp_path / f"{stem}.prj").write_text(prj)
    if cpg:
        (tmp_path / f"{stem}.cpg").write_text(cpg)
    return tmp_path / f"{stem}.shp"


def _geojson(tmp_path, stem="layer", name=None, crs=None, coords=None, extra=None):
    coords = coords or [[[105.28, 21.0], [105.63, 21.0], [105.63, 21.5], [105.28, 21.5], [105.28, 21.0]]]
    data = {"type": "FeatureCollection"}
    if name is not None:
        data["name"] = name
    if crs:
        data["crs"] = {"type": "name", "properties": {"name": crs}}
    data["features"] = [{"type": "Feature", "properties": {"name": "A", "area": 1.5, "note": None},
                         "geometry": {"type": "Polygon", "coordinates": coords}}] + (extra or [])
    p = tmp_path / f"{stem}.geojson"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _std(path):
    return standardize_vector_metadata(parse_vector_metadata(str(path))[1])


def _codes(std):
    return {s["Code"] for s in std["_Suggestions"]}


def test_shp_header(tmp_path):
    h = read_shp_header(str(_shapefile(tmp_path)))
    assert h["ShapeType"] == "Polygon" and h["BBox"] == list(BBOX) and not h["Truncated"]
    assert "ZRange" not in h


def test_shp_z_and_m_ranges(tmp_path):
    h = read_shp_header(str(_shapefile(tmp_path, shape_type=15)))
    assert h["ShapeType"] == "PolygonZ" and "ZRange" in h and "MRange" in h


def test_not_a_shapefile_is_reported_not_raised(tmp_path):
    p = tmp_path / "bad.shp"
    p.write_bytes(b"x" * 200)
    text, raw = parse_vector_metadata(str(p))
    assert "Failed to read Shapefile" in text and "SHP" not in raw


def test_dbf_header(tmp_path):
    _write_dbf(tmp_path / "t.dbf", records=3, fields=(("name", "C", 80), ("area", "N", 12)))
    h = read_dbf_header(str(tmp_path / "t.dbf"))
    assert h["Records"] == 3 and h["LastUpdate"] == "2026-09-26"
    assert [(f["Name"], f["TypeName"], f["Length"]) for f in h["Fields"]] == [("name", "text", 80), ("area", "number", 12)]


def test_wkt_description():
    assert describe_wkt(WKT)["Kind"] == "geographic" and describe_wkt(WKT)["Unit"] == "Degree"
    assert describe_wkt(UTM_WKT)["Kind"] == "projected" and describe_wkt(UTM_WKT)["Unit"] == "Meter"
    assert describe_wkt("")["Name"] == ""


def test_complete_shapefile_standardizes(tmp_path):
    std = _std(_shapefile(tmp_path))
    assert std["DataFormat"] == "ESRI Shapefile" and std["GeometryType"] == "Polygon" and std["FeatureCount"] == 1
    assert std["CRS_Kind"] == "geographic" and std["CRS_WKT"] == WKT and std["CharacterEncoding"] == "UTF-8"
    assert (std["BoundingBox_MinX"], std["BoundingBox_MaxY"]) == (105.28, 21.5)
    assert std["AttributeFields"] == "name (text 80)"
    assert _codes(std) <= {"VECTOR_NO_ISO_METADATA", "VECTOR_NO_EPSG"}


def test_missing_companions_are_flagged(tmp_path):
    p = _shapefile(tmp_path, prj=None, cpg=None)
    (tmp_path / "layer.shx").unlink()
    std = _std(p)
    assert {"VECTOR_SHP_INCOMPLETE", "VECTOR_NO_PRJ"} <= _codes(std)
    assert std["CRS_WKT"] == ""  # the shared NO_CRS_FOUND check fires from this
    flags, _ = compute_curation_flags([(str(p), "", std)])
    assert {"SHAPEFILE_INCOMPLETE", "NO_CRS_FOUND"} <= set(flags[str(p)])


def test_no_cpg_is_suggested_when_no_language_driver(tmp_path):
    assert "VECTOR_NO_CPG" in _codes(_std(_shapefile(tmp_path, cpg=None)))


def test_record_count_mismatch_is_flagged(tmp_path):
    p = _shapefile(tmp_path, records=2, dbf_records=3)
    assert "VECTOR_COUNT_MISMATCH" in _codes(_std(p))


def test_truncated_shp_is_flagged(tmp_path):
    p = _shapefile(tmp_path)
    p.write_bytes(p.read_bytes()[:-50])
    assert "VECTOR_TRUNCATED" in _codes(_std(p))


def test_ten_character_field_names_are_noted(tmp_path):
    assert "VECTOR_FIELD_NAMES_TRUNCATED" in _codes(_std(_shapefile(tmp_path, fields=(("habitat_ty", "C", 20),))))


def test_geojson_summary(tmp_path):
    g = read_geojson(str(_geojson(tmp_path, name="layer")))
    assert g["Type"] == "FeatureCollection" and g["FeatureCount"] == 1 and g["GeometryTypes"] == {"Polygon": 1}
    assert g["BBox"] == [105.28, 21.0, 105.63, 21.5] and g["PositionCount"] == 5
    assert g["Properties"] == {"name": ["string"], "area": ["number"], "note": ["null"]}


def test_geojson_default_crs_is_wgs84(tmp_path):
    std = _std(_geojson(tmp_path))
    assert std["CRS_EPSG"] == 4326 and std["CRS_WKT"] and std["CRS_Kind"] == "geographic"
    assert "GEOJSON_LEGACY_CRS" not in _codes(std)


def test_legacy_crs_member_and_name_mismatch(tmp_path):
    std = _std(_geojson(tmp_path, name="study_area_buffer_500m", crs="urn:ogc:def:crs:OGC:1.3:CRS84"))
    assert {"GEOJSON_LEGACY_CRS", "VECTOR_NAME_MISMATCH"} <= _codes(std)


def test_projected_coordinates_in_a_wgs84_file_are_flagged(tmp_path):
    p = _geojson(tmp_path, coords=[[[500000, 2300000], [510000, 2300000], [510000, 2310000], [500000, 2300000]]])
    std = _std(p)
    assert "GEOJSON_COORDS_OUT_OF_RANGE" in _codes(std)
    flags, _ = compute_curation_flags([(str(p), "", std)])
    assert "VECTOR_COORDS_OUT_OF_RANGE" in flags[str(p)]


def test_false_precision_is_noted(tmp_path):
    p = _geojson(tmp_path, coords=[[[105.331252328045693, 21.507659630330185], [105.4, 21.5], [105.4, 21.4],
                                    [105.331252328045693, 21.507659630330185]]])
    assert "VECTOR_FALSE_PRECISION" in _codes(_std(p))
    assert "VECTOR_FALSE_PRECISION" not in _codes(_std(_geojson(tmp_path, stem="short")))


def test_empty_geometry_is_noted(tmp_path):
    extra = [{"type": "Feature", "properties": {}, "geometry": None}]
    assert "VECTOR_EMPTY_GEOMETRY" in _codes(_std(_geojson(tmp_path, extra=extra)))


def test_matching_twins_are_consistent(tmp_path):
    shp = _shapefile(tmp_path)
    _geojson(tmp_path)
    raw = parse_vector_metadata(str(shp))[1]
    assert raw["TwinFile"] == "layer.geojson"
    assert "VECTOR_TWIN_MISMATCH" not in _codes(standardize_vector_metadata(raw))


def test_twins_with_different_extents_are_flagged(tmp_path):
    shp = _shapefile(tmp_path)
    _geojson(tmp_path, coords=[[[10.0, 10.0], [11.0, 10.0], [11.0, 11.0], [10.0, 10.0]]])
    assert "VECTOR_TWIN_MISMATCH" in _codes(_std(shp))
    assert "VECTOR_TWIN_MISMATCH" in _codes(_std(tmp_path / "layer.geojson"))


def test_invalid_geojson_is_reported_not_raised(tmp_path):
    p = tmp_path / "bad.geojson"
    p.write_text("{not json")
    text, raw = parse_vector_metadata(str(p))
    assert "Failed to read GeoJSON" in text
    assert standardize_vector_metadata(raw) == {"ImageName": "bad.geojson", "DataFormat": "GeoJSON"}


def test_suggestions_are_bilingual(tmp_path):
    for std in (_std(_shapefile(tmp_path, prj=None, cpg=None)), _std(_geojson(tmp_path, name="x", crs="urn:ogc:def:crs:OGC:1.3:CRS84"))):
        assert all(s["Message"] and s["Message_fr"] for s in std["_Suggestions"])


def test_registry_wiring(tmp_path):
    assert "Vector" in FORMAT_REGISTRY
    assert formats_for_extension(".shp") == ["Vector"] and formats_for_extension(".geojson") == ["Vector"]
    assert get_standardizer("Vector", CONTEXT) is standardize_vector_metadata
    for std in (_std(_shapefile(tmp_path)), _std(_geojson(tmp_path))):
        assert {k for k in std if not k.startswith("_")} <= set(get_profile(CONTEXT))
        assert compute_missing_fields("Vector", std, CONTEXT) == []
    assert "ISO 19115" in get_standard_info(CONTEXT)["standard_name"]
