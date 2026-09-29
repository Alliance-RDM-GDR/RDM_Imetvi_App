# tests/test_ppmstar_parser.py
#
# Synthetic PPMstar output mirroring the layout of the FRDR data releases:
#   <run>/prfs/<id>-NNNN.rprof, <run>/prfs/<id>-0000.hstry,
#   <run>/moms/myavsbq/NNNN/<id>-BQavNNNN.<abc>, <run>/variables.json,
#   <run>/<setup>.include, <run>/<run>-flags.F

import json

import numpy as np
import pytest

from main import FORMAT_REGISTRY, formats_for_extension, get_standardizer
from metadata_parsers.ppmstar_parser import parse_ppmstar_metadata
from metadata_profiles.profile_registry import get_profile
from metadata_profiles.required_fields_registry import compute_missing_fields
from standardizers.ppmstar_simulation_standardizer import standardize_ppmstar_simulation_metadata
from utils.curation_flags import compute_curation_flags
import utils.curation_flags as curation_flags

RPROF = """
DUMP     12  at time step # 4321,   at problem time =  1.50000000E+02,     and at     Sat Apr 18 20:28:25 2026
   dt =  1.50000000E-03,    courmx =  9.00000000E-01,     Gflop/s/thread = 6.00000000E-01
   Gflop/s =  3.68114E+04          threads/rank =  28,          nranks =    880

For the time interval of dump    12:
Gflop/s/thread =  6.04179E-01            flops/cell =  2.33583E+03
Nx =  1536


   IR      R              Rho0           Rho1           P0             P1             Mu0            FV             FVhhe          T9

 4     1.2000000E+01  8.5909019E+01  0.0000000E+00  9.8345642E+02  0.0000000E+00  1.7981654E+00  1.0000000E+00  0.0000000E+00  1.1923783E+00
 3     6.0000000E+00  8.5909035E+01  0.0000000E+00  9.8345685E+02  0.0000000E+00  1.7981658E+00  1.0000000E+00  0.0000000E+00  1.1923783E+00
 2     3.0000000E+00  8.5909035E+01  0.0000000E+00  9.8345636E+02  0.0000000E+00  1.7981663E+00  1.0000000E+00  0.0000000E+00  1.1923783E+00
 1     1.0000000E+00  8.5909035E+01  0.0000000E+00  9.8345636E+02  0.0000000E+00  1.7981663E+00  1.0000000E+00  0.0000000E+00  1.1923783E+00

   IR      R              S              RhoS

 2     6.0000000E+00  1.0000000E-01  2.0000000E+00
 1     3.0000000E+00  1.1000000E-01  2.1000000E+00

Line of sight            1 :
DATE:   4/18/2026;   TIME:  20:28:25
This is a test run with heating.
No burning of the entrained fluid.

1                        nsugar              4                     ncpucores             28
2                          ifheat              1                        ifburn              0
3                         nfluids              2

1                             g        -9.021900177001953E+00           TransitionThickness         2.500000000000000E-01
2                       radin0         4.492856979370117E+00                      radout0         1.199285697937012E+01
3                     totallum         2.015299987792969E+01                                       0.000000000000000E+00
"""

HSTRY = """
NDump  NCycle      time(secs)   time(mins)   dt(secs)     Courant      MachNoMax    TotalFlops        TimeStamp

    0         0  0.00000E+00  0.00000E+00  9.70687E-04  0.00000E+00  0.00000E+00  0.00000E+00  Tue Mar 10 20:36:06 2026
    1      3476  5.42454E+00  9.04090E-02  1.56953E-03  9.00000E-01  4.20585E-06  6.99865E+17  Tue Mar 10 20:50:47 2026
    2      6930  1.08457E+01  1.80762E-01  1.56953E-03  9.00000E-01  5.76540E-06  1.39530E+18  Tue Mar 10 21:06:42 2026
    2      6932  1.08460E+01  1.80766E-01  1.56953E-03  9.00000E-01  5.76540E-06  1.39530E+18  Wed Mar 11 09:06:42 2026
    3     10384  1.62669E+01  2.71115E-01  1.56953E-03  9.00000E-01  1.29192E-05  2.09074E+18  Wed Mar 11 09:20:07 2026
"""

