"""jskim method - extract methods from a Java file with context.

Usage: jskim <file.java> <method_name> [method2 ...]
       jskim <file.java> --list

Outputs method bodies with surrounding context:
  - Class declaration and instance fields
  - The full method source code (with its Javadoc and behaviour annotations;
    documentation-only annotations such as OpenAPI blocks are skipped)
  - Other methods called within the same class (signatures only)
"""

import sys
from pathlib import Path

from .util import (
    parse_java_source,
    instance_fields,
    format_method_annotations,
    walk_types,
    resolve_target_class,
    get_type_and_supertypes,
)


def parse_methods(content, source_name=None):
    """Parse all methods (across every top-level and nested type) from a Java file."""
    parsed = parse_java_source(content, source_name=source_name)
    types = parsed["types"]
    primary = types[0] if types else None

    classes = [label for label, _ in walk_types(types)]
    methods = []
    type_map = {}
    for label, t in walk_types(types):
        type_map[label] = t
        for m in t["methods"]:
            methods.append({
                "name": m["name"],
                "sig": m["sig"],
                "start": m["start"],
                "decl_start": m["decl_start"],
                "end": m["end"],
                "noise_spans": m["noise_spans"],
                "annotations": format_method_annotations(m),
                "class_name": label,
                "calls": m.get("calls", []),
                "raw_calls": m.get("raw_calls", []),
            })

    return {
        "package": parsed["package"],
        "class_name": primary["name"] if primary else None,
        "class_declaration": primary["declaration"] if primary else None,
        "classes": classes,
        "type_map": type_map,
        "fields": [
            f"{f['type']} {f['name']}" if f["name"] else f["type"]
            for f in (instance_fields(primary) if primary else [])
        ],
        "methods": methods,
        "lines": content.split("\n"),
    }


def _header(parsed):
    return f"// {parsed['class_declaration'] or parsed['class_name']}"


def _method_line(m, prefix="//   "):
    lines = m["end"] - m["start"] + 1
    loc = f"L{m['start']}-L{m['end']}"
    ann_str = f"{m['annotations']} " if m["annotations"] else ""
    return f"{prefix}{loc:>12} ({lines:>3} lines): {ann_str}{m['sig']}"


def list_methods(parsed):
    """List all methods with line ranges."""
    out = [_header(parsed), "//"]
    out.extend(_method_line(m) for m in parsed["methods"])
    return "\n".join(out)


def _walk_back_start(all_lines, start):
    """Include the Javadoc / comment lines directly above a declaration."""
    while start > 1:
        prev = all_lines[start - 2].strip()
        if prev.startswith(("*", "/*", "//")):
            start -= 1
        else:
            break
    return start


def _skipped_lines(all_lines, spans):
    """Line numbers fully covered by documentation annotations.

    A span is skipped only when nothing else shares its first and last
    line, so ``@Override @SuppressWarnings("x")`` on one line stays visible.
    """
    skipped = set()
    for span in spans:
        first = all_lines[span["start"] - 1]
        last = all_lines[span["end"] - 1]
        if first[: span["start_col"]].strip() or last[span["end_col"]:].strip():
            continue
        skipped.update(range(span["start"], span["end"] + 1))
    return skipped


def extract_methods(parsed, method_names):
    """Extract one or more methods and their context."""
    all_lines = parsed["lines"]
    not_found = []
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

    out = [_header(parsed)]
    if parsed["fields"]:
        out.append("// fields: " + ", ".join(parsed["fields"]))
    if not_found:
        out.append(f"// not found: {', '.join(not_found)}")
    out.append("//")

    for m in matches:
        ann_str = f"{m['annotations']} " if m["annotations"] else ""
        out.append(f"// {ann_str}{m['sig']} (L{m['start']}-L{m['end']})")
        out.append("")
        start = _walk_back_start(all_lines, m["decl_start"])
        skipped = _skipped_lines(all_lines, m["noise_spans"])
        for i in range(start - 1, m["end"]):
            if i + 1 not in skipped:
                out.append(f"{i + 1:>5} | {all_lines[i]}")
        out.append("")

    matched_names = {m["name"] for m in matches}
    known_classes = set(
        parsed.get("classes")
        or [om.get("class_name") for om in parsed["methods"] if om.get("class_name")]
    )
    type_map = parsed.get("type_map") or {}
    called_ids = set()
    for m in matches:
        m_cls = m.get("class_name", "")
        parts = m_cls.split(".") if m_cls else []
        enclosing_classes = [".".join(parts[:i]) for i in range(len(parts), 0, -1)]
        if not enclosing_classes:
            enclosing_classes = [""]

        for c in m.get("raw_calls", m.get("calls", [])):
            if "." not in c:
                matched_unqualified = False
                for enc_cls in enclosing_classes:
                    search_classes = get_type_and_supertypes(enc_cls, type_map, known_classes)
                    for target_cls in search_classes:
                        matching = [
                            x for x in parsed["methods"]
                            if x["name"] == c and x.get("class_name", "") == target_cls
                        ]
                        if matching:
                            for x in matching:
                                called_ids.add(id(x))
                            matched_unqualified = True
                            break
                    if matched_unqualified:
                        break
            else:
                target, called_name = c.rsplit(".", 1)
                resolved_cls = resolve_target_class(target, m_cls, known_classes)
                if resolved_cls is not None:
                    search_classes = get_type_and_supertypes(resolved_cls, type_map, known_classes)
                    for target_cls in search_classes:
                        matching = [
                            x for x in parsed["methods"]
                            if x["name"] == called_name and x.get("class_name", "") == target_cls
                        ]
                        if matching:
                            for x in matching:
                                called_ids.add(id(x))
                            break

    called = [
        om for om in parsed["methods"]
        if om["name"] not in matched_names and id(om) in called_ids
    ]
    if called:
        out.append("// --- called methods in same class ---")
        for c in called:
            out.append(f"//   L{c['start']}-L{c['end']}: {c['sig']}")

    return "\n".join(out)


def main(args):
    """List or extract methods from the first .java path in ``args.paths``."""
    filepath = Path(args.paths[0])
    if not filepath.exists():
        print(f"Error: {filepath} not found", file=sys.stderr)
        sys.exit(1)

    content = filepath.read_text(encoding="utf-8", errors="replace")
    parsed = parse_methods(content, source_name=filepath)

    method_names = [p for p in args.paths[1:] if not p.endswith(".java")]
    if args.list or not method_names:
        print(list_methods(parsed))
    else:
        print(extract_methods(parsed, method_names))
