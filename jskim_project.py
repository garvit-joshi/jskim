#!/usr/bin/env python3
"""jskim_project - Generate a compact project structure map for Java projects.

Usage: python3 jskim_project.py <src_dir> [options]

Options:
  --deps                 Show cross-class dependencies (import-based)
  --package <prefix>     Filter by package prefix (e.g. com.stw.server.tripsheet)
  --annotation <@Ann>    Filter by class-level annotation (e.g. @RestController)
  --extends <ClassName>  Filter by superclass name
"""

import sys
from pathlib import Path
from collections import defaultdict
from jskim_util import (
    parse_java_bytes, find_first_type_declaration, get_class_body,
    get_body_members, get_annotations, get_modifiers_node,
    extract_import_path, extract_field_info, get_type_keyword,
    get_declaration_name, get_superclass, get_interfaces,
    build_class_declaration_text,
)


LOMBOK_SET = {
    "@Data", "@Value", "@Getter", "@Setter", "@Builder", "@SuperBuilder",
    "@NoArgsConstructor", "@AllArgsConstructor", "@RequiredArgsConstructor",
    "@ToString", "@EqualsAndHashCode", "@Slf4j", "@Log", "@Log4j2",
}

INNER_TYPE_NODES = {
    "class_declaration", "interface_declaration",
    "enum_declaration", "record_declaration",
    "annotation_type_declaration",
}

METHOD_NODES = {"method_declaration", "constructor_declaration", "compact_constructor_declaration"}


def _scan_type_declaration(decl):
    """Extract structural info from a single type declaration node."""
    class_type = get_type_keyword(decl)
    class_name = get_declaration_name(decl)
    extends = get_superclass(decl)
    if extends:
        extends = " ".join(extends.split())
    ifaces = get_interfaces(decl)
    ifaces = [" ".join(i.split()) for i in ifaces]

    mods = get_modifiers_node(decl)
    annotations = get_annotations(mods)
    lombok_anns = [a for a in annotations if a in LOMBOK_SET]

    field_count = 0
    method_count = 0
    inner_types = []

    body = get_class_body(decl)
    for member in get_body_members(body):
        if member.type == "field_declaration":
            field_entries = extract_field_info(member)
            field_count += len(field_entries)
        elif member.type in METHOD_NODES:
            method_count += 1
        elif member.type in INNER_TYPE_NODES:
            kw = get_type_keyword(member)
            nm = get_declaration_name(member)
            inner_types.append(f"{kw} {nm}")

    return {
        "class_type": class_type,
        "class_name": class_name,
        "annotations": annotations,
        "lombok": lombok_anns,
        "extends": extends,
        "implements": ifaces,
        "field_count": field_count,
        "method_count": method_count,
        "inner_types": inner_types,
    }


def scan_java_file(filepath):
    """Extract structural info from a Java file using tree-sitter.

    Returns a list of info dicts — one per top-level type declaration.
    """
    content = filepath.read_text(encoding="utf-8", errors="replace")
    root = parse_java_bytes(content.encode("utf-8"))
    total_lines = len(content.split("\n"))

    package = None
    imports = []
    type_infos = []

    for child in root.children:
        if child.type == "package_declaration":
            for sub in child.children:
                if sub.type in ("scoped_identifier", "identifier"):
                    package = sub.text.decode()
                    break

        elif child.type == "import_declaration":
            path = extract_import_path(child)
            if path:
                imports.append(path)

        elif child.type in INNER_TYPE_NODES:
            type_infos.append(_scan_type_declaration(child))

    results = []
    for info in type_infos:
        results.append({
            "filepath": filepath,
            "content": content,
            "package": package,
            "imports": imports,
            "total_lines": total_lines,
            **info,
        })

    return results


def find_dependencies(file_info_list):
    """Find which classes reference which other classes in the project (import-based).

    Uses import statements to determine dependencies. O(N) instead of O(N²).
    Handles both explicit imports (com.example.Foo) and wildcard imports (com.example.*).
    """
    # Build lookup: class_name -> set, and package -> set of class names
    project_classes = set()
    package_to_classes = defaultdict(set)
    for info in file_info_list:
        if info["class_name"]:
            project_classes.add(info["class_name"])
            pkg = info["package"] or ""
            package_to_classes[pkg].add(info["class_name"])

    deps = {}
    for info in file_info_list:
        if not info["class_name"]:
            continue
        name = info["class_name"]
        referenced = set()

        for imp in info.get("imports", []):
            if imp.endswith(".*"):
                # Wildcard: match all project classes in that package
                pkg = imp[:-2]  # strip .*
                for cls in package_to_classes.get(pkg, []):
                    if cls != name:
                        referenced.add(cls)
            else:
                # Explicit: last segment is the class name
                cls = imp.rsplit(".", 1)[-1]
                if cls in project_classes and cls != name:
                    referenced.add(cls)

        # Also check extends/implements — those are direct references
        if info["extends"]:
            ext = info["extends"].split("<")[0].strip()
            if ext in project_classes and ext != name:
                referenced.add(ext)
        for iface in info.get("implements", []):
            iface_name = iface.split("<")[0].strip()
            if iface_name in project_classes and iface_name != name:
                referenced.add(iface_name)

        if referenced:
            deps[name] = sorted(referenced)

    return deps


