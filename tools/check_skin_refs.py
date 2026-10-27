"""Skin reference gate: every include, skin variable and font use must resolve.

Checks (skin XML only, stdlib only, offline):
  1. include use ``<include content="X">`` must have a matching
     ``<include name="X">`` definition somewhere in 1080p/*.xml.
     Undefined use is an ERROR (the window/control silently renders nothing).
  2. skin variable use ``$VAR[X]`` must have a matching
     ``<variable name="X">`` definition. Undefined use is an ERROR.
     Parameterised uses ``$VAR[X,arg]`` are resolved on ``X``; a name that
     is itself dynamic (``$VAR[$PARAM[ns]Suffix]``) is skipped, since it
     cannot be resolved without expanding the parameter.
  3. font use ``<font>X</font>`` must have a matching definition in
     Font.xml. Undefined use is an ERROR (Kodi silently falls back).

A missing or empty skin directory is an ERROR: a gate that inspects nothing
must not report success.

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
SKIN_REL = Path("source") / "skin.yoplayer.infuse" / "1080p"
BASELINE_FILE = Path(__file__).resolve().parent / "skin_refs_baseline.json"
# Capture the whole bracket body so parameterised uses (``$VAR[Name,arg]``)
# are checked on their head name instead of being skipped silently.
VAR_RE = re.compile(r"\$VAR\[([^\]]*)\]")


def variable_head(body):
    """Return the variable name of a ``$VAR[...]`` body, or None if dynamic.

    ``Name`` and ``Name,arg,arg`` both resolve on ``Name``. Parentheses stay
    part of the name: Kodi defines parameterised variables literally, e.g.
    ``Defs_PercentPlayed(-1)``. A body that embeds another reference
    (``$PARAM[ns]Suffix``) cannot be resolved statically and is skipped
    rather than reported as undefined.
    """
    name = body.split(",", 1)[0].strip()
    if not name or "$" in name:
        return None
    return name


def iter_skin_xmls(skin_dir):
    return sorted(skin_dir.glob("*.xml"))


def collect(skin_dir, font_file):
    """Return (defs, uses) dicts for includes, variables and fonts."""
    inc_defs, inc_uses = {}, []
    var_defs, var_uses = {}, []
    font_defs, font_uses = {}, []
    malformed = []

    def add_var_uses(text, where):
        for body in VAR_RE.findall(text):
            name = variable_head(body)
            if name is not None:
                var_uses.append((name, where))

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
                    add_var_uses(text, path.name)
            for value in elem.attrib.values():
                add_var_uses(value, path.name)
    if font_file.exists():
        try:
            for font in ET.parse(font_file).getroot().iter("font"):
                name_elem = font.find("name")
                if name_elem is not None and name_elem.text:
                    font_defs.setdefault(name_elem.text.strip(), font_file.name)
        except ET.ParseError as exc:
            malformed.append((font_file, str(exc)))
    return {
        "include": (inc_defs, inc_uses),
        "variable": (var_defs, var_uses),
        "font": (font_defs, font_uses),
    }, malformed


def load_baseline(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"dead_includes": [], "dead_variables": [], "dead_fonts": []}
    return {
        "dead_includes": set(data.get("dead_includes", [])),
        "dead_variables": set(data.get("dead_variables", [])),
        "dead_fonts": set(data.get("dead_fonts", [])),
    }


def parse_args(argv):
    """Return (strict, root); reject unknown flags instead of ignoring them."""
    strict = False
    root = ROOT
    rest = list(argv)
    while rest:
        arg = rest.pop(0)
        if arg == "--strict":
            strict = True
        elif arg == "--root":
            if not rest:
                raise SystemExit("--root needs a directory")
            root = Path(rest.pop(0)).resolve()
        elif arg.startswith("--root="):
            root = Path(arg.split("=", 1)[1]).resolve()
        else:
            raise SystemExit("unknown argument: %s" % arg)
    return strict, root


def main(argv=None):
    strict, root = parse_args(sys.argv[1:] if argv is None else argv)
    skin_dir = root / SKIN_REL
    errors, warnings = [], []
    if not skin_dir.is_dir():
        print("ERROR: skin directory not found: %s" % skin_dir)
        return 1
    xmls = iter_skin_xmls(skin_dir)
    if not xmls:
        print("ERROR: no skin XML files in %s" % skin_dir)
        return 1
    collected, malformed = collect(skin_dir, skin_dir / "Font.xml")
    for path, detail in malformed:
        errors.append("malformed XML %s: %s" % (path.name, detail))
    baseline = load_baseline(BASELINE_FILE)
    for kind, (defs, uses) in collected.items():
        used_names = {name for name, _ in uses}
        # One message per name, listing every file that uses it: a repeated
        # use in the same file must not hide a second broken one.
        undefined = {}
        for name, where in uses:
            if name not in defs:
                undefined.setdefault(name, set()).add(where)
        for name in sorted(undefined):
            errors.append("undefined %s %r used in %s"
                          % (kind, name, ", ".join(sorted(undefined[name]))))
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
