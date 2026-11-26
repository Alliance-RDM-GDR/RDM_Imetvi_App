# tests/test_cryoem_parser.py
#
# Synthetic cryo-EM acquisition set mirroring FRDR deposit 1877 (Falcon 4i on a
# Glacios, EPU): an MRC2014 micrograph with an FEI extended header, an EER
# BigTIFF movie, the EPU .xml sidecar, a .jpg preview and a .gain reference.

import struct

import numpy as np
import pytest
import tifffile
from PIL import Image

import utils.curation_flags as curation_flags
from main import FORMAT_REGISTRY, formats_for_extension, get_standardizer
from metadata_parsers.cryoem_parser import parse_cryoem_metadata, read_epu_xml, read_mrc_header
from metadata_profiles.profile_registry import get_profile
from metadata_profiles.required_fields_registry import compute_missing_fields
from metadata_profiles.standards_registry import get_standard_info
from standardizers.cryoem_standardizer import standardize_cryoem_metadata
from utils.curation_flags import compute_curation_flags
from utils.thumbnail import generate_thumbnail_bytes

CONTEXT = "Cryo-EM"
STEM = "FoilHole_1_Data_2_57_20260808_063655"
NX, NY = 32, 24
PIXEL_A = 0.7154640
EXT = 1024


def _kv(key, value, kind="b:string"):
    return (f'<a:KeyValueOfstringanyType><a:Key>{key}</a:Key>'
            f'<a:Value i:type="{kind}" xmlns:b="http://www.w3.org/2001/XMLSchema">{value}</a:Value>'
            f'</a:KeyValueOfstringanyType>')


def _xml(pixel_m=PIXEL_A * 1e-10, sample="Empty"):
    custom = "".join([
        _kv("Detectors[EF-Falcon].CommercialName", "Falcon 4i"),
        _kv("Detectors[EF-Falcon].CameraSerialNumber", "23-34-A46-OVV"),
        _kv("Detectors[EF-Falcon].ElectronCounted", "true", "b:boolean"),
        _kv("Detectors[EF-Falcon].FrameRate", "317.76", "b:double"),
        _kv("Detectors[EF-Falcon].DoseRate", "5.57", "b:double"),
        _kv("Detectors[EF-Falcon].EerGainReference", "ImagesForProcessing/EF-Falcon/200kV/20260324_EER_GainReference"),
        _kv("Dose", "3.7563570586799089E+21", "b:double"),
        _kv("AppliedDefocus", "-1.8E-06", "b:double"),
        _kv("Aperture[C2].Name", "20"),
        _kv("Aperture[OBJ].Name", "None"),
        _kv("PhasePlateUsed", "false", "b:boolean"),
    ])
    return (
        '<MicroscopeImage xmlns="http://schemas.datacontract.org/2004/07/Fei.SharedObjects" '
        'xmlns:i="http://www.w3.org/2001/XMLSchema-instance" '
        'xmlns:a="http://schemas.microsoft.com/2003/10/Serialization/Arrays">'
        f"<name>{sample}</name>"
        f"<SpatialScale><pixelSize><x><numericValue>{pixel_m}</numericValue></x>"
        f"<y><numericValue>{pixel_m}</numericValue></y></pixelSize></SpatialScale>"
        "<microscopeData><acquisition><acquisitionDateTime>2026-08-08T06:37:00-04:00</acquisitionDateTime>"
        "<camera><Name>EF-Falcon</Name><ExposureTime>3.46</ExposureTime>"
        "<ReadoutArea><width>4096</width><height>4096</height></ReadoutArea></camera></acquisition>"
        "<core><ApplicationSoftware>EPU</ApplicationSoftware>"
        "<ApplicationSoftwareVersion>3.15.0.11609</ApplicationSoftwareVersion></core>"
        "<gun><AccelerationVoltage>200000</AccelerationVoltage><Sourcetype>FieldEmission</Sourcetype></gun>"
        "<instrument><InstrumentModel>GLACIOS-9956511</InstrumentModel></instrument>"
        "<optics><ProbeMode>NanoProbe</ProbeMode><SpotIndex>3</SpotIndex>"
        "<TemMagnification><NominalMagnification>165000</NominalMagnification></TemMagnification></optics>"
        "</microscopeData>"
        f"<CustomData>{custom}</CustomData></MicroscopeImage>"
    )


