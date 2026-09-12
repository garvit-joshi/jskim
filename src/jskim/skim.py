"""jskim skim - summarize a Java file compactly.

Usage: jskim <file.java> [file2.java ...] [--grep pattern] [--annotation @Ann]
"""

import sys
from pathlib import Path

from .util import (
    parse_java_source, classify_method, instance_fields, static_fields,
    format_method_annotations, format_calls, format_enum_constants,
    format_static_field, ENUM_CONSTANTS_SKIM_MAX,
)


def _match_method(m, grep=None, annotation=None):
    """Check if a method matches the given filters."""
    if grep and grep.lower() not in m["sig"].lower():
        return False
    if annotation:
        ann = annotation if annotation.startswith("@") else "@" + annotation
        if not any(a["name"].startswith(ann) for a in m["annotations"]):
            return False
    return True


def _format_annotation_list(annotations):
    """Render rich annotation dicts as one space-joined string."""
    return " ".join(a["full"] for a in annotations)


def _format_field(f):
    """Render one field as ``Type name (@Ann @Ann)``."""
    ann = f" ({' '.join(f['annotations'])})" if f["annotations"] else ""
    name = f" {f['name']}" if f["name"] else ""
    return f"{f['type']}{name}{ann}"


def _format_methods(out, methods, indent, grep=None, annotation=None):
    """Append the collapsed/expanded method listing for one type."""
    wiring, getters, setters, boilerplate, named = [], [], [], [], []
    filtering = grep or annotation
    for m in methods:
        if filtering and not _match_method(m, grep, annotation):
            continue
        kind = classify_method(m)
        if kind == "wiring":
            wiring.append(m)
        elif kind == "getter":
            getters.append(m["name"])
        elif kind == "setter":
            setters.append(m["name"])
        elif kind == "boilerplate":
            boilerplate.append(m["name"])
        else:
            named.append(m)

    if wiring:
        spans = ", ".join(f"L{m['start']}-L{m['end']} ({len(m['params'])} params)" for m in wiring)
        out.append(f"//{indent} constructor: {spans}")
    if getters:
        out.append(f"//{indent} getters: {', '.join(getters)}")
    if setters:
        out.append(f"//{indent} setters: {', '.join(setters)}")
    if boilerplate:
        out.append(f"//{indent} boilerplate: {', '.join(boilerplate)}")
    if named:
        out.append(f"//{indent} methods:")
        for m in named:
            lines = m["end"] - m["start"] + 1
            loc = f"L{m['start']}-L{m['end']}"
            ann_str = format_method_annotations(m)
            ann_str = f" {ann_str}" if ann_str else ""
            out.append(f"//{indent}   {loc:>12} ({lines:>3} lines):{ann_str} {m['sig']}")
            if m["calls"]:
                out.append(f"//{indent}                → {format_calls(m['calls'])}")


def _format_inner_type(out, t, indent, grep=None, annotation=None):
    """Append one nested type as a header line plus a compact body."""
    ann = _format_annotation_list(t["annotations"])
    ann_str = f" {ann}" if ann else ""
    decl = t["declaration"]
    if t["enum_constants"]:
        decl += f" {{ {format_enum_constants(t['enum_constants'], ENUM_CONSTANTS_SKIM_MAX)} }}"
    out.append(f"//{indent} L{t['line']}:{ann_str} {decl}")
    body_indent = indent + "  "
    fields = instance_fields(t)
    if fields:
        out.append(f"//{body_indent} fields: {', '.join(_format_field(f) for f in fields)}")
    statics = static_fields(t)
    if statics:
        out.append(f"//{body_indent} static fields: {', '.join(format_static_field(f, t['constants']) for f in statics)}")
    if t["methods"]:
        _format_methods(out, t["methods"], body_indent, grep, annotation)
    for inner in t["inner_types"]:
        _format_inner_type(out, inner, body_indent, grep, annotation)


def _format_type(out, t, grep=None, annotation=None):
    """Append the body sections (fields, methods, inner types) of one type."""
    if t["enum_constants"]:
        out.append("//")
        out.append(f"// constants: {format_enum_constants(t['enum_constants'], ENUM_CONSTANTS_SKIM_MAX)}")

    fields = instance_fields(t)
    if fields:
        out.append("//")
        out.append("// fields:")
        for f in fields:
            out.append(f"//   {_format_field(f)}")

    statics = static_fields(t)
    if statics:
        out.append("//")
        out.append(f"// static fields: {', '.join(format_static_field(f, t['constants']) for f in statics)}")

    if t["static_initializers"]:
        out.append("//")
        for si in t["static_initializers"]:
            lines = si["end"] - si["start"] + 1
            out.append(f"// static initializer (L{si['start']}-L{si['end']}, {lines} lines)")

    if t["methods"]:
        out.append("//")
        _format_methods(out, t["methods"], "", grep, annotation)

    if t["inner_types"]:
        out.append("//")
        out.append("// inner types:")
        for inner in t["inner_types"]:
            _format_inner_type(out, inner, "  ", grep, annotation)


def format_output(parsed, filepath, grep=None, annotation=None):
    """Format a parse_java_source result into a compact summary."""
    out = [f"// {filepath}"]
    out.append(f"// {parsed['package'] or '(default)'}")
    if parsed["package_annotations"]:
        out.append(f"// {_format_annotation_list(parsed['package_annotations'])}")

    types = parsed["types"]
    if not types:
        out.append("//")
        out.append(f"// total: {parsed['total_lines']} lines")
        return "\n".join(out)

    primary = types[0]
    if primary["annotations"]:
        out.append(f"// {_format_annotation_list(primary['annotations'])}")
    out.append(f"// {primary['declaration']}")
    if primary["doc"]:
        out.append(f"// doc: {primary['doc']}")

    _format_type(out, primary, grep, annotation)

    extra_types = types[1:]
    if extra_types:
        out.append("//")
        out.append("// other classes in file:")
        for extra in extra_types:
            anns = _format_annotation_list(extra["annotations"])
            ann_str = f" {anns}" if anns else ""
            counts = []
            fc = len(instance_fields(extra))
            mc = len(extra["methods"])
            if fc:
                counts.append(f"{fc}F")
            if mc:
                counts.append(f"{mc}M")
            extra_str = f" [{', '.join(counts)}]" if counts else ""
            out.append(f"//   L{extra['line']}:{ann_str} {extra['declaration']}{extra_str}")

    out.append("//")
    out.append(f"// total: {parsed['total_lines']} lines")
    return "\n".join(out)


def main(args):
    """Summarize each .java path in ``args.paths``."""
    errors = 0
    for arg in args.paths:
        filepath = Path(arg)
        if not filepath.exists():
            print(f"Error: {filepath} not found", file=sys.stderr)
            errors += 1
            continue
        if filepath.suffix != ".java":
            print(f"Warning: {filepath} is not a .java file, skipping", file=sys.stderr)
            continue

        content = filepath.read_text(encoding="utf-8", errors="replace")
        parsed = parse_java_source(content, source_name=filepath)
        print(format_output(parsed, filepath, grep=args.grep, annotation=args.annotation))
        if len(args.paths) > 1:
            print()

    if errors:
        sys.exit(1)
