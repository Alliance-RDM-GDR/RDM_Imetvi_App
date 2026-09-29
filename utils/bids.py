# utils/bids.py
#
# Helpers shared by the NIfTI (BIDS MRI) and OME-Zarr (BIDS Microscopy)
# parsers: compound file extensions (.nii.gz), BIDS filename entities,
# dataset-root discovery, sidecar inheritance, and the standards-based
# suggestions (BIDS / ARRIVE / REMBI) shown in the "Recommended" and
# "Curation" tabs.
#
# Suggestions are plain dicts so they serialize to JSON as-is:
#   {"Code": str, "Standard": str, "Message": str (EN), "Message_fr": str,
#    "Flag": str | None}   # Flag: curation flag raised for this suggestion

import csv
import json
import os

COMPOUND_EXTENSIONS = (".nii.gz", ".ome.zarr")

# Values acquisition software / templates leave behind when a field was never
# filled in. "Visu*"/"ACQ_*" are Bruker ParaVision parameter *names* that
# BrkRaw copied instead of the parameter's value.
_PLACEHOLDER_EXACT = {
    "name of the dataset", "the license for the dataset",
    "author name 1", "author name 2",
}
_UNSPECIFIED_TEXT = "value was not specified"


def get_extension(path):
    """
    Lower-case extension of path, treating compound extensions as one unit
    (".nii.gz", ".ome.zarr") so extension-based format lookup works for them.
    """
    name = os.path.basename(str(path).rstrip("/\\")).lower()
    for comp in COMPOUND_EXTENSIONS:
        if name.endswith(comp):
            return comp
    return os.path.splitext(name)[1]


def strip_extension(path):
    """path without its (possibly compound) extension."""
    path = str(path)
    ext = get_extension(path)
    return path[: -len(ext)] if ext and path.lower().endswith(ext) else path


def read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def parse_tsv_header(text):
    """(column_names, row_count) of a TSV given as text."""
    rows = list(csv.reader(text.splitlines(), delimiter="\t"))
    if not rows:
        return [], 0
    return rows[0], len(rows) - 1


def bids_entities(filename):
    """
    Splits a BIDS filename into (entities dict, suffix), e.g.
    'sub-LD13_ses-baseline_dir-fwd_dwi.nii.gz' ->
    ({'sub': 'LD13', 'ses': 'baseline', 'dir': 'fwd'}, 'dwi').
    Non key-value parts (the suffix) are returned separately; a name with no
    BIDS structure yields ({}, '').
    """
    stem = strip_extension(os.path.basename(str(filename)))
    entities, suffix = {}, ""
    for part in stem.split("_"):
        if "-" in part:
            key, _, value = part.partition("-")
            entities[key] = value
        else:
            suffix = part
    if not entities:
        suffix = ""  # a bare word is not a BIDS suffix without entities
    return entities, suffix


def find_bids_root(start_path, max_levels=8):
    """Nearest ancestor directory containing dataset_description.json, or None."""
    d = os.path.dirname(os.path.abspath(start_path))
    for _ in range(max_levels):
        if os.path.isfile(os.path.join(d, "dataset_description.json")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return None


def find_sidecar(nifti_path, root=None):
    """
    Locates the JSON sidecar of a BIDS data file. First the same-stem file;
    then, following BIDS inheritance, any *_<suffix>.json in an ancestor
    directory (up to the dataset root) whose entities are a subset of the
    data file's. Returns a path or None.
    """
    same = strip_extension(nifti_path) + ".json"
    if os.path.isfile(same):
        return same
    entities, suffix = bids_entities(nifti_path)
    if not suffix:
        return None
    d = os.path.dirname(os.path.abspath(nifti_path))
    stop = os.path.abspath(root) if root else None
    while True:
        try:
            names = sorted(os.listdir(d))
        except OSError:
            names = []
        for name in names:
            if not name.endswith(f"_{suffix}.json") and name != f"{suffix}.json":
                continue
            ents, _ = bids_entities(name)
            if all(entities.get(k) == v for k, v in ents.items()):
                return os.path.join(d, name)
        parent = os.path.dirname(d)
        if parent == d or (stop and d == stop):
            return None
        d = parent


def find_placeholders(obj, prefix=""):
    """
    Walks a JSON-like object and returns (unresolved, unspecified): key paths
    whose value is an unresolved template/parameter-name placeholder, and key
    paths explicitly set to "Value was not specified".
    """
    unresolved, unspecified = [], []
    if isinstance(obj, dict):
        for k, v in obj.items():
            u, s = find_placeholders(v, f"{prefix}{k}.")
            unresolved += u
            unspecified += s
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            u, s = find_placeholders(v, f"{prefix}{i}.")
            unresolved += u
            unspecified += s
    elif isinstance(obj, str):
        key = prefix.rstrip(".")
        low = obj.strip().lower()
        if low == _UNSPECIFIED_TEXT:
            unspecified.append(key)
        elif (low in _PLACEHOLDER_EXACT or "fillyourid" in low
              or obj.startswith("Visu") or obj.startswith("ACQ_")):
            unresolved.append(key)
    return unresolved, unspecified


def _blank(value):
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list):
        return all(_blank(v) for v in value)
    return False


