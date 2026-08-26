# main.py

import sys
import os
import json
import csv
from collections import Counter
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QFileDialog, QMessageBox,
    QLabel, QComboBox, QProgressDialog, QDialog,
    QScrollArea, QFormLayout, QLineEdit, QDialogButtonBox,
    QTabWidget
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QPixmap

# === Import parsers, standardizers, and profiles ===
from metadata_parsers.tiff_parser import parse_tiff_metadata
from metadata_parsers.czi_parser import parse_czi_metadata
from metadata_parsers.jpg_parser import parse_jpg_metadata
from metadata_parsers.geotiff_parser import parse_geotiff_metadata
from metadata_parsers.ome_tiff_parser import parse_ome_tiff_metadata
from metadata_parsers.dicom_parser import parse_dicom_metadata
from metadata_parsers.fits_parser import parse_fits_metadata
from metadata_parsers.hdf5_parser import parse_hdf5_metadata
from metadata_parsers.png_parser import parse_png_metadata
from metadata_parsers.lif_parser import parse_lif_metadata
from metadata_parsers.netcdf_parser import parse_netcdf_metadata
from standardizers.tiff_microscopy_standardizer import standardize_tiff_microscopy_metadata
from standardizers.czi_microscopy_standardizer import standardize_czi_microscopy_metadata
from standardizers.jpg_general_standardizer import standardize_jpg_general_metadata
from standardizers.geotiff_remote_sensing_standardizer import standardize_geotiff_remote_sensing_metadata
from standardizers.ome_microscopy_standardizer import standardize_ome_microscopy_metadata
from standardizers.dicom_medical_standardizer import standardize_dicom_medical_metadata
from standardizers.fits_astronomy_standardizer import standardize_fits_astronomy_metadata
from standardizers.hdf5_general_standardizer import standardize_hdf5_general_metadata
from standardizers.png_general_standardizer import standardize_png_general_metadata
from standardizers.lif_microscopy_standardizer import standardize_lif_microscopy_metadata
from standardizers.netcdf_remote_sensing_standardizer import standardize_netcdf_remote_sensing_metadata
from utils.serialization import make_json_serializable
from utils.metadata_writer import write_metadata_to_file, SUPPORTED_WRITE_EXTENSIONS
from utils.sidecar import write_sidecar, sidecar_path_for
from utils.integrity import compute_md5, save_checksums, load_checksums, verify_checksums
from utils.thumbnail import generate_thumbnail_bytes
from utils.curation_flags import compute_curation_flags
from metadata_profiles.standards_registry import get_standard_info, get_reference_summary
from metadata_profiles.profile_registry import get_profile, format_label

# === Format / Context registries ===
# Each format declares which extensions it handles, its parser, and which
# application contexts (standardizer + profile) are valid for it.
FORMAT_REGISTRY = {
    "TIFF": {
        "extensions": [".tif", ".tiff"],
        "parser": parse_tiff_metadata,
        "contexts": ["Microscopy"],
    },
    "CZI": {
        "extensions": [".czi"],
        "parser": parse_czi_metadata,
        "contexts": ["Microscopy"],
    },
    "OME-TIFF": {
        "extensions": [".tif", ".tiff"],
        "parser": parse_ome_tiff_metadata,
        "contexts": ["Microscopy (OME)"],
    },
    "GeoTIFF": {
        "extensions": [".tif", ".tiff"],
        "parser": parse_geotiff_metadata,
        "contexts": ["Remote Sensing"],
    },
    "JPG": {
        "extensions": [".jpg", ".jpeg"],
        "parser": parse_jpg_metadata,
        "contexts": ["General / EXIF"],
    },
    "DICOM": {
        "extensions": [".dcm"],
        "parser": parse_dicom_metadata,
        "contexts": ["Medical Imaging"],
    },
    "FITS": {
        "extensions": [".fits", ".fit"],
        "parser": parse_fits_metadata,
        "contexts": ["Astronomy"],
    },
    "HDF5": {
        "extensions": [".h5", ".hdf5", ".nc4"],
        "parser": parse_hdf5_metadata,
        "contexts": ["General / HDF5"],
    },
    "PNG": {
        "extensions": [".png"],
        "parser": parse_png_metadata,
        "contexts": ["General / EXIF"],
    },
    "LIF": {
        "extensions": [".lif"],
        "parser": parse_lif_metadata,
        "contexts": ["Microscopy (Leica)"],
    },
    "NetCDF": {
        "extensions": [".nc", ".nc4"],
        "parser": parse_netcdf_metadata,
        "contexts": ["Remote Sensing (NetCDF)"],
    },
}

