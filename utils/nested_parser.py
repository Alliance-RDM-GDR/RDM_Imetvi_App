# utils/nested_parser.py

from collections import defaultdict

def set_nested_value(d, keys, value):
    """Recursive helper to set nested keys in a dict."""
    for key in keys[:-1]:
        d = d.setdefault(key, {})
    d[keys[-1]] = value

def parse_ij_metadata_info_string(info_string):
    """
    Parses the 'Info' field from IJMetadata (Zeiss-style multi-line metadata)
    into a nested dictionary structure.
    """
    parsed = {}
    lines = info_string.strip().splitlines()
    for line in lines:
        if " = " in line:
            path_str, val = line.split(" = ", 1)
            path_parts = [p.strip() for p in path_str.split("|") if p]
            set_nested_value(parsed, path_parts, val.strip())
    return parsed
