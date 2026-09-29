# standardizers/ppmstar_simulation_standardizer.py

import os

_KIND_LABELS = {
    "rprof": "Radial profiles of one dump (.rprof)",
    "hstry": "Run history (.hstry)",
    "moms_cube": "3-D moms cube block (raw float32)",
    "prfs_companion": "PPMstar-internal companion array",
    "setup_include": "Initial 1-D stratification (.include)",
    "flags": "Minimal flags file (.F)",
}


def _put(out, key, value):
    """Adds key only when there is something to show, so a kind that lacks a field doesn't list it empty."""
    if value is None or value == "" or value == []:
        return
    out[key] = value


def _yes_no(flag):
    return None if flag is None else ("yes" if flag else "no")


def standardize_ppmstar_simulation_metadata(raw_metadata):
    """
    Standardizes parsed PPMstar output into a flat, simulation-oriented
    dictionary (code, run, dump, time, grid, physics switches, layout).
    There is no file-level metadata standard for this code's output; the
    field set follows what the IVOA Simulation Data Model treats as the
    core of a simulation run (see standards_registry.py).

    Fields are emitted only when the file kind carries them: a .hstry file
    has no grid, a moms cube has no run description.
    """
    file_path = raw_metadata.get("FilePath", "")
    kind = raw_metadata.get("FileKind", "")
    ip = raw_metadata.get("IntegerParameters") or {}
    rp = raw_metadata.get("RealParameters") or {}

    out = {"ImageName": os.path.basename(file_path)}
    _put(out, "FileType", _KIND_LABELS.get(kind, kind))
    out["Code"] = raw_metadata.get("Code", "")
    out["RunLabel"] = raw_metadata.get("RunLabel", "")
    _put(out, "RunID", raw_metadata.get("RunID"))
    _put(out, "DumpNumber", raw_metadata.get("DumpNumber"))
    _put(out, "ProblemTime_s", raw_metadata.get("ProblemTime_s"))
    _put(out, "FileSizeMB", round(raw_metadata["FileSizeBytes"] / 1e6, 3) if "FileSizeBytes" in raw_metadata else None)

    # rprof
    _put(out, "TimeStep", raw_metadata.get("TimeStep"))
    _put(out, "TimeStepSize_s", raw_metadata.get("TimeStepSize_s"))
    _put(out, "CourantNumber", raw_metadata.get("CourantNumber"))
    grid = raw_metadata.get("GridCellsPerDim") or raw_metadata.get("HydroCellsPerDim") or raw_metadata.get("ReleasedGrid")
    _put(out, "HydroGrid", f"{grid}^3" if grid else None)
    _put(out, "InnerBoundaryRadius_Mm", rp.get("radin0"))
    _put(out, "OuterBoundaryRadius_Mm", rp.get("radout0"))
    _put(out, "NumFluids", ip.get("nfluids"))
    _put(out, "HeatingEnabled", _yes_no(bool(ip["ifheat"])) if "ifheat" in ip else None)
    _put(out, "PrescribedLuminosity", rp.get("totallum"))
    _put(out, "BurningNetworkEnabled", _yes_no(bool(ip["ifburn"])) if "ifburn" in ip else None)
    _put(out, "MPIRanks", raw_metadata.get("MPIRanks"))
    _put(out, "ThreadsPerRank", raw_metadata.get("ThreadsPerRank"))
    _put(out, "WallClockTimestamp", raw_metadata.get("WallClockTimestamp"))
    _put(out, "ProfileTableCount", raw_metadata.get("ProfileTableCount"))
    # Joined into one string, not a list: the CSV exporter would otherwise spread
    # a 200+ name inventory over one column per name.
    _put(out, "ProfileVariables", ", ".join(raw_metadata.get("ProfileVariables") or []))
    _put(out, "RunDescription", raw_metadata.get("RunDescription"))

    # hstry
    for key in ("DumpRecordCount", "FirstDump", "LastDump", "MissingDumpCount", "DuplicateDumpRecords",
                "StartTime_s", "EndTime_s", "TimeStepMin_s", "TimeStepMax_s", "MachNumberMax",
                "WallClockStart", "WallClockEnd"):
        if key in raw_metadata:
            out[key] = raw_metadata[key]

    # moms cube
    if kind == "moms_cube":
        _put(out, "SubCubeIndex", "".join("abc"[i] if i < 3 else str(i) for i in raw_metadata.get("SubCubeIndex_xyz", [])))
        _put(out, "SubCubeEdge", raw_metadata.get("SubCubeEdge"))
        _put(out, "FilesInDump", raw_metadata.get("FilesInDump"))
        _put(out, "DumpComplete", _yes_no(raw_metadata.get("DumpComplete")))
        _put(out, "CubeBriquettesPerDim", raw_metadata.get("CubeBriquettesPerDim"))
        _put(out, "DataType", raw_metadata.get("DataType"))
        _put(out, "VariablesDocumented", _yes_no(raw_metadata.get("VariablesJson")))
        _put(out, "CubeVariables", "; ".join(
            f"{v['Name']} — {v['Description']} [{v['Units']}]" for v in raw_metadata.get("Variables", [])
        ))
    elif kind == "prfs_companion":
        _put(out, "DataType", raw_metadata.get("DataType"))

    # include
    _put(out, "StellarModel", (f"{raw_metadata['StellarMass']}, MESA model {raw_metadata['MESAModelNumber']}"
                               if "StellarMass" in raw_metadata else None))
    if kind == "setup_include":
        hc = raw_metadata.get("HeaderConstants") or {}
        _put(out, "RadialPoints", raw_metadata.get("RadialPoints"))
        _put(out, "RadiusMin_Mm", raw_metadata.get("RadiusMin_Mm"))
        _put(out, "RadiusMax_Mm", raw_metadata.get("RadiusMax_Mm"))
        _put(out, "EntropyMin", raw_metadata.get("EntropyMin"))
        _put(out, "EntropyMax", raw_metadata.get("EntropyMax"))
        _put(out, "BasePressure", hc.get("pressure P0"))
        _put(out, "InnerEnclosedMass", hc.get("mass m0"))
        _put(out, "MeanMolecularWeightAir", hc.get("airmu"))
        _put(out, "MeanMolecularWeightCloud", hc.get("cldmu"))

    # flags
    if kind == "flags":
        _put(out, "SetupFileName", raw_metadata.get("SetupFileName"))
        _put(out, "OpacityModel", ", ".join(raw_metadata.get("OpacityModels", [])))

    return out
