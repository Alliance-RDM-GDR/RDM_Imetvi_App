# utils/manifest.py
#
# Verifies a dataset against its own MANIFEST.sha256 (the `sha256sum` format
# repositories such as FRDR ask depositors to ship): one line per file,
# "<64 hex digits>  <relative/path>" with forward slashes, relative to the
# manifest's folder. Complements utils/integrity.py, which only tracks the
# app's own MD5 checksums.json.
#
# Datasets can reach ~1 TB / tens of thousands of files, so nothing here
# reads a file whole, and the two stages are separate:
#   - check_coverage(): names only (a directory walk), seconds even for 25k files
#   - verify_manifest(): streams every file through SHA-256 in chunks, with a
#     progress callback and a cancel callback, and can be limited to a subset.
# Qt-free on purpose so it can be unit tested; main.py runs it in a QThread.

import hashlib
import os
import re

MANIFEST_FILENAME = "MANIFEST.sha256"
CHUNK_SIZE = 1 << 20          # 1 MiB
PROGRESS_EVERY_BYTES = 64 << 20

_LINE_RE = re.compile(r"^([0-9a-fA-F]{64}) [ *](.+)$")


def parse_manifest(path):
    """
    Reads a sha256sum-format manifest.

    Returns (entries, bad_lines):
      entries   — {relative_path: lowercase_hex_digest}, paths with forward
                  slashes and any leading "./" removed
      bad_lines — [(line_number, text)] for non-blank lines that don't parse
                  (including sha256sum's backslash-escaped lines, which this
                  reader does not support). A path listed twice keeps the
                  last digest and is reported as a bad line.
    """
    entries, bad_lines = {}, []
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
        for number, line in enumerate(f, 1):
            line = line.rstrip("\r\n")
            if not line.strip():
                continue
            m = None if line.startswith("\\") else _LINE_RE.match(line)
            if not m:
                bad_lines.append((number, line))
                continue
            rel = m.group(2)
            if rel.startswith("./"):
                rel = rel[2:]
            if rel in entries:
                bad_lines.append((number, f"duplicate entry: {rel}"))
            entries[rel] = m.group(1).lower()
    return entries, bad_lines


def _is_unsafe(rel):
    parts = rel.split("/")
    return rel.startswith("/") or ".." in parts or re.match(r"^[A-Za-z]:", rel) is not None


def list_files(folder, exclude=()):
    """Relative forward-slash paths of every file under folder, minus `exclude`."""
    exclude = set(exclude)
    found = []
    for dirpath, _, filenames in os.walk(folder):
        for name in filenames:
            rel = os.path.relpath(os.path.join(dirpath, name), folder).replace(os.sep, "/")
            if rel not in exclude:
                found.append(rel)
    return found


def check_coverage(folder, entries, manifest_rel=MANIFEST_FILENAME):
    """
    Compares the manifest's file list with what is on disk. Names only —
    no file is opened. The manifest file itself is ignored on both sides.

    Returns {"listed": n, "on_disk": n, "unlisted": [...], "missing": [...]}
    where unlisted = on disk but not in the manifest, and
    missing = in the manifest but not on disk. Both lists are sorted.
    """
    on_disk = set(list_files(folder, exclude={manifest_rel}))
    listed = set(entries) - {manifest_rel}
    return {
        "listed": len(listed),
        "on_disk": len(on_disk),
        "unlisted": sorted(on_disk - listed),
        "missing": sorted(listed - on_disk),
    }


def sha256_file(path, cancel=None, on_bytes=None, chunk_size=CHUNK_SIZE):
    """
    Streaming SHA-256 of one file. Returns the hex digest, or None if
    `cancel()` returned True between chunks. `on_bytes(n)` is called with the
    size of each chunk read. Raises OSError if the file can't be read.
    """
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            if cancel is not None and cancel():
                return None
            block = f.read(chunk_size)
            if not block:
                return h.hexdigest()
            h.update(block)
            if on_bytes is not None:
                on_bytes(len(block))


def verify_manifest(folder, entries, paths=None, progress=None, cancel=None, chunk_size=CHUNK_SIZE):
    """
    Hashes the manifest's files and compares them with the recorded digests.

    paths     — optional iterable of manifest paths to check (default: all).
                Paths not in the manifest are ignored.
    progress  — optional callable(files_done, files_total, rel_path,
                bytes_done, bytes_total), called when each file starts and
                about every 64 MiB read within a file.
    cancel    — optional callable() -> bool, polled between chunks; when it
                returns True the run stops and "cancelled" is True.

    Returns {"status": {rel_path: status}, "cancelled": bool, "bytes_hashed": n}
    with status one of:
      OK          — digest matches
      MODIFIED    — file present, digest differs
      MISSING     — listed but not on disk
      UNREADABLE  — present but could not be read (message in "errors")
      UNSAFE_PATH — path is absolute or climbs out of the folder; never opened
    Files not reached before a cancel are absent from "status".
    """
    wanted = sorted(entries if paths is None else (p for p in paths if p in entries))
    result = {"status": {}, "errors": {}, "cancelled": False, "bytes_hashed": 0}

    sizes = {}
    for rel in wanted:
        if _is_unsafe(rel):
            continue
        try:
            sizes[rel] = os.path.getsize(os.path.join(folder, rel))
        except OSError:
            pass
    bytes_total = sum(sizes.values())
    state = {"bytes": 0, "last_report": 0}

    for index, rel in enumerate(wanted, 1):
        if cancel is not None and cancel():
            result["cancelled"] = True
            break
        if _is_unsafe(rel):
            result["status"][rel] = "UNSAFE_PATH"
            continue
        full = os.path.join(folder, rel)
        if rel not in sizes:
            result["status"][rel] = "MISSING" if not os.path.exists(full) else "UNREADABLE"
            if result["status"][rel] == "UNREADABLE":
                result["errors"][rel] = "cannot stat file"
            continue

        if progress is not None:
            progress(index - 1, len(wanted), rel, state["bytes"], bytes_total)
            state["last_report"] = state["bytes"]

        def on_bytes(n, rel=rel, index=index):
            state["bytes"] += n
            if progress is not None and state["bytes"] - state["last_report"] >= PROGRESS_EVERY_BYTES:
                state["last_report"] = state["bytes"]
                progress(index - 1, len(wanted), rel, state["bytes"], bytes_total)

        try:
            digest = sha256_file(full, cancel=cancel, on_bytes=on_bytes, chunk_size=chunk_size)
        except OSError as e:
            result["status"][rel] = "UNREADABLE"
            result["errors"][rel] = str(e)
            continue
        if digest is None:
            result["cancelled"] = True
            break
        result["status"][rel] = "OK" if digest == entries[rel] else "MODIFIED"

    result["bytes_hashed"] = state["bytes"]
    if progress is not None and not result["cancelled"]:
        progress(len(wanted), len(wanted), "", state["bytes"], bytes_total)
    return result


def format_bytes(n):
    """Human-readable size (binary units), e.g. 878 GB -> '817.6 GiB'."""
    n = float(n)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TiB"


def total_size(folder, rel_paths):
    """Sum of on-disk sizes of the given manifest paths (missing/unsafe ones count 0)."""
    total = 0
    for rel in rel_paths:
        if _is_unsafe(rel):
            continue
        try:
            total += os.path.getsize(os.path.join(folder, rel))
        except OSError:
            pass
    return total
