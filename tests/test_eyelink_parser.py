# tests/test_eyelink_parser.py
#
# Synthetic EyeLink ASC exports mirroring FRDR deposit 1835 (EyeLink II CL,
# 500 Hz, right eye, converted with edf2asc): header, calibration messages,
# one recording block of samples with a blink, fixation/saccade summaries.

import pytest

from main import FORMAT_REGISTRY, formats_for_extension, get_standardizer
from metadata_parsers.eyelink_parser import parse_eyelink_metadata
from metadata_profiles.profile_registry import get_profile
from metadata_profiles.required_fields_registry import compute_missing_fields
from metadata_profiles.standards_registry import get_standard_info
from standardizers.eyelink_standardizer import standardize_eyelink_metadata
from utils.curation_flags import compute_curation_flags

CONTEXT = "Eye Tracking"

HEADER = """** CONVERTED FROM -text removed
** DATE: -text removed
** TYPE: EDF_FILE BINARY EVENT SAMPLE TAGGED
** VERSION: EYELINK II 1
** SOURCE: EYELINK CL
** EYELINK II CL v4.594 Jul  6 2012
** CAMERA: EyeLink CL-OL HEAD Version 1.0 Sensor=BJA
** SERIAL NUMBER: CLO-94115
** RECORDED BY -text removed
**

"""

CALIBRATION = """MSG\t100 DISPLAY_COORDS 0 0 1919 1079
MSG\t100 RETRACE_INTERVAL  8.33978542643
MSG\t110 disttoscreen 53.5  sheightinches 12.94 swidthinches 17.25  PPD 55.9
MSG\t200 !CAL CALIBRATION HV3 R RIGHT   GOOD
MSG\t300 !CAL VALIDATION HV3 R RIGHT GOOD ERROR 0.44 avg. 0.61 max  OFFSET 0.37 deg. 27.8,6.5 pix.
MSG\t400 TRIALID 0
MSG\t401 RECCFG CR 500 2 1 R
MSG\t401 GAZE_COORDS 0.00 0.00 1919.00 1079.00
MSG\t401 ELCL_PROC ELLIPSE  (5)
MSG\t402 !MODE RECORD CR 500 2 1 R
"""


def _block(n=10, start=1000, blink=(4, 5), end=True):
    lines = ["START\t%d \tRIGHT\tSAMPLES\tEVENTS" % start, "PRESCALER\t1", "VPRESCALER\t1", "PUPIL\tAREA",
             "EVENTS\tGAZE\tRIGHT\tRATE\t 500.00\tTRACKING\tCR\tFILTER\t2",
             "SAMPLES\tGAZE\tRIGHT\tRATE\t 500.00\tTRACKING\tCR\tFILTER\t2\tINPUT"]
    for i in range(n):
        ts = start + 2 * i
        if i in blink:
            lines.append(f"{ts}\t   .\t   .\t    0.0\t  127.0\t...")
        else:
            lines.append(f"{ts}\t 1888.6\t   42.5\t 2708.0\t  127.0\t...")
    lines += ["EFIX R   1000\t1006\t6\t 1884.7\t   49.8\t   2698",
              "ESACC R  1006\t1010\t4\t 1892.6\t   54.9\t  963.0\t  487.2\t  13.59\t    570",
              "EBLINK R 1008\t1010\t2", "INPUT\t1004\t127"]
    if end:
        lines.append("END\t%d \tSAMPLES\tEVENTS\tRES\t  77.12\t  64.57" % (start + 2 * n))
    lines.append("MSG\t%d !V TRIAL_VAR image stim.png" % (start + 2 * n + 1))
    lines.append("MSG\t%d TRIAL_RESULT 0" % (start + 2 * n + 2))
    return "\n".join(lines) + "\n"


def _write(tmp_path, name="eye_P1_series01.asc", header=HEADER, calibration=CALIBRATION, block=None):
    p = tmp_path / name
    p.write_text(header + calibration + (block if block is not None else _block()), encoding="utf-8")
    return p


def _std(path):
    return standardize_eyelink_metadata(parse_eyelink_metadata(str(path))[1])


def _codes(std):
    return {s["Code"] for s in std["_Suggestions"]}


def test_header_and_configuration(tmp_path):
    text, raw = parse_eyelink_metadata(str(_write(tmp_path)))
    assert raw["Header"]["SOURCE"] == "EYELINK CL" and raw["Header"]["SERIAL NUMBER"] == "CLO-94115"
    assert raw["Header"]["Tracker software"].startswith("EYELINK II CL v4.594")
    cfg = raw["Config"]
    assert cfg["Rate"] == 500.0 and cfg["Tracking"] == "CR" and cfg["Filter"] == "2"
    assert cfg["SampleType"] == "GAZE" and cfg["PupilMeasure"] == "AREA" and cfg["HasInputPort"]
    assert cfg["DisplayCoords"] == [0.0, 0.0, 1919.0, 1079.0]
    assert raw["Eyes"] == ["RIGHT"] and raw["Blocks"] == 1 and raw["UnclosedBlocks"] == 0
    assert "500.0 Hz" in text


def test_samples_events_and_missing(tmp_path):
    raw = parse_eyelink_metadata(str(_write(tmp_path)))[1]
    c = raw["Counts"]
    assert c["Samples"] == 10 and c["MissingSamples"] == 2
    assert (c["Fixations"], c["Saccades"], c["Blinks"], c["Trials"], c["InputEvents"]) == (1, 1, 1, 1, 1)
    assert raw["MissingFraction"] == pytest.approx(0.2)
    assert raw["ObservedRate"] == 500.0 and raw["RecordedSeconds"] == pytest.approx(0.018)
    assert raw["TrialVariables"] == ["image"]


