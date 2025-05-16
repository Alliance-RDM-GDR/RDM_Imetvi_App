# utils/inspect_czi_metadata.py
import czifile
import pprint

czi_file_path = "examples/czi/TnC-156B.czi"  # Adjust if your path is different

with czifile.CziFile(czi_file_path) as czi:
    # Print structure directly
    print("Structure of CZI file:")
    pprint.pprint(czi.__dict__)

    print("\nAvailable Metadata block (partial):")
    meta = czi.metadata()
    print(meta[:2000])  # Only first 2000 characters, not whole
