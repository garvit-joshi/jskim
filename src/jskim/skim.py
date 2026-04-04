"""jskim - Summarize Java files to save tokens for AI coding agents.

Usage: python3 jskim.py <file.java> [file2.java ...]
       python3 jskim.py <file.java> --grep <pattern>
       python3 jskim.py <file.java> --annotation <@Ann>
"""

import sys
import re
from pathlib import Path
from .util import (
    parse_file_structure, get_class_body,
    get_body_members, get_annotations, get_annotations_rich, get_modifiers_node,
    build_method_signature, build_class_declaration_text,
    extract_field_info, extract_record_components, get_type_keyword,
    get_declaration_name, get_interfaces, get_enum_constants,
    extract_method_calls, build_implicit_class_declaration, build_method_identity,
    INNER_TYPE_NODES, METHOD_NODES, MODIFIER_KEYWORDS,
)


LOMBOK_ANNOTATIONS = {
    "@Data": "getters, setters, toString, equals, hashCode",
    "@Value": "getters, toString, equals, hashCode (immutable)",
    "@Getter": "getters",
    "@Setter": "setters",
    "@Builder": "builder pattern",
    "@SuperBuilder": "builder pattern (inheritance)",
    "@NoArgsConstructor": "no-args constructor",
    "@AllArgsConstructor": "all-args constructor",
    "@RequiredArgsConstructor": "constructor for final fields",
    "@ToString": "toString",
    "@EqualsAndHashCode": "equals, hashCode",
    "@Slf4j": "Logger log",
    "@Log": "Logger log",
    "@Log4j2": "Logger log",
}


def categorize_imports(imports):
    """Group imports by top-level package."""
    cats = {}
    for imp in imports:
        parts = imp.split(".")
        if parts[0] in ("java", "javax", "jakarta") and len(parts) >= 2:
            key = f"{parts[0]}.{parts[1]}"
        elif len(parts) >= 3:
            key = f"{parts[0]}.{parts[1]}.{parts[2]}"
        else:
            key = parts[0]
        cats[key] = cats.get(key, 0) + 1
    return cats


def classify_method(sig):
    """Classify a method as getter/setter/boilerplate/constructor/business."""
    clean = sig.strip()

    name_match = re.search(r"(\w+)\s*\(", clean)
    if not name_match:
        # Compact constructor: "public ClassName" (no parens in record constructors)
        tokens = clean.split()
        if tokens and tokens[-1][0].isupper():
            return "constructor"
        raise ValueError(f"Cannot classify method signature: {sig!r}")
    name = name_match.group(1)

    idx = clean.find(name + "(")
    if idx == -1:
        idx = name_match.start()
    before_name = clean[:idx].strip()
    tokens = before_name.split()
    non_mod = [t for t in tokens if t not in MODIFIER_KEYWORDS and not t.startswith("@")]

    if not non_mod and name[0].isupper():
        return "constructor"

    return_type = non_mod[-1] if non_mod else ""

    if name in ("toString", "hashCode", "equals", "compareTo", "clone"):
        return "boilerplate"

    param_match = re.search(r"\(([^)]*)\)", clean)
    params = param_match.group(1).strip() if param_match else ""

    if not params and (
        (name.startswith("get") and len(name) > 3 and name[3].isupper() and return_type != "void")
        or (
            name.startswith("is")
            and len(name) > 2
            and name[2].isupper()
            and return_type in ("boolean", "Boolean")
        )
    ):
        return "getter"

    if (
        name.startswith("set")
        and len(name) > 3
        and name[3].isupper()
        and return_type == "void"
        and params
        and "," not in params
    ):
        return "setter"

    return "business"



def _parse_members(members):
    """Parse fields, methods, and nested declarations from a member list."""
    fields = []
    methods = []
    inner_types = []
    static_initializers = []
    for member in members:
        if member.type == "field_declaration":
            field_entries = extract_field_info(member)
            anns = get_annotations(get_modifiers_node(member))
            ann_str = " ".join(anns)
            for ftype, fname in field_entries:
                fields.append({
                    "type": ftype,
                    "name": fname,
                    "annotations": ann_str,
                })

        elif member.type in METHOD_NODES:
            sig = build_method_signature(member)
            rich = get_annotations_rich(get_modifiers_node(member))
            # Use full text (with params) for Spring annotations
            anns = [a["full"] for a in rich]
            start = member.start_point[0] + 1
            end = member.end_point[0] + 1
            calls = extract_method_calls(member)
            methods.append({
                "start": start,
                "end": end,
                "sig": sig,
                "identity": build_method_identity(member),
                "annotations": anns,
                "calls": calls,
            })

        elif member.type == "static_initializer":
            start = member.start_point[0] + 1
            end = member.end_point[0] + 1
            static_initializers.append({"start": start, "end": end})

        elif member.type in INNER_TYPE_NODES:
            inner_line = member.start_point[0] + 1
            inner_decl = build_class_declaration_text(member)
            inner_anns = get_annotations(get_modifiers_node(member))
            inner_types.append({
                "line": inner_line,
                "declaration": inner_decl,
                "annotations": inner_anns,
            })

    return {
        "fields": fields,
        "methods": methods,
        "inner_types": inner_types,
        "static_initializers": static_initializers,
    }