INCLUDE = '''c    M=25Msun, MESA cycle 28900
c    dir = /data/somewhere/LOGS
c    There are 3 radial points.
      write(idfile,'(9(a,a1))')
     & "H pressure P0 = 18779.467250028155831387",NEW_LINE("A"),
     & "H mass m0     = 2513830.934757364448159933",NEW_LINE("A"),
     & "H airmu       = 1.836766",NEW_LINE("A"),
     & "H cldmu       = 1.798186",NEW_LINE("A"),
     & "  radius     S           mu",NEW_LINE("A"),
     & "  4.492857   -20.846135  1.836766",NEW_LINE("A"),
     & "  4.578571   -20.500000  1.836765",NEW_LINE("A"),
     & "  4.664286   -19.000000  1.836764",NEW_LINE("A"),
'''

FLAGS = """c  Minimal flags file
#define setupfilename "O28.include"
#define iskappafunctofradiusonly2 1
#define aa110 3.1424919E-03
#define aa111 -1.4965588E-03
"""

VARIABLES = {
    "run": "OT", "runid": "Otest", "grid": 8, "files_per_dump": 8, "bytes_per_file": 2560,
    "dumps": [1], "dump_times_s": {"1": 12.5},
    "variables": [
        {"index": 0, "name": "ux", "description": "x-velocity", "units": "Mm/s", "definition": "ux",
         "masked_outside_star": True},
        {"index": 3, "name": "T9", "description": "temperature", "units": "10^9 K", "definition": "T9",
         "masked_outside_star": False},
    ],
}


@pytest.fixture
def run_dir(tmp_path):
    run = tmp_path / "OT"
    (run / "prfs" / "frombqavs").mkdir(parents=True)
    (run / "moms" / "myavsbq" / "0001").mkdir(parents=True)
    (run / "prfs" / "Otest-0012.rprof").write_text(RPROF)
    (run / "prfs" / "Otest-0000.hstry").write_text(HSTRY)
    (run / "prfs" / "Otest-0012.aaa").write_bytes(np.zeros(16, "<f4").tobytes())
    (run / "prfs" / "frombqavs" / "Otest-BQav0001.rprof").write_text(
        "\n\n   ir    ---ux---    ---T9---\n  2    0.0E+00  1.0E+00\n  1    1.0E-05  2.0E+00\n")
    (run / "OT.include").write_text(INCLUDE)
    (run / "OT-flags.F").write_text(FLAGS)
    (run / "variables.json").write_text(json.dumps(VARIABLES))
    return run


def _make_cube_files(run, complete=True):
    d = run / "moms" / "myavsbq" / "0001"
    m = 4  # sub-cube edge with ghosts -> n = 2
    payload = np.arange(10 * m ** 3, dtype="<f4").tobytes()
    exts = [f"{a}{b}{c}" for a in "ab" for b in "ab" for c in "ab"]
    for ext in exts[: (8 if complete else 5)]:
        (d / f"Otest-BQav0001.{ext}").write_bytes(payload)
    return d


def test_registered_for_all_extensions():
    for ext in (".rprof", ".hstry", ".include", ".f", ".aaa", ".bab", ".bbb"):
        assert "PPMstar" in formats_for_extension(ext)
    assert get_standardizer("PPMstar", "Astrophysical Simulation") is standardize_ppmstar_simulation_metadata
    assert FORMAT_REGISTRY["PPMstar"]["contexts"] == ["Astrophysical Simulation"]


def test_parse_rprof_banner_tables_and_parameters(run_dir):
    text, raw = parse_ppmstar_metadata(str(run_dir / "prfs" / "Otest-0012.rprof"))

    assert "Failed to read" not in text
    assert raw["FileKind"] == "rprof"
    assert raw["RunLabel"] == "OT"
    assert raw["RunID"] == "Otest"
    assert raw["DumpNumber"] == 12
    assert raw["TimeStep"] == 4321
    assert raw["ProblemTime_s"] == pytest.approx(150.0)
    assert raw["MPIRanks"] == 880 and raw["ThreadsPerRank"] == 28
    assert raw["GridCellsPerDim"] == 1536
    assert raw["ProfileTableCount"] == 2
    assert raw["ProfileRowCounts"] == [2, 4]
    assert raw["RadiusMin_Mm"] == pytest.approx(1.0) and raw["RadiusMax_Mm"] == pytest.approx(12.0)
    assert "Rho0" in raw["ProfileVariables"] and "RhoS" in raw["ProfileVariables"]
    assert raw["LinesOfSight"] == 1
    assert "heating" in raw["RunDescription"]
    assert raw["IntegerParameters"]["ifheat"] == 1 and raw["IntegerParameters"]["ifburn"] == 0
    assert raw["RealParameters"]["radout0"] == pytest.approx(11.99285697937012)