def test_validation_and_geometry(tmp_path):
    raw = parse_eyelink_metadata(str(_write(tmp_path)))[1]
    v = raw["Validations"][-1]
    assert (v["Type"], v["Eye"], v["Grade"], v["AvgError"], v["MaxError"]) == ("HV3", "R", "GOOD", 0.44, 0.61)
    assert raw["Geometry"]["disttoscreen"] == 53.5 and raw["Geometry"]["swidthinches"] == 17.25


def test_standardizer_fields(tmp_path):
    std = _std(_write(tmp_path))
    assert std["EyeTrackerManufacturer"] == "SR Research" and std["RecordedEye"] == "Right"
    assert std["SamplingFrequency"] == 500.0 and std["TrackingMethod"] == "Pupil-CR"
    assert (std["ScreenResolutionX"], std["ScreenResolutionY"]) == (1920, 1080)
    assert std["ScreenRefreshRate"] == pytest.approx(119.91, abs=0.01)
    assert std["ScreenWidth"] == pytest.approx(43.82, abs=0.01)
    assert std["CalibrationType"] == "HV3" and std["AverageCalibrationError"] == 0.44
    assert std["MissingSamples"] == pytest.approx(20.0)
    assert std["ConvertedFrom"] == "" and std["RecordedBy"] == ""  # redacted values are not echoed


def test_clean_recording_gets_only_documentation_suggestions(tmp_path):
    codes = _codes(_std(_write(tmp_path)))
    assert codes == {"EYELINK_NO_DATE", "EYELINK_GEOMETRY_UNITS", "EYELINK_ASC_ONLY", "EYELINK_NO_STUDY_CONTEXT"}


def test_no_validation_is_suggested_without_a_flag(tmp_path):
    cal = "\n".join(l for l in CALIBRATION.splitlines() if "!CAL" not in l) + "\n"
    std = _std(_write(tmp_path, calibration=cal))
    sug = [s for s in std["_Suggestions"] if s["Code"] == "EYELINK_NO_VALIDATION"]
    assert sug and sug[0]["Flag"] is None and std["CalibrationType"] == ""


def test_poor_validation_is_flagged(tmp_path):
    cal = CALIBRATION.replace("GOOD ERROR 0.44 avg. 0.61 max", "POOR ERROR 1.80 avg. 3.10 max")
    assert "EYELINK_POOR_VALIDATION" in _codes(_std(_write(tmp_path, calibration=cal)))


def test_truncated_recording_is_flagged(tmp_path):
    std = _std(_write(tmp_path, block=_block(end=False)))
    assert "EYELINK_TRUNCATED" in _codes(std)


def test_high_missing_is_flagged(tmp_path):
    std = _std(_write(tmp_path, block=_block(n=10, blink=tuple(range(6)))))
    assert "EYELINK_HIGH_MISSING" in _codes(std)


def test_identifiers_in_header_are_flagged(tmp_path):
    header = HEADER.replace("CONVERTED FROM -text removed", "CONVERTED FROM C:\\data\\jsmith_pilot.edf")
    std = _std(_write(tmp_path, header=header))
    assert std["ConvertedFrom"].endswith("jsmith_pilot.edf") and "EYELINK_HEADER_IDENTIFIERS" in _codes(std)


def test_edf_companion_is_detected(tmp_path):
    p = _write(tmp_path)
    (tmp_path / "EYE_P1_SERIES01.EDF").write_bytes(b"edf")
    assert "EYELINK_ASC_ONLY" not in _codes(_std(p))


def test_rate_mismatch_is_reported(tmp_path):
    block = _block().replace("RATE\t 500.00", "RATE\t 1000.00")
    assert "EYELINK_RATE_MISMATCH" in _codes(_std(_write(tmp_path, block=block)))


def test_non_eyelink_asc_is_reported_not_raised(tmp_path):
    p = tmp_path / "grid.asc"
    p.write_text("ncols 4\nnrows 4\nxllcorner 0\nyllcorner 0\ncellsize 1\n1 2 3 4\n", encoding="utf-8")
    text, raw = parse_eyelink_metadata(str(p))
    assert "Not an EyeLink ASC export" in text and "Header" not in raw
    assert standardize_eyelink_metadata(raw) == {"ImageName": "grid.asc"}


def test_suggestions_are_bilingual(tmp_path):
    assert all(s["Message"] and s["Message_fr"] for s in _std(_write(tmp_path))["_Suggestions"])


def test_registry_wiring(tmp_path):
    assert "EyeLink" in FORMAT_REGISTRY and formats_for_extension(".asc") == ["EyeLink"]
    assert get_standardizer("EyeLink", CONTEXT) is standardize_eyelink_metadata
    std = _std(_write(tmp_path))
    profile = get_profile(CONTEXT)
    assert profile and {k for k in std if not k.startswith("_")} <= set(profile)
    assert "BEP020" in get_standard_info(CONTEXT)["standard_name"]
    assert compute_missing_fields("EyeLink", std, CONTEXT) == []


def test_curation_flags_include_eyelink_flags(tmp_path):
    p = _write(tmp_path, block=_block(end=False))
    std = standardize_eyelink_metadata(parse_eyelink_metadata(str(p))[1])
    flags, _ = compute_curation_flags([(str(p), "", std)])
    assert "EYELINK_TRUNCATED" in flags[str(p)]
