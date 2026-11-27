# ui/file_list.py
#
# Side panel listing the files of a batch with a status glyph, a text filter and
# a "show only..." filter (flagged / clean / missing required fields / one given
# flag). It replaces a drop-down that could not cope with hundreds of files.

from collections import Counter

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QBrush, QColor
from PyQt5.QtWidgets import QComboBox, QLabel, QLineEdit, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from i18n import tr

OK_GLYPH, WARN_GLYPH = "✔", "⚠"
OK_COLOUR, WARN_COLOUR, MISSING_COLOUR = "#27ae60", "#e67e22", "#c0392b"

_ALL, _FLAGGED, _OK, _MISSING = "all", "flagged", "ok", "missing"


def file_flags(standardized_metadata):
    """The curation flags of one file as a list (empty when it is clean)."""
    raw = (standardized_metadata or {}).get("_CurationFlags") or ""
    return [] if raw in ("", "OK") else [f.strip() for f in raw.split(";") if f.strip()]


def file_missing(standardized_metadata):
    return list((standardized_metadata or {}).get("_MissingFields") or [])


def summarize(results):
    """(files, with_flags, with_missing_required) for a list of (path, text, std)."""
    flagged = sum(1 for _, _, std in results if file_flags(std))
    missing = sum(1 for _, _, std in results if file_missing(std))
    return len(results), flagged, missing


class FileListPanel(QWidget):
    fileSelected = pyqtSignal(int)  # index into the results list passed to set_results

    def __init__(self, parent=None):
        super().__init__(parent)
        self._results = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        self.search_edit = QLineEdit()
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._apply_filters)
        layout.addWidget(self.search_edit)

        self.filter_combo = QComboBox()
        self.filter_combo.currentIndexChanged.connect(self._apply_filters)
        layout.addWidget(self.filter_combo)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setRootIsDecorated(False)
        self.tree.setUniformRowHeights(True)
        self.tree.header().setSectionsClickable(True)
        self.tree.header().sectionClicked.connect(self._on_header_clicked)
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(1, self.tree.header().Stretch)
        self.tree.setColumnWidth(0, 28)
        self.tree.setColumnWidth(2, 54)
        self.tree.currentItemChanged.connect(self._on_current_changed)
        layout.addWidget(self.tree, 1)

        self.retranslate()

    # --- content ---
    def set_results(self, results):
        """results: list of (file_path, text_report, standardized_metadata)."""
        self._results = list(results)
        self.tree.setSortingEnabled(False)
        self.tree.clear()
        for idx, (path, _, std) in enumerate(self._results):
            flags, missing = file_flags(std), file_missing(std)
            item = QTreeWidgetItem(["", path.replace("\\", "/").rsplit("/", 1)[-1], str(len(flags) + (1 if missing else 0))])
            item.setData(0, Qt.UserRole, idx)
            item.setData(2, Qt.UserRole, len(flags) + (1 if missing else 0))
            if flags or missing:
                item.setText(0, WARN_GLYPH)
                colour = MISSING_COLOUR if any(f in ("CORRUPT",) or f.endswith("TRUNCATED") or f.endswith("INCOMPLETE") for f in flags) else WARN_COLOUR
                item.setForeground(0, QBrush(QColor(colour)))
                reasons = list(flags) + ([tr("ui_filter_missing")] if missing else [])
                item.setToolTip(0, "\n".join(reasons))
                item.setToolTip(1, "\n".join(reasons))
            else:
                item.setText(0, OK_GLYPH)
                item.setForeground(0, QBrush(QColor(OK_COLOUR)))
            item.setTextAlignment(2, Qt.AlignRight | Qt.AlignVCenter)
            self.tree.addTopLevelItem(item)
        self._rebuild_filter_combo()
        self._update_summary()
        self._apply_filters()

    def clear(self):
        self.set_results([])

    def select_index(self, index):
        """Selects the row of result `index` (without emitting fileSelected twice is not needed)."""
        for row in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(row)
            if item.data(0, Qt.UserRole) == index:
                self.tree.setCurrentItem(item)
                return

    def visible_indices(self):
        out = []
        for row in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(row)
            if not item.isHidden():
                out.append(item.data(0, Qt.UserRole))
        return out

    # --- text ---
    def retranslate(self):
        self.search_edit.setPlaceholderText(tr("ui_filter_files"))
        self.tree.setHeaderLabels(["", tr("ui_col_file"), tr("ui_col_flags")])
        self._rebuild_filter_combo()
        self._update_summary()

    # --- internals ---
    def _rebuild_filter_combo(self):
        current = self.filter_combo.currentData()
        self.filter_combo.blockSignals(True)
        self.filter_combo.clear()
        self.filter_combo.addItem(tr("ui_filter_all"), _ALL)
        self.filter_combo.addItem(tr("ui_filter_flagged"), _FLAGGED)
        self.filter_combo.addItem(tr("ui_filter_ok"), _OK)
        self.filter_combo.addItem(tr("ui_filter_missing"), _MISSING)
        counts = Counter(f for _, _, std in self._results for f in file_flags(std))
        for flag, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
            self.filter_combo.addItem(f"{flag} ({n})", ("flag", flag))
        idx = self.filter_combo.findData(current) if current is not None else 0
        self.filter_combo.setCurrentIndex(max(idx, 0))
        self.filter_combo.blockSignals(False)

    def _update_summary(self):
        n, flagged, missing = summarize(self._results)
        self.summary_label.setText(tr("ui_files_summary", n=n, flagged=flagged, missing=missing))

    def _matches(self, std, mode):
        flags, missing = file_flags(std), file_missing(std)
        if mode == _FLAGGED:
            return bool(flags)
        if mode == _OK:
            return not flags and not missing
        if mode == _MISSING:
            return bool(missing)
        if isinstance(mode, tuple):
            return mode[1] in flags
        return True

    def _apply_filters(self, *_):
        text = self.search_edit.text().strip().lower()
        mode = self.filter_combo.currentData() or _ALL
        for row in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(row)
            std = self._results[item.data(0, Qt.UserRole)][2]
            name = item.text(1).lower()
            item.setHidden(not ((not text or text in name) and self._matches(std, mode)))

    def _on_header_clicked(self, column):
        # keep the load order until the user asks for a sort
        if not self.tree.isSortingEnabled():
            self.tree.setSortingEnabled(True)
            self.tree.sortByColumn(column, Qt.AscendingOrder)

    def _on_current_changed(self, current, _previous):
        if current is not None:
            self.fileSelected.emit(current.data(0, Qt.UserRole))