CONTEXT_REGISTRY = {
    "Microscopy": {
        "standardizer": standardize_tiff_microscopy_metadata,  # default; overridden per-format below
    },
    "Microscopy (OME)": {
        "standardizer": standardize_ome_microscopy_metadata,
    },
    "Remote Sensing": {
        "standardizer": standardize_geotiff_remote_sensing_metadata,
    },
    "General / EXIF": {
        "standardizer": standardize_jpg_general_metadata,
    },
    "Medical Imaging": {
        "standardizer": standardize_dicom_medical_metadata,
    },
    "Astronomy": {
        "standardizer": standardize_fits_astronomy_metadata,
    },
    "General / HDF5": {
        "standardizer": standardize_hdf5_general_metadata,
    },
    "Microscopy (Leica)": {
        "standardizer": standardize_lif_microscopy_metadata,
    },
    "Remote Sensing (NetCDF)": {
        "standardizer": standardize_netcdf_remote_sensing_metadata,
    },
}

# Format-specific standardizer overrides (a context can be reached by more
# than one format, e.g. Microscopy via TIFF or CZI, each needing its own
# standardizer).
FORMAT_STANDARDIZERS = {
    "TIFF": standardize_tiff_microscopy_metadata,
    "CZI": standardize_czi_microscopy_metadata,
    "OME-TIFF": standardize_ome_microscopy_metadata,
    "GeoTIFF": standardize_geotiff_remote_sensing_metadata,
    "JPG": standardize_jpg_general_metadata,
    "DICOM": standardize_dicom_medical_metadata,
    "FITS": standardize_fits_astronomy_metadata,
    "HDF5": standardize_hdf5_general_metadata,
    "PNG": standardize_png_general_metadata,
    "LIF": standardize_lif_microscopy_metadata,
    "NetCDF": standardize_netcdf_remote_sensing_metadata,
}

ALL_EXTENSIONS = sorted({ext for fmt in FORMAT_REGISTRY.values() for ext in fmt["extensions"]})


def formats_for_extension(ext):
    """Returns the list of registered format names that handle a given extension."""
    return [name for name, fmt in FORMAT_REGISTRY.items() if ext.lower() in fmt["extensions"]]


class FolderLoadWorker(QThread):
    """Processes a folder of image files in a background thread, reporting
    progress so the UI stays responsive during batch loading."""

    progress = pyqtSignal(int, int, str)  # current index, total, current filename
    finished = pyqtSignal(list)  # list of (file_path, text_report, standardized_metadata)

    def __init__(self, file_paths, format_name, app_name):
        super().__init__()
        self.file_paths = file_paths
        self.format_name = format_name
        self.app_name = app_name

    def run(self):
        fmt = FORMAT_REGISTRY[self.format_name]
        standardizer = FORMAT_STANDARDIZERS[self.format_name]
        reference = get_reference_summary(self.app_name)
        results = []
        total = len(self.file_paths)

        for idx, full_path in enumerate(self.file_paths, 1):
            self.progress.emit(idx, total, os.path.basename(full_path))
            try:
                text_report, raw_metadata = fmt["parser"](full_path, application=self.app_name)
                standardized_metadata = standardizer(raw_metadata)
                if reference:
                    standardized_metadata["_StandardReference"] = reference
                results.append((full_path, text_report, standardized_metadata))
            except Exception as e:
                print(f"Failed to process {os.path.basename(full_path)}: {e}")

        # Attach curation flags (requires full batch for duplicate/outlier detection)
        if results:
            flags_by_path, checksums = compute_curation_flags(results)
            enriched = []
            for file_path, text_report, meta in results:
                flags = flags_by_path.get(file_path, [])
                meta["_CurationFlags"] = "; ".join(flags) if flags else "OK"
                md5 = checksums.get(file_path)
                if md5:
                    meta["_MD5Checksum"] = md5
                enriched.append((file_path, text_report, meta))
            results = enriched

        self.finished.emit(results)


class MetadataViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image Metadata Viewer")
        self.setGeometry(100, 100, 1000, 700)

        layout = QVBoxLayout()

        # === Top layout ===
        top_layout = QHBoxLayout()

        self.format_label = QLabel("Select Format:")
        self.format_dropdown = QComboBox()
        self.format_dropdown.addItems(list(FORMAT_REGISTRY.keys()))
        self.format_dropdown.currentTextChanged.connect(self.on_format_changed)
        top_layout.addWidget(self.format_label)
        top_layout.addWidget(self.format_dropdown)

        self.app_label = QLabel("Select Application:")
        self.app_dropdown = QComboBox()
        top_layout.addWidget(self.app_label)
        top_layout.addWidget(self.app_dropdown)

        self.standards_info_btn = QPushButton("Metadata Standard Info")
        self.standards_info_btn.clicked.connect(self.show_standards_info)
        top_layout.addWidget(self.standards_info_btn)

        self.file_selector_label = QLabel("Select File:")
        self.file_selector_dropdown = QComboBox()
        self.file_selector_dropdown.currentIndexChanged.connect(self.select_loaded_file)
        self.file_selector_label.hide()
        self.file_selector_dropdown.hide()
        top_layout.addWidget(self.file_selector_label)
        top_layout.addWidget(self.file_selector_dropdown)

        layout.addLayout(top_layout)

        # Initialize the application dropdown for the default format
        self.on_format_changed(self.format_dropdown.currentText())

        # === Buttons ===
        button_layout = QHBoxLayout()

        self.load_file_btn = QPushButton("Load File")
        self.load_file_btn.clicked.connect(self.load_file)
        button_layout.addWidget(self.load_file_btn)

        self.load_folder_btn = QPushButton("Load Folder")
        self.load_folder_btn.clicked.connect(self.load_folder)
        button_layout.addWidget(self.load_folder_btn)

        self.export_json_btn = QPushButton("Export as JSON")
        self.export_json_btn.clicked.connect(self.export_as_json)
        self.export_json_btn.setEnabled(False)
        button_layout.addWidget(self.export_json_btn)

        self.export_csv_btn = QPushButton("Export as CSV")
        self.export_csv_btn.clicked.connect(self.export_as_csv)
        self.export_csv_btn.setEnabled(False)
        button_layout.addWidget(self.export_csv_btn)

        self.write_metadata_btn = QPushButton("Write Metadata to File")
        self.write_metadata_btn.clicked.connect(self.write_metadata)
        self.write_metadata_btn.setEnabled(False)
        button_layout.addWidget(self.write_metadata_btn)

        self.save_sidecar_btn = QPushButton("Save Sidecar JSON")
        self.save_sidecar_btn.clicked.connect(self.save_sidecar)
        self.save_sidecar_btn.setEnabled(False)
        self.save_sidecar_btn.setToolTip(
            "Save metadata as a .json file beside the image (same folder, same base name)."
        )
        button_layout.addWidget(self.save_sidecar_btn)

        self.export_curation_btn = QPushButton("Export Curation Report")
        self.export_curation_btn.clicked.connect(self.export_curation_report)
        self.export_curation_btn.setEnabled(False)
        button_layout.addWidget(self.export_curation_btn)

        self.save_checksums_btn = QPushButton("Save Checksums")
        self.save_checksums_btn.clicked.connect(self.save_checksums)
        self.save_checksums_btn.setEnabled(False)
        self.save_checksums_btn.setToolTip(
            "Write checksums.json for the loaded files' folder, for later integrity checks."
        )
        button_layout.addWidget(self.save_checksums_btn)

        self.verify_integrity_btn = QPushButton("Verify Integrity")
        self.verify_integrity_btn.clicked.connect(self.verify_integrity)
        self.verify_integrity_btn.setEnabled(False)
        self.verify_integrity_btn.setToolTip(
            "Compare current file checksums against a saved checksums.json."
        )
        button_layout.addWidget(self.verify_integrity_btn)

        layout.addLayout(button_layout)

        # === Content row: collapsible thumbnail preview + tabbed metadata ===
        content_layout = QHBoxLayout()

        self.preview_panel = QWidget()
        preview_layout = QVBoxLayout()
        preview_layout.setContentsMargins(0, 0, 0, 0)

        self.thumbnail_display = QLabel("No Preview")
        self.thumbnail_display.setAlignment(Qt.AlignCenter)
        self.thumbnail_display.setFixedSize(160, 160)
        self.thumbnail_display.setStyleSheet(
            "border: 1px solid palette(mid); background: palette(base);"
        )
        preview_layout.addWidget(self.thumbnail_display)
        preview_layout.addStretch()
        self.preview_panel.setLayout(preview_layout)
        content_layout.addWidget(self.preview_panel)

        self.toggle_preview_btn = QPushButton("Hide Preview")
        self.toggle_preview_btn.setCheckable(True)
        self.toggle_preview_btn.clicked.connect(self.toggle_preview_panel)
        button_layout.addWidget(self.toggle_preview_btn)

        # === Metadata display — tabbed view ===
        self.tab_widget = QTabWidget()

        self.raw_metadata_display = QTextEdit()
        self.raw_metadata_display.setReadOnly(True)
        self.raw_metadata_display.setPlaceholderText("Raw metadata will appear here")
        self.tab_widget.addTab(self.raw_metadata_display, "Raw Metadata")

        self.recommended_metadata_display = QTextEdit()
        self.recommended_metadata_display.setReadOnly(True)
        self.recommended_metadata_display.setPlaceholderText("Recommended / standardized fields will appear here")
        self.tab_widget.addTab(self.recommended_metadata_display, "Recommended Fields")

        self.curation_display = QTextEdit()
        self.curation_display.setReadOnly(True)
        self.curation_display.setPlaceholderText("Curation flags and integrity info will appear here")
        self.tab_widget.addTab(self.curation_display, "Curation")

        content_layout.addWidget(self.tab_widget)
        layout.addLayout(content_layout)

        self.setLayout(layout)

        # Internal state
        self.last_standardized_metadata = None
        self.last_file_path = None
        self.all_standardized_metadata = []
        self.loaded_files = []
        self.current_display_file_path = None
        self.current_display_metadata = None
        self.folder_worker = None
        self.progress_dialog = None

    # === Thumbnail Preview ===
    def toggle_preview_panel(self, checked):
        self.preview_panel.setVisible(not checked)
        self.toggle_preview_btn.setText("Show Preview" if checked else "Hide Preview")

    def update_thumbnail(self, file_path):
        thumb_bytes = generate_thumbnail_bytes(file_path) if file_path else None

        if thumb_bytes:
            pixmap = QPixmap()
            pixmap.loadFromData(thumb_bytes)
            self.thumbnail_display.setPixmap(
                pixmap.scaled(160, 160, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        else:
            self.thumbnail_display.setPixmap(QPixmap())
            ext = os.path.splitext(file_path)[1].lstrip(".").upper() if file_path else ""
            self.thumbnail_display.setText(ext if ext else "No Preview")

    # === Standards Documentation ===
    def show_standards_info(self):
        context_name = self.app_dropdown.currentText()
        info = get_standard_info(context_name)

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Metadata Standard — {context_name}")
        dialog.setMinimumWidth(520)
        dialog_layout = QVBoxLayout()

        text_label = QLabel()
        text_label.setWordWrap(True)
        text_label.setTextFormat(Qt.RichText)
        text_label.setOpenExternalLinks(True)

        if not info:
            text_label.setText(f"No standards documentation is registered for '{context_name}' yet.")
        else:
            covered_html = "".join(f"<li>{item}</li>" for item in info["covered"])
            not_covered_html = "".join(f"<li>{item}</li>" for item in info["not_covered"])

            html = (
                f"<h3>{info['standard_name']}</h3>"
                f"<p><a href=\"{info['reference_url']}\">{info['reference_url']}</a></p>"
                f"<p><a href=\"{info['secondary_url']}\">{info['secondary_label']}</a></p>"
                f"<p><b>What this app extracts for this standard:</b></p>"
                f"<ul>{covered_html}</ul>"
                f"<p><b>Not covered by file metadata (must be supplied separately):</b></p>"
                f"<ul>{not_covered_html}</ul>"
            )
            text_label.setText(html)

        dialog_layout.addWidget(text_label)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        dialog_layout.addWidget(close_btn)

        dialog.setLayout(dialog_layout)
        dialog.exec_()

    # === Format/Context wiring ===
    def on_format_changed(self, format_name):
        fmt = FORMAT_REGISTRY.get(format_name)
        self.app_dropdown.clear()
        if fmt:
            self.app_dropdown.addItems(fmt["contexts"])

    def select_format_for_extension(self, file_path):
        """Auto-selects a format matching the file's extension, if not already compatible."""
        ext = os.path.splitext(file_path)[1].lower()
        candidates = formats_for_extension(ext)
        if not candidates:
            return
        if self.format_dropdown.currentText() not in candidates:
            self.format_dropdown.setCurrentText(candidates[0])

    def process_file(self, file_path):
        """Parses and standardizes a single file using the currently selected format/context."""
        selected_format = self.format_dropdown.currentText()
        selected_app = self.app_dropdown.currentText()

        fmt = FORMAT_REGISTRY.get(selected_format)
        if not fmt:
            raise ValueError(f"Unsupported format: {selected_format}")

        text_report, raw_metadata = fmt["parser"](file_path, application=selected_app)
        standardizer = FORMAT_STANDARDIZERS[selected_format]
        standardized_metadata = standardizer(raw_metadata)

        reference = get_reference_summary(selected_app)
        if reference:
            standardized_metadata["_StandardReference"] = reference

        # Curation flags for single-file load (no batch context, so only
        # CORRUPT and HAS_GPS_DATA can be evaluated; checksum is still computed).
        flags_by_path, checksums = compute_curation_flags(
            [(file_path, text_report, standardized_metadata)]
        )
        flags = flags_by_path.get(file_path, [])
        standardized_metadata["_CurationFlags"] = "; ".join(flags) if flags else "OK"
        md5 = checksums.get(file_path)
        if md5:
            standardized_metadata["_MD5Checksum"] = md5

        return text_report, standardized_metadata

    # === File and Folder Loading ===
    def load_file(self):
        filter_str = "Images (" + " ".join(f"*{ext}" for ext in ALL_EXTENSIONS) + ")"
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File", filter=filter_str)
        if file_path:
            self.select_format_for_extension(file_path)
            self.display_metadata(file_path, single_file=True)

    def load_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if not folder_path:
            return

        file_paths = [
            os.path.join(folder_path, fname)
            for fname in os.listdir(folder_path)
            if os.path.isfile(os.path.join(folder_path, fname))
            and os.path.splitext(fname)[1].lower() in ALL_EXTENSIONS
        ]

        if not file_paths:
            QMessageBox.information(self, "No Files Found", "No supported image files were found in this folder.")
            return

        self.loaded_files = []
        self.all_standardized_metadata = []
        self.file_selector_dropdown.clear()

        selected_format = self.format_dropdown.currentText()
        selected_app = self.app_dropdown.currentText()

        self.progress_dialog = QProgressDialog("Loading files...", "Cancel", 0, len(file_paths), self)
        self.progress_dialog.setWindowTitle("Batch Loading")
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setValue(0)

        self.folder_worker = FolderLoadWorker(file_paths, selected_format, selected_app)
        self.folder_worker.progress.connect(self.on_folder_load_progress)
        self.folder_worker.finished.connect(self.on_folder_load_finished)
        self.progress_dialog.canceled.connect(self.folder_worker.terminate)
        self.folder_worker.start()

    def on_folder_load_progress(self, current, total, filename):
        if self.progress_dialog is not None:
            self.progress_dialog.setLabelText(f"Processing {filename} ({current}/{total})")
            self.progress_dialog.setValue(current)

    def on_folder_load_finished(self, results):
        if self.progress_dialog is not None:
            self.progress_dialog.setValue(self.progress_dialog.maximum())
            self.progress_dialog = None

        self.loaded_files = results
        self.all_standardized_metadata = [r[2] for r in results]
        for file_path, _, _ in results:
            self.file_selector_dropdown.addItem(os.path.basename(file_path))

        if self.loaded_files:
            self.file_selector_label.show()
            self.file_selector_dropdown.show()
            self.file_selector_dropdown.setCurrentIndex(0)
            self.select_loaded_file(0)

        self.export_json_btn.setEnabled(bool(self.loaded_files))
        self.export_csv_btn.setEnabled(bool(self.loaded_files))
        self.export_curation_btn.setEnabled(bool(self.loaded_files))
        self.save_checksums_btn.setEnabled(bool(self.loaded_files))
        self.verify_integrity_btn.setEnabled(bool(self.loaded_files))

    def select_loaded_file(self, index):
        if 0 <= index < len(self.loaded_files):
            file_path, text_report, standardized_metadata = self.loaded_files[index]
            self.render_metadata(file_path, text_report, standardized_metadata)

    def render_metadata(self, file_path, text_report, standardized_metadata):
        self.current_display_file_path = file_path
        self.current_display_metadata = standardized_metadata
        ext = os.path.splitext(file_path)[1].lower()
        self.write_metadata_btn.setEnabled(ext in SUPPORTED_WRITE_EXTENSIONS)
        self.save_sidecar_btn.setEnabled(bool(file_path))
        self.update_thumbnail(file_path)

        fname = os.path.basename(file_path)

        # ── Tab 1: Raw Metadata ───────────────────────────────────────────────
        self.raw_metadata_display.clear()
        self.raw_metadata_display.append(f"File: {fname}\n")
        self.raw_metadata_display.append(text_report)

        # ── Tab 2: Recommended Fields ─────────────────────────────────────────
        self.recommended_metadata_display.clear()
        self.recommended_metadata_display.append(f"File: {fname}\n")

        _CURATION_KEYS = {"_CurationFlags", "_MD5Checksum", "_StandardReference"}
        active_profile = get_profile(self.app_dropdown.currentText())

        for key, value in standardized_metadata.items():
            if key in _CURATION_KEYS:
                continue

            display_key = format_label(key, active_profile)

            if key == "Channels" and isinstance(value, list):
                self.recommended_metadata_display.append(f"{display_key}:")
                for idx, ch in enumerate(value, 1):
                    name = ch.get("Name", "")
                    exc  = ch.get("ExcitationWavelength", "")
                    em   = ch.get("EmissionWavelength", "")
                    exp  = ch.get("ExposureTime_sec", "")
                    self.recommended_metadata_display.append(
                        f"  - Channel {idx}: {name}"
                        + (f"  |  Exc: {exc} nm" if exc else "")
                        + (f"  |  Em: {em} nm" if em else "")
                        + (f"  |  Exp: {exp} sec" if exp else "")
                    )
            elif key == "Datasets" and isinstance(value, list):
                self.recommended_metadata_display.append(f"{display_key}:")
                for obj in value:
                    risk = f"  ⚠ {obj['Risk']}" if obj.get("Risk") else ""
                    self.recommended_metadata_display.append(
                        f"  [{obj.get('Type','?')}] {obj.get('Path','')} | "
                        f"Dims: {obj.get('Dimensions','—')} | "
                        f"Type: {obj.get('DataType','—')} | "
                        f"Compression: {obj.get('Compression','—')}"
                        f"{risk}"
                    )
            else:
                self.recommended_metadata_display.append(f"{display_key}:  {value}")

        # ── Tab 3: Curation ───────────────────────────────────────────────────
        self.curation_display.clear()
        self.curation_display.setAcceptRichText(True)

        flags_str  = standardized_metadata.get("_CurationFlags", "")
        md5        = standardized_metadata.get("_MD5Checksum", "")
        comp_warn  = standardized_metadata.get("CompressionWarning", "")
        ref        = standardized_metadata.get("_StandardReference", {})

        # Colour each flag
        _FLAG_COLOURS = {
            "DUPLICATE":         "#e74c3c",
            "HAS_GPS_DATA":      "#e67e22",
            "DIMENSION_OUTLIER": "#8e44ad",
            "LOSSY_TIFF":        "#c0392b",
            "CORRUPT":           "#e74c3c",
        }
        flag_parts = []
        if flags_str and flags_str != "OK":
            for flag in flags_str.split("; "):
                colour = _FLAG_COLOURS.get(flag.strip(), "#555")
                flag_parts.append(
                    f'<span style="color:{colour}; font-weight:bold;">⚠ {flag}</span>'
                )
            flags_html = " &nbsp; ".join(flag_parts)
        else:
            flags_html = '<span style="color:#27ae60; font-weight:bold;">✔ OK — no issues detected</span>'

        html = (
            f"<h3 style='margin-bottom:4px;'>Curation Summary — {fname}</h3>"
            f"<p><b>Flags:</b> {flags_html}</p>"
        )

        if md5:
            html += f"<p><b>MD5 Checksum:</b> <code>{md5}</code></p>"

        if comp_warn:
            html += (
                f"<p style='color:#c0392b;'>"
                f"<b>⚠ Compression Warning:</b> {comp_warn}"
                f"</p>"
            )

        if isinstance(ref, dict) and ref.get("Standard"):
            html += (
                f"<p><b>Metadata Standard:</b> {ref['Standard']}<br>"
                f"<b>Reference:</b> <a href='{ref.get('URL','')}' style='color:#2980b9;'>"
                f"{ref.get('URL','')}</a></p>"
            )

        self.curation_display.setHtml(html)

    # === Metadata Display ===
    def display_metadata(self, file_path, single_file=False):
        self.last_standardized_metadata = None
        self.last_file_path = file_path

        try:
            text_report, self.last_standardized_metadata = self.process_file(file_path)
            self.render_metadata(file_path, text_report, self.last_standardized_metadata)
        except Exception as e:
            self.current_display_file_path = None
            self.current_display_metadata = None
            self.write_metadata_btn.setEnabled(False)
            self.save_sidecar_btn.setEnabled(False)
            self.update_thumbnail(None)
            self.raw_metadata_display.clear()
            self.recommended_metadata_display.clear()
            self.raw_metadata_display.append(f"File: {os.path.basename(file_path)}\n")
            self.raw_metadata_display.append(f"Error: {str(e)}")
            self.recommended_metadata_display.append("Metadata extraction failed.")

        if single_file and self.last_standardized_metadata:
            self.all_standardized_metadata = [self.last_standardized_metadata]

        self.export_json_btn.setEnabled(bool(self.all_standardized_metadata))
        self.export_csv_btn.setEnabled(bool(self.all_standardized_metadata))
        self.export_curation_btn.setEnabled(bool(self.all_standardized_metadata))
        self.save_checksums_btn.setEnabled(bool(self.all_standardized_metadata))
        self.verify_integrity_btn.setEnabled(bool(self.all_standardized_metadata))

    # === Metadata Writing ===
    def open_metadata_editor(self, metadata):
        """
        Shows an editable form pre-filled with the standardized metadata.
        Fields holding lists/dicts (e.g. Channels, _StandardReference) are
        shown read-only since they are structured, not single values.
        Returns the edited dict, or None if the user cancelled.
        """
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Metadata Before Writing")
        dialog.setMinimumSize(540, 600)
        outer_layout = QVBoxLayout()

        note = QLabel(
            "Edit the values below, then click Save to write them into the file. "
            "Fields with multiple sub-values (shown greyed out) are structured "
            "and not editable here."
        )
        note.setWordWrap(True)
        outer_layout.addWidget(note)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        form_widget = QWidget()
        form_layout = QFormLayout()

        editors = {}
        for key, value in metadata.items():
            if isinstance(value, (list, dict)):
                field = QLineEdit(str(value))
                field.setEnabled(False)
            else:
                field = QLineEdit("" if value is None else str(value))
            editors[key] = field
            form_layout.addRow(key, field)

        form_widget.setLayout(form_layout)
        scroll_area.setWidget(form_widget)
        outer_layout.addWidget(scroll_area)

        button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        outer_layout.addWidget(button_box)

        dialog.setLayout(outer_layout)

        if dialog.exec_() != QDialog.Accepted:
            return None

        edited_metadata = dict(metadata)
        for key, field in editors.items():
            if field.isEnabled():
                edited_metadata[key] = field.text()
        return edited_metadata

    def _apply_edited_metadata(self, edited_metadata):
        """Propagates an edit so all panels and pending exports stay
        consistent with what was actually written to the file."""
        self.current_display_metadata = edited_metadata

        text_report = ""
        for idx, (path, tr, _) in enumerate(self.loaded_files):
            if path == self.current_display_file_path:
                self.loaded_files[idx] = (path, tr, edited_metadata)
                text_report = tr
                break

        if self.loaded_files:
            self.all_standardized_metadata = [m for _, _, m in self.loaded_files]
        else:
            self.all_standardized_metadata = [edited_metadata]

        # Re-render all three tabs using the full render path
        self.render_metadata(self.current_display_file_path, text_report, edited_metadata)

    def write_metadata(self):
        if not self.current_display_file_path or not self.current_display_metadata:
            return

        edited_metadata = self.open_metadata_editor(self.current_display_metadata)
        if edited_metadata is None:
            return

        confirm = QMessageBox.warning(
            self,
            "Write Metadata to File",
            f"This will overwrite metadata in:\n{self.current_display_file_path}\n\n"
            "This action cannot be undone. Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        try:
            write_metadata_to_file(self.current_display_file_path, edited_metadata)
            self._apply_edited_metadata(edited_metadata)
            QMessageBox.information(self, "Success", "Metadata written to file successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to write metadata: {str(e)}")

    # === Curation Report Export ===
    def export_curation_report(self):
        """
        Exports a dedicated curation summary CSV — one row per file, columns
        for curation flags and key technical properties only.  Compatible with
        the CUR_Res_CurationTools Inspect_Images report format so curators can
        combine outputs from both tools.
        """
        if not self.all_standardized_metadata:
            return

        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save Curation Report", filter="CSV Files (*.csv)"
        )
        if not save_path:
            return

        _CURATION_COLS = [
            "FileName",
            "FilePath",
            "MD5Checksum",
            "Format",
            "Application",
            "DimensionX",
            "DimensionY",
            "BitDepth",
            "ColorSpace",
            "Compression",
            "CurationFlags",
            "Standard",
            "StandardURL",
        ]

        # Dimension key aliases across formats
        _DIM_X = ("DimensionX", "ImageWidth", "Width", "NAXIS1", "Columns")
        _DIM_Y = ("DimensionY", "ImageLength", "Height", "NAXIS2", "Rows")

        def _pick(meta, keys):
            for k in keys:
                if k in meta:
                    return str(meta[k])
            return ""

        try:
            rows = []
            sources = self.loaded_files if self.loaded_files else [
                (self.last_file_path, "", self.all_standardized_metadata[0])
            ]
            for file_path, _, meta in sources:
                ref = meta.get("_StandardReference", {})
                row = {
                    "FileName": os.path.basename(file_path) if file_path else "",
                    "FilePath": file_path or "",
                    "MD5Checksum": meta.get("_MD5Checksum", ""),
                    "Format": self.format_dropdown.currentText(),
                    "Application": self.app_dropdown.currentText(),
                    "DimensionX": _pick(meta, _DIM_X),
                    "DimensionY": _pick(meta, _DIM_Y),
                    "BitDepth": meta.get("BitDepth", ""),
                    "ColorSpace": meta.get("ColorSpace", ""),
                    "Compression": meta.get("Compression", ""),
                    "CurationFlags": meta.get("_CurationFlags", ""),
                    "Standard": ref.get("Standard", "") if isinstance(ref, dict) else "",
                    "StandardURL": ref.get("URL", "") if isinstance(ref, dict) else "",
                }
                rows.append(row)

            with open(save_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=_CURATION_COLS)
                writer.writeheader()
                writer.writerows(rows)

            QMessageBox.information(self, "Success", "Curation report saved successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save curation report: {str(e)}")

    # === Integrity Verification ===
    def _current_batch_sources(self):
        """Returns the (file_path, _, meta) list backing the loaded batch,
        falling back to the single displayed file when nothing was batch-loaded."""
        if self.loaded_files:
            return self.loaded_files
        if self.current_display_file_path and self.current_display_metadata:
            return [(self.current_display_file_path, "", self.current_display_metadata)]
        return []

    def save_checksums(self):
        sources = self._current_batch_sources()
        if not sources:
            return

        folder = os.path.dirname(sources[0][0])
        checksums = {}
        for file_path, _, meta in sources:
            md5 = meta.get("_MD5Checksum") or compute_md5(file_path)
            if md5:
                checksums[os.path.basename(file_path)] = md5

        try:
            out_path = save_checksums(folder, checksums)
            QMessageBox.information(
                self, "Success",
                f"Checksums saved for {len(checksums)} file(s):\n{out_path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save checksums: {str(e)}")

    def verify_integrity(self):
        sources = self._current_batch_sources()
        if not sources:
            return

        folder = os.path.dirname(sources[0][0])
        stored = load_checksums(folder)
        if stored is None:
            QMessageBox.information(
                self, "No Checksums Found",
                f"No checksums.json found in this folder.\n"
                "Use 'Save Checksums' first to create a baseline."
            )
            return

        current = {}
        for file_path, _, meta in sources:
            md5 = meta.get("_MD5Checksum") or compute_md5(file_path)
            current[os.path.basename(file_path)] = md5

        status_by_filename = verify_checksums(stored, current)

        counts = Counter(status_by_filename.values())
        lines = [
            f"OK: {counts.get('OK', 0)}   "
            f"MODIFIED: {counts.get('MODIFIED', 0)}   "
            f"MISSING: {counts.get('MISSING', 0)}   "
            f"NEW: {counts.get('NEW', 0)}",
            "",
        ]
        for name, status in sorted(status_by_filename.items()):
            if status != "OK":
                lines.append(f"[{status}] {name}")

        dialog = QDialog(self)
        dialog.setWindowTitle("Integrity Verification Result")
        dialog.setMinimumSize(480, 360)
        dialog_layout = QVBoxLayout()

        result_display = QTextEdit()
        result_display.setReadOnly(True)
        result_display.setPlainText("\n".join(lines))
        dialog_layout.addWidget(result_display)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        dialog_layout.addWidget(close_btn)

        dialog.setLayout(dialog_layout)
        dialog.exec_()

    # === Sidecar JSON ===
    def save_sidecar(self):
        """Writes metadata as a .json sidecar beside the currently displayed image."""
        if not self.current_display_file_path or not self.current_display_metadata:
            return

        out_path = sidecar_path_for(self.current_display_file_path)

        if os.path.exists(out_path):
            confirm = QMessageBox.warning(
                self,
                "Save Sidecar JSON",
                f"A sidecar file already exists:\n{out_path}\n\nOverwrite it?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if confirm != QMessageBox.Yes:
                return

        try:
            written = write_sidecar(self.current_display_file_path, self.current_display_metadata)
            QMessageBox.information(self, "Success", f"Sidecar saved:\n{written}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save sidecar: {str(e)}")

    # === Export Functions ===
    def export_as_json(self):
        if not self.all_standardized_metadata:
            return
        save_path, _ = QFileDialog.getSaveFileName(self, "Save JSON", filter="JSON Files (*.json)")
        if save_path:
            try:
                serializable_data = make_json_serializable(self.all_standardized_metadata)
                with open(save_path, 'w', encoding='utf-8') as f:
                    json.dump(serializable_data, f, indent=4)
                QMessageBox.information(self, "Success", "JSON file saved successfully.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save JSON: {str(e)}")

    def export_as_csv(self):
        if not self.all_standardized_metadata:
            return
        save_path, _ = QFileDialog.getSaveFileName(self, "Save CSV", filter="CSV Files (*.csv)")
        if save_path:
            try:
                flat_list = []
                for metadata in self.all_standardized_metadata:
                    flat = {}
                    for key, val in metadata.items():
                        if isinstance(val, list):
                            for idx, entry in enumerate(val):
                                if isinstance(entry, dict):
                                    for subkey, subval in entry.items():
                                        flat[f"{key}.{idx}.{subkey}"] = subval
                                else:
                                    flat[f"{key}.{idx}"] = entry
                        elif isinstance(val, dict):
                            for subkey, subval in val.items():
                                flat[f"{key}.{subkey}"] = subval
                        else:
                            flat[key] = val
                    flat_list.append(flat)

                all_keys = ["ImageName"] + sorted(k for d in flat_list for k in d.keys() if k != "ImageName")
                with open(save_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=all_keys)
                    writer.writeheader()
                    for row in flat_list:
                        writer.writerow(row)
                QMessageBox.information(self, "Success", "CSV file saved successfully.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save CSV: {str(e)}")


def main():
    app = QApplication(sys.argv)
    viewer = MetadataViewer()
    viewer.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