def _parse_type_declaration(decl):
    """Parse a single type declaration node and return its structural info."""
    mods = get_modifiers_node(decl)
    rich_anns = get_annotations_rich(mods)
    class_annotations = [a["full"] for a in rich_anns]
    class_declaration = build_class_declaration_text(decl)
    class_line = decl.start_point[0] + 1

    lombok_notes = []
    for a in rich_anns:
        if a["name"] in LOMBOK_ANNOTATIONS:
            lombok_notes.append(f"{a['name']}: {LOMBOK_ANNOTATIONS[a['name']]}")

    body = get_class_body(decl)
    parsed_members = _parse_members(get_body_members(body))

    # Record components (shown as fields)
    record_fields = []
    for ftype, fname in extract_record_components(decl):
        record_fields.append({"type": ftype, "name": fname, "annotations": ""})

    enum_constants_list = []
    if decl.type == "enum_declaration" and body:
        enum_constants_list = get_enum_constants(body)

    return {
        "class_annotations": class_annotations,
        "class_declaration": class_declaration,
        "class_line": class_line,
        "fields": record_fields + parsed_members["fields"],
        "methods": parsed_members["methods"],
        "inner_types": parsed_members["inner_types"],
        "lombok_notes": lombok_notes,
        "enum_constants": enum_constants_list,
        "static_initializers": parsed_members["static_initializers"],
    }


def _parse_implicit_declaration(program_members, source_name=None):
    """Parse the synthetic implicit class for a Java simple source file."""
    parsed_members = _parse_members(program_members)
    return {
        "class_annotations": [],
        "class_declaration": build_implicit_class_declaration(source_name),
        "class_line": 1,
        "fields": parsed_members["fields"],
        "methods": parsed_members["methods"],
        "inner_types": parsed_members["inner_types"],
        "lombok_notes": [],
        "enum_constants": [],
        "static_initializers": parsed_members["static_initializers"],
    }


def parse_java(content, source_name=None):
    """Parse a Java file using tree-sitter and extract structural information."""
    structure = parse_file_structure(content.encode("utf-8"))
    lines = content.split("\n")

    if structure["program_members"]:
        primary = _parse_implicit_declaration(structure["program_members"], source_name)
        extra_types = []
    else:
        type_declarations = [_parse_type_declaration(node) for node in structure["type_nodes"]]

        if not type_declarations:
            primary = {
                "class_annotations": [],
                "class_declaration": None,
                "class_line": 1,
                "fields": [],
                "methods": [],
                "inner_types": [],
                "lombok_notes": [],
                "enum_constants": [],
                "static_initializers": [],
            }
            extra_types = []
        else:
            # Primary class is the first declaration
            primary = type_declarations[0]

            # Additional top-level classes (package-private helpers, sealed subtypes, etc.)
            extra_types = type_declarations[1:]

    return {
        "package": structure["package"],
        "imports": structure["imports"],
        **primary,
        "extra_types": extra_types,
        "total_lines": len(lines),
    }


def _match_method(m, grep=None, annotation=None):
    """Check if a method matches the given filters."""
    if grep and grep.lower() not in m["sig"].lower():
        return False
    if annotation:
        ann = annotation if annotation.startswith("@") else "@" + annotation
        if not any(a.startswith(ann) for a in m.get("annotations", [])):
            return False
    return True


