# metadata_profiles/vector_profile.py
#
# Display labels/units for the "Vector GIS" context (ESRI Shapefile and
# GeoJSON). Key names for the CRS and extent match the other geospatial
# contexts so the labels and the NO_CRS_FOUND check are shared.

VECTOR_PROFILE = {
    "ImageName": {"label": "File Name", "unit": None},
    "DataFormat": {"label": "File Format", "unit": None},
    "LayerName": {"label": "Layer Name (in file)", "unit": None},
    "GeometryType": {"label": "Geometry Type", "unit": None},
    "FeatureCount": {"label": "Feature Count", "unit": "features"},
    "CRS_EPSG": {"label": "CRS (EPSG Code)", "unit": None},
    "CRS_WKT": {"label": "CRS (WKT)", "unit": None},
    "CRS_Name": {"label": "CRS Name", "unit": None},
    "CRS_Kind": {"label": "CRS Kind", "unit": None},
    "CRS_Unit": {"label": "CRS Unit", "unit": None},
    "BoundingBox_MinX": {"label": "Bounding Box Min X", "unit": None},
    "BoundingBox_MinY": {"label": "Bounding Box Min Y", "unit": None},
    "BoundingBox_MaxX": {"label": "Bounding Box Max X", "unit": None},
    "BoundingBox_MaxY": {"label": "Bounding Box Max Y", "unit": None},
    "HasZ": {"label": "Has Z Values", "unit": None},
    "HasM": {"label": "Has M Values", "unit": None},
    "AttributeFieldCount": {"label": "Attribute Fields", "unit": None},
    "AttributeFields": {"label": "Attribute Table Schema", "unit": None},
    "CharacterEncoding": {"label": "Attribute Text Encoding", "unit": None},
    "LastUpdate": {"label": "Attribute Table Last Update", "unit": None},
    "CoordinateDecimals": {"label": "Coordinate Decimals Written", "unit": None},
    "CompanionFiles": {"label": "Companion Files", "unit": None},
    "MetadataRecord": {"label": "ISO Metadata Record (.shp.xml)", "unit": None},
    "SameNameFile": {"label": "Same-Name Counterpart", "unit": None},
}
