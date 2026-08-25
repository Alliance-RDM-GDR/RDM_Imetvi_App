# standardizers/png_general_standardizer.py


def standardize_png_general_metadata(raw_metadata):
    std = {}

    std["FilePath"] = raw_metadata.get("FilePath", "")
    std["ImageWidth"] = str(raw_metadata.get("ImageWidth", ""))
    std["ImageHeight"] = str(raw_metadata.get("ImageHeight", ""))
    std["DimensionX"] = std["ImageWidth"]
    std["DimensionY"] = std["ImageHeight"]
    std["ColorMode"] = raw_metadata.get("Mode", "")
    std["BitDepth"] = str(raw_metadata.get("BitDepth", ""))
    std["ResolutionX"] = str(raw_metadata.get("ResolutionX", ""))
    std["ResolutionY"] = str(raw_metadata.get("ResolutionY", ""))
    std["FileSizeMB"] = str(raw_metadata.get("FileSizeMB", ""))

    # Promote common text chunks to top-level fields
    _CHUNK_MAP = {
        "TextChunk_Author":        "Author",
        "TextChunk_Copyright":     "Copyright",
        "TextChunk_Creation Time": "CreationTime",
        "TextChunk_Software":      "Software",
        "TextChunk_Description":   "Description",
        "TextChunk_Comment":       "Comment",
        "TextChunk_Title":         "Title",
        "TextChunk_Source":        "Source",
    }
    for raw_key, std_key in _CHUNK_MAP.items():
        val = raw_metadata.get(raw_key)
        if val:
            std[std_key] = str(val)

    return std
