# ui/status_strip.py
#
# One-line summary above the metadata tabs: how many curation flags, standards
# suggestions and missing required fields the displayed file has. Each count is
# a button that jumps to the tab where the details are. A glyph accompanies
# every colour so the state does not depend on colour vision alone.

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from i18n import tr

_STYLE = ("QPushButton {{ color: {c}; font-weight: bold; border: 1px solid {c}; "
          "border-radius: 4px; padding: 2px 10px; background: transparent; }}"
          "QPushButton:hover {{ background: palette(midlight); }}")


class StatusStrip(QWidget):
    flagsClicked = pyqtSignal()
    suggestionsClicked = pyqtSignal()
    missingClicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 4)

        self.ok_label = QLabel()
        self.ok_label.setStyleSheet("color: #27ae60; font-weight: bold;")
        layout.addWidget(self.ok_label)

        self.flags_btn = QPushButton()
        self.suggestions_btn = QPushButton()
        self.missing_btn = QPushButton()
        self.flags_btn.setStyleSheet(_STYLE.format(c="#e67e22"))
        self.suggestions_btn.setStyleSheet(_STYLE.format(c="#2471a3"))
        self.missing_btn.setStyleSheet(_STYLE.format(c="#c0392b"))
        for btn, sig in ((self.flags_btn, self.flagsClicked), (self.suggestions_btn, self.suggestionsClicked),
                         (self.missing_btn, self.missingClicked)):
            btn.clicked.connect(sig)
            layout.addWidget(btn)
        layout.addStretch()

        self._state = None
        self.retranslate()
        self.set_state(None)

    def set_state(self, state):
        """state: None (nothing displayed) or (n_flags, n_suggestions, n_missing)."""
        self._state = state
        if state is None:
            self.setVisible(False)
            return
        flags, suggestions, missing = state
        self.setVisible(True)
        self.flags_btn.setVisible(flags > 0)
        self.suggestions_btn.setVisible(suggestions > 0)
        self.missing_btn.setVisible(missing > 0)
        self.flags_btn.setText(f"⚠ {tr('ui_strip_flags', n=flags)}")
        self.suggestions_btn.setText(f"ℹ {tr('ui_strip_suggestions', n=suggestions)}")
        self.missing_btn.setText(f"✖ {tr('ui_strip_missing', n=missing)}")
        clean = flags == 0 and missing == 0
        self.ok_label.setVisible(clean)
        self.ok_label.setText(f"✔ {tr('ui_strip_ok')}")

    def retranslate(self):
        tip = tr("ui_strip_tip")
        for btn in (self.flags_btn, self.suggestions_btn, self.missing_btn):
            btn.setToolTip(tip)
        if self._state is not None:
            self.set_state(self._state)