def format_output(file_infos, show_deps=False):
    """Format the project map."""
    out = []

    packages = defaultdict(list)
    for info in file_infos:
        pkg = info["package"] or "(default)"
        packages[pkg].append(info)

    total_files = len(file_infos)
    total_lines = sum(info["total_lines"] for info in file_infos)

    out.append(f"// Project Map: {total_files} files, {total_lines} lines")
    out.append("//")

    for pkg in sorted(packages.keys()):
        infos = sorted(packages[pkg], key=lambda x: x["class_name"] or "")
        pkg_lines = sum(i["total_lines"] for i in infos)
        out.append(f"// {pkg} ({len(infos)} files, {pkg_lines} lines)")

        for info in infos:
            name = info["class_name"] or "(unknown)"
            ctype = info["class_type"] or "?"

            parts = []
            if info["annotations"]:
                key_anns = [a for a in info["annotations"] if a in (
                    "@Entity", "@Service", "@Component", "@Controller",
                    "@RestController", "@Configuration", "@Repository",
                    "@Data", "@Value", "@Builder",
                )]
                if key_anns:
                    parts.append(" ".join(key_anns))

            desc = f"{ctype} {name}"
            if info["extends"]:
                desc += f" extends {info['extends']}"
            if info["implements"]:
                desc += f" implements {', '.join(info['implements'])}"

            extras = []
            if info["field_count"]:
                extras.append(f"{info['field_count']}F")
            if info["method_count"]:
                extras.append(f"{info['method_count']}M")
            extras.append(f"{info['total_lines']}L")
            if info["lombok"]:
                extras.append(f"lombok:{','.join(a.lstrip('@') for a in info['lombok'])}")
            if info["inner_types"]:
                extras.append(f"inner:{','.join(t.split()[-1] for t in info['inner_types'])}")

            extra_str = " | ".join(extras)
            ann_str = f" {' '.join(parts)}" if parts else ""
            out.append(f"//   {desc}{ann_str} [{extra_str}]")

        out.append("//")

    if show_deps:
        deps = find_dependencies(file_infos)
        if deps:
            out.append("// === Dependencies ===")
            for name in sorted(deps.keys()):
                refs = deps[name]
                out.append(f"//   {name} → {', '.join(refs)}")
            out.append("//")

    return "\n".join(out)


def _parse_args(argv):
    """Parse CLI arguments."""
    src_dir = None
    show_deps = False
    pkg_filter = None
    ann_filter = None
    ext_filter = None
    i = 0
    while i < len(argv):
        if argv[i] == "--deps":
            show_deps = True
            i += 1
        elif argv[i] == "--package" and i + 1 < len(argv):
            pkg_filter = argv[i + 1]
            i += 2
        elif argv[i] == "--annotation" and i + 1 < len(argv):
            ann_filter = argv[i + 1]
            i += 2
        elif argv[i] == "--extends" and i + 1 < len(argv):
            ext_filter = argv[i + 1]
            i += 2
        elif src_dir is None:
            src_dir = argv[i]
            i += 1
        else:
            i += 1
    return src_dir, show_deps, pkg_filter, ann_filter, ext_filter


def _filter_infos(file_infos, pkg_filter, ann_filter, ext_filter):
    """Filter file infos by package, annotation, or superclass."""
    result = file_infos
    if pkg_filter:
        result = [i for i in result if i["package"] and i["package"].startswith(pkg_filter)]
    if ann_filter:
        ann = ann_filter if ann_filter.startswith("@") else "@" + ann_filter
        result = [i for i in result if any(a.startswith(ann) for a in i["annotations"])]
    if ext_filter:
        result = [i for i in result if i["extends"] and ext_filter in i["extends"]]
    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 jskim_project.py <src_dir> [--deps] [--package pkg] [--annotation @Ann] [--extends Class]", file=sys.stderr)
        sys.exit(1)

    src_dir_str, show_deps, pkg_filter, ann_filter, ext_filter = _parse_args(sys.argv[1:])

    if not src_dir_str:
        print("Error: no source directory specified", file=sys.stderr)
        sys.exit(1)

    src_dir = Path(src_dir_str)

    if not src_dir.is_dir():
        print(f"Error: {src_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    java_files = sorted(src_dir.rglob("*.java"))

    if not java_files:
        print(f"No .java files found in {src_dir}", file=sys.stderr)
        sys.exit(1)

    file_infos = []
    for f in java_files:
        infos = scan_java_file(f)
        file_infos.extend(infos)

    if pkg_filter or ann_filter or ext_filter:
        file_infos = _filter_infos(file_infos, pkg_filter, ann_filter, ext_filter)

    print(format_output(file_infos, show_deps))


if __name__ == "__main__":
    main()
