"""Skin reference gate: every include, skin variable and font use must resolve.

Checks (skin XML only, stdlib only, offline):
  1. include use ``<include content="X">`` must have a matching
     ``<include name="X">`` definition somewhere in 1080p/*.xml.
     Undefined use is an ERROR (the window/control silently renders nothing).
  2. skin variable use ``$VAR[X]`` must have a matching
     ``<variable name="X">`` definition. Undefined use is an ERROR.
  3. font use ``<font>X</font>`` must have a matching definition in
     Font.xml. Undefined use is an ERROR (Kodi silently falls back).

Zero-reference definitions are NOT errors: deleting an include/variable/font
just because nothing references it today has bitten this repo before
(the 2026-10-27 review found 48 zero-reference includes whose deletion
still needs a full-window walkthrough to confirm). Instead they are
tracked in ``skin_refs_baseline.json``: names already in the baseline are
reported as known; only NEW zero-reference names print a WARNING.
Pass ``--strict`` to turn new zero-reference names into errors too.

Exit codes: 1 on any ERROR (or on new dead names with --strict),
0 otherwise. Warnings never fail a default run.

Usage: python3 tools/check_skin_refs.py [--strict] [--root DIR]
"""

import json
import re
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
SKIN_DIR = ROOT / "source" / "skin.yoplayer.infuse" / "1080p"
FONT_FILE = SKIN_DIR / "Font.xml"
BASELINE_FILE = Path(__file__).resolve().parent / "skin_refs_baseline.json"
VAR_RE = re.compile(r"\$VAR\[([A-Za-z0-9_]+)\]")


def iter_skin_xmls(skin_dir):
    return sorted(skin_dir.glob("*.xml"))


def collect(skin_dir):
    """Return (defs, uses) dicts for includes, variables and fonts."""
    inc_defs, inc_uses = {}, []
    var_defs, var_uses = {}, []
    font_defs, font_uses = {}, []
    malformed = []
    for path in iter_skin_xmls(skin_dir):
        try:
            tree = ET.parse(path)
        except ET.ParseError as exc:
            malformed.append((path, str(exc)))
            continue
        for elem in tree.iter():
            if elem.tag == "include":
                if elem.get("name"):
                    inc_defs.setdefault(elem.get("name"), path.name)
                elif elem.get("content"):
                    inc_uses.append((elem.get("content"), path.name))
                elif elem.text and elem.text.strip():
                    # Text form: <include>Animation_FadeIn</include>, used
                    # for animation and other non-parameterised includes.
                    inc_uses.append((elem.text.strip(), path.name))
            elif elem.tag == "variable":
                if elem.get("name"):
                    var_defs.setdefault(elem.get("name"), path.name)
            elif elem.tag == "font" and elem.text and elem.text.strip():
                font_uses.append((elem.text.strip(), path.name))
            for text in (elem.text, elem.tail):
                if text:
                    for name in VAR_RE.findall(text):
                        var_uses.append((name, path.name))
            for value in elem.attrib.values():
                for name in VAR_RE.findall(value):
                    var_uses.append((name, path.name))
    if FONT_FILE.exists():
        try:
            for font in ET.parse(FONT_FILE).getroot().iter("font"):
                name_elem = font.find("name")
                if name_elem is not None and name_elem.text:
                    font_defs.setdefault(name_elem.text.strip(), FONT_FILE.name)
        except ET.ParseError as exc:
            malformed.append((FONT_FILE, str(exc)))
    return {
        "include": (inc_defs, inc_uses),
        "variable": (var_defs, var_uses),
        "font": (font_defs, font_uses),
    }, malformed


def load_baseline():
    try:
        data = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"dead_includes": [], "dead_variables": [], "dead_fonts": []}
    return {
        "dead_includes": set(data.get("dead_includes", [])),
        "dead_variables": set(data.get("dead_variables", [])),
        "dead_fonts": set(data.get("dead_fonts", [])),
    }


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    strict = "--strict" in argv
    errors, warnings = [], []
    collected, malformed = collect(SKIN_DIR)
    for path, detail in malformed:
        errors.append("malformed XML %s: %s" % (path.name, detail))
    baseline = load_baseline()
    for kind, (defs, uses) in collected.items():
        used_names = {name for name, _ in uses}
        seen_undefined = set()
        for name, where in sorted(uses):
            if name not in defs and (kind, name, where) not in seen_undefined:
                seen_undefined.add((kind, name, where))
                errors.append(
                    "undefined %s %r used in %s" % (kind, name, where))
        dead = sorted(set(defs) - used_names)
        base_key = "dead_%ss" % kind if kind != "include" else "dead_includes"
        known = baseline.get(base_key, set())
        for name in dead:
            if name in known:
                continue
            warnings.append(
                "new zero-reference %s %r (defined in %s, not in baseline)"
                % (kind, name, defs[name]))
        print("%s: %d defined, %d uses, %d zero-reference (%d already baselined)"
              % (kind, len(defs), len(uses), len(dead),
                 len([n for n in dead if n in known])))
    if errors:
        print("\nERRORS (%d):" % len(errors))
        for line in errors:
            print("  - " + line)
    if warnings:
        print("\nWARNINGS (%d):" % len(warnings))
        for line in warnings:
            print("  - " + line)
    if errors or (strict and warnings):
        return 1
    print("\nOK: no undefined references"
          + (" (warnings only)" if warnings else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