def summarize_dataset_description(dd):
    """Compact, serializable digest of a BIDS dataset_description.json."""
    if not dd:
        return {}
    authors = dd.get("Authors")
    return {
        "Name": dd.get("Name", ""),
        "BIDSVersion": dd.get("BIDSVersion", ""),
        "DatasetType": dd.get("DatasetType", ""),
        "License": dd.get("License", ""),
        "Authors": authors if isinstance(authors, list) else ([authors] if authors else []),
        "DatasetDOI": dd.get("DatasetDOI", ""),
        "GeneratedBy": dd.get("GeneratedBy", ""),
    }


# ── suggestion builders ─────────────────────────────────────────────────────

_BIDS = "BIDS 1.9.0"
_ARRIVE = "ARRIVE 2.0"
_REMBI = "REMBI"
_NGFF = "OME-NGFF 0.4"


def _s(code, standard, en, fr, flag=None):
    return {"Code": code, "Standard": standard, "Message": en, "Message_fr": fr, "Flag": flag}


def dataset_description_suggestions(dd):
    """Suggestions for a BIDS dataset_description.json (dict or None)."""
    out = []
    if dd is None:
        return [_s("BIDS_NO_DATASET_DESCRIPTION", _BIDS,
                   "No dataset_description.json found: BIDS requires it at the dataset root "
                   "(Name and BIDSVersion are mandatory).",
                   "Aucun dataset_description.json trouvé : BIDS l'exige à la racine du jeu de "
                   "données (Name et BIDSVersion sont obligatoires).",
                   "BIDS_DATASET_INCOMPLETE")]
    unresolved, _ = find_placeholders(dd)
    if unresolved:
        out.append(_s("BIDS_TEMPLATE_DATASET_DESCRIPTION", _BIDS,
                      "dataset_description.json still contains template text (" + ", ".join(unresolved[:6])
                      + "). Replace it with the real dataset name, license and authors.",
                      "dataset_description.json contient encore du texte gabarit ("
                      + ", ".join(unresolved[:6]) + "). Remplacez-le par le vrai nom, la licence et les auteurs.",
                      "BIDS_TEMPLATE_METADATA"))
    template_keys = {u.split(".")[0] for u in unresolved}
    if _blank(dd.get("License")):
        out.append(_s("BIDS_LICENSE_MISSING", _BIDS,
                      "dataset_description.json has no License. Recommended: a license identifier "
                      "from SPDX / the BIDS list (e.g. CC-BY-4.0 or CC0) so reuse terms travel with the data.",
                      "dataset_description.json n'a pas de License. Recommandé : un identifiant de licence "
                      "(p. ex. CC-BY-4.0 ou CC0) pour que les conditions de réutilisation accompagnent les données.",
                      "BIDS_DATASET_INCOMPLETE"))
    if _blank(dd.get("Authors")) and "Authors" not in template_keys:
        out.append(_s("BIDS_AUTHORS_MISSING", _BIDS,
                      "dataset_description.json has no Authors. List the people who should be credited "
                      "(ORCID iDs are recommended).",
                      "dataset_description.json n'a pas d'Authors. Indiquez les personnes à créditer "
                      "(les identifiants ORCID sont recommandés).",
                      "BIDS_DATASET_INCOMPLETE"))
    if _blank(dd.get("DatasetDOI")) and _blank(dd.get("ReferencesAndLinks")):
        out.append(_s("BIDS_DOI_MISSING", _BIDS,
                      "No DatasetDOI or ReferencesAndLinks in dataset_description.json. Add the repository DOI "
                      "(e.g. the FRDR DOI) once minted so the metadata is self-citing.",
                      "Aucun DatasetDOI ni ReferencesAndLinks dans dataset_description.json. Ajoutez le DOI du "
                      "dépôt (p. ex. FRDR) une fois attribué.", None))
    return out


