"""Section maps: the arrangement as data, so a new track is a data change.

One YAML (or JSON) file per build. Every section names the elements playing
and exactly one ``sub_owner`` - the element allowed to hold 30-120 Hz there.
That is the taste rule made machine-checkable, and the QC gate measures
whether the render kept it.
"""
import json
from pathlib import Path

MIN_BPM, MAX_BPM = 20.0, 300.0
MAX_BARS = 4096


class SectionMapError(ValueError):
    """The section map is unusable; the message says which section and why."""


def load_section_map(path):
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError as error:
            raise SectionMapError(
                "PyYAML is needed for YAML section maps (pip install '.[producer]'), "
                "or write the map as JSON") from error
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    if not isinstance(data, dict):
        raise SectionMapError("A section map must be a mapping at the top level")
    return validate_section_map(data)


def validate_section_map(data):
    """Validate and normalise: adds start_bar/end_bar per section and totals."""
    name = data.get("name")
    if not name or not isinstance(name, str):
        raise SectionMapError("Section map needs a 'name'")
    try:
        bpm = float(data["bpm"])
    except (KeyError, TypeError, ValueError) as error:
        raise SectionMapError("Section map needs a numeric 'bpm'") from error
    if not MIN_BPM <= bpm <= MAX_BPM:
        raise SectionMapError("bpm %s is outside %s-%s" % (bpm, MIN_BPM, MAX_BPM))
    beats_per_bar = int(data.get("beats_per_bar", 4))
    if not 1 <= beats_per_bar <= 32:
        raise SectionMapError("beats_per_bar must be 1-32")

    sections = data.get("sections")
    if not isinstance(sections, list) or not sections:
        raise SectionMapError("Section map needs a non-empty 'sections' list")

    normalised, bar = [], 0
    seen = set()
    for index, section in enumerate(sections):
        where = "section %d" % index
        if not isinstance(section, dict):
            raise SectionMapError("%s is not a mapping" % where)
        section_name = section.get("name")
        if not section_name:
            raise SectionMapError("%s needs a 'name'" % where)
        where = "section %r" % section_name
        if section_name in seen:
            raise SectionMapError("%s appears twice; names must be unique" % where)
        seen.add(section_name)
        try:
            bars = int(section["bars"])
        except (KeyError, TypeError, ValueError) as error:
            raise SectionMapError("%s needs an integer 'bars'" % where) from error
        if bars <= 0:
            raise SectionMapError("%s has bars <= 0" % where)
        elements = section.get("elements")
        if not isinstance(elements, list) or not elements:
            raise SectionMapError("%s needs a non-empty 'elements' list" % where)
        if len(set(elements)) != len(elements):
            raise SectionMapError("%s lists an element twice" % where)
        sub_owner = section.get("sub_owner")
        if not sub_owner:
            raise SectionMapError(
                "%s needs a 'sub_owner': exactly one element owns 30-120 Hz" % where)
        if sub_owner not in elements:
            raise SectionMapError(
                "%s sub_owner %r is not in its elements" % (where, sub_owner))
        normalised.append({
            "name": section_name,
            "bars": bars,
            "start_bar": bar,
            "end_bar": bar + bars,
            "elements": list(elements),
            "sub_owner": sub_owner,
            "energy": section.get("energy"),
            "notes": section.get("notes", ""),
        })
        bar += bars
        if bar > MAX_BARS:
            raise SectionMapError("Arrangement exceeds %d bars" % MAX_BARS)

    seconds = bar * beats_per_bar * 60.0 / bpm
    return {
        "name": name,
        "bpm": bpm,
        "beats_per_bar": beats_per_bar,
        "reference": data.get("reference"),
        "sections": normalised,
        "total_bars": bar,
        "total_seconds": round(seconds, 2),
        "sub_owners": sorted({s["sub_owner"] for s in normalised}),
    }