def test_parse_frombqavs_variant(run_dir):
    text, raw = parse_ppmstar_metadata(str(run_dir / "prfs" / "frombqavs" / "Otest-BQav0001.rprof"))

    assert raw["ProfileVariables"] == ["ux", "T9"]
    assert raw["RadialPoints"] == 2
    assert "frombqavs" in text


def test_parse_hstry_detects_restart_records(run_dir):
    text, raw = parse_ppmstar_metadata(str(run_dir / "prfs" / "Otest-0000.hstry"))

    assert raw["DumpRecordCount"] == 5
    assert raw["FirstDump"] == 0 and raw["LastDump"] == 3
    assert raw["DuplicateDumpRecords"] == 1
    assert raw["MissingDumpCount"] == 0
    assert raw["EndTime_s"] == pytest.approx(16.2669)
    assert raw["MachNumberMax"] == pytest.approx(1.29192e-05)
    assert raw["WallClockEnd"] == "Wed Mar 11 09:20:07 2026"
    assert "repeated" in text


def test_parse_cube_geometry_and_variables_json(run_dir):
    d = _make_cube_files(run_dir)
    text, raw = parse_ppmstar_metadata(str(d / "Otest-BQav0001.bab"))

    assert raw["FileKind"] == "moms_cube"
    assert raw["SubCubeIndex_xyz"] == [1, 0, 1]
    assert raw["SubCubeEdgeWithGhosts"] == 4 and raw["SubCubeEdge"] == 2
    assert raw["LayoutConsistent"] is True
    assert raw["FilesInDump"] == 8 and raw["SubCubesPerDim"] == 2 and raw["DumpComplete"] is True
    assert raw["CubeBriquettesPerDim"] == 4 and raw["HydroCellsPerDim"] == 16
    assert raw["VariablesJson"] is True
    assert raw["ProblemTime_s"] == 12.5
    assert [v["Name"] for v in raw["Variables"]] == ["ux", "T9"]
    assert raw["MatchesVariablesJsonLayout"] is True
    assert "Failed to read" not in text


def test_parse_cube_never_reads_payload_and_flags_bad_size(run_dir):
    d = run_dir / "moms" / "myavsbq" / "0001"
    (d / "Otest-BQav0001.aaa").write_bytes(b"\0" * 1000)  # not 10 * m^3 * 4
    text, raw = parse_ppmstar_metadata(str(d / "Otest-BQav0001.aaa"))

    assert raw["LayoutConsistent"] is False
    assert "Warning" in text


def test_parse_cube_without_variables_json(run_dir):
    (run_dir / "variables.json").unlink()
    d = _make_cube_files(run_dir)
    _, raw = parse_ppmstar_metadata(str(d / "Otest-BQav0001.aaa"))

    assert raw["VariablesJson"] is False
    assert "Variables" not in raw


def test_parse_prfs_companion(run_dir):
    _, raw = parse_ppmstar_metadata(str(run_dir / "prfs" / "Otest-0012.aaa"))

    assert raw["FileKind"] == "prfs_companion"
    assert raw["FloatCount"] == 16
    assert raw["PairedRprofPresent"] is True


def test_parse_include(run_dir):
    _, raw = parse_ppmstar_metadata(str(run_dir / "OT.include"))

    assert raw["StellarMass"] == "25Msun" and raw["MESAModelNumber"] == 28900
    assert raw["RadialPoints"] == 3 and raw["DeclaredRadialPoints"] == 3
    assert raw["RadiusMin_Mm"] == pytest.approx(4.492857)
    assert raw["EntropyMax"] == pytest.approx(-19.0)
    assert raw["HeaderConstants"]["airmu"] == pytest.approx(1.836766)


