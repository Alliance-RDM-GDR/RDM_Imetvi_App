# metadata_parsers/eyelink_parser.py
#
# Streaming reader for SR Research EyeLink ASCII (.asc) files, the text export
# of an EDF recording (edf2asc). A recording is hundreds of thousands of sample
# lines, so the file is read once, line by line: header, recording
# configuration, calibration/validation messages and event summaries are kept;
# samples are only counted (and their timestamps used to check the rate).

import os
import re

EYELINK_EXTENSIONS = [".asc"]

_MAX_HEADER_LINES = 60
_MAX_KEYWORDS = 60
_VALIDATION_RE = re.compile(
    r"!CAL VALIDATION (\S+) (\S) (\S+) (\w+)\s+ERROR ([\d.]+) avg\.\s+([\d.]+) max\s+OFFSET ([\d.]+) deg")
_CALIBRATION_RE = re.compile(r"!CAL CALIBRATION (\S+) (\S) (\S+)\s+(\w+)")
_MODE_RE = re.compile(r"!MODE RECORD (\w+) (\d+) (\d+) (\d+) (\w+)")
_GEOMETRY_RE = re.compile(r"(disttoscreen|sheightinches|swidthinches|PPD)\s+([-\d.]+)")
_REDACTED = "removed"


def _num(text):
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def parse_eyelink_metadata(file_path, application=None):
    """
    Reads an EyeLink .asc file in a single streaming pass. Returns
    (text_report, raw_metadata) per the parser contract; a read failure or a
    file that is not an EyeLink export is reported in the text, never raised.
    """
    fname = os.path.basename(file_path)
    text = [f"EyeLink ASC Metadata Report for {fname}"]
    raw = {"FilePath": file_path, "FileSize": 0}
    try:
        raw["FileSize"] = os.path.getsize(file_path)
    except OSError as e:
        text.append(f"Failed to read file: {e}")
        return "\n".join(text), raw

    header = []
    config = {}
    geometry = {}
    keywords = {}
    trial_vars = {}
    validations, calibrations = [], []
    blocks = []          # one dict per START..END recording block
    cur = None
    counts = {"Samples": 0, "MissingSamples": 0, "Fixations": 0, "Saccades": 0, "Blinks": 0,
              "InputEvents": 0, "Messages": 0, "Trials": 0, "TrialResults": 0}
    fix_ms = blink_ms = 0
    saw_eyelink = False

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            in_header = True
            for line in f:
                c = line[:1]
                if c.isdigit():  # a sample line: time, x, y, pupil, ...
                    counts["Samples"] += 1
                    parts = line.split("\t", 3)
                    in_header = False
                    if len(parts) > 2 and parts[1].strip() == ".":
                        counts["MissingSamples"] += 1
                    if cur is not None:
                        ts = int(parts[0]) if parts[0].isdigit() else None
                        if ts is not None:
                            if cur["First"] is None:
                                cur["First"] = ts
                            cur["Last"] = ts
                            cur["Samples"] += 1
                    continue
                if c == "*":
                    if in_header and len(header) < _MAX_HEADER_LINES:
                        header.append(line.rstrip("\n").lstrip("*").strip())
                    continue
                in_header = False
                if c == "M" and line.startswith("MSG"):
                    counts["Messages"] += 1
                    fields = line.rstrip("\n").split(None, 2)
                    if len(fields) < 3:
                        continue
                    ts, msg = fields[1], fields[2]
                    key = msg.split(None, 1)[0]
                    if key.startswith("!"):
                        key = " ".join(msg.split(None, 2)[:2])
                    if key in keywords or len(keywords) < _MAX_KEYWORDS:
                        keywords[key] = keywords.get(key, 0) + 1
                    if msg.startswith("DISPLAY_COORDS"):
                        config["DisplayCoords"] = [_num(v) for v in msg.split()[1:5]]
                    elif msg.startswith("GAZE_COORDS"):
                        config["GazeCoords"] = [_num(v) for v in msg.split()[1:5]]
                    elif msg.startswith("RETRACE_INTERVAL"):
                        config["RetraceInterval_ms"] = _num(msg.split()[1]) if len(msg.split()) > 1 else None
                    elif msg.startswith("RECCFG"):
                        config["RecordingConfig"] = msg[len("RECCFG"):].strip()
                    elif msg.startswith("ELCLCFG"):
                        config["CameraConfig"] = msg[len("ELCLCFG"):].strip()
                    elif msg.startswith("ELCL_PROC"):
                        config["PupilFitMethod"] = msg[len("ELCL_PROC"):].strip()
                    elif msg.startswith("!MODE RECORD"):
                        m = _MODE_RE.match(msg)
                        if m:
                            config["TrackingMode"] = m.group(1)
                            config["ModeRate"] = int(m.group(2))
                            config["ModeFilter"] = int(m.group(3))
                    elif msg.startswith("TRIALID"):
                        counts["Trials"] += 1
                    elif msg.startswith("TRIAL_RESULT"):
                        counts["TrialResults"] += 1
                    elif msg.startswith("!CAL VALIDATION"):
                        m = _VALIDATION_RE.search(msg)
                        if m:
                            validations.append({"Type": m.group(1), "Eye": m.group(2), "Grade": m.group(4),
                                                "AvgError": float(m.group(5)), "MaxError": float(m.group(6)),
                                                "Offset": float(m.group(7))})
                    elif msg.startswith("!CAL CALIBRATION"):
                        m = _CALIBRATION_RE.search(msg)
                        if m:
                            calibrations.append({"Type": m.group(1), "Eye": m.group(2), "Grade": m.group(4)})
                    elif msg.startswith("!V TRIAL_VAR"):
                        bits = msg.split(None, 3)
                        if len(bits) >= 3 and (bits[2] in trial_vars or len(trial_vars) < 80):
                            trial_vars[bits[2]] = trial_vars.get(bits[2], 0) + 1
                    elif "disttoscreen" in msg or "PPD" in msg:
                        for k, v in _GEOMETRY_RE.findall(msg):
                            geometry[k] = _num(v)
                    continue
                if c == "E":
                    if line.startswith("EFIX"):
                        counts["Fixations"] += 1
                        p = line.split()
                        if len(p) > 4 and p[4].isdigit():
                            fix_ms += int(p[4])
                    elif line.startswith("ESACC"):
                        counts["Saccades"] += 1
                    elif line.startswith("EBLINK"):
                        counts["Blinks"] += 1
                        p = line.split()
                        if len(p) > 4 and p[4].isdigit():
                            blink_ms += int(p[4])
                    elif line.startswith("END"):
                        if cur is not None:
                            m = re.search(r"RES\s+([\d.]+)\s+([\d.]+)", line)
                            if m:
                                cur["Resolution"] = [float(m.group(1)), float(m.group(2))]
                            cur["Closed"] = True
                            cur = None
                    elif line.startswith("EVENTS"):
                        saw_eyelink = True
                    continue
                if c == "S":
                    if line.startswith("START"):
                        p = line.split()
                        cur = {"Start": int(p[1]) if len(p) > 1 and p[1].isdigit() else None,
                               "Eyes": [t for t in p if t in ("LEFT", "RIGHT")],
                               "First": None, "Last": None, "Samples": 0, "Closed": False}
                        blocks.append(cur)
                        saw_eyelink = True
                    elif line.startswith("SAMPLES"):
                        p = line.split()
                        config["SampleType"] = p[1] if len(p) > 1 else ""
                        if "RATE" in p and p.index("RATE") + 1 < len(p):
                            config["Rate"] = _num(p[p.index("RATE") + 1])
                        if "TRACKING" in p and p.index("TRACKING") + 1 < len(p):
                            config["Tracking"] = p[p.index("TRACKING") + 1]
                        if "FILTER" in p and p.index("FILTER") + 1 < len(p):
                            config["Filter"] = p[p.index("FILTER") + 1]
                        config["HasInputPort"] = "INPUT" in p
                    continue
                if c == "I" and line.startswith("INPUT"):
                    counts["InputEvents"] += 1
                elif c == "P" and line.startswith("PUPIL"):
                    config["PupilMeasure"] = line.split()[1] if len(line.split()) > 1 else ""
    except OSError as e:
        text.append(f"Failed to read file: {e}")
        return "\n".join(text), raw

    head = {}
    for h in header:
        # free-text lines first: a converted path such as C:\data\x.edf contains a colon
        key = next((k for k in ("RECORDED BY", "CONVERTED FROM") if h.startswith(k)), None)
        if key:
            head[key] = h[len(key):].strip()
        elif ":" in h:
            k, v = h.split(":", 1)
            head[k.strip()] = v.strip()
        elif h.startswith("EYELINK"):
            head["Tracker software"] = h
    saw_eyelink = saw_eyelink or any("EYELINK" in h.upper() for h in header)
    if not saw_eyelink:
        text.append("Not an EyeLink ASC export (no EyeLink header or START/EVENTS lines found).")
        return "\n".join(text), raw

    # sampling rate observed from timestamps inside recording blocks
    span = sum((b["Last"] - b["First"]) for b in blocks if b["First"] is not None and b["Samples"] > 1)
    steps = sum(b["Samples"] - 1 for b in blocks if b["First"] is not None and b["Samples"] > 1)
    observed = round(1000.0 * steps / span, 2) if span > 0 else None
    recorded_ms = sum((b["Last"] - b["First"]) for b in blocks if b["First"] is not None)

    raw.update({
        "Header": head, "HeaderLines": header, "Config": config, "Geometry": geometry,
        "Counts": counts, "Keywords": keywords, "TrialVariables": sorted(trial_vars),
        "Validations": validations, "Calibrations": calibrations,
        "Blocks": len(blocks),
        "UnclosedBlocks": sum(1 for b in blocks if not b["Closed"]),
        "Eyes": sorted({e for b in blocks for e in b["Eyes"]}),
        "ObservedRate": observed, "RecordedSeconds": round(recorded_ms / 1000.0, 3),
        "FixationMs": fix_ms, "BlinkMs": blink_ms,
        "MissingFraction": round(counts["MissingSamples"] / counts["Samples"], 5) if counts["Samples"] else None,
    })

    stem = os.path.splitext(fname)[0]
    try:
        names = os.listdir(os.path.dirname(os.path.abspath(file_path)))
    except OSError:
        names = []
    raw["EdfCompanion"] = next((n for n in names if n.lower() == stem.lower() + ".edf"), "")

    rate = config.get("Rate")
    text += [
        f"Tracker: {head.get('Tracker software') or head.get('VERSION') or '?'}  |  source: {head.get('SOURCE', '?')}  |  "
        f"camera: {head.get('CAMERA', '?')}  |  serial: {head.get('SERIAL NUMBER', '?')}",
        f"Recording: {', '.join(raw['Eyes']) or '?'} eye, {rate or '?'} Hz ({config.get('Tracking', '?')} tracking, "
        f"filter {config.get('Filter', '?')}), {config.get('SampleType', '?')} samples, pupil {config.get('PupilMeasure', '?')}",
        f"{counts['Samples']:,} samples in {raw['Blocks']} block(s), {raw['RecordedSeconds']:.1f} s recorded"
        + (f", observed rate {observed:g} Hz" if observed else ""),
        f"Events: {counts['Fixations']:,} fixations, {counts['Saccades']:,} saccades, {counts['Blinks']:,} blinks; "
        f"{counts['Trials']} trials, {counts['InputEvents']} input events",
    ]
    if config.get("DisplayCoords"):
        d = config["DisplayCoords"]
        text.append(f"Display: {d[2] + 1:g} x {d[3] + 1:g} px")
    if validations:
        v = validations[-1]
        text.append(f"Validation: {len(validations)} recorded, last {v['Grade']} ({v['AvgError']} avg, {v['MaxError']} max deg)")
    else:
        text.append("Validation: none recorded in this file")
    if raw["UnclosedBlocks"]:
        text.append("WARNING: a recording block has no END line (file cut short?).")
    return "\n".join(text), raw
