# metadata_parsers/omezarr_parser.py
#
# Reads OME-Zarr (OME-NGFF) images either from a ".zarr" directory or from an
# uncompressed ".tar" that packages a BIDS-Microscopy dataset around one (the
# layout FRDR deposits use: <id>_bids.tar -> sub-X/micr/<...>_SPIM.ome.zarr).
#
# Only metadata is read — .zattrs/.zarray (zarr v2) or zarr.json (zarr v3),
# the BIDS JSON sidecar, dataset_description.json, samples.tsv, README. Chunk
# files are counted from the tar/directory index but never opened, and the
# tar is never extracted, so a 17 GB archive is inspected in seconds. No
# zarr/ome-zarr dependency is needed for the same reason.

import json
import os
import tarfile

from utils.bids import (
    bids_entities, parse_tsv_header, summarize_dataset_description, read_json, find_bids_root,
)

OMEZARR_EXTENSIONS = [".zarr", ".ome.zarr", ".tar"]

_UNIT_TO_UM = {
    "nanometer": 0.001, "micrometer": 1.0, "micron": 1.0, "millimeter": 1000.0,
    "centimeter": 10000.0, "meter": 1e6,
}
_ZARR_META = (".zgroup", ".zattrs", ".zarray", "zarr.json")


class _Store:
    """Minimal read-only view over a tar archive or a directory tree."""

    def __init__(self, path):
        self.path = path
        self.is_tar = os.path.isfile(path)
        self._tar = None
        self._members = {}      # tar: name -> TarInfo
        self.names = []         # every file name (relative, '/' separated)
        if self.is_tar:
            self._tar = tarfile.open(path, "r:")
            for m in self._tar:
                if m.isfile():
                    self._members[m.name] = m
                    self.names.append(m.name)
        else:
            # Walk everything: chunk *names* are needed for counting; nothing
            # is opened. os.walk over a few thousand entries is fast.
            for dirpath, _dirs, files in os.walk(path):
                rel = os.path.relpath(dirpath, path).replace("\\", "/")
                for f in files:
                    self.names.append(f if rel == "." else f"{rel}/{f}")

    def read(self, name):
        try:
            if self.is_tar:
                m = self._members.get(name)
                return self._tar.extractfile(m).read() if m else None
            with open(os.path.join(self.path, name), "rb") as f:
                return f.read()
        except OSError:
            return None

    def read_json(self, name):
        raw = self.read(name)
        if raw is None:
            return None
        try:
            data = json.loads(raw.decode("utf-8"))
            return data if isinstance(data, dict) else None
        except ValueError:
            return None

    def size(self, name):
        if self.is_tar:
            m = self._members.get(name)
            return m.size if m else 0
        try:
            return os.path.getsize(os.path.join(self.path, name))
        except OSError:
            return 0

    def close(self):
        if self._tar is not None:
            self._tar.close()


def _find_zarr_root(store):
    """Prefix ('' when the store itself is the zarr) of the first zarr group."""
    if not store.is_tar and (".zgroup" in store.names or "zarr.json" in store.names):
        return ""
    for n in sorted(store.names):
        base = n.rsplit("/", 1)[-1]
        if base in (".zgroup", "zarr.json") and ".zarr/" in "/" + n:
            prefix = n.rsplit("/", 1)[0] if "/" in n else ""
            # first match with the shortest prefix ending in .zarr
            if prefix.lower().endswith(".zarr"):
                return prefix
    return None


def _array_meta(store, prefix):
    """Shape/chunks/dtype/compressor of a zarr array (v2 or v3), or None."""
    z2 = store.read_json(f"{prefix}/.zarray" if prefix else ".zarray")
    if z2:
        comp = z2.get("compressor") or {}
        return {
            "Shape": z2.get("shape"), "Chunks": z2.get("chunks"), "DType": z2.get("dtype"),
            "Compressor": (comp.get("cname") or comp.get("id") or "none") if comp else "none",
            "ZarrFormat": 2,
        }
    z3 = store.read_json(f"{prefix}/zarr.json" if prefix else "zarr.json")
    if z3 and z3.get("node_type") == "array":
        codecs = [c.get("name") for c in z3.get("codecs", []) if isinstance(c, dict)]
        chunks = (z3.get("chunk_grid", {}).get("configuration", {}) or {}).get("chunk_shape")
        return {
            "Shape": z3.get("shape"), "Chunks": chunks, "DType": z3.get("data_type"),
            "Compressor": ",".join(c for c in codecs if c not in ("bytes",)) or "none",
            "ZarrFormat": 3,
        }
    return None


def _channels(attrs, ome):
    omero = ome.get("omero") or attrs.get("omero") or {}
    chans = []
    for ch in omero.get("channels", []) or []:
        chans.append({"Name": ch.get("label", ""), "Color": ch.get("color", ""),
                      "Active": ch.get("active", None)})
    return chans


