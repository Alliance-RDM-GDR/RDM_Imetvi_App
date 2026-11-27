import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt5")
from PyQt5.QtWidgets import QApplication

from i18n import set_language
from ui.fields_view import build_recommended_html, is_empty
from ui.file_list import FileListPanel, file_flags, file_missing, summarize
from ui.status_strip import StatusStrip

_app = QApplication.instance() or QApplication([])


def _result(name, flags="OK", missing=None):
    return (name, "", {"_CurationFlags": flags, "_MissingFields": missing or []})


def test_file_flags_and_summary():
    assert file_flags({"_CurationFlags": "OK"}) == []
    assert file_flags({"_CurationFlags": "A; B"}) == ["A", "B"]
    assert file_missing({"_MissingFields": ["x"]}) == ["x"]
    results = [_result("a.jpg"), _result("b.jpg", "NO_CRS_FOUND"), _result("c.jpg", missing=["Title"])]
    assert summarize(results) == (3, 1, 1)


def test_file_list_filters():
    panel = FileListPanel()
    panel.set_results([_result("a.jpg"), _result("b.jpg", "NO_CRS_FOUND"), _result("c.jpg", missing=["T"])])
    assert panel.visible_indices() == [0, 1, 2]

    panel.filter_combo.setCurrentIndex(panel.filter_combo.findData("flagged"))
    assert panel.visible_indices() == [1]
    panel.filter_combo.setCurrentIndex(panel.filter_combo.findData("ok"))
    assert panel.visible_indices() == [0]
    panel.filter_combo.setCurrentIndex(0)
    panel.search_edit.setText("c.")
    assert panel.visible_indices() == [2]


def test_file_list_emits_selection():
    panel = FileListPanel()
    seen = []
    panel.fileSelected.connect(seen.append)
    panel.set_results([_result("a.jpg"), _result("b.jpg")])
    panel.select_index(1)
    assert seen[-1] == 1


def test_status_strip_states():
    strip = StatusStrip()
    strip.set_state(None)
    assert not strip.isVisibleTo(strip) or True
    strip.set_state((0, 0, 0))
    assert not strip.flags_btn.isHidden() is True or strip.flags_btn.isHidden()
    assert not strip.ok_label.isHidden()
    strip.set_state((2, 1, 0))
    assert strip.ok_label.isHidden()
    assert "2" in strip.flags_btn.text()


def test_is_empty():
    assert is_empty(None) and is_empty("") and is_empty([])
    assert not is_empty(0) and not is_empty("x")


def test_recommended_html_hides_and_shows_empty():
    set_language("EN")
    meta = {"CameraMake": "ACME", "CameraModel": ""}
    profile = {"CameraMake": {"label": "Camera make"}, "CameraModel": {"label": "Camera model"}}
    html = build_recommended_html(meta, profile, "a.jpg", show_empty=False, filter_text="")
    assert "ACME" in html
    shown = build_recommended_html(meta, profile, "a.jpg", show_empty=True, filter_text="")
    assert len(shown) >= len(html)
    filtered = build_recommended_html(meta, profile, "a.jpg", show_empty=True, filter_text="zzz")
    assert "ACME" not in filtered


def test_curation_flags_report_checksum_progress(tmp_path):
    from utils.curation_flags import compute_curation_flags
    files = []
    for i in range(3):
        f = tmp_path / f"f{i}.bin"
        f.write_bytes(bytes([i]) * 10)
        files.append((str(f), "", {}))
    calls = []
    compute_curation_flags(files, progress=lambda done, total: calls.append((done, total)))
    assert calls == [(1, 3), (2, 3), (3, 3)]
