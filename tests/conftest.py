# tests/conftest.py

import numpy as np
import piexif
import pytest
import tifffile
from PIL import Image


@pytest.fixture
def synthetic_jpg(tmp_path):
    """Creates a small JPG with known EXIF tags."""
    file_path = tmp_path / "synthetic.jpg"

    img = Image.new("RGB", (64, 48), color="blue")
    exif_dict = {
        "0th": {
            piexif.ImageIFD.Make: b"AcmeCam",
            piexif.ImageIFD.Model: b"Model X",
            piexif.ImageIFD.Software: b"PytestSuite",
            piexif.ImageIFD.XResolution: (300, 1),
            piexif.ImageIFD.YResolution: (300, 1),
        },
        "Exif": {
            piexif.ExifIFD.DateTimeOriginal: b"2026:01:01 10:00:00",
        },
        "GPS": {
            piexif.GPSIFD.GPSLatitudeRef: b"N",
            piexif.GPSIFD.GPSLatitude: ((52, 1), (0, 1), (0, 1)),
            piexif.GPSIFD.GPSLongitudeRef: b"W",
            piexif.GPSIFD.GPSLongitude: ((106, 1), (0, 1), (0, 1)),
        },
    }
    exif_bytes = piexif.dump(exif_dict)
    img.save(file_path, exif=exif_bytes)

    return str(file_path)


@pytest.fixture
def synthetic_tiff(tmp_path):
    """Creates a small TIFF with an ImageJ-style ImageDescription."""
    file_path = tmp_path / "synthetic.tiff"

    data = np.zeros((32, 32), dtype=np.uint8)
    description = "ImageJ=1.54f\nimages=1\nchannels=1\nunit=micron\n"
    tifffile.imwrite(
        str(file_path),
        data,
        description=description,
        resolution=(100.0, 100.0),
        metadata=None,
    )

    return str(file_path)


@pytest.fixture
def synthetic_jpg_with_iptc(tmp_path):
    """Creates a JPG with IPTC IIM fields set (caption, keywords, credit, etc.)."""
    from iptcinfo3 import IPTCInfo

    file_path = tmp_path / "synthetic_iptc.jpg"
    img = Image.new("RGB", (40, 40), color="green")
    img.save(file_path)

    info = IPTCInfo(str(file_path), force=True)
    info["caption/abstract"] = "A test caption"
    info["keywords"] = ["test", "sample"]
    info["by-line"] = "Jane Doe"
    info["credit"] = "Test Lab"
    info["copyright notice"] = "CC-BY 4.0"
    info["city"] = "Saskatoon"
    info["country/primary location name"] = "Canada"
    info.save_as(str(file_path))

    return str(file_path)


@pytest.fixture
def synthetic_ome_tiff(tmp_path):
    """Creates a TIFF whose ImageDescription holds a minimal OME-XML block."""
    file_path = tmp_path / "synthetic_ome.tiff"

    data = np.zeros((10, 10), dtype=np.uint8)
    ome_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<OME xmlns="http://www.openmicroscopy.org/Schemas/OME/2016-06">'
        '<Image ID="Image:0" Name="TestImage">'
        '<AcquisitionDate>2026-01-01T10:00:00</AcquisitionDate>'
        '<Pixels ID="Pixels:0" DimensionOrder="XYCZT" Type="uint8" '
        'SizeX="10" SizeY="10" SizeZ="1" SizeC="2" SizeT="1" '
        'PhysicalSizeX="0.5" PhysicalSizeXUnit="micron" '
        'PhysicalSizeY="0.5" PhysicalSizeYUnit="micron">'
        '<Channel ID="Channel:0:0" Name="DAPI" SamplesPerPixel="1" IlluminationType="Epifluorescence"/>'
        '<Channel ID="Channel:0:1" Name="GFP" SamplesPerPixel="1" IlluminationType="Epifluorescence"/>'
        '</Pixels></Image>'
        '<Instrument ID="Instrument:0">'
        '<Objective ID="Objective:0" Model="Plan-Apo 20x" NominalMagnification="20.0" '
        'LensNA="0.75" Immersion="Air"/>'
        '</Instrument></OME>'
    )
    tifffile.imwrite(str(file_path), data, description=ome_xml, metadata=None)

    return str(file_path)


@pytest.fixture
def synthetic_dicom(tmp_path):
    """Creates a minimal DICOM file with both PHI and research-relevant fields."""
    import pydicom
    from pydicom.dataset import Dataset, FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian, generate_uid

    file_path = tmp_path / "synthetic.dcm"

    ds = Dataset()
    ds.PatientName = "Doe^Jane"
    ds.PatientID = "12345"
    ds.PatientBirthDate = "19900101"
    ds.PatientSex = "F"
    ds.Modality = "MR"
    ds.Manufacturer = "AcmeScan"
    ds.ManufacturerModelName = "ScanMaster 3000"
    ds.StudyDate = "20260101"
    ds.StudyDescription = "Brain study"
    ds.SeriesDescription = "T1 weighted"
    ds.BodyPartExamined = "BRAIN"
    ds.ProtocolName = "Standard"
    ds.Rows = 256
    ds.Columns = 256
    ds.PixelSpacing = [0.5, 0.5]
    ds.SliceThickness = 1.0
    ds.BitsAllocated = 16
    ds.BitsStored = 12
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.InstitutionName = "Test Hospital"
    ds.SOPClassUID = generate_uid()
    ds.SOPInstanceUID = generate_uid()

    ds.file_meta = FileMetaDataset()
    ds.file_meta.MediaStorageSOPClassUID = ds.SOPClassUID
    ds.file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.is_little_endian = True
    ds.is_implicit_VR = False
    ds.save_as(str(file_path), enforce_file_format=True)

    return str(file_path)


@pytest.fixture
def synthetic_hdf5(tmp_path):
    """Creates a minimal HDF5 file with groups, datasets, and root attributes."""
    import h5py

    file_path = tmp_path / "synthetic.h5"
    with h5py.File(str(file_path), "w") as f:
        f.attrs["Conventions"] = "CF-1.8"
        f.attrs["institution"] = "Test University"

        grp = f.create_group("measurements")
        ds = grp.create_dataset("image_stack", data=np.zeros((10, 64, 64), dtype=np.float32),
                                compression="gzip")
        ds.attrs["units"] = "intensity"
        ds.attrs["long_name"] = "Fluorescence stack"

        grp.create_dataset("timestamps", data=np.arange(10, dtype=np.float64))

    return str(file_path)


@pytest.fixture
def synthetic_fits(tmp_path):
    """Creates a small FITS file with telescope and WCS header fields."""
    from astropy.io import fits

    file_path = tmp_path / "synthetic.fits"

    hdu = fits.PrimaryHDU(np.zeros((20, 20), dtype=np.uint8))
    hdu.header["TELESCOP"] = "TestScope"
    hdu.header["INSTRUME"] = "TestCam"
    hdu.header["OBJECT"] = "M31"
    hdu.header["DATE-OBS"] = "2026-01-01T00:00:00"
    hdu.header["EXPTIME"] = 30.0
    hdu.header["FILTER"] = "R"
    hdu.header["CRVAL1"] = 10.5
    hdu.header["CRVAL2"] = 41.2
    hdu.header["CTYPE1"] = "RA---TAN"
    hdu.header["CTYPE2"] = "DEC--TAN"
    hdu.writeto(str(file_path), overwrite=True)

    return str(file_path)