def _to_um(scale, unit):
    f = _UNIT_TO_UM.get((unit or "").lower())
    return None if f is None or scale is None else scale * f


def parse_omezarr_metadata(file_path, application=None):
    """
    Extracts OME-NGFF image metadata plus the BIDS-Microscopy context.
    Returns (text_report, raw_metadata) per the parser contract.
    """
    fname = os.path.basename(file_path.rstrip("/\\"))
    text_lines = [f"OME-Zarr Metadata Report for {fname}"]
    raw = {"FilePath": file_path, "Container": ""}

    store = None
    try:
        store = _Store(file_path)
    except (OSError, tarfile.TarError) as e:
        text_lines.append(f"Failed to read OME-Zarr source: {e}")
        return "\n".join(text_lines), raw

    try:
        raw["Container"] = "tar" if store.is_tar else "directory"
        zroot = _find_zarr_root(store)
        if zroot is None:
            text_lines.append("Failed to read OME-Zarr: no zarr group (.zgroup / zarr.json) found in "
                              + ("archive." if store.is_tar else "folder."))
            return "\n".join(text_lines), raw

        def z(name):
            return f"{zroot}/{name}" if zroot else name

        # ── OME-NGFF attributes ─────────────────────────────────────────────
        attrs = store.read_json(z(".zattrs"))
        if attrs is None:
            g3 = store.read_json(z("zarr.json")) or {}
            attrs = g3.get("attributes", {}) or {}
        ome = attrs.get("ome", attrs)  # NGFF 0.5 nests under "ome"
        ms_list = ome.get("multiscales") or []
        if not ms_list:
            text_lines.append("Failed to read OME-Zarr: no 'multiscales' metadata (not an OME-NGFF image).")
            return "\n".join(text_lines), raw
        ms = ms_list[0]
        raw["NGFFVersion"] = ms.get("version") or ome.get("version", "")
        axes = ms.get("axes") or []
        raw["Axes"] = [{"Name": a.get("name", ""), "Type": a.get("type", ""), "Unit": a.get("unit", "")}
                       for a in axes if isinstance(a, dict)]
        raw["Channels"] = _channels(attrs, ome)
        datasets = ms.get("datasets") or []
        raw["NumLevels"] = len(datasets)

        levels = []
        for ds in datasets:
            path = ds.get("path", "")
            arr = _array_meta(store, z(path)) or {}
            scale = None
            for t in ds.get("coordinateTransformations", []) or []:
                if t.get("type") == "scale":
                    scale = t.get("scale")
            chunk_files = [n for n in store.names
                           if n.startswith(z(path) + "/") and n.rsplit("/", 1)[-1] not in _ZARR_META]
            levels.append({
                "Path": path, "Shape": arr.get("Shape"), "Chunks": arr.get("Chunks"),
                "DType": arr.get("DType"), "Compressor": arr.get("Compressor"),
                "ZarrFormat": arr.get("ZarrFormat"), "Scale": scale,
                "ChunkFiles": len(chunk_files),
                "StoredBytes": sum(store.size(n) for n in chunk_files),
            })
        raw["Levels"] = levels

        text_lines.append(f"OME-NGFF version: {raw['NGFFVersion']}   container: {raw['Container']}")
        text_lines.append("Axes: " + ", ".join(
            f"{a['Name']}({a['Type']}{', ' + a['Unit'] if a['Unit'] else ''})" for a in raw["Axes"]))
        for lv in levels:
            text_lines.append(
                f"Level {lv['Path']}: shape {lv['Shape']}  chunks {lv['Chunks']}  {lv['DType']}  "
                f"{lv['Compressor']}  {lv['ChunkFiles']} chunk files  scale {lv['Scale']}")
        if raw["Channels"]:
            text_lines.append("Channels: " + ", ".join(c["Name"] or "(unnamed)" for c in raw["Channels"]))

        # physical pixel size (µm) from the first level
        if levels and levels[0]["Scale"]:
            px = {}
            for a, s in zip(raw["Axes"], levels[0]["Scale"]):
                if a["Type"] == "space":
                    px[a["Name"].upper()] = _to_um(s, a["Unit"])
            raw["PixelSizeUM"] = px
            text_lines.append("Pixel size (µm): " + ", ".join(
                f"{k}={v:g}" if v is not None else f"{k}=?" for k, v in px.items()))
        raw["UnitsPresent"] = all(a["Unit"] for a in raw["Axes"] if a["Type"] == "space")

        # ── BIDS-Microscopy context ─────────────────────────────────────────
        # sidecar: <zarr name without .ome.zarr>.json next to the zarr
        zname = zroot.rsplit("/", 1)[-1] if zroot else fname
        stem = zname[: -len(".ome.zarr")] if zname.lower().endswith(".ome.zarr") \
            else os.path.splitext(zname)[0]
        parent = zroot.rsplit("/", 1)[0] if zroot and "/" in zroot else ""
        on_disk_zarr = (not store.is_tar) and zroot == ""
        if on_disk_zarr:
            # the .zarr folder itself was opened: its sidecar and BIDS root live on disk around it
            sidecar = read_json(os.path.join(os.path.dirname(os.path.abspath(file_path.rstrip("/\\"))),
                                             stem + ".json"))
        else:
            sidecar = store.read_json(f"{parent}/{stem}.json" if parent else f"{stem}.json")
        raw["SidecarFound"] = sidecar is not None
        if sidecar is not None:
            raw["Sidecar"] = sidecar
            for k in ("PixelSize", "PixelSizeUnits", "Magnification", "NumericalAperture",
                      "Immersion", "InstrumentModel", "SoftwareVersions", "OtherAcquisitionParameters"):
                if k in sidecar:
                    text_lines.append(f"{k}: {sidecar[k]}")
            ps = sidecar.get("PixelSize")
            px = raw.get("PixelSizeUM") or {}
            if isinstance(ps, list) and ps and px.get("X"):
                sc_um = ps[0] * {"um": 1.0, "mm": 1000.0, "nm": 0.001}.get(sidecar.get("PixelSizeUnits", "um"), 1.0)
                if sc_um:
                    raw["DownsampleFactorXY"] = round(px["X"] / sc_um, 3)
                    text_lines.append(f"Downsample vs. sidecar pixel size (XY): {raw['DownsampleFactorXY']:g}x")
            extra = sidecar.get("ExtraMetadata") or {}
            for key in ("ExcitationWL", "EmissionWL"):
                val = (extra.get(key) or {}).get(key)
                if val not in (None, ""):
                    raw[key] = val
            if (raw.get("ExcitationWL") or raw.get("EmissionWL")) and len(raw["Channels"]) > 1:
                raw["WavelengthAmbiguous"] = True
                text_lines.append("Note: sidecar carries one excitation/emission pair for a multi-channel image; "
                                  "it cannot be attributed to a specific channel.")
            for k in ("Manufacturer",):
                if sidecar.get(k):
                    raw[k] = sidecar[k]

        entities, suffix = bids_entities(stem)
        raw["BIDSEntities"] = entities
        raw["BIDSSuffix"] = suffix
        if entities:
            text_lines.append("BIDS entities: " + ", ".join(f"{k}-{v}" for k, v in entities.items())
                              + f" | suffix: {suffix}")

        # dataset-level files: shallowest dataset_description.json in the store
        dd_names = sorted((n for n in store.names if n.rsplit("/", 1)[-1] == "dataset_description.json"),
                          key=lambda n: n.count("/"))
        disk_root = find_bids_root(file_path.rstrip("/\\")) if on_disk_zarr else None
        if disk_root:
            dd = read_json(os.path.join(disk_root, "dataset_description.json"))
        else:
            dd = store.read_json(dd_names[0]) if dd_names else None
        raw["DatasetDescriptionFound"] = dd is not None
        raw["DatasetDescription"] = summarize_dataset_description(dd)
        root_prefix = dd_names[0].rsplit("/", 1)[0] if dd_names and "/" in dd_names[0] else ""
        samples = f"{root_prefix}/samples.tsv" if root_prefix else "samples.tsv"
        raw["SamplesColumns"] = None
        txt = None
        if disk_root and os.path.isfile(os.path.join(disk_root, "samples.tsv")):
            with open(os.path.join(disk_root, "samples.tsv"), "r", encoding="utf-8", errors="replace") as f:
                txt = f.read()
        elif not disk_root and samples in store.names:
            txt = (store.read(samples) or b"").decode("utf-8", "replace")
        if txt is not None:
            cols, n = parse_tsv_header(txt)
            raw["SamplesColumns"], raw["SamplesCount"] = cols, n
        raw["ReadmeFound"] = any(n.rsplit("/", 1)[-1].lower().startswith("readme") for n in store.names) or             bool(disk_root and any(f.lower().startswith("readme") for f in os.listdir(disk_root)))
        if dd:
            text_lines.append(
                f"BIDS dataset: {dd.get('Name', '')!s} (BIDS {dd.get('BIDSVersion', '?')}, "
                f"license: {dd.get('License') or 'not set'})")
        gen = (dd or {}).get("GeneratedBy")
        if isinstance(gen, list):
            raw["GeneratedBy"] = "; ".join(
                " ".join(f"{k}={v}" for k, v in g.items()) for g in gen if isinstance(g, dict))

        raw["ArchiveFileCount"] = len(store.names)
        raw["ArchiveSizeBytes"] = os.path.getsize(file_path) if store.is_tar else \
            sum(store.size(n) for n in store.names)
    except Exception as e:  # never crash the UI on a malformed store
        text_lines.append(f"Failed to read OME-Zarr: {e}")
    finally:
        if store is not None:
            store.close()

    return "\n".join(text_lines), raw
