import pytest

from i18n import set_language
from metadata_profiles.labels_fr import LABELS_FR, UNITS_FR
from metadata_profiles.profile_registry import PROFILE_REGISTRY, get_profile, format_label
from metadata_profiles.standards_fr import STANDARDS_FR
from metadata_profiles.standards_registry import STANDARDS_REGISTRY, get_standard_info


@pytest.fixture(autouse=True)
def reset_language():
    yield
    set_language("EN")


def test_every_profile_label_has_a_french_translation():
    labels = {v["label"] for p in PROFILE_REGISTRY.values() for v in p.values()}
    assert sorted(labels - set(LABELS_FR)) == []


def test_no_stale_french_labels():
    labels = {v["label"] for p in PROFILE_REGISTRY.values() for v in p.values()}
    assert sorted(set(LABELS_FR) - labels) == []


def test_format_label_follows_active_language():
    profile = get_profile("Remote Sensing (LiDAR)")
    assert format_label("BoundingBox_MinX", profile) == "Bounding Box Min X"
    set_language("FR")
    assert format_label("BoundingBox_MinX", profile) == LABELS_FR["Bounding Box Min X"]
    assert format_label("FileSizeMB", profile) == f"{LABELS_FR['File Size']} (MB)"


def test_french_units_are_translated_when_needed():
    set_language("FR")
    profile = {"K": {"label": "Dump Number", "unit": "days"}}
    assert format_label("K", profile).endswith(f"({UNITS_FR['days']})")


def test_unknown_key_falls_back_to_raw_key():
    set_language("FR")
    assert format_label("NoSuchKey", get_profile("Astronomy")) == "NoSuchKey"


def test_standards_fr_matches_english_structure():
    assert set(STANDARDS_FR) == set(STANDARDS_REGISTRY)
    for context, fr in STANDARDS_FR.items():
        en = STANDARDS_REGISTRY[context]
        assert len(fr["covered"]) == len(en["covered"]), context
        assert len(fr["not_covered"]) == len(en["not_covered"]), context
        assert set(fr) <= set(en), context


def test_get_standard_info_follows_active_language():
    en = get_standard_info("Astronomy")
    set_language("FR")
    fr = get_standard_info("Astronomy")
    assert fr["covered"] != en["covered"]
    assert fr["reference_url"] == en["reference_url"]
    assert fr["standard_name"] == en["standard_name"] or fr["standard_name"] in STANDARDS_FR["Astronomy"].values()