def _write_mrc(path, mode=6, truncate=0, endian="<"):
    h = bytearray(1024)
    struct.pack_into(endian + "4i", h, 0, NX, NY, 1, mode)
    struct.pack_into(endian + "3f", h, 40, NX * PIXEL_A, NY * PIXEL_A, 0.0)
    struct.pack_into(endian + "3f", h, 76, 10.0, 200.0, 55.5)
    struct.pack_into(endian + "i", h, 92, EXT)
    h[104:108] = b"FEI2"
    struct.pack_into(endian + "i", h, 108, 20140)
    h[208:212] = b"MAP "
    h[212:216] = b"\x44\x44\x00\x00" if endian == "<" else b"\x11\x11\x00\x00"
    data = (np.arange(NX * NY, dtype=endian + "u2") % 200).tobytes()
    blob = bytes(h) + bytes(EXT) + data
    path.write_bytes(blob[:len(blob) - truncate] if truncate else blob)


def _write_eer(path):
    items = ('<metadata><item name="exposureTime" unit="s">3.4617</item>'
             '<item name="numberOfFrames">2</item>'
             '<item name="sensorPixelSize.width" unit="m">7.15464007e-11</item>'
             '<item name="eerGainReference">x/20260324_EER_GainReference.gain</item>'
             '<item name="commercialName">Falcon 4i</item></metadata>').encode()
    tifffile.imwrite(str(path), np.zeros((2, 8, 8), dtype="u1"), bigtiff=True,
                     extratags=[(65001, 1, len(items), items, True)])


@pytest.fixture
def acquisition(tmp_path):
    (tmp_path / f"{STEM}.xml").write_text(_xml(), encoding="utf-8")
    _write_mrc(tmp_path / f"{STEM}.mrc")
    _write_eer(tmp_path / f"{STEM}_EER.eer")
    Image.new("L", (16, 16), 90).save(tmp_path / f"{STEM}.jpg")
    (tmp_path / "20260324_EER_GainReference.gain").write_bytes(b"gain")
    return tmp_path


def _std(folder, name):
    return standardize_cryoem_metadata(parse_cryoem_metadata(str(folder / name))[1])


def _codes(std):
    return {s["Code"] for s in std["_Suggestions"]}


def test_mrc_header_fields(acquisition):
    h = read_mrc_header(str(acquisition / f"{STEM}.mrc"))
    assert (h["Nx"], h["Ny"], h["Nz"], h["DataType"]) == (NX, NY, 1, "uint16")
    assert h["ExtendedHeaderType"] == "FEI2" and h["ExtendedHeaderBytes"] == EXT
    assert h["Version"] == 20140 and h["MapId"] == "MAP" and not h["Truncated"]
    assert h["Dmean"] == pytest.approx(55.5)


def test_mrc_big_endian_is_detected(tmp_path):
    _write_mrc(tmp_path / "a.mrc", endian=">")
    h = read_mrc_header(str(tmp_path / "a.mrc"))
    assert h["ByteOrder"] == "big-endian" and (h["Nx"], h["Ny"]) == (NX, NY)


def test_invalid_mrc_is_reported_not_raised(tmp_path):
    p = tmp_path / "bad.mrc"
    p.write_bytes(b"\xff" * 2048)
    text, raw = parse_cryoem_metadata(str(p))
    assert "Failed to read MRC" in text and "MRC" not in raw


def test_epu_xml_fields(acquisition):
    e = read_epu_xml(str(acquisition / f"{STEM}.xml"))
    assert e["AccelerationVoltage_V"] == 200000 and e["InstrumentModel"] == "GLACIOS-9956511"
    assert e["PixelSizeX_m"] == pytest.approx(PIXEL_A * 1e-10)
    assert e["CommercialName"] == "Falcon 4i" and e["ElectronCounted"] == "true"
    assert e["Dose_e_m2"] == pytest.approx(3.7563570586799089e21)


def test_non_epu_xml_is_rejected(tmp_path):
    (tmp_path / "x.xml").write_text("<root/>")
    with pytest.raises(ValueError):
        read_epu_xml(str(tmp_path / "x.xml"))


def test_parse_mrc_pulls_in_sidecars(acquisition):
    text, raw = parse_cryoem_metadata(str(acquisition / f"{STEM}.mrc"))
    assert raw["Kind"] == "MRC" and raw["EPU"] and raw["EER"]["FrameCount"] == 2
    assert raw["Companions"] == {"Mrc": f"{STEM}.mrc", "Eer": f"{STEM}_EER.eer",
                                 "Xml": f"{STEM}.xml", "Jpg": f"{STEM}.jpg"}
    assert raw["GainReferenceFound"] == "20260324_EER_GainReference.gain"
    assert "200 kV" in text and "Falcon 4i" in text


def test_parse_eer_reads_tags_only(acquisition):
    text, raw = parse_cryoem_metadata(str(acquisition / f"{STEM}_EER.eer"))
    assert raw["Kind"] == "EER" and raw["EER"]["FrameCount"] == 2
    assert raw["EER"]["Acquisition"]["exposureTime"]["value"] == "3.4617"
    assert "EER movie: 2 frames" in text


