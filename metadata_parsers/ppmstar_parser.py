# metadata_parsers/ppmstar_parser.py
#
# Extracts metadata from the output files of PPMstar, the 3-D stellar
# hydrodynamics code of the PPMstar collaboration (Woodward, Herwig et al.),
# as released in FRDR simulation datasets. None of these files is an image
# and none carries a self-describing header like FITS, so each kind is
# recognised by extension + location and read with plain text/size parsing:
#
#   .rprof   spherically averaged radial profiles of one dump. ASCII, despite
#            dataset READMEs calling it binary: a run banner (dump, cycle,
#            problem time, performance counters), ~30 numeric tables, a
#            free-text run description and the code's parameter blocks.
#            frombqavs/*BQav*.rprof is a different, single-table variant.
#   .hstry   text history, one row per dump.
#   .aaa ... raw float32 "moms" cube blocks (moms/<name>/<dump>/), headerless
#            — geometry is inferred from the file size and, when available,
#            from the variables.json the data release ships per run.
#            The same extensions inside prfs/ are opaque internal companions.
#   .include initial 1-D stratification (Fortran-wrapped text table).
#   .F       minimal flags file: #define lines only.
#
# Cube data is never read, only sized: files reach 2.3 GB each.

import json
import os
import re

_FLOAT = r"[-+]?\d+\.?\d*(?:[EeDd][-+]?\d+)?"

# 8 sub-cubes (2x2x2) in the released data; letters a..c cover up to 3x3x3.
CUBE_EXTENSIONS = [f".{a}{b}{c}" for a in "abc" for b in "abc" for c in "abc"]
PPMSTAR_EXTENSIONS = [".rprof", ".hstry", ".include", ".f"] + CUBE_EXTENSIONS

_CUBE_EXT_RE = re.compile(r"^\.[a-c]{3}$")
_DUMP_RE = re.compile(r"-(?:BQav)?(\d+)\.[^.]+$")
_RUNID_RE = re.compile(r"^(.*?)-(?:BQav)?\d+\.[^.]+$")
_NVAR = 10  # variables per moms cube file, fixed by the release layout


def _num(text):
    try:
        return float(text.replace("D", "E").replace("d", "e"))
    except ValueError:
        return None


def _run_label(file_path):
    """Run directory name (e.g. O32): parent of prfs/ or moms/, else the file's folder."""
    parts = os.path.normpath(os.path.abspath(file_path)).split(os.sep)
    for marker in ("prfs", "moms"):
        if marker in parts[:-1]:
            i = len(parts) - 2 - parts[:-1][::-1].index(marker)
            return parts[i - 1] if i > 0 else ""
    return os.path.basename(os.path.dirname(os.path.abspath(file_path)))