def participants_suggestions(columns):
    """Suggestions for participants.tsv columns (list or None when the file is absent)."""
    if columns is None:
        return [_s("BIDS_NO_PARTICIPANTS", _BIDS,
                   "No participants.tsv found. Add one describing each subject (species, strain, sex, age, group).",
                   "Aucun participants.tsv trouvé. Ajoutez-en un décrivant chaque sujet (espèce, souche, sexe, âge, groupe).",
                   None)]
    cols = {c.strip().lower() for c in columns}
    wanted = {"species", "strain", "sex", "age"}
    missing = sorted(wanted - cols)
    if missing:
        return [_s("ARRIVE_PARTICIPANT_DESCRIPTORS", f"{_BIDS} / {_ARRIVE}",
                   "participants.tsv lacks animal descriptors: " + ", ".join(missing)
                   + ". BIDS defines species/strain/sex/age columns and ARRIVE 2.0 (essential set) asks for "
                   "them; add also the experimental group (e.g. sham vs injury) as a column.",
                   "participants.tsv n'a pas les descripteurs de l'animal : " + ", ".join(missing)
                   + ". BIDS définit les colonnes species/strain/sex/age et ARRIVE 2.0 les exige ; ajoutez aussi "
                   "le groupe expérimental (p. ex. sham vs lésion).", None)]
    return []


def sidecar_suggestions(sidecar, suffix, has_bval_bvec=None, sidecar_found=True):
    """Suggestions for a BIDS MRI JSON sidecar of a given suffix (T2w, dwi, bold...)."""
    out = []
    if not sidecar_found:
        return [_s("BIDS_NO_SIDECAR", _BIDS,
                   "No JSON sidecar found for this image. BIDS requires acquisition parameters "
                   "(e.g. RepetitionTime, EchoTime, PhaseEncodingDirection) in a sidecar.",
                   "Aucun fichier JSON associé à cette image. BIDS exige les paramètres d'acquisition "
                   "(RepetitionTime, EchoTime, PhaseEncodingDirection, etc.) dans un fichier JSON.", None)]
    unresolved, unspecified = find_placeholders(sidecar)
    if unresolved:
        out.append(_s("BIDS_SIDECAR_UNRESOLVED", _BIDS,
                      f"{len(unresolved)} sidecar field(s) hold unresolved converter placeholders instead of "
                      "values (" + ", ".join(unresolved[:5]) + (", …" if len(unresolved) > 5 else "")
                      + "). Fill in the real value or remove the field.",
                      f"{len(unresolved)} champ(s) du fichier JSON contiennent des marqueurs non résolus du "
                      "convertisseur (" + ", ".join(unresolved[:5]) + (", …" if len(unresolved) > 5 else "")
                      + "). Renseignez la vraie valeur ou retirez le champ.", "BIDS_TEMPLATE_METADATA"))
    if unspecified:
        out.append(_s("BIDS_SIDECAR_UNSPECIFIED", _BIDS,
                      f"{len(unspecified)} sidecar field(s) are set to the text 'Value was not specified'. "
                      "BIDS expects such fields to be omitted (or given a real value), not filled with text.",
                      f"{len(unspecified)} champ(s) du JSON valent « Value was not specified ». BIDS attend que "
                      "ces champs soient omis (ou renseignés), pas remplis avec du texte.", None))
    required = []
    if suffix in ("bold", "cbv", "phase"):
        required = ["RepetitionTime", "TaskName"]
    elif suffix == "dwi":
        required = ["PhaseEncodingDirection", "TotalReadoutTime"]
    missing = [k for k in required if _blank((sidecar or {}).get(k))]
    if missing:
        out.append(_s("BIDS_SIDECAR_REQUIRED_MISSING", _BIDS,
                      f"Sidecar for a '{suffix}' image is missing {', '.join(missing)}, which BIDS "
                      "requires or strongly recommends for this suffix.",
                      f"Le JSON d'une image « {suffix} » n'a pas {', '.join(missing)}, requis ou fortement "
                      "recommandé par BIDS pour ce suffixe.", "BIDS_DATASET_INCOMPLETE"))
    if suffix == "dwi" and has_bval_bvec is False:
        out.append(_s("BIDS_DWI_NO_BVAL_BVEC", _BIDS,
                      "Diffusion image without matching .bval/.bvec files: BIDS requires both.",
                      "Image de diffusion sans fichiers .bval/.bvec associés : BIDS exige les deux.",
                      "BIDS_DATASET_INCOMPLETE"))
    return out


