#!/usr/bin/env python3
"""jskim_method - Extract methods from a Java file with context.

Usage: python3 jskim_method.py <file.java> <method_name> [method2 ...]
       python3 jskim_method.py <file.java> --list

Options:
  --list    List all methods with line ranges (no bodies)

Outputs method bodies with surrounding context:
  - Class name and relevant fields
  - The full method source code
  - Other methods called within the same class (signatures only)
"""

import sys
import re
from pathlib import Path
from .util import (
    parse_java_bytes, find_first_type_declaration, get_class_body,
    get_body_members, get_annotations, get_modifiers_node,
    build_method_signature, build_class_declaration_text,
    extract_field_info, get_declaration_name,
    INNER_TYPE_NODES, METHOD_NODES,
)



def _parse_type_methods(decl):
    """Parse methods and fields from a single type declaration node."""
    class_name = get_declaration_name(decl)
    class_declaration = build_class_declaration_text(decl)
    fields = []
    methods = []

    body = get_class_body(decl)
    for member in get_body_members(body):
        if member.type == "field_declaration":
            field_entries = extract_field_info(member)
            for ftype, fname in field_entries:
                fields.append(f"{ftype} {fname}" if fname else ftype)

        elif member.type in METHOD_NODES:
            sig = build_method_signature(member)
            anns = get_annotations(get_modifiers_node(member))
            name_node = member.child_by_field_name("name")
            if not name_node:
                for c in member.children:
                    if c.type == "identifier":
                        name_node = c
                        break
            mname = name_node.text.decode() if name_node else "unknown"
            start = member.start_point[0] + 1
            end = member.end_point[0] + 1
            methods.append({
                "name": mname,
                "sig": sig,
                "start": start,
                "end": end,
                "annotations": anns,
                "class_name": class_name,
            })

    return class_name, class_declaration, fields, methods


def parse_methods(content):
    """Parse all methods from a Java file using tree-sitter."""
    root = parse_java_bytes(content.encode("utf-8"))
    lines = content.split("\n")

    package = None
    class_name = None
    class_declaration = None
    fields = []
    methods = []

    for child in root.children:
        if child.type == "package_declaration":
            for sub in child.children:
                if sub.type in ("scoped_identifier", "identifier"):
                    package = sub.text.decode()
                    break

        elif child.type in INNER_TYPE_NODES:
            cn, cd, fs, ms = _parse_type_methods(child)
            if class_name is None:
                class_name = cn
                class_declaration = cd
                fields = fs
            methods.extend(ms)

    return {
        "package": package,
        "class_name": class_name,
        "class_declaration": class_declaration,
        "fields": fields,
        "methods": methods,
        "lines": lines,
    }


def list_methods(parsed):
    """List all methods with line ranges."""
    out = []
    out.append(f"// {parsed['class_declaration'] or parsed['class_name']}")
    out.append("//")
    for m in parsed["methods"]:
        lines = m["end"] - m["start"] + 1
        loc = f"L{m['start']}-L{m['end']}"
        ann_str = " ".join(m["annotations"]) + " " if m["annotations"] else ""
        out.append(f"//   {loc:>12} ({lines:>3} lines): {ann_str}{m['sig']}")
    return "\n".join(out)


def extract_methods(parsed, method_names):
    """Extract one or more methods and their context."""
    all_lines = parsed["lines"]
    out = []
    not_found = []

    # Collect matches for all requested names, dedup by start line
    matches = []
    seen = set()
    for method_name in method_names:
        hits = [m for m in parsed["methods"] if m["name"] == method_name]
        if not hits:
            hits = [m for m in parsed["methods"] if method_name.lower() in m["name"].lower()]
        if not hits:
            not_found.append(method_name)
            continue
        for m in hits:
            if m["start"] not in seen:
                seen.add(m["start"])
                matches.append(m)

    if not matches:
        names = ", ".join(f"'{n}'" for n in method_names)
        return f"// Methods {names} not found in {parsed['class_name']}"

    out.append(f"// {parsed['class_declaration'] or parsed['class_name']}")

    if parsed["fields"]:
        out.append("// fields: " + ", ".join(parsed["fields"]))

    if not_found:
        out.append(f"// not found: {', '.join(not_found)}")

    out.append("//")

    for m in matches:
        ann_str = " ".join(m["annotations"]) + " " if m["annotations"] else ""
        out.append(f"// {ann_str}{m['sig']} (L{m['start']}-L{m['end']})")
        out.append("")

        start = m["start"]
        while start > 1:
            prev = all_lines[start - 2].strip()
            if prev.startswith("@") or prev.startswith("*") or prev.startswith("/*") or prev.startswith("//"):
                start -= 1
            else:
                break

        for i in range(start - 1, m["end"]):
            out.append(f"{i + 1:>5} | {all_lines[i]}")
        out.append("")

    method_bodies = ""
    for m in matches:
        for i in range(m["start"] - 1, m["end"]):
            method_bodies += all_lines[i] + "\n"

    matched_names = {m["name"] for m in matches}
    other_methods = [
        om for om in parsed["methods"]
        if om["name"] not in matched_names
    ]

    called = []
    for om in other_methods:
        if re.search(rf"\b{re.escape(om['name'])}\s*\(", method_bodies):
            called.append(om)

    if called:
        out.append("// --- called methods in same class ---")
        for c in called:
            out.append(f"//   L{c['start']}-L{c['end']}: {c['sig']}")

    return "\n".join(out)


def main():
    if len(sys.argv) < 3:
        print(
            "Usage: python3 jskim_method.py <file.java> <method> [method2 ...]",
            file=sys.stderr,
        )
        print(
            "       python3 jskim_method.py <file.java> --list",
            file=sys.stderr,
        )
        sys.exit(1)

    filepath = Path(sys.argv[1])
    if not filepath.exists():
        print(f"Error: {filepath} not found", file=sys.stderr)
        sys.exit(1)

    content = filepath.read_text(encoding="utf-8", errors="replace")
    parsed = parse_methods(content)

    if sys.argv[2] == "--list":
        print(list_methods(parsed))
    else:
        method_names = sys.argv[2:]
        print(extract_methods(parsed, method_names))


if __name__ == "__main__":
    main()