def _find_variables_json(file_path, max_up=4):
    d = os.path.dirname(os.path.abspath(file_path))
    for _ in range(max_up):
        cand = os.path.join(d, "variables.json")
        if os.path.isfile(cand):
            try:
                with open(cand, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (OSError, ValueError):
                return None
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return None


def _classify(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".rprof":
        return "rprof"
    if ext == ".hstry":
        return "hstry"
    if ext == ".include":
        return "setup_include"
    if ext == ".f":
        return "flags"
    if _CUBE_EXT_RE.match(ext):
        parts = os.path.normpath(os.path.abspath(file_path)).split(os.sep)
        return "prfs_companion" if "prfs" in parts[:-1] else "moms_cube"
    return "unknown"


# ── .rprof ────────────────────────────────────────────────────────────────

def _parse_param_line(line, into):
    """Reads '  17   name  value   name  value' pairs into `into`."""
    toks = line.split()
    if len(toks) < 3 or not toks[0].isdigit():
        return False
    i, found = 1, False
    while i + 1 < len(toks):
        name, val = toks[i], toks[i + 1]
        v = _num(val)
        if v is None:
            i += 1
            continue
        into[name] = int(v) if re.fullmatch(r"-?\d+", val) else v
        found = True
        i += 2
    return found


def _parse_rprof(file_path, raw, text):
    tables = []          # {"Columns": [...], "Rows": n}
    description = []
    int_params, real_params = {}, {}
    radius_range = None

    with open(file_path, "r", encoding="latin-1") as f:
        lines = f.read().splitlines()

    banner = "\n".join(lines[:40])
    m = re.search(r"DUMP\s+(\d+)\s+at time step #\s*(\d+),\s+at problem time =\s*(" + _FLOAT +
                  r"),\s+and at\s+(.+)", banner)
    if m:
        raw["DumpNumber"] = int(m.group(1))
        raw["TimeStep"] = int(m.group(2))
        raw["ProblemTime_s"] = _num(m.group(3))
        raw["WallClockTimestamp"] = m.group(4).strip()
    m = re.search(r"dt =\s*(" + _FLOAT + r"),\s+courmx =\s*(" + _FLOAT + r")", banner)
    if m:
        raw["TimeStepSize_s"] = _num(m.group(1))
        raw["CourantNumber"] = _num(m.group(2))
    m = re.search(r"Gflop/s =\s*(" + _FLOAT + r")\s+threads/rank =\s*(\d+),\s+nranks =\s*(\d+)", banner)
    if m:
        raw["Gflops"] = _num(m.group(1))
        raw["ThreadsPerRank"] = int(m.group(2))
        raw["MPIRanks"] = int(m.group(3))
    m = re.search(r"Nx =\s*(\d+)", banner)
    if m:
        raw["GridCellsPerDim"] = int(m.group(1))

    i, n = 0, len(lines)
    in_first_table = True
    while i < n:
        line = lines[i]
        s = line.strip()
        if s.startswith("IR") and len(s.split()) > 2:
            cols = s.split()
            j = i + 1
            while j < n and not lines[j].strip():
                j += 1
            rows = 0
            rmin = rmax = None
            while j < n and re.match(r"^\s*\d+\s", lines[j]) and len(lines[j].split()) >= 2:
                if in_first_table and cols[1] == "R":
                    r = _num(lines[j].split()[1])
                    if r is not None:
                        rmin = r if rmin is None else min(rmin, r)
                        rmax = r if rmax is None else max(rmax, r)
                rows += 1
                j += 1
            tables.append({"Columns": cols[1:], "Rows": rows})
            if in_first_table and rmin is not None:
                radius_range = (rmin, rmax)
            in_first_table = False
            i = j
            continue
        if s.startswith("Line of sight"):
            raw["LinesOfSight"] = raw.get("LinesOfSight", 0) + 1
        elif s.startswith("DATE:"):
            raw["RunDate"] = s
            j = i + 1
            while j < n and lines[j].strip():
                description.append(lines[j].strip())
                j += 1
            i = j
            continue
        elif tables:
            # parameter blocks trail the last table: ints first, then reals
            block = real_params if int_params and re.search(r"\d\.\d+E[-+]\d+", s) else int_params
            _parse_param_line(line, block)
        i += 1

    raw["ProfileTableCount"] = len(tables)
    raw["ProfileTables"] = tables
    variables = []
    for t in tables:
        for c in t["Columns"]:
            if c != "R" and c not in variables:
                variables.append(c)
    raw["ProfileVariables"] = variables
    raw["ProfileRowCounts"] = sorted({t["Rows"] for t in tables})
    if radius_range:
        raw["RadiusMin_Mm"], raw["RadiusMax_Mm"] = radius_range
    raw["RunDescription"] = " ".join(description)
    raw["IntegerParameters"] = int_params
    raw["RealParameters"] = real_params

    text.append(f"Dump: {raw.get('DumpNumber', '?')}   Cycle: {raw.get('TimeStep', '?')}   "
                f"Problem time: {raw.get('ProblemTime_s', '?')} s")
    text.append(f"Wall clock: {raw.get('WallClockTimestamp', '?')}   "
                f"Ranks: {raw.get('MPIRanks', '?')} x {raw.get('ThreadsPerRank', '?')} threads")
    text.append(f"Hydro grid: {raw.get('GridCellsPerDim', '?')}^3   dt: {raw.get('TimeStepSize_s', '?')} s   "
                f"Courant: {raw.get('CourantNumber', '?')}")
    if radius_range:
        text.append(f"Radial grid: {radius_range[0]:.3f} .. {radius_range[1]:.3f} Mm")
    text.append(f"Profile tables: {len(tables)} ({', '.join(str(r) for r in raw['ProfileRowCounts'])} rows)")
    text.append(f"Profile variables ({len(variables)}): {', '.join(variables)}")
    if raw["RunDescription"]:
        text.append(f"Run description: {raw['RunDescription']}")
    text.append(f"Code parameters: {len(int_params)} integer/flag, {len(real_params)} real")
    if not tables:
        text.append("Warning: no profile tables found — file may be truncated or not an rprof.")


def _parse_bqav_rprof(file_path, raw, text):
    """frombqavs/*BQav*.rprof: one table of spherical averages of the cube variables."""
    with open(file_path, "r", encoding="latin-1") as f:
        lines = [l for l in f.read().splitlines() if l.strip()]
    if not lines or not lines[0].strip().lower().startswith("ir"):
        raise ValueError("no 'ir' header line found")
    cols = [c.strip("-") for c in lines[0].split()[1:]]
    rows = len(lines) - 1
    raw["Variant"] = "cube spherical averages (frombqavs)"
    raw["ProfileVariables"] = cols
    raw["RadialPoints"] = rows
    text.append("Variant: spherical averages of the 3-D moms cube variables (frombqavs)")
    text.append(f"Radial points: {rows}")
    text.append(f"Variables ({len(cols)}): {', '.join(cols)}")


# ── .hstry ────────────────────────────────────────────────────────────────

def _parse_hstry(file_path, raw, text):
    with open(file_path, "r", encoding="latin-1") as f:
        lines = f.read().splitlines()
    header = next((l for l in lines if l.strip().startswith("NDump")), None)
    if header is None:
        raise ValueError("no NDump header line found")
    cols = header.split()
    # TimeStamp holds spaces ("Tue Mar 10 20:36:06 2026"): split off the fixed columns only
    n_fixed = len(cols) - 1
    rows = []
    for l in lines:
        t = l.split(None, n_fixed)
        if len(t) == len(cols) and t[0].isdigit():
            rows.append(t)
    raw["Columns"] = cols
    raw["DumpRecordCount"] = len(rows)
    if not rows:
        text.append("Columns: " + ", ".join(cols))
        text.append("Warning: history table is empty.")
        return

    def col(name):
        return [_num(r[cols.index(name)]) for r in rows]

    dumps = [int(r[0]) for r in rows]
    raw["FirstDump"], raw["LastDump"] = dumps[0], dumps[-1]
    raw["MissingDumpCount"] = (dumps[-1] - dumps[0] + 1) - len(set(dumps))
    # A dump number recorded more than once means the run was restarted from
    # an earlier checkpoint; the repeated rows can differ in cycle and time.
    raw["DuplicateDumpRecords"] = len(dumps) - len(set(dumps))
    times = col("time(secs)")
    raw["StartTime_s"], raw["EndTime_s"] = times[0], times[-1]
    dts = [v for v in col("dt(secs)") if v]
    if dts:
        raw["TimeStepMin_s"], raw["TimeStepMax_s"] = min(dts), max(dts)
    if "MachNoMax" in cols:
        raw["MachNumberMax"] = max(v for v in col("MachNoMax") if v is not None)
    if "TotalFlops" in cols:
        raw["TotalFlops"] = col("TotalFlops")[-1]
    ts_i = cols.index("TimeStamp") if "TimeStamp" in cols else None
    if ts_i is not None:
        raw["WallClockStart"], raw["WallClockEnd"] = rows[0][ts_i], rows[-1][ts_i]
    raw["MonotonicTime"] = all(b >= a for a, b in zip(times, times[1:]))

    text.append(f"Columns: {', '.join(cols)}")
    text.append(f"Dump records: {len(rows)} (dumps {dumps[0]}..{dumps[-1]}, missing: {raw['MissingDumpCount']}, "
                f"repeated: {raw['DuplicateDumpRecords']})")
    text.append(f"Simulated time: {times[0]:.5g} .. {times[-1]:.5g} s ({times[-1] / 3600.0:.3f} h)")
    if dts:
        text.append(f"dt range: {raw['TimeStepMin_s']:.4g} .. {raw['TimeStepMax_s']:.4g} s")
    if "MachNumberMax" in raw:
        text.append(f"Max Mach number over run: {raw['MachNumberMax']:.4g}")
    if ts_i is not None:
        text.append(f"Wall clock: {raw['WallClockStart']} -> {raw['WallClockEnd']}")
    if raw["DuplicateDumpRecords"]:
        text.append(f"Note: {raw['DuplicateDumpRecords']} repeated dump records — the run was restarted from "
                    "earlier checkpoints, so a dump number can map to more than one time here.")
    if not raw["MonotonicTime"]:
        text.append("Warning: problem time is not monotonically increasing.")


# ── moms cubes and companions ─────────────────────────────────────────────

def _parse_cube(file_path, raw, text):
    size = os.path.getsize(file_path)
    ext = os.path.splitext(file_path)[1].lower()
    dump_m = _DUMP_RE.search(os.path.basename(file_path))
    dump = int(dump_m.group(1)) if dump_m else None
    n_floats = size // 4
    m = round((n_floats / _NVAR) ** (1.0 / 3.0)) if n_floats else 0
    consistent = size % 4 == 0 and m ** 3 * _NVAR * 4 == size
    raw["DataType"] = "float32 little-endian, no header"
    raw["VariablesPerFile"] = _NVAR
    raw["SubCubeIndex_xyz"] = [ord(c) - 97 for c in ext[1:]]
    raw["SubCubeEdgeWithGhosts"] = m
    raw["SubCubeEdge"] = m - 2
    raw["LayoutConsistent"] = consistent
    if dump is not None:
        raw["DumpNumber"] = dump

    siblings = []
    if dump is not None:
        d = os.path.dirname(os.path.abspath(file_path))
        tail = f"-BQav{dump_m.group(1)}."
        siblings = sorted(f for f in os.listdir(d) if tail in f and _CUBE_EXT_RE.match(os.path.splitext(f)[1]))
    n_files = len(siblings) or 1
    s = round(n_files ** (1.0 / 3.0))
    raw["FilesInDump"] = n_files
    raw["SubCubesPerDim"] = s
    raw["DumpComplete"] = s ** 3 == n_files
    raw["SiblingSizesEqual"] = len({os.path.getsize(os.path.join(os.path.dirname(os.path.abspath(file_path)), f))
                                    for f in siblings}) <= 1 if siblings else True
    if consistent and s ** 3 == n_files:
        raw["CubeBriquettesPerDim"] = (m - 2) * s
        raw["HydroCellsPerDim"] = (m - 2) * s * 4   # each briquette averages 4x4x4 cells

    meta = _find_variables_json(file_path)
    if meta:
        raw["VariablesJson"] = True
        raw["RunID"] = meta.get("runid", "")
        raw["ReleasedGrid"] = meta.get("grid")
        raw["ExpectedFilesPerDump"] = meta.get("files_per_dump")
        raw["ExpectedBytesPerFile"] = meta.get("bytes_per_file")
        raw["Variables"] = [
            {"Index": v.get("index"), "Name": v.get("name"), "Description": v.get("description", ""),
             "Units": v.get("units", ""), "Definition": v.get("definition", ""),
             "MaskedOutsideStar": v.get("masked_outside_star")}
            for v in meta.get("variables", [])
        ]
        if dump is not None:
            t = (meta.get("dump_times_s") or {}).get(str(dump))
            raw["ProblemTime_s"] = t
            raw["DumpListedInVariablesJson"] = str(dump) in (meta.get("dump_times_s") or {}) or \
                dump in (meta.get("dumps") or [])
        raw["MatchesVariablesJsonLayout"] = (
            meta.get("bytes_per_file") == size and meta.get("files_per_dump") == n_files
        )
    else:
        raw["VariablesJson"] = False

    text.append(f"Kind: raw 3-D moms cube block ({raw['DataType']})")
    text.append(f"File size: {size} bytes ({size / 1e9:.3f} GB)")
    text.append(f"Sub-cube index (x,y,z): {tuple(raw['SubCubeIndex_xyz'])}   "
                f"edge: {m - 2} (+2 ghost layers = {m}), {_NVAR} variables")
    text.append(f"Files in this dump: {n_files} ({s}x{s}x{s} sub-cubes) — "
                f"{'complete' if raw['DumpComplete'] else 'INCOMPLETE'}")
    if "HydroCellsPerDim" in raw:
        text.append(f"Assembled cube: {raw['CubeBriquettesPerDim']}^3 briquettes "
                    f"(= {raw['HydroCellsPerDim']}^3 hydro cells)")
    if not consistent:
        text.append("Warning: file size is not 10 x (n+2)^3 float32 values — layout unrecognised or file truncated.")
    if meta:
        text.append(f"variables.json found — run {meta.get('run', '?')}, grid {meta.get('grid', '?')}^3")
        if raw.get("ProblemTime_s") is not None:
            text.append(f"Problem time of this dump: {raw['ProblemTime_s']} s")
        for v in raw["Variables"]:
            text.append(f"  [{v['Index']}] {v['Name']}: {v['Description']} ({v['Units']})")
        if not raw["MatchesVariablesJsonLayout"]:
            text.append("Warning: size / file count differs from variables.json.")
    else:
        text.append("No variables.json found within 4 folders up — variable names and units are unknown.")


def _parse_companion(file_path, raw, text):
    size = os.path.getsize(file_path)
    stem = os.path.splitext(file_path)[0]
    raw["DataType"] = "float32 array (PPMstar-internal)"
    raw["FloatCount"] = size // 4
    raw["PairedRprofPresent"] = os.path.isfile(stem + ".rprof")
    dump_m = _DUMP_RE.search(os.path.basename(file_path))
    if dump_m:
        raw["DumpNumber"] = int(dump_m.group(1))
    text.append("Kind: PPMstar-internal companion array (not documented, not needed to read the release)")
    text.append(f"File size: {size} bytes ({raw['FloatCount']} float32 values)")
    text.append(f"Paired .rprof present: {raw['PairedRprofPresent']}")


# ── .include and .F ───────────────────────────────────────────────────────

def _parse_include(file_path, raw, text):
    with open(file_path, "r", encoding="latin-1") as f:
        lines = f.read().splitlines()
    comments = [l[1:].strip() for l in lines if l[:1] in ("c", "C") and l[1:2] in (" ", "")]
    raw["Comments"] = comments
    for c in comments:
        m = re.search(r"M\s*=\s*(\S+),\s*MESA cycle\s*(\d+)", c)
        if m:
            raw["StellarMass"], raw["MESAModelNumber"] = m.group(1), int(m.group(2))
        m = re.search(r"There are\s+(\d+)\s+radial points", c)
        if m:
            raw["DeclaredRadialPoints"] = int(m.group(1))
        if c.lower().startswith(("dir =", "1d model =")):
            raw.setdefault("SourcePaths", []).append(c)
    header = {}
    for m in re.finditer(r'"H\s+(.+?)\s*=\s*(' + _FLOAT + r')"', "\n".join(lines)):
        header[m.group(1).strip()] = _num(m.group(2))
    raw["HeaderConstants"] = header
    table = []
    for m in re.finditer(r'"\s+(' + _FLOAT + r')\s+(' + _FLOAT + r')\s+(' + _FLOAT + r')\s*"', "\n".join(lines)):
        table.append((_num(m.group(1)), _num(m.group(2)), _num(m.group(3))))
    raw["RadialPoints"] = len(table)
    if table:
        raw["RadiusMin_Mm"], raw["RadiusMax_Mm"] = table[0][0], table[-1][0]
        raw["EntropyMin"], raw["EntropyMax"] = min(t[1] for t in table), max(t[1] for t in table)
        raw["MuMin"], raw["MuMax"] = min(t[2] for t in table), max(t[2] for t in table)
    text.append("Kind: initial 1-D stratification (setup file)")
    for c in comments:
        text.append(f"  {c}")
    for k, v in header.items():
        text.append(f"{k}: {v}")
    text.append(f"Radial points: {len(table)}" + (f" (declared {raw['DeclaredRadialPoints']})"
                                                   if "DeclaredRadialPoints" in raw else ""))
    if table:
        text.append(f"Radius: {raw['RadiusMin_Mm']} .. {raw['RadiusMax_Mm']} Mm")
    if "DeclaredRadialPoints" in raw and raw["DeclaredRadialPoints"] != len(table):
        text.append("Warning: declared and parsed radial point counts differ.")
    if not table:
        text.append("Warning: no radius/S/mu table rows found.")


def _parse_flags(file_path, raw, text):
    with open(file_path, "r", encoding="latin-1") as f:
        lines = f.read().splitlines()
    defines = {}
    for l in lines:
        m = re.match(r"#define\s+(\S+)\s+(.*\S)?", l)
        if m:
            defines[m.group(1)] = (m.group(2) or "").strip().strip('"')
    raw["Defines"] = defines
    raw["SetupFileName"] = defines.get("setupfilename", "")
    raw["OpacityModels"] = [k for k, v in defines.items() if k.startswith("iskappa") and v == "1"]
    raw["OpacityCoefficientCount"] = sum(1 for k in defines if re.fullmatch(r"aa\d+", k))
    raw["Comments"] = [l[1:].strip() for l in lines if l[:1] in ("c", "C") and l[1:2] in (" ", "")]
    text.append("Kind: minimal PPMstar flags file (#define lines read by ppmpy)")
    text.append(f"Setup file: {raw['SetupFileName'] or '(none)'}")
    text.append(f"Opacity model(s): {', '.join(raw['OpacityModels']) or '(none)'}   "
                f"coefficients: {raw['OpacityCoefficientCount']}")
    text.append(f"#define entries: {len(defines)}")
    if not defines:
        text.append("Warning: no #define lines found.")


# ── entry point ───────────────────────────────────────────────────────────

_HANDLERS = {
    "hstry": _parse_hstry,
    "moms_cube": _parse_cube,
    "prfs_companion": _parse_companion,
    "setup_include": _parse_include,
    "flags": _parse_flags,
}


def parse_ppmstar_metadata(file_path, application=None):
    """
    Extracts metadata from a PPMstar simulation output file.

    Returns:
        - text_report: human-readable report.
        - raw_metadata: dict; always has FilePath, FileKind, FileSizeBytes.
    """
    text_lines = [f"PPMstar Metadata Report for {os.path.basename(file_path)}"]
    raw_metadata = {"FilePath": file_path}

    try:
        kind = _classify(file_path)
        raw_metadata["FileKind"] = kind
        raw_metadata["FileSizeBytes"] = os.path.getsize(file_path)
        raw_metadata["Code"] = "PPMstar"
        raw_metadata["RunLabel"] = _run_label(file_path)
        m = _RUNID_RE.match(os.path.basename(file_path))
        if m:
            raw_metadata["RunID"] = m.group(1)
        dump_m = _DUMP_RE.search(os.path.basename(file_path))
        if dump_m:
            raw_metadata["DumpNumber"] = int(dump_m.group(1))
        text_lines.append(f"Run: {raw_metadata['RunLabel'] or '(unknown)'}   "
                          f"Run ID: {raw_metadata.get('RunID', '(n/a)')}")

        if kind == "rprof":
            with open(file_path, "r", encoding="latin-1") as f:
                first = next((l for l in f if l.strip()), "")
            if first.strip().lower().startswith("ir"):
                _parse_bqav_rprof(file_path, raw_metadata, text_lines)
            else:
                _parse_rprof(file_path, raw_metadata, text_lines)
        elif kind in _HANDLERS:
            _HANDLERS[kind](file_path, raw_metadata, text_lines)
        else:
            text_lines.append("Failed to read PPMstar file: unrecognised file kind")
    except Exception as e:
        text_lines.append(f"Failed to read PPMstar file: {str(e)}")

    return "\n".join(text_lines), raw_metadata
