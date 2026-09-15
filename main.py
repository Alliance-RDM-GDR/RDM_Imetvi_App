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
    QTabWidget, QGroupBox
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QPixmap, QTextCharFormat

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
from metadata_parsers.las_parser import parse_las_metadata
from standardizers.tiff_microscopy_standardizer import standardize_tiff_microscopy_metadata
from standardizers.tiff_general_standardizer import standardize_tiff_general_metadata
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
from standardizers.las_lidar_standardizer import standardize_las_lidar_metadata
from utils.serialization import make_json_serializable
from utils.metadata_writer import write_metadata_to_file, SUPPORTED_WRITE_EXTENSIONS, is_write_supported
from utils.sidecar import write_sidecar, sidecar_path_for
from utils.integrity import compute_md5, save_checksums, load_checksums, verify_checksums
from utils.thumbnail import generate_thumbnail_bytes
from utils.curation_flags import compute_curation_flags
from utils.compliance_summary import compute_batch_compliance_summary
from metadata_profiles.standards_registry import get_standard_info, get_reference_summary
from metadata_profiles.profile_registry import get_profile, format_label
from metadata_profiles.required_fields_registry import compute_missing_fields
from i18n import tr, set_language, get_language, LANGUAGES

# === Format / Context registries ===
# Each format declares which extensions it handles, its parser, and which
# application contexts (standardizer + profile) are valid for it.
FORMAT_REGISTRY = {
    "TIFF": {
        "extensions": [".tif", ".tiff"],
        "parser": parse_tiff_metadata,
        # TIFF is a general-purpose container, not just a microscopy
        # format — it's equally common for scans, scientific illustrations,
        # and general photography. Both contexts are offered; the dropdown
        # defaults to the first ("Microscopy") since that's this app's
        # primary use case, but "General / EXIF" is one click away.
        "contexts": ["Microscopy", "General / EXIF"],
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
    "LAS": {
        "extensions": [".las", ".laz"],
        "parser": parse_las_metadata,
        "contexts": ["Remote Sensing (LiDAR)"],
    },
}

# Maps each (format, context) pair to the standardizer that produces that
# context's field set. A format can support more than one context — TIFF
# is used for both microscopy captures and general photographs/scans/
# illustrations, and each needs its own standardizer, since the same raw
# tags map to a different set of REMBI/EXIF/etc. fields depending on what
# the file actually represents.
FORMAT_STANDARDIZERS = {
    "TIFF": {
        "Microscopy": standardize_tiff_microscopy_metadata,
        "General / EXIF": standardize_tiff_general_metadata,
    },
    "CZI": {"Microscopy": standardize_czi_microscopy_metadata},
    "OME-TIFF": {"Microscopy (OME)": standardize_ome_microscopy_metadata},
    "GeoTIFF": {"Remote Sensing": standardize_geotiff_remote_sensing_metadata},
    "JPG": {"General / EXIF": standardize_jpg_general_metadata},
    "DICOM": {"Medical Imaging": standardize_dicom_medical_metadata},
    "FITS": {"Astronomy": standardize_fits_astronomy_metadata},
    "HDF5": {"General / HDF5": standardize_hdf5_general_metadata},
    "PNG": {"General / EXIF": standardize_png_general_metadata},
    "LIF": {"Microscopy (Leica)": standardize_lif_microscopy_metadata},
    "NetCDF": {"Remote Sensing (NetCDF)": standardize_netcdf_remote_sensing_metadata},
    "LAS": {"Remote Sensing (LiDAR)": standardize_las_lidar_metadata},
}


def get_standardizer(format_name, context_name):
    """
    Returns the standardizer function for a (format, context) pair. Falls
    back to the format's only/first registered standardizer if the exact
    context isn't found there — defensive only; the UI always populates
    context choices from FORMAT_REGISTRY, so this matters only if the two
    registries ever drift out of sync.
    """
    per_context = FORMAT_STANDARDIZERS.get(format_name, {})
    if context_name in per_context:
        return per_context[context_name]
    return next(iter(per_context.values()), None)


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
        standardizer = get_standardizer(self.format_name, self.app_name)
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
                standardized_metadata["_MissingFields"] = compute_missing_fields(
                    self.format_name, standardized_metadata, self.app_name
                )
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


# Shared width for the left column (sidebar + thumbnail preview below it) —
# the thumbnail is sized to match so it fills the column's full width while
# staying square, instead of leaving blank space on either side.
SIDEBAR_WIDTH = 260


class MetadataViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setGeometry(100, 100, 1000, 700)

        layout = QVBoxLayout()

        # === Top layout ===
        top_layout = QHBoxLayout()

        self.format_label = QLabel()
        self.format_dropdown = QComboBox()
        self.format_dropdown.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.format_dropdown.addItems(list(FORMAT_REGISTRY.keys()))
        self.format_dropdown.currentTextChanged.connect(self.on_format_changed)
        top_layout.addWidget(self.format_label)
        top_layout.addWidget(self.format_dropdown)

        self.app_label = QLabel()
        self.app_dropdown = QComboBox()
        # Context names are set dynamically per format (on_format_changed) and
        # vary a lot in length ("Microscopy" vs "Remote Sensing (NetCDF)") —
        # AdjustToContents keeps the box wide enough to show the current
        # selection in full instead of a fixed width truncating longer names.
        self.app_dropdown.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        top_layout.addWidget(self.app_label)
        top_layout.addWidget(self.app_dropdown)

        self.standards_info_btn = QPushButton()
        self.standards_info_btn.clicked.connect(self.show_standards_info)
        top_layout.addWidget(self.standards_info_btn)

        self.file_selector_label = QLabel()
        self.file_selector_dropdown = QComboBox()
        self.file_selector_dropdown.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.file_selector_dropdown.setMaximumWidth(380)
        self.file_selector_dropdown.currentIndexChanged.connect(self.select_loaded_file)
        self.file_selector_label.hide()
        self.file_selector_dropdown.hide()
        top_layout.addWidget(self.file_selector_label)
        top_layout.addWidget(self.file_selector_dropdown)

        top_layout.addStretch()

        self.language_label = QLabel()
        self.language_dropdown = QComboBox()
        self.language_dropdown.addItems(list(LANGUAGES.keys()))
        self.language_dropdown.setCurrentText(get_language())
        self.language_dropdown.currentTextChanged.connect(self.on_language_changed)
        top_layout.addWidget(self.language_label)
        top_layout.addWidget(self.language_dropdown)

        layout.addLayout(top_layout)

        # Initialize the application dropdown for the default format
        self.on_format_changed(self.format_dropdown.currentText())

        # === Content row: action sidebar + thumbnail preview + tabbed metadata ===
        content_layout = QHBoxLayout()

        # --- Left column: action sidebar (grouped, titled sections) with the
        # thumbnail preview stacked below it, instead of beside it — keeps
        # the sidebar wide enough for longer translated button labels
        # (French routinely runs longer than English) without competing with
        # the preview for horizontal space.
        left_column_widget = QWidget()
        left_column_layout = QVBoxLayout()
        left_column_layout.setContentsMargins(0, 0, 0, 0)

        sidebar_widget = QWidget()
        sidebar_widget.setFixedWidth(SIDEBAR_WIDTH)
        sidebar_layout = QVBoxLayout()
        sidebar_layout.setContentsMargins(0, 0, 0, 0)

        self.file_group = QGroupBox()
        file_group_layout = QVBoxLayout()

        self.load_file_btn = QPushButton()
        self.load_file_btn.clicked.connect(self.load_file)
        file_group_layout.addWidget(self.load_file_btn)

        self.load_folder_btn = QPushButton()
        self.load_folder_btn.clicked.connect(self.load_folder)
        file_group_layout.addWidget(self.load_folder_btn)

        self.file_group.setLayout(file_group_layout)
        sidebar_layout.addWidget(self.file_group)

        self.export_group = QGroupBox()
        export_group_layout = QVBoxLayout()

        self.export_json_btn = QPushButton()
        self.export_json_btn.clicked.connect(self.export_as_json)
        self.export_json_btn.setEnabled(False)
        export_group_layout.addWidget(self.export_json_btn)

        self.export_csv_btn = QPushButton()
        self.export_csv_btn.clicked.connect(self.export_as_csv)
        self.export_csv_btn.setEnabled(False)
        export_group_layout.addWidget(self.export_csv_btn)

        self.export_curation_btn = QPushButton()
        self.export_curation_btn.clicked.connect(self.export_curation_report)
        self.export_curation_btn.setEnabled(False)
        export_group_layout.addWidget(self.export_curation_btn)

        self.batch_compliance_btn = QPushButton()
        self.batch_compliance_btn.clicked.connect(self.show_batch_compliance_summary)
        self.batch_compliance_btn.setEnabled(False)
        export_group_layout.addWidget(self.batch_compliance_btn)

        self.export_group.setLayout(export_group_layout)
        sidebar_layout.addWidget(self.export_group)

        self.write_group = QGroupBox()
        write_group_layout = QVBoxLayout()

        self.write_metadata_btn = QPushButton()
        self.write_metadata_btn.clicked.connect(self.write_metadata)
        self.write_metadata_btn.setEnabled(False)
        write_group_layout.addWidget(self.write_metadata_btn)

        self.save_sidecar_btn = QPushButton()
        self.save_sidecar_btn.clicked.connect(self.save_sidecar)
        self.save_sidecar_btn.setEnabled(False)
        write_group_layout.addWidget(self.save_sidecar_btn)

        self.write_group.setLayout(write_group_layout)
        sidebar_layout.addWidget(self.write_group)

        self.integrity_group = QGroupBox()
        integrity_group_layout = QVBoxLayout()

        self.save_checksums_btn = QPushButton()
        self.save_checksums_btn.clicked.connect(self.save_checksums)
        self.save_checksums_btn.setEnabled(False)
        integrity_group_layout.addWidget(self.save_checksums_btn)

        self.verify_integrity_btn = QPushButton()
        self.verify_integrity_btn.clicked.connect(self.verify_integrity)
        self.verify_integrity_btn.setEnabled(False)
        integrity_group_layout.addWidget(self.verify_integrity_btn)

        self.integrity_group.setLayout(integrity_group_layout)
        sidebar_layout.addWidget(self.integrity_group)

        self.view_group = QGroupBox()
        view_group_layout = QVBoxLayout()

        self.toggle_preview_btn = QPushButton()
        self.toggle_preview_btn.setCheckable(True)
        self.toggle_preview_btn.clicked.connect(self.toggle_preview_panel)
        view_group_layout.addWidget(self.toggle_preview_btn)

        self.view_group.setLayout(view_group_layout)
        sidebar_layout.addWidget(self.view_group)

        sidebar_layout.addStretch()
        sidebar_widget.setLayout(sidebar_layout)
        left_column_layout.addWidget(sidebar_widget)

        self.preview_panel = QWidget()
        preview_layout = QVBoxLayout()
        preview_layout.setContentsMargins(0, 0, 0, 0)

        self.thumbnail_display = QLabel()
        self.thumbnail_display.setAlignment(Qt.AlignCenter)
        self.thumbnail_display.setFixedSize(SIDEBAR_WIDTH, SIDEBAR_WIDTH)
        self.thumbnail_display.setStyleSheet(
            "border: 1px solid palette(mid); background: palette(base);"
        )
        preview_layout.addWidget(self.thumbnail_display)
        self.preview_panel.setLayout(preview_layout)
        left_column_layout.addWidget(self.preview_panel)

        left_column_layout.addStretch()
        left_column_widget.setLayout(left_column_layout)
        content_layout.addWidget(left_column_widget)

        # === Metadata display — tabbed view ===
        self.tab_widget = QTabWidget()

        self.raw_metadata_display = QTextEdit()
        self.raw_metadata_display.setReadOnly(True)
        self.tab_widget.addTab(self.raw_metadata_display, "")

        self.recommended_metadata_display = QTextEdit()
        self.recommended_metadata_display.setReadOnly(True)
        self.tab_widget.addTab(self.recommended_metadata_display, "")

        self.curation_display = QTextEdit()
        self.curation_display.setReadOnly(True)
        self.tab_widget.addTab(self.curation_display, "")

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
        self.current_display_text_report = ""
        self.folder_worker = None
        self.progress_dialog = None

        self.retranslate_ui()

    # === Language ===
    def on_language_changed(self, lang_code):
        set_language(lang_code)
        self.retranslate_ui()
        # Re-render the current file (if any) so dynamic curation/error text
        # picks up the new language too.
        if self.current_display_file_path and self.current_display_metadata:
            self.render_metadata(
                self.current_display_file_path,
                self.current_display_text_report,
                self.current_display_metadata,
            )
        else:
            self.update_thumbnail(None)

    def retranslate_ui(self):
        self.setWindowTitle(tr("window_title"))

        self.format_label.setText(tr("label_select_format"))
        self.app_label.setText(tr("label_select_application"))
        self.standards_info_btn.setText(tr("btn_standards_info"))
        self.file_selector_label.setText(tr("label_select_file"))
        self.language_label.setText(tr("label_language"))

        self.file_group.setTitle(tr("group_file"))
        self.load_file_btn.setText(tr("btn_load_file"))
        self.load_folder_btn.setText(tr("btn_load_folder"))

        self.export_group.setTitle(tr("group_export"))
        self.export_json_btn.setText(tr("btn_export_json"))
        self.export_csv_btn.setText(tr("btn_export_csv"))
        self.export_curation_btn.setText(tr("btn_export_curation"))
        self.batch_compliance_btn.setText(tr("btn_batch_compliance"))
        self.batch_compliance_btn.setToolTip(tr("tooltip_batch_compliance"))

        self.write_group.setTitle(tr("group_write"))
        self.write_metadata_btn.setText(tr("btn_write_metadata"))
        self.save_sidecar_btn.setText(tr("btn_save_sidecar"))
        self.save_sidecar_btn.setToolTip(tr("tooltip_save_sidecar"))

        self.integrity_group.setTitle(tr("group_integrity"))
        self.save_checksums_btn.setText(tr("btn_save_checksums"))
        self.save_checksums_btn.setToolTip(tr("tooltip_save_checksums"))
        self.verify_integrity_btn.setText(tr("btn_verify_integrity"))
        self.verify_integrity_btn.setToolTip(tr("tooltip_verify_integrity"))

        self.view_group.setTitle(tr("group_view"))
        self.toggle_preview_btn.setText(
            tr("btn_show_preview") if self.toggle_preview_btn.isChecked() else tr("btn_hide_preview")
        )

        self.tab_widget.setTabText(0, tr("tab_raw_metadata"))
        self.tab_widget.setTabText(1, tr("tab_recommended_fields"))
        self.tab_widget.setTabText(2, tr("tab_curation"))
        self.raw_metadata_display.setPlaceholderText(tr("placeholder_raw_metadata"))
        self.recommended_metadata_display.setPlaceholderText(tr("placeholder_recommended_fields"))
        self.curation_display.setPlaceholderText(tr("placeholder_curation"))

        if not self.thumbnail_display.pixmap() or self.thumbnail_display.pixmap().isNull():
            self.thumbnail_display.setText(tr("label_no_preview"))

    # === Thumbnail Preview ===
    def toggle_preview_panel(self, checked):
        self.preview_panel.setVisible(not checked)
        self.toggle_preview_btn.setText(tr("btn_show_preview") if checked else tr("btn_hide_preview"))

    def update_thumbnail(self, file_path):
        thumb_bytes = generate_thumbnail_bytes(file_path) if file_path else None

        if thumb_bytes:
            pixmap = QPixmap()
            pixmap.loadFromData(thumb_bytes)
            self.thumbnail_display.setPixmap(
                pixmap.scaled(SIDEBAR_WIDTH, SIDEBAR_WIDTH, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        else:
            self.thumbnail_display.setPixmap(QPixmap())
            ext = os.path.splitext(file_path)[1].lstrip(".").upper() if file_path else ""
            self.thumbnail_display.setText(ext if ext else tr("label_no_preview"))

    # === Standards Documentation ===
    def show_standards_info(self):
        context_name = self.app_dropdown.currentText()
        info = get_standard_info(context_name)

        dialog = QDialog(self)
        dialog.setWindowTitle(tr("dialog_title_metadata_standard", context=context_name))
        dialog.setMinimumWidth(520)
        dialog_layout = QVBoxLayout()

        text_label = QLabel()
        text_label.setWordWrap(True)
        text_label.setTextFormat(Qt.RichText)
        text_label.setOpenExternalLinks(True)

        if not info:
            text_label.setText(tr("text_no_standards_doc", context=context_name))
        else:
            covered_html = "".join(f"<li>{item}</li>" for item in info["covered"])
            not_covered_html = "".join(f"<li>{item}</li>" for item in info["not_covered"])

            html = (
                f"<h3>{info['standard_name']}</h3>"
                f"<p><a href=\"{info['reference_url']}\">{info['reference_url']}</a></p>"
                f"<p><a href=\"{info['secondary_url']}\">{info['secondary_label']}</a></p>"
                f"<p><b>{tr('text_covers')}</b></p>"
                f"<ul>{covered_html}</ul>"
                f"<p><b>{tr('text_not_covered')}</b></p>"
                f"<ul>{not_covered_html}</ul>"
            )
            text_label.setText(html)

        dialog_layout.addWidget(text_label)

        close_btn = QPushButton(tr("btn_close"))
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
        standardizer = get_standardizer(selected_format, selected_app)
        standardized_metadata = standardizer(raw_metadata)

        reference = get_reference_summary(selected_app)
        if reference:
            standardized_metadata["_StandardReference"] = reference

        standardized_metadata["_MissingFields"] = compute_missing_fields(
            selected_format, standardized_metadata, selected_app
        )

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
        file_path, _ = QFileDialog.getOpenFileName(self, tr("dialog_select_file"), filter=filter_str)
        if file_path:
            self.select_format_for_extension(file_path)
            self.display_metadata(file_path, single_file=True)

    def load_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, tr("dialog_select_folder"))
        if not folder_path:
            return

        file_paths = [
            os.path.join(folder_path, fname)
            for fname in os.listdir(folder_path)
            if os.path.isfile(os.path.join(folder_path, fname))
            and os.path.splitext(fname)[1].lower() in ALL_EXTENSIONS
        ]

        if not file_paths:
            QMessageBox.information(self, tr("msg_no_files_found_title"), tr("msg_no_files_found_text"))
            return

        self.loaded_files = []
        self.all_standardized_metadata = []
        self.file_selector_dropdown.clear()

        selected_format = self.format_dropdown.currentText()
        selected_app = self.app_dropdown.currentText()

        self.progress_dialog = QProgressDialog(tr("progress_loading_files"), tr("progress_cancel"), 0, len(file_paths), self)
        self.progress_dialog.setWindowTitle(tr("progress_batch_loading_title"))
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setValue(0)

        self.folder_worker = FolderLoadWorker(file_paths, selected_format, selected_app)
        self.folder_worker.progress.connect(self.on_folder_load_progress)
        self.folder_worker.finished.connect(self.on_folder_load_finished)
        self.progress_dialog.canceled.connect(self.folder_worker.terminate)
        self.folder_worker.start()

    def on_folder_load_progress(self, current, total, filename):
        if self.progress_dialog is not None:
            self.progress_dialog.setLabelText(tr("progress_processing", filename=filename, current=current, total=total))
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
        self.batch_compliance_btn.setEnabled(bool(self.loaded_files))
        self.save_checksums_btn.setEnabled(bool(self.loaded_files))
        self.verify_integrity_btn.setEnabled(bool(self.loaded_files))

    def select_loaded_file(self, index):
        if 0 <= index < len(self.loaded_files):
            file_path, text_report, standardized_metadata = self.loaded_files[index]
            self.render_metadata(file_path, text_report, standardized_metadata)

    @staticmethod
    def _reset_text_format(text_edit):
        """
        Resets a QTextEdit's insertion character format to the widget's
        default. QTextEdit.append() with an HTML fragment (used for the
        colored warning spans below) leaves the *next* insertion using
        whatever character format the HTML ended on — clear() does not
        reset this. Without this reset, a colored span that happens to be
        the last thing appended (e.g. the final flagged variable in a long
        list) leaves every subsequent append(), including ones for a
        completely different file loaded later, colored the same way.
        """
        cursor = text_edit.textCursor()
        cursor.setCharFormat(QTextCharFormat())
        text_edit.setTextCursor(cursor)

    def render_metadata(self, file_path, text_report, standardized_metadata):
        self.current_display_file_path = file_path
        self.current_display_metadata = standardized_metadata
        self.current_display_text_report = text_report
        write_supported = is_write_supported(file_path, self.format_dropdown.currentText())
        self.write_metadata_btn.setEnabled(write_supported)
        self.write_metadata_btn.setToolTip("" if write_supported else tr("tooltip_write_metadata_unsafe"))
        self.save_sidecar_btn.setEnabled(bool(file_path))
        self.update_thumbnail(file_path)

        fname = os.path.basename(file_path)

        # ── Tab 1: Raw Metadata ───────────────────────────────────────────────
        self.raw_metadata_display.clear()
        self.raw_metadata_display.append(f"{tr('label_file')} {fname}\n")
        self.raw_metadata_display.append(text_report)

        # ── Tab 2: Recommended Fields ─────────────────────────────────────────
        self.recommended_metadata_display.clear()
        self._reset_text_format(self.recommended_metadata_display)
        self.recommended_metadata_display.append(f"{tr('label_file')} {fname}\n")

        _CURATION_KEYS = {"_CurationFlags", "_MD5Checksum", "_StandardReference", "_MissingFields"}
        active_profile = get_profile(self.app_dropdown.currentText())

        missing_fields = standardized_metadata.get("_MissingFields") or []
        if missing_fields:
            missing_labels = ", ".join(format_label(k, active_profile) for k in missing_fields)
            self.recommended_metadata_display.append(
                f'<span style="color:#c0392b; font-weight:bold;">'
                f'⚠ {tr("missing_fields_label")} {missing_labels}</span>'
            )
            self._reset_text_format(self.recommended_metadata_display)
            self.recommended_metadata_display.append("")

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
            elif key == "Variables" and isinstance(value, list):
                # NetCDF/CF variable inventory. standard_name is the CF
                # controlled-vocabulary term that makes a variable
                # machine-interpretable across tools (FAIR: Interoperable) —
                # flag variables that lack one so a curator can spot
                # non-CF-compliant fields at a glance.
                self.recommended_metadata_display.append(f"{display_key}:")
                for v in value:
                    name = v.get("Name", "")
                    std_name = v.get("StandardName", "")
                    units = v.get("Units", "")
                    long_name = v.get("LongName", "")
                    shape = v.get("Shape", "")

                    line = f"  - {name}"
                    if std_name:
                        line += f"  [{std_name}]"
                    else:
                        line += '  <span style="color:#e67e22;">⚠ no standard_name (not CF-mapped)</span>'
                    if units:
                        line += f"  ({units})"
                    if long_name:
                        line += f"  — {long_name}"
                    if shape:
                        line += f"  shape: {shape}"
                    self.recommended_metadata_display.append(line)
                    if not std_name:
                        self._reset_text_format(self.recommended_metadata_display)
            else:
                if isinstance(value, list) and all(isinstance(v, str) for v in value):
                    # Plain string lists (e.g. CoordinateVariables, GeoTIFF's
                    # BandDescriptions) — join instead of dumping a Python
                    # list repr with quotes/brackets.
                    self.recommended_metadata_display.append(f"{display_key}:  {', '.join(value)}")
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
            "NO_CRS_FOUND":      "#e67e22",
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
            flags_html = f'<span style="color:#27ae60; font-weight:bold;">✔ {tr("curation_ok_text")}</span>'

        html = (
            f"<h3 style='margin-bottom:4px;'>{tr('curation_summary_title', filename=fname)}</h3>"
            f"<p><b>{tr('curation_flags_label')}</b> {flags_html}</p>"
        )

        if md5:
            html += f"<p><b>{tr('curation_md5_label')}</b> <code>{md5}</code></p>"

        if comp_warn:
            html += (
                f"<p style='color:#c0392b;'>"
                f"<b>⚠ {tr('curation_compression_warning_label')}</b> {comp_warn}"
                f"</p>"
            )

        if isinstance(ref, dict) and ref.get("Standard"):
            html += (
                f"<p><b>{tr('curation_standard_label')}</b> {ref['Standard']}<br>"
                f"<b>{tr('curation_reference_label')}</b> <a href='{ref.get('URL','')}' style='color:#2980b9;'>"
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
            self.write_metadata_btn.setToolTip("")
            self.save_sidecar_btn.setEnabled(False)
            self.update_thumbnail(None)
            self.raw_metadata_display.clear()
            self.recommended_metadata_display.clear()
            self.raw_metadata_display.append(f"{tr('label_file')} {os.path.basename(file_path)}\n")
            self.raw_metadata_display.append(tr("text_error_prefix", error=str(e)))
            self.recommended_metadata_display.append(tr("text_metadata_extraction_failed"))

        if single_file and self.last_standardized_metadata:
            self.all_standardized_metadata = [self.last_standardized_metadata]

        self.export_json_btn.setEnabled(bool(self.all_standardized_metadata))
        self.export_csv_btn.setEnabled(bool(self.all_standardized_metadata))
        self.export_curation_btn.setEnabled(bool(self.all_standardized_metadata))
        self.batch_compliance_btn.setEnabled(bool(self.all_standardized_metadata))
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
        dialog.setWindowTitle(tr("dialog_title_edit_metadata"))
        dialog.setMinimumSize(540, 600)
        outer_layout = QVBoxLayout()

        note = QLabel(tr("text_edit_metadata_note"))
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

        # Defense in depth: the button is already disabled for unsafe
        # formats (render_metadata), but guard here too in case this is
        # ever called from somewhere that doesn't go through that check.
        if not is_write_supported(self.current_display_file_path, self.format_dropdown.currentText()):
            QMessageBox.warning(self, tr("msg_error_title"), tr("msg_write_unsafe_format"))
            return

        edited_metadata = self.open_metadata_editor(self.current_display_metadata)
        if edited_metadata is None:
            return

        confirm = QMessageBox.warning(
            self,
            tr("dialog_title_write_metadata"),
            tr("confirm_overwrite_metadata", path=self.current_display_file_path),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        try:
            write_metadata_to_file(self.current_display_file_path, edited_metadata)
            self._apply_edited_metadata(edited_metadata)
            QMessageBox.information(self, tr("msg_success_title"), tr("msg_write_metadata_success"))
        except Exception as e:
            QMessageBox.critical(self, tr("msg_error_title"), tr("msg_write_metadata_failed", error=str(e)))

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
            self, tr("dialog_save_curation_report"), filter="CSV Files (*.csv)"
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
            "MissingFields",
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
                    "MissingFields": "; ".join(meta.get("_MissingFields") or []),
                    "Standard": ref.get("Standard", "") if isinstance(ref, dict) else "",
                    "StandardURL": ref.get("URL", "") if isinstance(ref, dict) else "",
                }
                rows.append(row)

            with open(save_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=_CURATION_COLS)
                writer.writeheader()
                writer.writerows(rows)

            QMessageBox.information(self, tr("msg_success_title"), tr("msg_curation_report_success"))
        except Exception as e:
            QMessageBox.critical(self, tr("msg_error_title"), tr("msg_curation_report_failed", error=str(e)))

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
                self, tr("msg_success_title"),
                tr("msg_checksums_success", count=len(checksums), path=out_path)
            )
        except Exception as e:
            QMessageBox.critical(self, tr("msg_error_title"), tr("msg_checksums_failed", error=str(e)))

    def verify_integrity(self):
        sources = self._current_batch_sources()
        if not sources:
            return

        folder = os.path.dirname(sources[0][0])
        stored = load_checksums(folder)
        if stored is None:
            QMessageBox.information(
                self, tr("msg_no_checksums_title"), tr("msg_no_checksums_text")
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
        dialog.setWindowTitle(tr("dialog_title_integrity_result"))
        dialog.setMinimumSize(480, 360)
        dialog_layout = QVBoxLayout()

        result_display = QTextEdit()
        result_display.setReadOnly(True)
        result_display.setPlainText("\n".join(lines))
        dialog_layout.addWidget(result_display)

        close_btn = QPushButton(tr("btn_close"))
        close_btn.clicked.connect(dialog.accept)
        dialog_layout.addWidget(close_btn)

        dialog.setLayout(dialog_layout)
        dialog.exec_()

    def show_batch_compliance_summary(self):
        """
        Aggregates _MissingFields / _CurationFlags across the loaded batch
        into a single readiness snapshot — how many files are fully
        compliant, and which specific fields/flags are the most common
        gaps — so a curator can judge dataset-wide readiness (e.g. before
        depositing) without reading every file's Curation tab individually.
        """
        sources = self._current_batch_sources()
        if not sources:
            return

        summary = compute_batch_compliance_summary(sources)
        active_profile = get_profile(self.app_dropdown.currentText())

        lines = [
            tr(
                "compliance_summary_header",
                compliant=summary["fully_compliant"],
                total=summary["total_files"],
            ),
            "",
        ]

        if summary["missing_field_counts"]:
            lines.append(tr("compliance_missing_fields_header"))
            for field, count in sorted(
                summary["missing_field_counts"].items(), key=lambda kv: -kv[1]
            ):
                label = format_label(field, active_profile)
                lines.append(f"  - {label}: {tr('compliance_files_count', count=count)}")
            lines.append("")

        if summary["curation_flag_counts"]:
            lines.append(tr("compliance_curation_flags_header"))
            for flag, count in sorted(
                summary["curation_flag_counts"].items(), key=lambda kv: -kv[1]
            ):
                lines.append(f"  - {flag}: {tr('compliance_files_count', count=count)}")
            lines.append("")

        if not summary["missing_field_counts"] and not summary["curation_flag_counts"]:
            lines.append(tr("compliance_all_clear"))

        dialog = QDialog(self)
        dialog.setWindowTitle(tr("dialog_title_batch_compliance"))
        dialog.setMinimumSize(480, 360)
        dialog_layout = QVBoxLayout()

        result_display = QTextEdit()
        result_display.setReadOnly(True)
        result_display.setPlainText("\n".join(lines))
        dialog_layout.addWidget(result_display)

        close_btn = QPushButton(tr("btn_close"))
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
                tr("dialog_title_save_sidecar"),
                tr("confirm_overwrite_sidecar", path=out_path),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if confirm != QMessageBox.Yes:
                return

        try:
            written = write_sidecar(self.current_display_file_path, self.current_display_metadata)
            QMessageBox.information(self, tr("msg_success_title"), tr("msg_sidecar_success", path=written))
        except Exception as e:
            QMessageBox.critical(self, tr("msg_error_title"), tr("msg_sidecar_failed", error=str(e)))

    # === Export Functions ===
    def export_as_json(self):
        if not self.all_standardized_metadata:
            return
        save_path, _ = QFileDialog.getSaveFileName(self, tr("dialog_save_json"), filter="JSON Files (*.json)")
        if save_path:
            try:
                serializable_data = make_json_serializable(self.all_standardized_metadata)
                with open(save_path, 'w', encoding='utf-8') as f:
                    json.dump(serializable_data, f, indent=4)
                QMessageBox.information(self, tr("msg_success_title"), tr("msg_json_success"))
            except Exception as e:
                QMessageBox.critical(self, tr("msg_error_title"), tr("msg_json_failed", error=str(e)))

    def export_as_csv(self):
        if not self.all_standardized_metadata:
            return
        save_path, _ = QFileDialog.getSaveFileName(self, tr("dialog_save_csv"), filter="CSV Files (*.csv)")
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
                QMessageBox.information(self, tr("msg_success_title"), tr("msg_csv_success"))
            except Exception as e:
                QMessageBox.critical(self, tr("msg_error_title"), tr("msg_csv_failed", error=str(e)))


def main():
    app = QApplication(sys.argv)
    viewer = MetadataViewer()
    viewer.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
