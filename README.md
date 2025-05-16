# Image Metadata Viewer (IMetVi)

**IMetVi** is a cross-format desktop application for extracting, displaying, and exporting image metadata. It currently supports TIFF and CZI image formats and is optimized for use in the context of the **REMBI** (Recommended Metadata for Biological Images) guidelines.

## Features

- 🧠 **Application context support**: Tailored display for *Microscopy* metadata.
- 🖼️ **Supported formats**: 
  - `TIFF`
  - `CZI` (Zeiss proprietary format)
- 📁 Load a single file or a folder of image files
- 🧾 View and compare:
  - Raw metadata (left panel)
  - Standardized recommended metadata (right panel)
- 💾 Export metadata:
  - JSON (human- and machine-readable)
  - CSV (tabular format, suitable for spreadsheets or further processing)
- 📊 Handles **multi-channel images**, including:
  - Fluorophore names
  - Excitation and emission wavelengths
  - Exposure time (in seconds)

## Screenshot

> ![IMetVi GUI](docs/AppImage.png.png)  
> *Example showing TIFF metadata extraction with four channels*

---

## Standardized Metadata Fields

The following metadata fields are extracted (if available) and exported in standardized format:

| Field             | Description                                                                 |
|------------------|-----------------------------------------------------------------------------|
| `ImageName`       | File name of the image                                                      |
| `AcquisitionTime` | ISO-formatted timestamp of acquisition                                      |
| `DimensionX/Y`    | Image dimensions in pixels                                                  |
| `SizeZ`, `SizeT`  | Number of Z-slices and time points                                          |
| `DefaultUnitFormat` | Unit of spatial calibration (e.g. `microns`)                            |
| `PixelSizeX/Y/Z`  | Pixel size in calibrated units (e.g. microns per pixel)                     |
| `BitDepth`        | Bit depth of each channel                                                   |
| `ObjectiveName`   | Microscope objective model                                                  |
| `NA`              | Numerical Aperture of the objective lens                                    |
| `Magnification`   | Total magnification including eyepiece zoom                                 |
| `MicroscopeName`  | Microscope model name                                                       |
| `MicroscopeType`  | Microscope orientation (e.g. `Upright`, `Inverted`)                         |
| `DetectorName`    | Name of the detector                                                        |
| `DetectorModel`   | Detector model (e.g. camera model)                                          |
| `LightSource`     | Illumination source (if available)                                          |
| `Channels`        | List of channels, including:  
  - `Name`: Fluorophore  
  - `ExcitationWavelength`, `EmissionWavelength`  
  - `ExposureTime_sec` (converted from nanoseconds where needed)                                  |
| `ContourType`     | Shape of the sample area (e.g. `Rectangle`)                                |

---

## Installation

### Requirements

- Python 3.8+
- Tested on Windows 10/11
- Recommended: run within a conda environment

### Dependencies

#Open bash chunk
pip install pyqt5 czifile tifffile numpy
#Close bash chunk

### Launch the App

Clone the repository and run:

#Open bash chunk
python main.py
#Close bash chunk

---

## License
This project is licensed under the MIT License. See LICENSE for details.

---

## Acknowledgements

    - Zeiss CZI Reader: Powered by czifile
    - TIFF Handling: Powered by tifffile
    - REMBI Guidelines: https://doi.org/10.1038/s41592-021-01166-8