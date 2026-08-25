# utils/integrity.py
#
# Persists MD5 checksums for a batch of files to checksums.json in the same
# folder, and compares a later re-scan against that record. This lets a
# curator confirm a dataset hasn't been altered between sessions — the same
# check archivists run against a fixity/manifest file in FRDR/Archivematica.

import hashlib
import json
import os

CHECKSUMS_FILENAME = "checksums.json"


def compute_md5(file_path):
    h = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def checksums_path_for_folder(folder):
    return os.path.join(folder, CHECKSUMS_FILENAME)


def save_checksums(folder, checksums_by_filename):
    """
    Writes {filename: md5} to checksums.json in folder.
    Returns the path written.
    """
    out_path = checksums_path_for_folder(folder)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(checksums_by_filename, f, indent=4, sort_keys=True)
    return out_path


def load_checksums(folder):
    """Returns the stored {filename: md5} dict, or None if no record exists."""
    path = checksums_path_for_folder(folder)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def verify_checksums(stored, current):
    """
    Compares a stored {filename: md5} record against a current one.

    Returns {filename: status} where status is one of:
      OK       — checksum matches
      MODIFIED — file present in both, but the checksum changed
      MISSING  — file was recorded but is not present now
      NEW      — file is present now but was not in the stored record
    """
    status_by_filename = {}
    for name in set(stored) | set(current):
        if name not in current:
            status_by_filename[name] = "MISSING"
        elif name not in stored:
            status_by_filename[name] = "NEW"
        elif stored[name] != current[name]:
            status_by_filename[name] = "MODIFIED"
        else:
            status_by_filename[name] = "OK"
    return status_by_filename