def nifti_geometry_suggestions(sform_code, qform_code, spatial_unit="mm"):
    out = []
    if spatial_unit not in ("mm", "meter", "micron"):
        out.append(_s("NIFTI_UNITS_UNSET", "NIfTI-1",
                      "The header does not declare spatial units (xyzt_units): voxel sizes cannot be "
                      "interpreted safely. BIDS expects millimetres; set xyzt_units accordingly.",
                      "L'en-tête ne déclare pas d'unités spatiales (xyzt_units) : les tailles de voxel ne "
                      "peuvent pas être interprétées avec certitude. BIDS attend des millimètres.", None))
    if int(sform_code) == 0 and int(qform_code) == 0:
        return out + [_s("NIFTI_NO_SPATIAL_TRANSFORM", "NIfTI-1",
                   "Neither sform nor qform is set: the image has no defined position/orientation in space.",
                   "Ni sform ni qform ne sont définis : l'image n'a pas de position/orientation dans l'espace.",
                   "NIFTI_NO_SFORM")]
    elif int(sform_code) == 0:
        return out + [_s("NIFTI_NO_SFORM", "NIfTI-1",
                   "Only the qform is set (sform_code 0). Many registration/atlas tools (ANTs, FSL, SPM) prefer "
                   "or require an sform; consider setting both consistently.",
                   "Seul le qform est défini (sform_code 0). Plusieurs outils de recalage/atlas (ANTs, FSL, SPM) "
                   "préfèrent ou exigent un sform ; envisagez de définir les deux de façon cohérente.",
                   "NIFTI_NO_SFORM")]
    return out


def zarr_bids_suggestions(sidecar, sample_columns, channels, ngff_units_ok):
    """Suggestions for a BIDS-Microscopy OME-Zarr (sidecar may be None)."""
    out = []
    if sidecar is None:
        out.append(_s("BIDS_MICR_NO_SIDECAR", "BIDS Microscopy (BEP031)",
                      "No JSON sidecar beside the OME-Zarr. BIDS Microscopy requires PixelSize and "
                      "PixelSizeUnits there.",
                      "Aucun JSON à côté de l'OME-Zarr. BIDS Microscopie y exige PixelSize et PixelSizeUnits.",
                      "BIDS_DATASET_INCOMPLETE"))
    else:
        missing = [k for k in ("PixelSize", "PixelSizeUnits") if _blank(sidecar.get(k))]
        if missing:
            out.append(_s("BIDS_MICR_REQUIRED_MISSING", "BIDS Microscopy (BEP031)",
                          f"Sidecar is missing required field(s): {', '.join(missing)}.",
                          f"Champ(s) requis manquant(s) dans le JSON : {', '.join(missing)}.",
                          "BIDS_DATASET_INCOMPLETE"))
        rec = [k for k in ("Manufacturer", "InstrumentModel", "SoftwareVersions", "Magnification",
                           "NumericalAperture", "SampleEnvironment") if _blank(sidecar.get(k))]
        if rec:
            out.append(_s("REMBI_ACQUISITION_RECOMMENDED", f"{_REMBI} / BIDS Microscopy",
                          "Recommended acquisition fields absent from the sidecar: " + ", ".join(rec)
                          + " (REMBI 'Image acquisition').",
                          "Champs d'acquisition recommandés absents du JSON : " + ", ".join(rec)
                          + " (REMBI « Image acquisition »).", None))
        unresolved, _ = find_placeholders(sidecar)
        if unresolved:
            out.append(_s("BIDS_SIDECAR_UNRESOLVED", "BIDS Microscopy (BEP031)",
                          "Sidecar holds unresolved placeholders: " + ", ".join(unresolved[:5]) + ".",
                          "Le JSON contient des marqueurs non résolus : " + ", ".join(unresolved[:5]) + ".",
                          "BIDS_TEMPLATE_METADATA"))
    if not ngff_units_ok:
        out.append(_s("NGFF_AXES_NO_UNITS", _NGFF,
                      "Some spatial axes have no 'unit': OME-NGFF recommends explicit units so pixel sizes are "
                      "interpretable.",
                      "Certains axes spatiaux n'ont pas d'« unit » : OME-NGFF recommande des unités explicites.",
                      None))
    if not channels or all(_blank(c.get("Name")) for c in channels):
        out.append(_s("NGFF_CHANNELS_UNNAMED", f"{_NGFF} (omero)",
                      "Channels have no labels: name them (marker/fluorophore) in the 'omero' metadata.",
                      "Les canaux n'ont pas d'étiquette : nommez-les (marqueur/fluorophore) dans « omero ».",
                      None))
    cols = {c.strip().lower() for c in (sample_columns or [])}
    if not cols or cols <= {"participant_id", "sample_id", "sample_type"}:
        out.append(_s("REMBI_BIOSAMPLE_MISSING", f"{_REMBI} (Biosample/Specimen)",
                      "samples.tsv only identifies the sample. REMBI asks for Biosample (organism, strain, "
                      "genotype, treatment/group) and Specimen (fixation, clearing, labelling: antibodies/"
                      "reporters) — add them to samples.tsv/samples.json or a study record.",
                      "samples.tsv identifie seulement l'échantillon. REMBI demande Biosample (organisme, souche, "
                      "génotype, traitement/groupe) et Specimen (fixation, clarification, marquage : anticorps/"
                      "rapporteurs) — ajoutez-les à samples.tsv/samples.json ou à un dossier d'étude.", None))
    return out
