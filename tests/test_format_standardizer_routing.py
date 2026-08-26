# tests/test_format_standardizer_routing.py
#
# get_standardizer() is the fix for a real routing bug: previously the app
# picked a format's standardizer purely by format name, ignoring which
# application context was selected — so a format offering more than one
# context (TIFF: Microscopy vs General / EXIF) could never actually use
# the second one's standardizer. These tests pin that routing behavior
# directly, importing from main.py since the function has no UI coupling.

from main import FORMAT_REGISTRY, FORMAT_STANDARDIZERS, get_standardizer
from standardizers.tiff_microscopy_standardizer import standardize_tiff_microscopy_metadata
from standardizers.tiff_general_standardizer import standardize_tiff_general_metadata
from standardizers.czi_microscopy_standardizer import standardize_czi_microscopy_metadata


def test_tiff_routes_to_microscopy_standardizer():
    assert get_standardizer("TIFF", "Microscopy") is standardize_tiff_microscopy_metadata


def test_tiff_routes_to_general_exif_standardizer():
    assert get_standardizer("TIFF", "General / EXIF") is standardize_tiff_general_metadata


def test_single_context_format_ignores_irrelevant_context_name():
    # CZI only has one registered context; an unrelated context_name still
    # resolves via the fallback rather than returning None.
    assert get_standardizer("CZI", "Some Other Context") is standardize_czi_microscopy_metadata


def test_unknown_format_returns_none():
    assert get_standardizer("NotARealFormat", "Microscopy") is None


def test_every_format_registry_context_has_a_standardizer():
    # Catches the registries drifting out of sync: every context listed in
    # FORMAT_REGISTRY must resolve to a real standardizer via
    # FORMAT_STANDARDIZERS, for every format that declares it.
    for format_name, fmt in FORMAT_REGISTRY.items():
        for context_name in fmt["contexts"]:
            standardizer = get_standardizer(format_name, context_name)
            assert standardizer is not None, f"{format_name} / {context_name} has no standardizer"
            assert callable(standardizer)


def test_format_standardizers_registry_is_nested_per_context():
    # Guards the (format, context) keying shape the routing above depends
    # on -- a flattened {format: fn} entry would silently break lookups.
    for format_name, entry in FORMAT_STANDARDIZERS.items():
        assert isinstance(entry, dict), f"{format_name} entry must be a {{context: fn}} dict"