def format_output(parsed, filepath, grep=None, annotation=None):
    """Format parsed data into compact summary."""
    out = []
    filtering = grep or annotation

    # Header
    cats = categorize_imports(parsed["imports"])
    pkg = parsed["package"] or "(default)"
    out.append(f"// {filepath}")
    if cats:
        cat_str = ", ".join(f"{k}({v})" for k, v in sorted(cats.items()))
        out.append(f"// {pkg} | {len(parsed['imports'])} imports: {cat_str}")
    else:
        out.append(f"// {pkg} | 0 imports")

    # Lombok
    if parsed["lombok_notes"]:
        out.append(f"// lombok: {' | '.join(parsed['lombok_notes'])}")

    # Class
    if parsed["class_annotations"]:
        out.append(f"// {' '.join(parsed['class_annotations'])}")
    if parsed["class_declaration"]:
        out.append(f"// {parsed['class_declaration']}")

    # Enum constants
    if parsed.get("enum_constants"):
        out.append("//")
        constants = parsed["enum_constants"]
        if len(constants) <= 10:
            out.append(f"// constants: {', '.join(constants)}")
        else:
            out.append(f"// constants: {', '.join(constants[:8])}, ... +{len(constants) - 8} more")

    # Fields
    if parsed["fields"]:
        out.append("//")
        out.append("// fields:")
        for f in parsed["fields"]:
            ann = f" ({f['annotations']})" if f["annotations"] else ""
            name = f" {f['name']}" if f["name"] else ""
            out.append(f"//   {f['type']}{name}{ann}")

    # Static initializers
    if parsed.get("static_initializers"):
        out.append("//")
        for si in parsed["static_initializers"]:
            lines = si["end"] - si["start"] + 1
            out.append(f"// static initializer (L{si['start']}-L{si['end']}, {lines} lines)")

    # Methods
    if parsed["methods"]:
        out.append("//")

        getters = []
        setters = []
        boilerplate = []
        constructors = []
        business = []

        for m in parsed["methods"]:
            kind = classify_method(m["sig"])
            name_match = re.search(r"(\w+)\s*\(", m["sig"])
            name = name_match.group(1) if name_match else m["sig"]

            if filtering and not _match_method(m, grep, annotation):
                continue

            if kind == "getter":
                getters.append(name)
            elif kind == "setter":
                setters.append(name)
            elif kind == "boilerplate":
                boilerplate.append(name)
            elif kind == "constructor":
                constructors.append(m)
            else:
                business.append(m)

        if getters:
            out.append(f"// getters: {', '.join(getters)}")
        if setters:
            out.append(f"// setters: {', '.join(setters)}")
        if boilerplate:
            out.append(f"// boilerplate: {', '.join(boilerplate)}")

        all_named = constructors + business
        if all_named:
            out.append("// methods:")
            for m in all_named:
                lines = m["end"] - m["start"] + 1
                loc = f"L{m['start']}-L{m['end']}"
                ann_str = ""
                if m["annotations"]:
                    ann_str = " " + " ".join(m["annotations"])
                out.append(f"//   {loc:>12} ({lines:>3} lines):{ann_str} {m['sig']}")
                calls = m.get("calls", [])
                if calls:
                    if len(calls) <= 10:
                        out.append(f"//                → {', '.join(calls)}")
                    else:
                        out.append(f"//                → {', '.join(calls[:10])}, ... +{len(calls) - 10} more")

    # Inner types
    if parsed["inner_types"]:
        out.append("//")
        out.append("// inner types:")
        for t in parsed["inner_types"]:
            ann = " ".join(t["annotations"])
            ann_str = f" {ann}" if ann else ""
            out.append(f"//   L{t['line']}:{ann_str} {t['declaration']}")

    # Extra top-level types (package-private classes, sealed subtypes, etc.)
    if parsed.get("extra_types"):
        out.append("//")
        out.append("// other classes in file:")
        for extra in parsed["extra_types"]:
            decl = extra["class_declaration"] or "?"
            anns = " ".join(extra["class_annotations"])
            ann_str = f" {anns}" if anns else ""
            mc = len(extra["methods"])
            fc = len(extra["fields"])
            line = extra["class_line"]
            parts = []
            if fc:
                parts.append(f"{fc}F")
            if mc:
                parts.append(f"{mc}M")
            extra_str = f" [{', '.join(parts)}]" if parts else ""
            out.append(f"//   L{line}:{ann_str} {decl}{extra_str}")

    out.append(f"//")
    out.append(f"// total: {parsed['total_lines']} lines")

    return "\n".join(out)


def _parse_args(argv):
    """Parse CLI arguments into files and filter flags."""
    grep = None
    annotation = None
    files = []
    i = 0
    while i < len(argv):
        if argv[i] == "--grep" and i + 1 < len(argv):
            grep = argv[i + 1]
            i += 2
        elif argv[i] == "--annotation" and i + 1 < len(argv):
            annotation = argv[i + 1]
            i += 2
        else:
            files.append(argv[i])
            i += 1
    return files, grep, annotation


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 jskim.py <file.java> [--grep pattern] [--annotation @Ann]", file=sys.stderr)
        sys.exit(1)

    files, grep, annotation = _parse_args(sys.argv[1:])

    if not files:
        print("Error: no files specified", file=sys.stderr)
        sys.exit(1)

    errors = 0
    for arg in files:
        filepath = Path(arg)
        if not filepath.exists():
            print(f"Error: {filepath} not found", file=sys.stderr)
            errors += 1
            continue
        if not filepath.suffix == ".java":
            print(f"Warning: {filepath} is not a .java file, skipping", file=sys.stderr)
            continue

        content = filepath.read_text(encoding="utf-8", errors="replace")
        parsed = parse_java(content, source_name=filepath)
        print(format_output(parsed, filepath, grep=grep, annotation=annotation))
        if len(files) > 1:
            print()

    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
