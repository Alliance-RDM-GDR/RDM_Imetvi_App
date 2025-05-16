# utils/serialization.py

import numpy as np

def make_json_serializable(obj):
    """
    Recursively convert metadata to JSON-serializable types.
    Handles numpy arrays, numpy scalar types, bytes, sets, and unsupported objects.
    """
    if isinstance(obj, dict):
        return {k: make_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, set, tuple)):
        return [make_json_serializable(item) for item in obj]
    elif isinstance(obj, (np.ndarray,)):
        return obj.tolist()
    elif isinstance(obj, (np.generic,)):
        return obj.item()
    elif isinstance(obj, bytes):
        try:
            return obj.decode('utf-8', errors='replace')
        except Exception:
            return str(obj)
    elif isinstance(obj, (complex,)):
        return str(obj)
    elif hasattr(obj, '__dict__'):
        return make_json_serializable(obj.__dict__)
    else:
        return obj