def test_standardizer_micrograph(acquisition):
    std = _std(acquisition, f"{STEM}.mrc")
    assert std["FileType"] == "MRC2014 micrograph"
    assert std["PixelSize"] == pytest.approx(PIXEL_A, abs=1e-4) and std["PixelSizeSource"] == "MRC header"
    assert std["AccelerationVoltage"] == 200.0 and std["Defocus"] == -1.8
    assert std["TotalDose"] == pytest.approx(37.564, abs=1e-3)
    assert std["Detector"] == "Falcon 4i" and std["FrameCount"] == 2
    assert std["GainReferenceFound"] == "yes" and std["ObjectiveAperture"] == ""
    assert _codes(std) == {"CRYOEM_NO_SAMPLE"}  # nothing else is wrong with a complete set


def test_standardizer_eer_movie(acquisition):
    std = _std(acquisition, f"{STEM}_EER.eer")
    assert std["FileType"] == "EER electron-event movie" and std["FrameCount"] == 2
    assert std["PixelSizeSource"] == "EPU XML"


def test_truncated_mrc_is_flagged(acquisition):
    _write_mrc(acquisition / f"{STEM}.mrc", truncate=100)
    std = _std(acquisition, f"{STEM}.mrc")
    assert "CRYOEM_MRC_TRUNCATED" in _codes(std)
    assert [s["Flag"] for s in std["_Suggestions"] if s["Code"] == "CRYOEM_MRC_TRUNCATED"] == ["CRYOEM_TRUNCATED"]


def test_missing_sidecar_and_movie(tmp_path):
    _write_mrc(tmp_path / f"{STEM}.mrc")
    assert {"CRYOEM_NO_XML", "CRYOEM_NO_MOVIE"} <= _codes(_std(tmp_path, f"{STEM}.mrc"))


def test_missing_gain_reference_is_flagged(acquisition):
    (acquisition / "20260324_EER_GainReference.gain").unlink()
    std = _std(acquisition, f"{STEM}.mrc")
    assert "CRYOEM_NO_GAIN" in _codes(std) and std["GainReferenceFound"] == "no"


def test_pixel_size_mismatch_is_flagged(acquisition):
    (acquisition / f"{STEM}.xml").write_text(_xml(pixel_m=1.2e-10), encoding="utf-8")
    assert "CRYOEM_PIXEL_MISMATCH" in _codes(_std(acquisition, f"{STEM}.mrc"))


def test_named_sample_swaps_the_suggestion(acquisition):
    (acquisition / f"{STEM}.xml").write_text(_xml(sample="IFNL3 complex"), encoding="utf-8")
    codes = _codes(_std(acquisition, f"{STEM}.mrc"))
    assert "CRYOEM_NO_SAMPLE" not in codes and "CRYOEM_NO_SPECIMEN_PREP" in codes


def test_suggestions_are_bilingual(acquisition):
    std = _std(acquisition, f"{STEM}.mrc")
    assert all(s["Message"] and s["Message_fr"] for s in std["_Suggestions"])


def test_registry_wiring(acquisition):
    assert "CryoEM" in FORMAT_REGISTRY
    assert formats_for_extension(".eer") == ["CryoEM"] and formats_for_extension(".mrc") == ["CryoEM"]
    assert get_standardizer("CryoEM", CONTEXT) is standardize_cryoem_metadata
    std = _std(acquisition, f"{STEM}.mrc")
    profile = get_profile(CONTEXT)
    assert profile and {k for k in std if not k.startswith("_")} <= set(profile)
    assert get_standard_info(CONTEXT)["standard_name"].startswith("MRC2014")
    assert compute_missing_fields("CryoEM", std, CONTEXT) == []


def test_curation_flags_include_cryoem_flags(acquisition):
    _write_mrc(acquisition / f"{STEM}.mrc", truncate=100)
    p = str(acquisition / f"{STEM}.mrc")
    std = standardize_cryoem_metadata(parse_cryoem_metadata(p)[1])
    flags, _ = compute_curation_flags([(p, "", std)])
    assert "CRYOEM_TRUNCATED" in flags[p]


def test_large_cryoem_files_are_not_hashed():
    assert curation_flags.MAX_MD5_BYTES_BY_EXT[".eer"] <= 64 << 20


def test_thumbnails(acquisition):
    assert generate_thumbnail_bytes(str(acquisition / f"{STEM}.mrc")).startswith(b"\x89PNG")
    assert generate_thumbnail_bytes(str(acquisition / f"{STEM}_EER.eer")).startswith(b"\x89PNG")
    (acquisition / f"{STEM}.jpg").unlink()
    assert generate_thumbnail_bytes(str(acquisition / f"{STEM}_EER.eer")) is None
