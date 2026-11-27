# ui/fields_view.py
#
# Builds the HTML of the "Recommended Fields" tab from a standardized metadata
# dict. Qt-free (it returns a string), so it can be tested without a
# QApplication. The tab shows: the standards suggestions first (they are what a
# curator acts on), then a two-column table of fields. Empty fields are hidden
# unless asked for, except required ones, which stay visible in red.

from html import escape

from i18n import get_language, tr
from metadata_profiles.profile_registry import format_label
from utils.wkt_display import pretty_wkt

# Keys that carry curation bookkeeping, not metadata fields.
CURATION_KEYS = {"_CurationFlags", "_MD5Checksum", "_StandardReference", "_MissingFields", "_Suggestions"}

MISSING_COLOUR = "#c0392b"
WARNING_COLOUR = "#e67e22"
SUGGESTION_COLOUR = "#2471a3"


def is_empty(value):
    return value is None or value == "" or value == [] or value == {}


def format_suggestion(sug):
    """One standards suggestion as an HTML fragment, in the active language."""
    use_fr = get_language() == "FR" and sug.get("Message_fr")
    msg = sug["Message_fr"] if use_fr else sug.get("Message", "")
    return (f'<span style="color:{SUGGESTION_COLOUR};">&bull; [{escape(sug.get("Standard", ""))}]</span> '
            f'{escape(msg)}')


def _list_of_dicts_lines(key, value):
    """Lines for the structured list fields (Channels, Datasets, Variables)."""
    lines = []
    if key == "Channels":
        for idx, ch in enumerate(value, 1):
            exc, em, exp = ch.get("ExcitationWavelength", ""), ch.get("EmissionWavelength", ""), ch.get("ExposureTime_sec", "")
            lines.append(escape(
                tr("render_channel_line", idx=idx, name=ch.get("Name", ""))
                + (tr("render_channel_exc", v=exc) if exc else "")
                + (tr("render_channel_em", v=em) if em else "")
                + (tr("render_channel_exp", v=exp) if exp else "")))
    elif key == "Datasets":
        for obj in value:
            risk = f' <span style="color:{WARNING_COLOUR};">⚠ {escape(str(obj["Risk"]))}</span>' if obj.get("Risk") else ""
            lines.append(escape(
                f"[{obj.get('Type', '?')}] {obj.get('Path', '')} | "
                f"{tr('render_dims')} {obj.get('Dimensions', '—')} | "
                f"{tr('render_type')} {obj.get('DataType', '—')} | "
                f"{tr('render_compression')} {obj.get('Compression', '—')}") + risk)
    elif key == "Variables":
        # NetCDF/CF variables: standard_name is the CF controlled-vocabulary term
        # that makes a variable machine-interpretable (FAIR: Interoperable), so a
        # variable without one is flagged.
        for v in value:
            line = escape(f"{v.get('Name', '')}")
            if v.get("StandardName"):
                line += escape(f"  [{v['StandardName']}]")
            else:
                line += f'  <span style="color:{WARNING_COLOUR};">⚠ {escape(tr("render_no_standard_name"))}</span>'
            if v.get("Units"):
                line += escape(f"  ({v['Units']})")
            if v.get("LongName"):
                line += escape(f"  — {v['LongName']}")
            if v.get("Shape"):
                line += escape(f"  {tr('render_shape')} {v['Shape']}")
            lines.append(line)
    return lines


def _value_html(key, value):
    """HTML for a value cell, and the plain text used for searching."""
    if key in ("Channels", "Datasets", "Variables") and isinstance(value, list) and all(isinstance(v, dict) for v in value):
        lines = _list_of_dicts_lines(key, value)
        return "<br>".join(lines), " ".join(str(v) for v in value)
    if key == "CRS_WKT" and value:
        # Raw WKT is one unbroken line of 1000+ characters; indent it by nesting depth
        # for display only (exports keep the original single line).
        wkt = pretty_wkt(value)
        return f"<pre style='margin:0'>{escape(wkt)}</pre>", str(value)
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        text = ", ".join(value)
        return escape(text), text
    return escape(str(value)), str(value)


def build_recommended_html(standardized_metadata, profile, file_name, show_empty=False, filter_text=""):
    """
    HTML for the Recommended Fields tab.

    show_empty  -- also list fields whose value is empty (required ones are always listed).
    filter_text -- case-insensitive substring; keeps only the rows (and suggestions) that match.
    """
    needle = (filter_text or "").strip().lower()
    missing = list(standardized_metadata.get("_MissingFields") or [])
    suggestions = standardized_metadata.get("_Suggestions") or []

    parts = [f"<p><b>{escape(tr('label_file'))}</b> {escape(file_name)}</p>"]

    if suggestions:
        shown = [s for s in suggestions
                 if not needle or needle in (s.get("Message", "") + s.get("Message_fr", "") + s.get("Standard", "")).lower()]
        if shown:
            parts.append(f"<h4 style='margin-bottom:2px;'>{escape(tr('suggestions_title'))} ({len(shown)})</h4>")
            parts.append("<p style='margin-top:2px;'>" + "<br>".join(format_suggestion(s) for s in shown) + "</p>")

    rows = []
    seen = set()
    for key, value in standardized_metadata.items():
        if key in CURATION_KEYS:
            continue
        seen.add(key)
        label = format_label(key, profile)
        required_blank = key in missing and is_empty(value)
        if is_empty(value) and not required_blank and not show_empty:
            continue
        if required_blank:
            value_html = f'<span style="color:{MISSING_COLOUR};">⚠ {escape(tr("ui_field_missing_value"))}</span>'
            plain = ""
            label_html = f'<span style="color:{MISSING_COLOUR};"><b>{escape(label)}</b></span>'
        else:
            value_html, plain = _value_html(key, value) if not is_empty(value) else ("—", "")
            label_html = f"<b>{escape(label)}</b>"
        if needle and needle not in label.lower() and needle not in plain.lower():
            continue
        rows.append(f"<tr><td valign='top' style='padding-right:14px;'>{label_html}</td><td valign='top'>{value_html}</td></tr>")

    # required fields the standardizer did not emit at all
    for key in missing:
        if key in seen:
            continue
        label = format_label(key, profile)
        if needle and needle not in label.lower():
            continue
        rows.append(
            f"<tr><td valign='top' style='padding-right:14px;'><span style='color:{MISSING_COLOUR};'><b>{escape(label)}</b></span></td>"
            f"<td valign='top'><span style='color:{MISSING_COLOUR};'>⚠ {escape(tr('ui_field_missing_value'))}</span></td></tr>")

    if rows:
        parts.append("<table cellspacing='0' cellpadding='2'>" + "".join(rows) + "</table>")
    elif needle:
        parts.append(f"<p>{escape(tr('ui_no_match', text=filter_text.strip()))}</p>")
    return "".join(parts)