def test_parse_flags(run_dir):
    _, raw = parse_ppmstar_metadata(str(run_dir / "OT-flags.F"))

    assert raw["SetupFileName"] == "O28.include"
    assert raw["OpacityModels"] == ["iskappafunctofradiusonly2"]
    assert raw["OpacityCoefficientCount"] == 2


def test_parse_missing_file_fails_gracefully():
    text, raw = parse_ppmstar_metadata("does_not_exist.rprof")

    assert "Failed to read PPMstar file" in text
    assert raw["FilePath"] == "does_not_exist.rprof"


def test_parse_truncated_hstry_fails_gracefully(tmp_path):
    p = tmp_path / "x-0000.hstry"
    p.write_text("not a history file\n")
    text, _ = parse_ppmstar_metadata(str(p))

    assert "Failed to read PPMstar file" in text


def test_standardize_rprof_maps_fields(run_dir):
    _, raw = parse_ppmstar_metadata(str(run_dir / "prfs" / "Otest-0012.rprof"))
    result = standardize_ppmstar_simulation_metadata(raw)

    assert result["Code"] == "PPMstar"
    assert result["RunLabel"] == "OT"
    assert result["DumpNumber"] == 12
    assert result["HydroGrid"] == "1536^3"
    assert result["HeatingEnabled"] == "yes"
    assert result["BurningNetworkEnabled"] == "no"
    assert result["OuterBoundaryRadius_Mm"] == pytest.approx(11.99285697937012)
    assert "CubeVariables" not in result          # kinds omit fields they don't carry
    assert compute_missing_fields("PPMstar", result, "Astrophysical Simulation") == []


def test_standardize_cube_lists_variables_with_units(run_dir):
    d = _make_cube_files(run_dir)
    _, raw = parse_ppmstar_metadata(str(d / "Otest-BQav0001.abb"))
    result = standardize_ppmstar_simulation_metadata(raw)

    assert result["SubCubeIndex"] == "abb"
    assert result["DumpComplete"] == "yes"
    assert result["HydroGrid"] == "16^3"
    assert result["CubeVariables"].split("; ")[0] == "ux — x-velocity [Mm/s]"
    assert all(not isinstance(v, (list, dict)) for v in result.values())   # CSV-friendly


def test_every_standardized_key_has_a_profile_label(run_dir):
    d = _make_cube_files(run_dir)
    profile = get_profile("Astrophysical Simulation")
    paths = [
        run_dir / "prfs" / "Otest-0012.rprof", run_dir / "prfs" / "Otest-0000.hstry",
        run_dir / "prfs" / "Otest-0012.aaa", run_dir / "OT.include", run_dir / "OT-flags.F",
        d / "Otest-BQav0001.aaa",
    ]
    for p in paths:
        _, raw = parse_ppmstar_metadata(str(p))
        for key in standardize_ppmstar_simulation_metadata(raw):
            assert key in profile, f"{key} ({p.name}) has no label in the profile"


def test_curation_flags_incomplete_dump_and_undocumented_variables(run_dir):
    (run_dir / "variables.json").unlink()
    d = _make_cube_files(run_dir, complete=False)
    path = str(d / "Otest-BQav0001.aaa")
    text, raw = parse_ppmstar_metadata(path)
    flags, _ = compute_curation_flags([(path, text, standardize_ppmstar_simulation_metadata(raw))])

    assert "INCOMPLETE_DUMP" in flags[path]
    assert "UNDOCUMENTED_VARIABLES" in flags[path]
    assert "CORRUPT" not in flags[path]


def test_curation_flags_restart_records(run_dir):
    path = str(run_dir / "prfs" / "Otest-0000.hstry")
    text, raw = parse_ppmstar_metadata(path)
    flags, _ = compute_curation_flags([(path, text, standardize_ppmstar_simulation_metadata(raw))])

    assert flags[path] == ["RESTART_RECORDS"]


def test_md5_skipped_above_size_cap(tmp_path, monkeypatch):
    f = tmp_path / "big.bin"
    f.write_bytes(b"abc")
    assert curation_flags._compute_md5(str(f)) is not None
    monkeypatch.setattr(curation_flags, "MAX_MD5_BYTES", 2)
    assert curation_flags._compute_md5(str(f)) is None
