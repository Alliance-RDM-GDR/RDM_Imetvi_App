import sys
import os
import xml.etree.ElementTree as ET
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QPushButton, 
                             QTextEdit, QFileDialog, QMessageBox, QHBoxLayout)
from PyQt5.QtCore import Qt

try:
    import czifile
except ImportError:
    czifile = None

try:
    import tifffile
except ImportError:
    tifffile = None


class MetadataViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Imetvi (Image Metadata Viewer)")

        layout = QVBoxLayout()

        # Buttons layout
        btn_layout = QHBoxLayout()

        # Button to load multiple files
        self.load_files_button = QPushButton("Load Files")
        self.load_files_button.clicked.connect(self.load_files)
        btn_layout.addWidget(self.load_files_button)

        # Button to load a folder
        self.load_folder_button = QPushButton("Load Folder")
        self.load_folder_button.clicked.connect(self.load_folder)
        btn_layout.addWidget(self.load_folder_button)

        # Button to save reports for all loaded files
        self.save_button = QPushButton("Save Reports")
        self.save_button.clicked.connect(self.save_reports)
        self.save_button.setEnabled(False)  # Enabled after metadata is loaded
        btn_layout.addWidget(self.save_button)

        layout.addLayout(btn_layout)

        # TextEdit to display metadata
        self.metadata_display = QTextEdit()
        self.metadata_display.setReadOnly(True)
        layout.addWidget(self.metadata_display)

        self.setLayout(layout)

        # Store all parsed metadata in a dictionary: {file_path: report_string}
        self.image_metadata = {}

    def load_files(self):
        file_names, _ = QFileDialog.getOpenFileNames(self, "Select images", "",
                                                     "Image Files (*.czi *.tif *.tiff)")
        if not file_names:
            return
        self.load_and_parse_images(file_names)

    def load_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if not folder:
            return
        # Gather all .czi, .tif, .tiff files from folder
        all_files = []
        for fname in os.listdir(folder):
            fpath = os.path.join(folder, fname)
            if os.path.isfile(fpath):
                ext = os.path.splitext(fname)[1].lower()
                if ext in [".czi", ".tif", ".tiff"]:
                    all_files.append(fpath)
        if not all_files:
            QMessageBox.information(self, "No Images Found", "No CZI or TIFF images found in the selected folder.")
            return
        self.load_and_parse_images(all_files)

    def load_and_parse_images(self, file_list):
        # Clear previous display and metadata
        self.metadata_display.clear()
        self.image_metadata.clear()

        for file_name in file_list:
            _, ext = os.path.splitext(file_name)
            ext = ext.lower()
            try:
                if ext == ".czi":
                    if czifile is None:
                        QMessageBox.critical(self, "Error", "czifile library not installed.")
                        return
                    with czifile.CziFile(file_name) as czi:
                        metadata = czi.metadata()
                        report = self.parse_czi_metadata(metadata, os.path.basename(file_name))
                        self.image_metadata[file_name] = report
                elif ext in [".tif", ".tiff"]:
                    if tifffile is None:
                        QMessageBox.critical(self, "Error", "tifffile library not installed.")
                        return
                    with tifffile.TiffFile(file_name) as tif:
                        if tif.pages and hasattr(tif.pages[0], 'tags'):
                            tags = {tag.name: tag.value for tag in tif.pages[0].tags.values()}
                            report = self.parse_tiff_metadata(tags, os.path.basename(file_name))
                            self.image_metadata[file_name] = report
                        else:
                            # No metadata found
                            self.image_metadata[file_name] = f"Image Name: {os.path.basename(file_name)}\nNo metadata found."
                else:
                    QMessageBox.warning(self, "Unsupported Format", f"File {file_name} is not supported.")
                    continue
            except Exception as e:
                QMessageBox.critical(self, "Error reading metadata", f"File: {file_name}\n{str(e)}")
                continue

        # Display combined metadata
        if self.image_metadata:
            self.metadata_display.append("=== Parsed Metadata Reports ===")
            for f, report in self.image_metadata.items():
                self.metadata_display.append(f"\n--- {os.path.basename(f)} ---\n")
                self.metadata_display.append(report)
            self.save_button.setEnabled(True)
        else:
            self.metadata_display.append("No files loaded.")
            self.save_button.setEnabled(False)

    def parse_czi_metadata(self, xml_str, image_name):
        # Parse the XML and extract key info
        root = ET.fromstring(xml_str)

        # Acquisition date/time
        acq_time_el = root.find('.//AcquisitionDateAndTime')
        acquisition_time = acq_time_el.text if acq_time_el is not None else "Unknown"

        # Image dimensions
        size_x = root.find('.//SizeX')
        size_y = root.find('.//SizeY')
        size_c = root.find('.//SizeC')
        dim_x = size_x.text if size_x is not None else "Unknown"
        dim_y = size_y.text if size_y is not None else "Unknown"
        dim_c = size_c.text if size_c is not None else "Unknown"

        # Pixel size
        px_size_x_el = root.find(".//Scaling/Items/Distance[@Id='X']/Value")
        px_size_y_el = root.find(".//Scaling/Items/Distance[@Id='Y']/Value")
        px_size_x = float(px_size_x_el.text) if px_size_x_el is not None else None
        px_size_y = float(px_size_y_el.text) if px_size_y_el is not None else None

        # Bit depth
        bit_depth_el = root.find('.//ComponentBitCount')
        bit_depth = bit_depth_el.text if bit_depth_el is not None else "Unknown"

        # Collect channel info
        channels = {}
        for ch in root.findall('.//Channel'):
            ch_name = ch.get('Name', 'Unknown Channel')
            if ch_name not in channels:
                channels[ch_name] = {
                    'Excitation': None,
                    'Emission': None,
                    'Dye': None,
                    'Exposure': None
                }

            exc = ch.find('ExcitationWavelength')
            emis = ch.find('EmissionWavelength')
            dye = ch.find('DyeName')
            exposure = ch.find('ExposureTime')

            if exc is not None:
                channels[ch_name]['Excitation'] = exc.text + " nm"
            if emis is not None:
                channels[ch_name]['Emission'] = emis.text + " nm"
            if dye is not None:
                channels[ch_name]['Dye'] = dye.text
            if exposure is not None:
                try:
                    exp_val_ns = float(exposure.text)
                    exp_val_ms = exp_val_ns / 1_000_000.0
                    channels[ch_name]['Exposure'] = f"{exp_val_ms} ms"
                except:
                    channels[ch_name]['Exposure'] = exposure.text

        # Objective info
        objective = root.find('.//Objectives/Objective')
        if objective is None:
            objective = root.find('.//Objective')
        obj_name = objective.get('Name', 'Unknown Objective') if objective is not None else "Unknown Objective"
        na = objective.find('LensNA') if objective is not None else None
        magnification = objective.find('NominalMagnification') if objective is not None else None
        obj_na = na.text if na is not None else "Unknown"
        obj_mag = magnification.text + "x" if magnification is not None else "Unknown"

        # Build report lines
        report_lines = []
        report_lines.append(f"Acquisition Date and Time: {acquisition_time}")
        report_lines.append(f"Image Name: {image_name}\n")
        report_lines.append(f"Image Dimensions: {dim_x} x {dim_y} pixels")
        report_lines.append(f"Number of Channels: {dim_c}")
        if px_size_x and px_size_y:
            report_lines.append(f"Pixel Size: {px_size_x:.4e} x {px_size_y:.4e} µm")
        report_lines.append(f"Bit Depth: {bit_depth}")

        report_lines.append("\nObjective Info:")
        report_lines.append(f"  Objective Name: {obj_name}")
        report_lines.append(f"  Numerical Aperture: {obj_na}")
        report_lines.append(f"  Magnification: {obj_mag}")

        report_lines.append("\nChannels:")
        for ch_name, ch_data in channels.items():
            report_lines.append(f"  Channel: {ch_name}")
            if ch_data['Dye']:
                report_lines.append(f"    Dye: {ch_data['Dye']}")
            if ch_data['Excitation']:
                report_lines.append(f"    Excitation: {ch_data['Excitation']}")
            if ch_data['Emission']:
                report_lines.append(f"    Emission: {ch_data['Emission']}")
            if ch_data['Exposure']:
                report_lines.append(f"    Exposure: {ch_data['Exposure']}")

        return "\n".join(report_lines)

    def parse_tiff_metadata(self, tags, image_name):
        # Attempt to parse TIFF metadata, especially if it's ImageJ-type
        report_lines = []
        report_lines.append(f"Image Name: {image_name}")

        img_width = tags.get('ImageWidth', 'Unknown')
        img_length = tags.get('ImageLength', 'Unknown')
        report_lines.append(f"Image Dimensions: {img_width} x {img_length} pixels")

        bits_per_sample = tags.get('BitsPerSample', 'Unknown')
        report_lines.append(f"Bit Depth: {bits_per_sample}")

        image_desc = tags.get('ImageDescription', '')
        desc_dict = {}
        for line in image_desc.split('\n'):
            if '=' in line:
                key, val = line.split('=', 1)
                desc_dict[key.strip()] = val.strip()

        num_channels = desc_dict.get('channels', 'Unknown')
        report_lines.append(f"Number of Channels: {num_channels}")

        unit = desc_dict.get('unit', '')
        xres = tags.get('XResolution', None)
        yres = tags.get('YResolution', None)

        if unit and xres and yres and len(xres) == 2 and len(yres) == 2:
            if xres[0] != 0 and yres[0] != 0:
                x_px_size = xres[1]/xres[0]
                y_px_size = yres[1]/yres[0]
                report_lines.append(f"Approx. Pixel Size: {x_px_size:.4f} x {y_px_size:.4f} {unit} per pixel")

        if 'images' in desc_dict:
            report_lines.append(f"Total Images (Z/T): {desc_dict['images']}")
        if 'hyperstack' in desc_dict:
            report_lines.append(f"Hyperstack: {desc_dict['hyperstack']}")
        if 'mode' in desc_dict:
            report_lines.append(f"Mode: {desc_dict['mode']}")

        return "\n".join(report_lines)

    def save_reports(self):
        if not self.image_metadata:
            QMessageBox.information(self, "No Metadata", "No metadata available to save.")
            return

        # For each file loaded, save a report in the same directory with '_metadata.txt' suffix
        for img_path, report in self.image_metadata.items():
            base, ext = os.path.splitext(img_path)
            out_path = base + "_metadata.txt"
            try:
                with open(out_path, 'w', encoding='utf-8') as f:
                    f.write(report)
            except Exception as e:
                QMessageBox.critical(self, "Error Saving Report", f"File: {out_path}\n{str(e)}")

        QMessageBox.information(self, "Success", "All reports saved successfully.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = MetadataViewer()
    viewer.show()
    sys.exit(app.exec_())
