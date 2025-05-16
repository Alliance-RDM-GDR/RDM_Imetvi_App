# main.py

import sys
import os
import json
import pprint
import csv
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QFileDialog, QMessageBox,
    QLabel, QComboBox
)
from PyQt5.QtCore import Qt

# === Import TIFF and CZI parsers and standardizers ===
from metadata_parsers.tiff_parser import parse_tiff_metadata
from metadata_parsers.czi_parser import parse_czi_metadata
from standardizers.tiff_microscopy_standardizer import standardize_tiff_microscopy_metadata
from standardizers.czi_microscopy_standardizer import standardize_czi_microscopy_metadata
from utils.serialization import make_json_serializable


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
        self.format_dropdown.addItems(["TIFF", "CZI"])
        top_layout.addWidget(self.format_label)
        top_layout.addWidget(self.format_dropdown)

        self.app_label = QLabel("Select Application:")
        self.app_dropdown = QComboBox()
        self.app_dropdown.addItems(["Microscopy"])
        top_layout.addWidget(self.app_label)
        top_layout.addWidget(self.app_dropdown)

        self.file_selector_label = QLabel("Select File:")
        self.file_selector_dropdown = QComboBox()
        self.file_selector_dropdown.currentIndexChanged.connect(self.select_loaded_file)
        self.file_selector_label.hide()
        self.file_selector_dropdown.hide()
        top_layout.addWidget(self.file_selector_label)
        top_layout.addWidget(self.file_selector_dropdown)

        layout.addLayout(top_layout)

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

        layout.addLayout(button_layout)

        # === Metadata display panels ===
        panel_layout = QHBoxLayout()

        self.raw_metadata_display = QTextEdit()
        self.raw_metadata_display.setReadOnly(True)
        self.raw_metadata_display.setPlaceholderText("Raw metadata will appear here")
        panel_layout.addWidget(self.raw_metadata_display)

        self.recommended_metadata_display = QTextEdit()
        self.recommended_metadata_display.setReadOnly(True)
        self.recommended_metadata_display.setPlaceholderText("Recommended metadata will appear here")
        panel_layout.addWidget(self.recommended_metadata_display)

        layout.addLayout(panel_layout)

        self.setLayout(layout)

        # Internal state
        self.last_standardized_metadata = None
        self.last_file_path = None
        self.all_standardized_metadata = []
        self.loaded_files = []

    # === File and Folder Loading ===
    def load_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File")
        if file_path:
            self.display_metadata(file_path, single_file=True)

    def load_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder_path:
            self.loaded_files = []
            self.all_standardized_metadata = []
            self.file_selector_dropdown.clear()

            selected_format = self.format_dropdown.currentText()

            for fname in os.listdir(folder_path):
                full_path = os.path.join(folder_path, fname)
                if os.path.isfile(full_path) and fname.lower().endswith((".tif", ".tiff", ".czi")):
                    try:
                        if selected_format == "TIFF":
                            text_report, raw_metadata = parse_tiff_metadata(full_path, application=self.app_dropdown.currentText())
                            standardized_metadata = standardize_tiff_microscopy_metadata(raw_metadata)
                        elif selected_format == "CZI":
                            text_report, raw_metadata = parse_czi_metadata(full_path, application=self.app_dropdown.currentText())
                            standardized_metadata = standardize_czi_microscopy_metadata(raw_metadata)
                        else:
                            continue

                        self.loaded_files.append((full_path, text_report, standardized_metadata))
                        self.all_standardized_metadata.append(standardized_metadata)
                        self.file_selector_dropdown.addItem(os.path.basename(full_path))
                    except Exception as e:
                        print(f"Failed to process {fname}: {e}")

            if self.loaded_files:
                self.file_selector_label.show()
                self.file_selector_dropdown.show()
                self.file_selector_dropdown.setCurrentIndex(0)
                self.select_loaded_file(0)

            self.export_json_btn.setEnabled(bool(self.loaded_files))
            self.export_csv_btn.setEnabled(bool(self.loaded_files))

    def select_loaded_file(self, index):
        if 0 <= index < len(self.loaded_files):
            file_path, text_report, standardized_metadata = self.loaded_files[index]

            self.raw_metadata_display.clear()
            self.recommended_metadata_display.clear()
            self.raw_metadata_display.append(f"File: {os.path.basename(file_path)}\n")
            self.recommended_metadata_display.append(f"File: {os.path.basename(file_path)}\n")

            self.raw_metadata_display.append(text_report)

            for key, value in standardized_metadata.items():
                if key == "Channels" and isinstance(value, list):
                    self.recommended_metadata_display.append("Channels:")
                    for idx, channel_info in enumerate(value, 1):
                        name = channel_info.get('Name', '')
                        exc = channel_info.get('ExcitationWavelength', 'nm')
                        em = channel_info.get('EmissionWavelength', 'nm')
                        exp = channel_info.get('ExposureTime_sec', 'sec')
                        self.recommended_metadata_display.append(f"  - Channel {idx}: {name} (Exc: {exc} nm, Em: {em} nm, Exp: {exp} sec)")
                else:
                    self.recommended_metadata_display.append(f"{key}: {value}")

    # === Metadata Display ===
    def display_metadata(self, file_path, single_file=False):
        selected_format = self.format_dropdown.currentText()
        selected_app = self.app_dropdown.currentText()

        self.raw_metadata_display.clear()
        self.recommended_metadata_display.clear()
        self.last_standardized_metadata = None
        self.last_file_path = file_path

        self.raw_metadata_display.append(f"File: {os.path.basename(file_path)}\n")
        self.recommended_metadata_display.append(f"File: {os.path.basename(file_path)}\n")

        try:
            if selected_format == "TIFF":
                text_report, raw_metadata = parse_tiff_metadata(file_path, application=selected_app)
                self.last_standardized_metadata = standardize_tiff_microscopy_metadata(raw_metadata)
            elif selected_format == "CZI":
                text_report, raw_metadata = parse_czi_metadata(file_path, application=selected_app)
                self.last_standardized_metadata = standardize_czi_microscopy_metadata(raw_metadata)
            else:
                self.raw_metadata_display.append("Unsupported file format.")
                self.recommended_metadata_display.append("No recommended metadata.")
                return

            self.raw_metadata_display.append(text_report)

            for key, value in self.last_standardized_metadata.items():
                if key == "Channels" and isinstance(value, list):
                    self.recommended_metadata_display.append("Channels:")
                    for idx, channel_info in enumerate(value, 1):
                        name = channel_info.get('Name', '')
                        exc = channel_info.get('ExcitationWavelength', 'nm')
                        em = channel_info.get('EmissionWavelength', 'nm')
                        exp = channel_info.get('ExposureTime_sec', 'sec')
                        self.recommended_metadata_display.append(f"  - Channel {idx}: {name} (Exc: {exc} nm, Em: {em} nm, Exp: {exp} sec)")
                else:
                    self.recommended_metadata_display.append(f"{key}: {value}")

        except Exception as e:
            self.raw_metadata_display.append(f"Error: {str(e)}")
            self.recommended_metadata_display.append("Metadata extraction failed.")

        if single_file and self.last_standardized_metadata:
            self.all_standardized_metadata = [self.last_standardized_metadata]

        self.export_json_btn.setEnabled(bool(self.all_standardized_metadata))
        self.export_csv_btn.setEnabled(bool(self.all_standardized_metadata))

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
                                for subkey, subval in entry.items():
                                    flat[f"{key}.{idx}.{subkey}"] = subval
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
