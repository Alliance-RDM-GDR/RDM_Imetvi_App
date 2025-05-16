# explore_tiff_metadata.py

import tifffile
import json
import pprint

def explore_tiff(file_path):
    with tifffile.TiffFile(file_path) as tif:
        print(f"--- Exploring TIFF: {file_path} ---\n")

        # Basic tags from the first page
        print("== TIFF TAGS ==")
        tags = tif.pages[0].tags
        for tag in tags.values():
            print(f"{tag.name}: {tag.value}")

        print("\n== TIFF PAGE SHAPE/DTYPE ==")
        print(f"Shape: {tif.pages[0].shape}")
        print(f"Dtype: {tif.pages[0].dtype}")

        # ImageJ metadata (if present)
        print("\n== ImageJ Metadata ==")
        pp = pprint.PrettyPrinter(indent=4)
        pp.pprint(tif.imagej_metadata or {})

        # IJMetadata (byte data possibly containing useful strings)
        if "IJMetadata" in tif.pages[0].tags:
            print("\n== IJMetadata Byte Dump ==")
            ij = tif.pages[0].tags["IJMetadata"].value
            if isinstance(ij, dict):
                for k, v in ij.items():
                    print(f"{k}: {v}")
            else:
                print(ij)

        # ImageDescription (often multiline text)
        desc = tif.pages[0].description
        print("\n== ImageDescription ==")
        print(desc)

        # Raw dump as JSON
        print("\n== RAW JSON DUMP (serializable only) ==")
        raw = {}
        for tag in tags.values():
            try:
                json.dumps(tag.value)  # try serializing
                raw[tag.name] = tag.value
            except:
                raw[tag.name] = str(tag.value)
        print(json.dumps(raw, indent=4))


if __name__ == "__main__":
    # Replace this with the path to your TIFF image
    explore_tiff("examples/tif/TnC-156B.tif")
