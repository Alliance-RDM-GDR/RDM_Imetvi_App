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
    QTabWidget, QGroupBox, QSplitter, QAction, QMenu, QShortcut
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QSettings
from PyQt5.QtGui import QPixmap, QTextCharFormat, QKeySequence

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
from metadata_parsers.las_parser import parse_las_metadata, analyze_las_point_data
from metadata_parsers.ppmstar_parser import parse_ppmstar_metadata, PPMSTAR_EXTENSIONS
from metadata_parsers.nifti_parser import parse_nifti_metadata
from metadata_parsers.omezarr_parser import parse_omezarr_metadata, OMEZARR_EXTENSIONS
from metadata_parsers.aim_parser import parse_aim_metadata, AIM_EXTENSIONS
from metadata_parsers.cryoem_parser import parse_cryoem_metadata, CRYOEM_EXTENSIONS
from metadata_parsers.eyelink_parser import parse_eyelink_metadata, EYELINK_EXTENSIONS
from metadata_parsers.vector_parser import parse_vector_metadata, VECTOR_EXTENSIONS
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
from standardizers.ppmstar_simulation_standardizer import standardize_ppmstar_simulation_metadata
from standardizers.nifti_neuroimaging_standardizer import standardize_nifti_neuroimaging_metadata
from standardizers.omezarr_microscopy_standardizer import standardize_omezarr_microscopy_metadata
from standardizers.aim_microct_standardizer import standardize_aim_microct_metadata
from standardizers.cryoem_standardizer import standardize_cryoem_metadata
from standardizers.eyelink_standardizer import standardize_eyelink_metadata
from standardizers.vector_standardizer import standardize_vector_metadata
from utils.serialization import make_json_serializable
from utils.metadata_writer import write_metadata_to_file, SUPPORTED_WRITE_EXTENSIONS, is_write_supported
from utils.sidecar import write_sidecar, sidecar_path_for
from utils.integrity import compute_md5, save_checksums, load_checksums, verify_checksums
from utils.manifest import parse_manifest, check_coverage, verify_manifest, total_size, format_bytes
from utils.thumbnail import generate_thumbnail_bytes
from utils.curation_flags import compute_curation_flags
from utils.compliance_summary import compute_batch_compliance_summary
from utils.wkt_display import pretty_wkt
from utils.bids import get_extension
from metadata_profiles.standards_registry import get_standard_info, get_reference_summary
from metadata_profiles.profile_registry import get_profile, format_label
from metadata_profiles.required_fields_registry import compute_missing_fields
from i18n import tr, set_language, get_language, LANGUAGES
from ui.fields_view import build_recommended_html, format_suggestion
from ui.file_list import FileListPanel, file_flags, summarize
from ui.status_strip import StatusStrip

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
    # Neuroimaging: NIfTI volumes, normally inside a BIDS dataset (sidecar JSON,
    # .bval/.bvec, dataset_description.json are picked up around the image).
    "NIfTI": {
        "extensions": [".nii", ".nii.gz"],
        "parser": parse_nifti_metadata,
        "contexts": ["Neuroimaging (BIDS)"],
    },
    # OME-Zarr image, opened as a .zarr folder or from inside an uncompressed
    # BIDS-Microscopy .tar (light-sheet deposits), never extracted.
    "OME-Zarr": {
        "extensions": OMEZARR_EXTENSIONS,
        "parser": parse_omezarr_metadata,
        "contexts": ["Microscopy (OME-Zarr)"],
    },
    # Scanco micro-CT volumes (.aim, versions 020 and 030) and their
    # segmentations; the .txt dump and Amira .hx script beside them are read too.
    # Cryo-EM micrographs (.mrc) and EER movies from Thermo Fisher EPU, read
    # together with their .xml sidecars.
    "CryoEM": {
        "extensions": CRYOEM_EXTENSIONS,
        "parser": parse_cryoem_metadata,
        "contexts": ["Cryo-EM"],
    },
    # SR Research EyeLink eye-tracking recordings exported to text (.asc).
    "EyeLink": {
        "extensions": EYELINK_EXTENSIONS,
        "parser": parse_eyelink_metadata,
        "contexts": ["Eye Tracking"],
    },
    # Vector GIS: ESRI Shapefile (.shp with .shx/.dbf/.prj) and GeoJSON.
    "Vector": {
        "extensions": VECTOR_EXTENSIONS,
        "parser": parse_vector_metadata,
        "contexts": ["Vector GIS"],
    },
    "AIM": {
        "extensions": AIM_EXTENSIONS,
        "parser": parse_aim_metadata,
        "contexts": ["Micro-CT (Scanco)"],
    },
    # Simulation output, not images: radial profiles, run history, raw 3-D
    # cube blocks and setup files of the PPMstar stellar hydrodynamics code.
    "PPMstar": {
        "extensions": PPMSTAR_EXTENSIONS,
        "parser": parse_ppmstar_metadata,
        "contexts": ["Astrophysical Simulation"],
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
    "PPMstar": {"Astrophysical Simulation": standardize_ppmstar_simulation_metadata},
    "NIfTI": {"Neuroimaging (BIDS)": standardize_nifti_neuroimaging_metadata},
    "OME-Zarr": {"Microscopy (OME-Zarr)": standardize_omezarr_microscopy_metadata},
    "AIM": {"Micro-CT (Scanco)": standardize_aim_microct_metadata},
    "CryoEM": {"Cryo-EM": standardize_cryoem_metadata},
    "EyeLink": {"Eye Tracking": standardize_eyelink_metadata},
    "Vector": {"Vector GIS": standardize_vector_metadata},
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


class ManifestVerifyWorker(QThread):
    """Compares a dataset with its MANIFEST.sha256 off the UI thread.

    mode "coverage" only lists names (fast); mode "full" also streams every
    listed file through SHA-256 and can be cancelled between chunks."""

    progress = pyqtSignal(int, int, str, object, object)  # files done, files total, path, bytes done, bytes total
    done = pyqtSignal(dict)

    def __init__(self, folder, entries, manifest_name, mode):
        super().__init__()
        self.folder = folder
        self.entries = entries
        self.manifest_name = manifest_name
        self.mode = mode
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        out = {"coverage": None, "verify": None, "bytes_total": 0, "error": None}
        try:
            out["coverage"] = check_coverage(self.folder, self.entries, self.manifest_name)
            if self.mode == "full":
                out["verify"] = verify_manifest(
                    self.folder, self.entries,
                    progress=self.progress.emit, cancel=lambda: self._cancelled,
                )
            else:
                out["bytes_total"] = total_size(self.folder, self.entries)
        except Exception as e:
            out["error"] = str(e)
        self.done.emit(out)


# Shared width for the left column (sidebar + thumbnail preview below it) —
# the thumbnail is sized to match so it fills the column's full width while
# staying square, instead of leaving blank space on either side.
SIDEBAR_WIDTH = 260


class MetadataViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setGeometry(100, 100, 1280, 800)
        self.setAcceptDrops(True)

        # Set by main(): only the real application remembers window size, language
        # and last folder; tests and the screenshot script leave it off.
        self.persist_settings = False
        self._last_dir = ""
        self._selector_manual = False
        self._selector_ambiguous = False
        self._skipped_count = 0

        layout = QVBoxLayout()

        # === Toolbar: actions, detected format, language ===
        top_layout = QHBoxLayout()

        self.load_file_btn = QPushButton()
        self.load_file_btn.clicked.connect(self.load_file)
        top_layout.addWidget(self.load_file_btn)

        self.load_folder_btn = QPushButton()
        self.load_folder_btn.clicked.connect(self.load_folder)
        top_layout.addWidget(self.load_folder_btn)

        # Menu entries are QActions: they keep the attribute names the rest of the
        # code uses (setEnabled / setToolTip / setText) and carry the enabled state.
        self.export_json_btn = self._new_action(self.export_as_json)
        self.export_csv_btn = self._new_action(self.export_as_csv)
        self.export_curation_btn = self._new_action(self.export_curation_report)
        self.batch_compliance_btn = self._new_action(self.show_batch_compliance_summary)
        self.export_button, self.export_menu = self._new_menu_button(
            [self.export_json_btn, self.export_csv_btn, self.export_curation_btn, self.batch_compliance_btn])
        top_layout.addWidget(self.export_button)

        self.write_metadata_btn = self._new_action(self.write_metadata)
        self.save_sidecar_btn = self._new_action(self.save_sidecar)
        self.write_button, self.write_menu = self._new_menu_button([self.write_metadata_btn, self.save_sidecar_btn])
        top_layout.addWidget(self.write_button)

        self.save_checksums_btn = self._new_action(self.save_checksums)
        self.verify_integrity_btn = self._new_action(self.verify_integrity)
        # Works on a whole dataset folder, not on the loaded files, so it is
        # never disabled waiting for a load.
        self.verify_manifest_btn = self._new_action(self.verify_manifest, enabled=True)
        self.integrity_button, self.integrity_menu = self._new_menu_button(
            [self.save_checksums_btn, self.verify_integrity_btn, self.verify_manifest_btn])
        top_layout.addWidget(self.integrity_button)

        # Only shown when the displayed file is LAS/LAZ.
        self.analyze_las_btn = QPushButton()
        self.analyze_las_btn.clicked.connect(self.analyze_las_points)
        self.analyze_las_btn.setEnabled(False)
        self.analyze_las_btn.setVisible(False)
        top_layout.addWidget(self.analyze_las_btn)

        self.toggle_preview_btn = QAction(self)
        self.toggle_preview_btn.setCheckable(True)
        self.toggle_preview_btn.triggered.connect(self.toggle_preview_panel)
        self.show_empty_action = QAction(self)
        self.show_empty_action.setCheckable(True)
        self.show_empty_action.toggled.connect(lambda _: self._render_recommended())
        self.change_format_action = QAction(self)
        self.change_format_action.setCheckable(True)
        self.change_format_action.toggled.connect(self._on_change_format_toggled)
        self.view_button, self.view_menu = self._new_menu_button(
            [self.toggle_preview_btn, self.show_empty_action, self.change_format_action])
        top_layout.addWidget(self.view_button)

        top_layout.addStretch()

        # Format and context are auto-selected from the file extension; the two
        # drop-downs only appear when the choice is ambiguous (.tif: TIFF, OME-TIFF,
        # GeoTIFF) or when asked for through View > Change format / context.
        self.detected_label = QLabel()
        top_layout.addWidget(self.detected_label)

        self.selector_box = QWidget()
        selector_layout = QHBoxLayout(self.selector_box)
        selector_layout.setContentsMargins(0, 0, 0, 0)
        self.format_label = QLabel()
        self.format_dropdown = QComboBox()
        self.format_dropdown.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.format_dropdown.addItems(list(FORMAT_REGISTRY.keys()))
        self.format_dropdown.currentTextChanged.connect(self.on_format_changed)
        selector_layout.addWidget(self.format_label)
        selector_layout.addWidget(self.format_dropdown)
        self.app_label = QLabel()
        self.app_dropdown = QComboBox()
        # Context names are set dynamically per format (on_format_changed) and vary
        # a lot in length, so the box adjusts to the current selection.
        self.app_dropdown.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        selector_layout.addWidget(self.app_label)
        selector_layout.addWidget(self.app_dropdown)
        self.selector_box.setVisible(False)
        top_layout.addWidget(self.selector_box)

        self.standards_info_btn = QPushButton()
        self.standards_info_btn.clicked.connect(self.show_standards_info)
        top_layout.addWidget(self.standards_info_btn)

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

        # === Content: left column (file list + preview) | right column (status + tabs) ===
        self.splitter = QSplitter(Qt.Horizontal)

        left_column_widget = QWidget()
        left_column_layout = QVBoxLayout(left_column_widget)
        left_column_layout.setContentsMargins(0, 0, 6, 0)

        self.file_list = FileListPanel()
        self.file_list.fileSelected.connect(self.select_loaded_file)
        self.file_list.setVisible(False)
        left_column_layout.addWidget(self.file_list, 1)

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
        left_column_widget.setMinimumWidth(SIDEBAR_WIDTH + 10)
        self.splitter.addWidget(left_column_widget)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.status_strip = StatusStrip()
        self.status_strip.flagsClicked.connect(lambda: self.tab_widget.setCurrentIndex(2))
        self.status_strip.suggestionsClicked.connect(lambda: self.tab_widget.setCurrentIndex(1))
        self.status_strip.missingClicked.connect(lambda: self.tab_widget.setCurrentIndex(1))
        right_layout.addWidget(self.status_strip)

        self.tab_widget = QTabWidget()

        self.raw_metadata_display = QTextEdit()
        self.raw_metadata_display.setReadOnly(True)
        self.tab_widget.addTab(self.raw_metadata_display, "")

        recommended_tab = QWidget()
        recommended_layout = QVBoxLayout(recommended_tab)
        recommended_layout.setContentsMargins(0, 4, 0, 0)
        self.field_search = QLineEdit()
        self.field_search.setClearButtonEnabled(True)
        self.field_search.textChanged.connect(lambda _: self._render_recommended())
        recommended_layout.addWidget(self.field_search)
        self.recommended_metadata_display = QTextEdit()
        self.recommended_metadata_display.setReadOnly(True)
        recommended_layout.addWidget(self.recommended_metadata_display)
        self.tab_widget.addTab(recommended_tab, "")

        self.curation_display = QTextEdit()
        self.curation_display.setReadOnly(True)
        self.tab_widget.addTab(self.curation_display, "")

        right_layout.addWidget(self.tab_widget)
        self.splitter.addWidget(right_widget)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([300, 980])
        layout.addWidget(self.splitter, 1)

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

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
        self.manifest_worker = None
        self.manifest_progress = None

        self._shortcuts = [
            QShortcut(QKeySequence("Ctrl+O"), self, activated=self.load_file),
            QShortcut(QKeySequence("Ctrl+Shift+O"), self, activated=self.load_folder),
            QShortcut(QKeySequence("Ctrl+E"), self, activated=lambda: self._if_enabled(self.export_json_btn, self.export_as_json)),
            QShortcut(QKeySequence("Ctrl+Shift+E"), self, activated=lambda: self._if_enabled(self.export_csv_btn, self.export_as_csv)),
            QShortcut(QKeySequence("Ctrl+F"), self, activated=self.focus_field_search),
        ]

        self.retranslate_ui()
        self.status_label.setText(tr("ui_status_ready"))

    # === Widget helpers ===
    def _new_action(self, handler, enabled=False):
        action = QAction(self)
        action.triggered.connect(lambda _checked=False: handler())
        action.setEnabled(enabled)
        return action

    def _new_menu_button(self, actions):
        button = QPushButton()
        menu = QMenu(button)
        menu.setToolTipsVisible(True)  # a disabled entry explains itself in its tooltip
        for action in actions:
            menu.addAction(action)
        button.setMenu(menu)
        return button, menu

    @staticmethod
    def _if_enabled(action, handler):
        if action.isEnabled():
            handler()

    def focus_field_search(self):
        self.tab_widget.setCurrentIndex(1)
        self.field_search.setFocus()
        self.field_search.selectAll()

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
        self.standards_info_btn.setText("ⓘ " + tr("btn_standards_info"))
        self.standards_info_btn.setToolTip(tr("tooltip_standards_info"))
        self.language_label.setText(tr("label_language"))

        self.load_file_btn.setText(tr("btn_load_file"))
        self.load_file_btn.setToolTip(tr("tooltip_load_file") + "  (Ctrl+O)")
        self.load_folder_btn.setText(tr("btn_load_folder"))
        self.load_folder_btn.setToolTip(tr("tooltip_load_folder") + "  (Ctrl+Shift+O)")

        self.export_button.setText(tr("group_export") + " ▾")
        self.export_json_btn.setText(tr("btn_export_json") + "\tCtrl+E")
        self.export_json_btn.setToolTip(tr("tooltip_export_json"))
        self.export_csv_btn.setText(tr("btn_export_csv") + "\tCtrl+Shift+E")
        self.export_csv_btn.setToolTip(tr("tooltip_export_csv"))
        self.export_curation_btn.setText(tr("btn_export_curation"))
        self.export_curation_btn.setToolTip(tr("tooltip_export_curation"))
        self.batch_compliance_btn.setText(tr("btn_batch_compliance"))
        self.batch_compliance_btn.setToolTip(tr("tooltip_batch_compliance"))

        self.write_button.setText(tr("group_write") + " ▾")
        self.write_metadata_btn.setText(tr("btn_write_metadata"))
        self.save_sidecar_btn.setText(tr("btn_save_sidecar"))
        self.save_sidecar_btn.setToolTip(tr("tooltip_save_sidecar"))

        self.integrity_button.setText(tr("group_integrity") + " ▾")
        self.save_checksums_btn.setText(tr("btn_save_checksums"))
        self.save_checksums_btn.setToolTip(tr("tooltip_save_checksums"))
        self.verify_integrity_btn.setText(tr("btn_verify_integrity"))
        self.verify_integrity_btn.setToolTip(tr("tooltip_verify_integrity"))
        self.verify_manifest_btn.setText(tr("btn_verify_manifest"))
        self.verify_manifest_btn.setToolTip(tr("tooltip_verify_manifest"))

        self.analyze_las_btn.setText(tr("btn_analyze_las"))
        self.analyze_las_btn.setToolTip(tr("tooltip_analyze_las"))

        self.view_button.setText(tr("group_view") + " ▾")
        self.toggle_preview_btn.setText(
            tr("btn_show_preview") if self.toggle_preview_btn.isChecked() else tr("btn_hide_preview")
        )
        self.toggle_preview_btn.setToolTip(tr("tooltip_toggle_preview"))
        self.show_empty_action.setText(tr("ui_show_empty_fields"))
        self.change_format_action.setText(tr("ui_change_format"))

        self.tab_widget.setTabText(0, tr("tab_raw_metadata"))
        self.tab_widget.setTabText(1, tr("tab_recommended_fields"))
        self.tab_widget.setTabText(2, tr("tab_curation"))
        self.raw_metadata_display.setPlaceholderText(tr("ui_welcome"))
        self.recommended_metadata_display.setPlaceholderText(tr("ui_welcome"))
        self.curation_display.setPlaceholderText(tr("placeholder_curation"))
        self.field_search.setPlaceholderText(tr("ui_search_fields"))

        self.file_list.retranslate()
        self.status_strip.retranslate()
        self._update_detected()

        if not self.thumbnail_display.pixmap() or self.thumbnail_display.pixmap().isNull():
            self.thumbnail_display.setText(tr("label_no_preview"))

    def _update_detected(self):
        if self.current_display_file_path:
            self.detected_label.setText(tr(
                "ui_detected", format=self.format_dropdown.currentText(), context=self.app_dropdown.currentText()))
        else:
            self.detected_label.setText(tr("ui_detected_none"))

    # === Format / context selector visibility ===
    def _on_change_format_toggled(self, checked):
        self._selector_manual = checked
        self._refresh_selector_visibility()

    def _refresh_selector_visibility(self):
        self.selector_box.setVisible(self._selector_manual or self._selector_ambiguous)

    # === Settings (window size, language, last folder) ===
    def restore_settings(self, settings):
        geometry = settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        self._last_dir = settings.value("last_dir", "") or ""

    def closeEvent(self, event):
        if self.persist_settings:
            settings = QSettings("IMetVi", "IMetVi")
            settings.setValue("geometry", self.saveGeometry())
            settings.setValue("language", get_language())
            settings.setValue("last_dir", self._last_dir)
        super().closeEvent(event)

    def _remember_dir(self, path):
        folder = path if os.path.isdir(path) else os.path.dirname(path)
        if folder:
            self._last_dir = folder

    # === Drag and drop ===
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if not paths:
            return
        event.acceptProposedAction()
        if len(paths) == 1:
            self.open_path(paths[0])
        else:
            self.load_paths([p for p in paths if os.path.isfile(p) and get_extension(p) in ALL_EXTENSIONS])

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
            ext = get_extension(file_path).lstrip(".").upper() if file_path else ""
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
        ext = get_extension(file_path)
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
    def set_status(self, text):
        self.status_label.setText(text)

    def _update_actions_enabled(self):
        enabled = bool(self.all_standardized_metadata)
        for action in (self.export_json_btn, self.export_csv_btn, self.export_curation_btn,
                       self.batch_compliance_btn, self.save_checksums_btn, self.verify_integrity_btn):
            action.setEnabled(enabled)

    def _show_single(self):
        """Leaves batch mode: a single file replaces whatever batch was loaded."""
        self.loaded_files = []
        self.file_list.clear()
        self.file_list.setVisible(False)

    def load_file(self):
        filter_str = "Images (" + " ".join(f"*{ext}" for ext in ALL_EXTENSIONS) + ")"
        file_path, _ = QFileDialog.getOpenFileName(self, tr("dialog_select_file"), self._last_dir, filter_str)
        if file_path:
            self.open_path(file_path)

    def open_path(self, path):
        """Opens a file or a folder (the entry point for the dialogs and for drag and drop)."""
        if os.path.isdir(path):
            self.load_folder_path(path)
            return
        if not formats_for_extension(get_extension(path)):
            self.set_status(tr("ui_status_unsupported", name=os.path.basename(path)))
            return
        self._remember_dir(path)
        self.select_format_for_extension(path)
        self._show_single()
        self.display_metadata(path, single_file=True)

    def load_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, tr("dialog_select_folder"), self._last_dir)
        if folder_path:
            self.load_folder_path(folder_path)

    def load_folder_path(self, folder_path):
        self._remember_dir(folder_path)

        if folder_path.lower().endswith(".zarr"):
            # the chosen folder is itself an OME-Zarr image, not a folder of images
            self.select_format_for_extension(folder_path)
            self._show_single()
            self.display_metadata(folder_path, single_file=True)
            return

        file_paths = self.collect_folder_files(folder_path)
        if not file_paths:
            # a dataset root that only holds one sub-folder per sample
            file_paths = self.collect_nested_files(folder_path)

        if not file_paths:
            QMessageBox.information(self, tr("msg_no_files_found_title"), tr("msg_no_files_found_text"))
            return

        self._start_batch(file_paths, os.path.basename(folder_path.rstrip("/\\")) or folder_path)

    def load_paths(self, file_paths):
        """Batch-loads several files dropped together."""
        if file_paths:
            self._remember_dir(file_paths[0])
            self._start_batch(file_paths, os.path.dirname(file_paths[0]))

    def _homogeneous(self, file_paths):
        """
        Selects the format of the first file (a folder load used to parse every file with
        whichever format happened to be selected) and keeps only the files that format
        handles. Returns (kept, number_skipped).
        """
        self.select_format_for_extension(file_paths[0])
        fmt = FORMAT_REGISTRY.get(self.format_dropdown.currentText())
        wanted = set(fmt["extensions"]) if fmt else set(ALL_EXTENSIONS)
        kept = [p for p in file_paths if get_extension(p) in wanted]
        return kept, len(file_paths) - len(kept)

    def _start_batch(self, file_paths, folder_label):
        file_paths, self._skipped_count = self._homogeneous(file_paths)
        self._batch_label = folder_label

        self.loaded_files = []
        self.all_standardized_metadata = []
        self.file_list.clear()
        self.file_list.setVisible(False)

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

    def collect_folder_files(self, folder_path):
        """
        Supported files in a folder. A BIDS dataset root (it holds a
        dataset_description.json) is searched recursively, since images sit
        in sub-*/ses-*/<datatype>/, restricted to the selected format's
        extensions so sidecars and tables are not mistaken for images.
        Otherwise only the folder's own entries are listed. A *.zarr
        directory counts as one image and is never descended into.
        """
        recursive = os.path.isfile(os.path.join(folder_path, "dataset_description.json"))
        wanted = set(ALL_EXTENSIONS)
        if recursive:
            fmt = FORMAT_REGISTRY.get(self.format_dropdown.currentText())
            if fmt:
                wanted = set(fmt["extensions"])
        found = []
        for dirpath, dirnames, filenames in os.walk(folder_path):
            zarr_dirs = [d for d in dirnames if d.lower().endswith(".zarr")]
            for d in sorted(zarr_dirs):
                if get_extension(d) in wanted:
                    found.append(os.path.join(dirpath, d))
            dirnames[:] = sorted(d for d in dirnames if d not in zarr_dirs) if recursive else []
            for fname in sorted(filenames):
                if get_extension(fname) in wanted:
                    found.append(os.path.join(dirpath, fname))
        return found

    def collect_nested_files(self, folder_path):
        """
        Fallback for a folder with no supported files of its own but sub-folders
        that have some (e.g. one folder per micro-CT sample). Searches the whole
        tree, selects the format of the first supported file found, and returns
        only the files that format handles, so the batch stays homogeneous.
        """
        candidates = []
        for dirpath, dirnames, filenames in os.walk(folder_path):
            dirnames.sort()
            candidates += [os.path.join(dirpath, f) for f in sorted(filenames)
                           if get_extension(f) in ALL_EXTENSIONS]
        if not candidates:
            return []
        self.select_format_for_extension(candidates[0])
        fmt = FORMAT_REGISTRY.get(self.format_dropdown.currentText())
        wanted = set(fmt["extensions"]) if fmt else set(ALL_EXTENSIONS)
        return [p for p in candidates if get_extension(p) in wanted]

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
        self.file_list.set_results(results)
        self.file_list.setVisible(len(results) > 1)
        if len(results) > 1:
            self.file_list.select_index(0)
        elif results:
            self.select_loaded_file(0)
        self._update_actions_enabled()

        count, flagged, _ = summarize(results)
        message = tr("ui_status_loaded_folder", n=count, folder=getattr(self, "_batch_label", ""), flagged=flagged)
        if self._skipped_count:
            message += tr("ui_status_skipped", n=self._skipped_count)
        self.set_status(message)

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

    @staticmethod
    def _format_suggestion(sug):
        """One standards suggestion as an HTML fragment, in the active language."""
        return format_suggestion(sug)

    def _render_recommended(self):
        """Rebuilds the Recommended Fields tab (also when the search box or 'show empty' changes)."""
        if not self.current_display_metadata or not self.current_display_file_path:
            return
        self.recommended_metadata_display.setHtml(build_recommended_html(
            self.current_display_metadata,
            get_profile(self.app_dropdown.currentText()),
            os.path.basename(self.current_display_file_path),
            show_empty=self.show_empty_action.isChecked(),
            filter_text=self.field_search.text(),
        ))

    def render_metadata(self, file_path, text_report, standardized_metadata):
        self.current_display_file_path = file_path
        self.current_display_metadata = standardized_metadata
        self.current_display_text_report = text_report
        write_supported = is_write_supported(file_path, self.format_dropdown.currentText())
        self.write_metadata_btn.setEnabled(write_supported)
        self.write_metadata_btn.setToolTip(
            tr("tooltip_write_metadata") if write_supported else tr("tooltip_write_metadata_unsafe")
        )
        self.save_sidecar_btn.setEnabled(bool(file_path))
        is_las = self.format_dropdown.currentText() == "LAS"
        self.analyze_las_btn.setVisible(is_las)
        self.analyze_las_btn.setEnabled(is_las)
        self.update_thumbnail(file_path)

        fname = os.path.basename(file_path)

        # ── Tab 1: Raw Metadata ───────────────────────────────────────────────
        self.raw_metadata_display.clear()
        self.raw_metadata_display.append(f"{tr('label_file')} {fname}\n")
        self.raw_metadata_display.append(text_report)

        # ── Tab 2: Recommended Fields ─────────────────────────────────────────
        suggestions = standardized_metadata.get("_Suggestions") or []
        self._render_recommended()

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
            "INCOMPLETE_DUMP":   "#e74c3c",
            "UNDOCUMENTED_VARIABLES": "#e67e22",
            "RESTART_RECORDS":   "#8e44ad",
            "BIDS_TEMPLATE_METADATA":  "#c0392b",
            "BIDS_DATASET_INCOMPLETE": "#e67e22",
            "NIFTI_NO_SFORM":          "#8e44ad",
            "CRYOEM_TRUNCATED":        "#e74c3c",
            "EYELINK_TRUNCATED":       "#e74c3c",
            "SHAPEFILE_INCOMPLETE":    "#e74c3c",
            "SHAPEFILE_TRUNCATED":     "#e74c3c",
            "VECTOR_COUNT_MISMATCH":   "#c0392b",
            "VECTOR_TWIN_MISMATCH":    "#8e44ad",
            "VECTOR_COORDS_OUT_OF_RANGE": "#c0392b",
            "EYELINK_POOR_VALIDATION": "#c0392b",
            "EYELINK_HIGH_MISSING":    "#8e44ad",
            "EYELINK_HEADER_IDENTIFIERS": "#e67e22",
            "CRYOEM_NO_SIDECAR":       "#e67e22",
            "CRYOEM_PIXEL_MISMATCH":   "#c0392b",
            "CRYOEM_NO_GAIN_REF":      "#e67e22",
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

        if suggestions:
            html += f"<h4 style='margin-bottom:2px;'>{tr('suggestions_title')}</h4><ul>"
            html += "".join(f"<li>{self._format_suggestion(s)}</li>" for s in suggestions)
            html += "</ul>"

        self.curation_display.setHtml(html)

        self.status_strip.set_state((len(file_flags(standardized_metadata)), len(suggestions),
                                     len(standardized_metadata.get("_MissingFields") or [])))
        self._update_detected()

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
            self.analyze_las_btn.setVisible(False)
            self.analyze_las_btn.setEnabled(False)
            self.status_strip.set_state(None)
            self._update_detected()
            self.update_thumbnail(None)
            self.raw_metadata_display.clear()
            self.recommended_metadata_display.clear()
            self.raw_metadata_display.append(f"{tr('label_file')} {os.path.basename(file_path)}\n")
            self.raw_metadata_display.append(tr("text_error_prefix", error=str(e)))
            self.recommended_metadata_display.append(tr("text_metadata_extraction_failed"))
            self.set_status(tr("ui_status_failed", name=os.path.basename(file_path)))

        if single_file and self.last_standardized_metadata:
            self.all_standardized_metadata = [self.last_standardized_metadata]

        self._update_actions_enabled()
        if single_file and self.last_standardized_metadata:
            self.set_status(tr("ui_status_loaded_file", name=os.path.basename(file_path)))

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

    # === Dataset manifest (MANIFEST.sha256) ===
    def verify_manifest(self):
        start_dir = os.path.dirname(self.current_display_file_path) if self.current_display_file_path else ""
        manifest_path, _ = QFileDialog.getOpenFileName(
            self, tr("dialog_select_manifest"), start_dir, "Manifest (*.sha256 *.txt);;All files (*)"
        )
        if not manifest_path:
            return
        try:
            entries, bad_lines = parse_manifest(manifest_path)
        except OSError as e:
            QMessageBox.critical(self, tr("msg_error_title"), tr("msg_manifest_unreadable", error=str(e)))
            return
        if not entries:
            QMessageBox.information(self, tr("msg_manifest_empty_title"), tr("msg_manifest_empty_text"))
            return

        self._manifest_context = {
            "folder": os.path.dirname(manifest_path),
            "name": os.path.basename(manifest_path),
            "entries": entries,
            "bad_lines": bad_lines,
        }
        self._start_manifest_worker("coverage")

    def _start_manifest_worker(self, mode):
        ctx = self._manifest_context
        self.manifest_progress = QProgressDialog(self)
        self.manifest_progress.setWindowTitle(tr("progress_manifest_title"))
        self.manifest_progress.setMinimumDuration(0)
        if mode == "coverage":
            self.manifest_progress.setLabelText(tr("progress_manifest_scanning"))
            self.manifest_progress.setRange(0, 0)     # busy indicator: total unknown
            self.manifest_progress.setCancelButton(None)
        else:
            self.manifest_progress.setCancelButtonText(tr("progress_cancel"))
            self.manifest_progress.setRange(0, 1000)
            self.manifest_progress.setValue(0)

        self.manifest_worker = ManifestVerifyWorker(ctx["folder"], ctx["entries"], ctx["name"], mode)
        self.manifest_worker.progress.connect(self.on_manifest_progress)
        self.manifest_worker.done.connect(lambda out, m=mode: self.on_manifest_done(m, out))
        # cancel() only raises a flag: the worker stops between chunks and
        # still returns the partial results, unlike terminate().
        self.manifest_progress.canceled.connect(self.manifest_worker.cancel)
        self.manifest_worker.start()

    def on_manifest_progress(self, files_done, files_total, rel_path, bytes_done, bytes_total):
        if self.manifest_progress is None:
            return
        if rel_path:
            self.manifest_progress.setLabelText(tr(
                "progress_manifest_hashing", filename=rel_path, current=files_done + 1, total=files_total,
                done=format_bytes(bytes_done), size=format_bytes(bytes_total),
            ))
        self.manifest_progress.setValue(int(1000 * bytes_done / bytes_total) if bytes_total else 0)

    def on_manifest_done(self, mode, out):
        if self.manifest_progress is not None:
            self.manifest_progress.canceled.disconnect()
            self.manifest_progress.close()
            self.manifest_progress = None
        if out.get("error"):
            QMessageBox.critical(self, tr("msg_error_title"), tr("manifest_error", error=out["error"]))
            return

        ctx = self._manifest_context
        cov, verify = out["coverage"], out["verify"]
        limit = 200

        def listing(title_key, items):
            if not items:
                return []
            lines = ["", tr(title_key)] + [f"  {p}" for p in items[:limit]]
            if len(items) > limit:
                lines.append("  " + tr("manifest_more", count=len(items) - limit))
            return lines

        lines = [tr("manifest_coverage_summary", listed=cov["listed"], on_disk=cov["on_disk"],
                    unlisted=len(cov["unlisted"]), missing=len(cov["missing"]))]
        if ctx["bad_lines"]:
            lines.append(tr("manifest_bad_lines", count=len(ctx["bad_lines"]), line=ctx["bad_lines"][0][0]))
        lines += listing("manifest_section_unlisted", cov["unlisted"])
        lines += listing("manifest_section_missing", cov["missing"])

        offer_verify = verify is None
        if verify is not None:
            counts = Counter(verify["status"].values())
            lines += ["", tr("manifest_checksum_summary", ok=counts.get("OK", 0), modified=counts.get("MODIFIED", 0),
                             missing=counts.get("MISSING", 0), unreadable=counts.get("UNREADABLE", 0),
                             unsafe=counts.get("UNSAFE_PATH", 0))]
            if verify["cancelled"]:
                lines.append(tr("manifest_cancelled", done=len(verify["status"]), total=len(ctx["entries"])))
            problems = sorted(p for p, s in verify["status"].items() if s != "OK")
            if problems:
                lines += ["", tr("manifest_section_problems")]
                lines += [f"  [{verify['status'][p]}] {p}" for p in problems[:limit]]
                if len(problems) > limit:
                    lines.append("  " + tr("manifest_more", count=len(problems) - limit))
            elif not verify["cancelled"]:
                lines += ["", tr("manifest_all_ok")]
        else:
            lines += ["", tr("manifest_checksum_hint", size=format_bytes(out["bytes_total"]))]

        title = tr("dialog_title_manifest_coverage" if offer_verify else "dialog_title_manifest_result")
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setMinimumSize(640, 440)
        dialog_layout = QVBoxLayout()
        display = QTextEdit()
        display.setReadOnly(True)
        display.setPlainText("\n".join(lines))
        dialog_layout.addWidget(display)

        buttons = QHBoxLayout()
        if offer_verify:
            verify_btn = QPushButton(tr("btn_manifest_verify_checksums", size=format_bytes(out["bytes_total"])))
            verify_btn.clicked.connect(lambda: dialog.done(2))
            buttons.addWidget(verify_btn)
        close_btn = QPushButton(tr("btn_close"))
        close_btn.clicked.connect(dialog.reject)
        buttons.addWidget(close_btn)
        dialog_layout.addLayout(buttons)
        dialog.setLayout(dialog_layout)

        if dialog.exec_() == 2:
            self._start_manifest_worker("full")

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

    # === LiDAR point-data analysis ===
    def analyze_las_points(self):
        """
        Reads the currently displayed LAS/LAZ file's full point records
        (not just the header) to report what only a point-level scan can
        answer: the point classification breakdown, scan angle range, GPS
        time range (when the point format stores it), and flight-line
        count. Deliberately on-demand — see analyze_las_point_data()'s
        docstring for why this isn't part of the normal load path.
        """
        if not self.current_display_file_path:
            return

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            result = analyze_las_point_data(self.current_display_file_path)
        finally:
            QApplication.restoreOverrideCursor()

        fname = os.path.basename(self.current_display_file_path)

        if "Error" in result:
            QMessageBox.critical(self, tr("msg_error_title"), result["Error"])
            return

        lines = [tr("las_analysis_header", filename=fname), ""]

        classification_counts = result.get("ClassificationCounts") or {}
        total_points = sum(classification_counts.values())
        if classification_counts:
            lines.append(tr("las_classification_header"))
            for name, count in sorted(classification_counts.items(), key=lambda kv: -kv[1]):
                pct = (count / total_points * 100) if total_points else 0
                lines.append(f"  - {name}: {count:,} ({pct:.1f}%)")
            lines.append("")

        if result.get("ScanAngleMin") is not None:
            lines.append(
                tr(
                    "las_scan_angle_range",
                    min=result["ScanAngleMin"],
                    max=result["ScanAngleMax"],
                )
            )

        if result.get("HasGPSTime"):
            gps_type = result.get("GPSTimeType") or ""
            lines.append(
                tr(
                    "las_gps_time_range",
                    min=result["GPSTimeMin"],
                    max=result["GPSTimeMax"],
                    type=gps_type,
                )
            )
        else:
            lines.append(tr("las_gps_time_unavailable"))

        lines.append(tr("las_flight_line_count", count=result.get("FlightLineCount", 0)))
        lines.append("")
        lines.append(tr("las_sensor_note"))

        dialog = QDialog(self)
        dialog.setWindowTitle(tr("dialog_title_las_analysis"))
        dialog.setMinimumSize(480, 380)
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
    settings = QSettings("IMetVi", "IMetVi")
    set_language(settings.value("language", "EN"))
    viewer = MetadataViewer()
    viewer.persist_settings = True
    viewer.restore_settings(settings)
    viewer.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
