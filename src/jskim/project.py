"""jskim_project - Generate a compact project structure map for Java projects.

Usage: python3 jskim_project.py <src_dir> [options]

Options:
  --deps                 Show cross-class dependencies (import-based)
  --package <prefix>     Filter by package prefix (e.g. com.stw.server.tripsheet)
  --annotation <@Ann>    Filter by class-level annotation (e.g. @RestController)
  --extends <ClassName>  Filter by superclass name
  --implements <Name>    Filter by implemented interface name
  --callers <Class.method>  Show upstream callers for a method
  --impact <Class.method>   Show callers and callees for a method
  --depth <N>            Traversal depth for --callers/--impact (default: 1)
"""

import sys
from pathlib import Path
from collections import defaultdict
from .util import (
    parse_file_structure, get_class_body,
    get_body_members, get_annotations, get_modifiers_node,
    extract_field_info, extract_record_components, get_type_keyword,
    get_declaration_name, get_superclass, get_interfaces,
    build_class_declaration_text, get_enum_constants, is_field_final, is_field_static,
    get_annotation_name_from_node, HTTP_MAPPING_ANNOTATIONS,
    extract_mapping_paths, extract_request_method,
    extract_first_annotation_string,
    build_method_signature, build_method_identity, extract_method_calls, get_method_name,
    INNER_TYPE_NODES, METHOD_NODES, LOMBOK_SET,
)



def _join_paths(base, method_path):
    """Join a base path and method path into a full endpoint path."""
    if not base and not method_path:
        return "/"
    if not base:
        return method_path if method_path.startswith("/") else "/" + method_path
    if not method_path:
        return base if base.startswith("/") else "/" + base
    return base.rstrip("/") + "/" + method_path.lstrip("/")


def _scan_members(
    members,
    class_type,
    class_name,
    annotations,
    is_controller=False,
    is_spring_bean=False,
    has_constructor_injection=False,
    base_paths=None,
):
    """Scan fields, methods, and nested types from a member list."""
    if not base_paths:
        base_paths = [""]

    field_count = 0
    method_count = 0
    inner_types = []
    endpoints = []
    bean_deps = []
    bean_produces = []
    fields_detail = []
    methods_detail = []
    static_initializers = []

    for member in members:
        if member.type == "field_declaration":
            field_entries = extract_field_info(member)
            field_count += len(field_entries)

            for ftype, fname in field_entries:
                fields_detail.append({"type": ftype, "name": fname})

            if is_spring_bean:
                field_mods = get_modifiers_node(member)
                field_anns = get_annotations(field_mods) if field_mods else []
                field_final = is_field_final(member)
                field_static = is_field_static(member)
                is_injected = (
                    "@Autowired" in field_anns or "@Inject" in field_anns
                    or (has_constructor_injection and field_final and not field_static)
                )
                if is_injected:
                    for ftype, fname in field_entries:
                        if ftype:
                            dep_type = ftype.split("<")[0].strip()
                            bean_deps.append(dep_type)

        elif member.type in METHOD_NODES:
            method_count += 1

            method_mods = get_modifiers_node(member)
            method_name = get_method_name(member)
            start_line = member.start_point[0] + 1
            end_line = member.end_point[0] + 1
            methods_detail.append({
                "name": method_name,
                "identity": build_method_identity(member),
                "sig": build_method_signature(member),
                "start": start_line,
                "end": end_line,
                "calls": extract_method_calls(member),
            })

            if is_controller and method_mods:
                for child in method_mods.children:
                    if child.type in ("marker_annotation", "annotation"):
                        ann_name = get_annotation_name_from_node(child)
                        if ann_name in HTTP_MAPPING_ANNOTATIONS:
                            http_method = HTTP_MAPPING_ANNOTATIONS[ann_name]
                            if http_method is None:
                                http_method = extract_request_method(child) or "REQUEST"
                            method_paths = extract_mapping_paths(child)
                            if not method_paths:
                                method_paths = [""]
                            for bp in base_paths:
                                for mp in method_paths:
                                    endpoints.append({
                                        "method": http_method,
                                        "path": _join_paths(bp, mp),
                                        "handler": f"{class_name}.{method_name}()",
                                        "line": start_line,
                                    })

            if method_mods:
                method_anns = get_annotations(method_mods)
                if "@Bean" in method_anns:
                    type_node = member.child_by_field_name("type")
                    if type_node:
                        bean_type = type_node.text.decode().split("<")[0].strip()
                        bean_produces.append(bean_type)

        elif member.type == "static_initializer":
            start = member.start_point[0] + 1
            end = member.end_point[0] + 1
            static_initializers.append({"start": start, "end": end})

        elif member.type in INNER_TYPE_NODES:
            kw = get_type_keyword(member)
            nm = get_declaration_name(member)
            inner_types.append(f"{kw} {nm}")

    return {
        "field_count": field_count,
        "method_count": method_count,
        "inner_types": inner_types,
        "endpoints": endpoints,
        "bean_deps": bean_deps,
        "bean_produces": bean_produces,
        "fields_detail": fields_detail,
        "methods_detail": methods_detail,
        "static_initializers": static_initializers,
    }


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

    # --- Spring Boot detection ---
    is_controller = any(a in ("@RestController", "@Controller") for a in annotations)
    is_spring_bean = any(a in (
        "@Service", "@Component", "@Repository",
        "@Controller", "@RestController", "@Configuration",
    ) for a in annotations)
    has_constructor_injection = any(a in ("@RequiredArgsConstructor", "@AllArgsConstructor") for a in annotations)

    # Class-level base path and config prefix from annotation params
    base_paths = []
    config_prefix = None
    if mods:
        for child in mods.children:
            if child.type in ("marker_annotation", "annotation"):
                ann_name = get_annotation_name_from_node(child)
                if ann_name == "@RequestMapping":
                    base_paths = extract_mapping_paths(child)
                elif ann_name == "@ConfigurationProperties":
                    config_prefix = extract_first_annotation_string(child)
    if not base_paths:
        base_paths = [""]

    enum_constants_list = []

    body = get_class_body(decl)
    scanned_members = _scan_members(
        get_body_members(body),
        class_type,
        class_name,
        annotations,
        is_controller=is_controller,
        is_spring_bean=is_spring_bean,
        has_constructor_injection=has_constructor_injection,
        base_paths=base_paths,
    )

    if class_type == "enum" and body:
        enum_constants_list = get_enum_constants(body)

    record_components = extract_record_components(decl)
    record_fields = [{"type": ftype, "name": fname} for ftype, fname in record_components]

    return {
        "class_type": class_type,
        "class_name": class_name,
        "annotations": annotations,
        "lombok": lombok_anns,
        "extends": extends,
        "implements": ifaces,
        "field_count": len(record_fields) + scanned_members["field_count"],
        "method_count": scanned_members["method_count"],
        "inner_types": scanned_members["inner_types"],
        "enum_constants": enum_constants_list,
        "endpoints": scanned_members["endpoints"],
        "bean_deps": scanned_members["bean_deps"],
        "bean_produces": scanned_members["bean_produces"],
        "config_prefix": config_prefix,
        "fields_detail": record_fields + scanned_members["fields_detail"],
        "methods_detail": scanned_members["methods_detail"],
        "static_initializers": scanned_members["static_initializers"],
    }


def _scan_implicit_source_file(filepath, program_members):
    """Scan the implicit class produced by a Java simple source file."""
    class_name = filepath.stem
    scanned_members = _scan_members(
        program_members,
        "implicit class",
        class_name,
        [],
    )
    return {
        "class_type": "implicit class",
        "class_name": class_name,
        "annotations": [],
        "lombok": [],
        "extends": None,
        "implements": [],
        "enum_constants": [],
        "config_prefix": None,
        **scanned_members,
    }


def scan_java_file(filepath):
    """Extract structural info from a Java file using tree-sitter.

    Returns a list of info dicts — one per top-level type declaration.
    """
    content = filepath.read_text(encoding="utf-8", errors="replace")
    structure = parse_file_structure(content.encode("utf-8"))
    total_lines = len(content.split("\n"))

    results = []
    if structure["program_members"]:
        info = _scan_implicit_source_file(filepath, structure["program_members"])
        results.append({
            "filepath": filepath,
            "package": structure["package"],
            "imports": structure["imports"],
            "total_lines": total_lines,
            **info,
        })
    else:
        for node in structure["type_nodes"]:
            info = _scan_type_declaration(node)
            results.append({
                "filepath": filepath,
                "package": structure["package"],
                "imports": structure["imports"],
                "total_lines": total_lines,
                **info,
            })

    return results


def _qualified_name(info):
    """Build a fully-qualified name for a project type info dict."""
    name = info.get("class_name")
    if not name:
        return None
    pkg = info.get("package")
    return f"{pkg}.{name}" if pkg else name


def _strip_type_details(type_name):
    """Strip generics and array suffixes from a type reference."""
    if not type_name:
        return None
    cleaned = type_name.split("<", 1)[0].strip()
    while cleaned.endswith("[]"):
        cleaned = cleaned[:-2].strip()
    return cleaned


def _build_dependency_indexes(file_info_list):
    """Build lookup indexes for dependency resolution."""
    fq_names = set()
    package_to_fqns = defaultdict(set)
    simple_to_fqns = defaultdict(set)
    explicit_imports = {}
    wildcard_imports = defaultdict(set)

    for info in file_info_list:
        fq_name = _qualified_name(info)
        if fq_name:
            fq_names.add(fq_name)
            package = info.get("package") or ""
            package_to_fqns[package].add(fq_name)
            simple_to_fqns[info["class_name"]].add(fq_name)

        source_name = _qualified_name(info)
        if not source_name:
            continue
        for imp in info.get("imports", []):
            if imp.endswith(".*"):
                wildcard_imports[source_name].add(imp[:-2])
            else:
                explicit_imports[source_name] = explicit_imports.get(source_name, {})
                explicit_imports[source_name][imp.rsplit(".", 1)[-1]] = imp

    return fq_names, package_to_fqns, simple_to_fqns, explicit_imports, wildcard_imports


def _resolve_type_reference(type_name, info, indexes):
    """Resolve a type reference to a fully-qualified project type name."""
    fq_names, package_to_fqns, simple_to_fqns, explicit_imports, wildcard_imports = indexes
    stripped = _strip_type_details(type_name)
    if not stripped:
        return None

    if stripped in fq_names:
        return stripped

    source_name = _qualified_name(info)
    package = info.get("package") or ""

    same_package = f"{package}.{stripped}" if package else stripped
    if same_package in fq_names:
        return same_package

    explicit = explicit_imports.get(source_name, {}).get(stripped)
    if explicit in fq_names:
        return explicit

    for wildcard_pkg in wildcard_imports.get(source_name, set()):
        wildcard_match = f"{wildcard_pkg}.{stripped}" if wildcard_pkg else stripped
        if wildcard_match in fq_names:
            return wildcard_match

    matches = simple_to_fqns.get(stripped, set())
    if len(matches) == 1:
        return next(iter(matches))

    return None


def _dependency_display_name(fq_name, simple_to_fqns):
    """Prefer short names when they are unique in the project."""
    simple = fq_name.rsplit(".", 1)[-1]
    return simple if len(simple_to_fqns.get(simple, set())) == 1 else fq_name


def find_dependencies(file_info_list):
    """Find which classes reference which other classes in the project (import-based).

    Uses import statements to determine dependencies. O(N) instead of O(N²).
    Handles both explicit imports (com.example.Foo) and wildcard imports (com.example.*).
    """
    indexes = _build_dependency_indexes(file_info_list)
    _, package_to_fqns, simple_to_fqns, _, _ = indexes

    deps = {}
    for info in file_info_list:
        source_name = _qualified_name(info)
        if not source_name:
            continue
        referenced = set()

        for imp in info.get("imports", []):
            if imp.endswith(".*"):
                # Wildcard: match all project classes in that package
                pkg = imp[:-2]  # strip .*
                for fq_name in package_to_fqns.get(pkg, []):
                    if fq_name != source_name:
                        referenced.add(fq_name)
            else:
                if imp in indexes[0] and imp != source_name:
                    referenced.add(imp)

        # Also check extends/implements — those are direct references
        if info["extends"]:
            ext = _resolve_type_reference(info["extends"], info, indexes)
            if ext and ext != source_name:
                referenced.add(ext)
        for iface in info.get("implements", []):
            iface_name = _resolve_type_reference(iface, info, indexes)
            if iface_name and iface_name != source_name:
                referenced.add(iface_name)

        if referenced:
            display_name = _dependency_display_name(source_name, simple_to_fqns)
            deps[display_name] = sorted(
                _dependency_display_name(ref, simple_to_fqns) for ref in referenced
            )

    return deps


# ---------------------------------------------------------------------------
# Call hierarchy / impact support
# ---------------------------------------------------------------------------

def _iter_method_nodes(file_infos):
    """Yield normalized method nodes from project scan results."""
    for info in file_infos:
        fq_class = _qualified_name(info)
        if not fq_class:
            continue

        fields_by_name = {
            field["name"]: field["type"]
            for field in info.get("fields_detail", [])
            if field.get("name") and field.get("type")
        }

        for method in info.get("methods_detail", []):
            yield {
                "class_name": info.get("class_name"),
                "fq_class": fq_class,
                "name": method["name"],
                "identity": method["identity"],
                "sig": method["sig"],
                "start": method["start"],
                "end": method["end"],
                "calls": method.get("calls", []),
                "filepath": info.get("filepath"),
                "info": info,
                "fields_by_name": fields_by_name,
            }


def _method_key(method):
    """Build a unique key for a normalized method node."""
    return (
        str(method.get("filepath")),
        method["fq_class"],
        method["identity"],
        method["start"],
    )


def _method_display(method):
    """Build a compact display label for a normalized method node."""
    return f"{method['fq_class']}.{method['identity']}"


def _method_location(method):
    """Build a path:line location string for a normalized method node."""
    filepath = method.get("filepath")
    location = str(filepath) if filepath is not None else "?"
    return f"{location}:L{method['start']}"


def _resolve_call_target(call, source_method, indexes):
    """Resolve one extracted call string to a project class and method name."""
    if "." not in call:
        return source_method["fq_class"], call

    owner, method_name = call.rsplit(".", 1)
    type_name = None

    if owner == "super":
        type_name = source_method["info"].get("extends")
    elif owner in source_method["fields_by_name"]:
        type_name = source_method["fields_by_name"][owner]
    elif owner and owner[0].isupper():
        # Static calls such as FooFactory.create() use the class name as owner.
        type_name = owner

    if not type_name:
        return None

    fq_class = _resolve_type_reference(type_name, source_method["info"], indexes)
    if not fq_class:
        return None

    return fq_class, method_name


def _build_call_graph(file_infos):
    """Build resolved method-level incoming and outgoing call edges."""
    methods = list(_iter_method_nodes(file_infos))
    methods_by_key = {_method_key(method): method for method in methods}

    methods_by_class_name = defaultdict(list)
    for method in methods:
        methods_by_class_name[(method["fq_class"], method["name"])].append(method)

    indexes = _build_dependency_indexes(file_infos)
    incoming = defaultdict(list)
    outgoing = defaultdict(list)
    seen_edges = set()

    for source in methods:
        source_key = _method_key(source)
        for call in source.get("calls", []):
            resolved = _resolve_call_target(call, source, indexes)
            if not resolved:
                continue

            candidates = methods_by_class_name.get(resolved, [])
            if len(candidates) != 1:
                continue

            target = candidates[0]
            target_key = _method_key(target)
            edge = (source_key, target_key)
            if edge in seen_edges:
                continue

            seen_edges.add(edge)
            outgoing[source_key].append(target_key)
            incoming[target_key].append(source_key)

    return methods, methods_by_key, incoming, outgoing


def _resolve_target_method(methods, target):
    """Resolve a Class.method target to exactly one method node."""
    if "." not in target:
        return None, [], f"Error: target {target!r} requires Class.method"

    class_part, method_name = target.rsplit(".", 1)
    if not class_part or not method_name:
        return None, [], f"Error: target {target!r} requires Class.method"

    candidates = [
        method for method in methods
        if method["name"] == method_name
        and (method["class_name"] == class_part or method["fq_class"] == class_part)
    ]

    if len(candidates) == 1:
        return candidates[0], [], None
    if not candidates:
        return None, [], f"No target found: {target}"
    return None, candidates, f"Ambiguous target: {target}"


def _append_candidate_lines(out, candidates):
    """Append target candidate lines to output."""
    out.append("// candidates:")
    for method in sorted(candidates, key=lambda m: (_method_display(m), _method_location(m))):
        out.append(f"//   {_method_display(method)}  {_method_location(method)}")


def _append_call_tree(out, root, edges, methods_by_key, depth, arrow, indent_level=1, seen=None):
    """Append a bounded caller/callee tree rooted at a method."""
    if seen is None:
        seen = {_method_key(root)}

    if depth <= 0:
        return

    next_keys = [
        key for key in edges.get(_method_key(root), [])
        if key not in seen
    ]
    next_methods = sorted(
        (methods_by_key[key] for key in next_keys),
        key=lambda m: (_method_display(m), _method_location(m)),
    )

    if not next_methods and indent_level == 1:
        out.append("//   (none found)")
        return

    prefix = "  " * indent_level
    for method in next_methods:
        out.append(f"// {prefix}{arrow} {_method_display(method)}  {_method_location(method)}")
        _append_call_tree(
            out,
            method,
            edges,
            methods_by_key,
            depth - 1,
            arrow,
            indent_level + 1,
            seen | {_method_key(method)},
        )


def format_callers_output(file_infos, target, depth=1):
    """Format a bounded upstream caller hierarchy for a Class.method target."""
    methods, methods_by_key, incoming, _ = _build_call_graph(file_infos)
    target_method, candidates, error = _resolve_target_method(methods, target)

    out = [f"// === Callers: {target} (depth {depth}) ==="]
    if error:
        out.append(f"// {error}")
        if candidates:
            _append_candidate_lines(out, candidates)
            out.append("// use the fully-qualified class name to disambiguate")
        return "\n".join(out)

    out.append(f"// target: {_method_display(target_method)}  {_method_location(target_method)}")
    out.append("//")
    out.append("// callers:")
    _append_call_tree(out, target_method, incoming, methods_by_key, depth, "←")
    return "\n".join(out)


def format_impact_output(file_infos, target, depth=1):
    """Format bounded upstream callers and downstream callees for a target."""
    methods, methods_by_key, incoming, outgoing = _build_call_graph(file_infos)
    target_method, candidates, error = _resolve_target_method(methods, target)

    out = [f"// === Impact: {target} (depth {depth}) ==="]
    if error:
        out.append(f"// {error}")
        if candidates:
            _append_candidate_lines(out, candidates)
            out.append("// use the fully-qualified class name to disambiguate")
        return "\n".join(out)

    out.append(f"// target: {_method_display(target_method)}  {_method_location(target_method)}")
    out.append("//")
    out.append("// callers:")
    _append_call_tree(out, target_method, incoming, methods_by_key, depth, "←")
    out.append("//")
    out.append("// calls:")
    _append_call_tree(out, target_method, outgoing, methods_by_key, depth, "→")
    return "\n".join(out)


def _count_unique_files(file_infos):
    """Count files and lines once per filepath, not once per top-level type."""
    unique_files = {}
    fallback_count = 0
    fallback_lines = 0

    for info in file_infos:
        filepath = info.get("filepath")
        if filepath is None:
            fallback_count += 1
            fallback_lines += info.get("total_lines", 0)
            continue

        if filepath not in unique_files:
            unique_files[filepath] = info.get("total_lines", 0)

    return len(unique_files) + fallback_count, sum(unique_files.values()) + fallback_lines


def format_output(file_infos, show_deps=False, show_endpoints=False, show_beans=False):
    """Format the project map."""
    out = []

    packages = defaultdict(list)
    for info in file_infos:
        pkg = info["package"] or "(default)"
        packages[pkg].append(info)

    total_files, total_lines = _count_unique_files(file_infos)

    out.append(f"// Project Map: {total_files} files, {total_lines} lines")
    out.append("//")

    for pkg in sorted(packages.keys()):
        infos = sorted(packages[pkg], key=lambda x: x["class_name"] or "")
        pkg_files, pkg_lines = _count_unique_files(infos)
        out.append(f"// {pkg} ({pkg_files} files, {pkg_lines} lines)")

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

            # For enums, show constants inline
            if ctype == "enum" and info.get("enum_constants"):
                constants = info["enum_constants"]
                if len(constants) <= 6:
                    desc = f"{ctype} {name} {{ {', '.join(constants)} }}"
                else:
                    desc = f"{ctype} {name} {{ {', '.join(constants[:5])}, ...+{len(constants) - 5} }}"
            else:
                desc = f"{ctype} {name}"
            if info["extends"]:
                desc += f" extends {info['extends']}"
            if info["implements"]:
                keyword = "extends" if ctype == "interface" else "implements"
                desc += f" {keyword} {', '.join(info['implements'])}"

            extras = []
            if info["field_count"]:
                extras.append(f"{info['field_count']}F")
            if info["method_count"]:
                extras.append(f"{info['method_count']}M")
            extras.append(f"{info['total_lines']}L")
            if info["lombok"]:
                extras.append(f"lombok:{','.join(a.lstrip('@') for a in info['lombok'])}")
            if info.get("static_initializers"):
                si = info["static_initializers"]
                ranges = ", ".join(f"L{s['start']}-L{s['end']}" for s in si)
                extras.append(f"static-init:{ranges}")
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

    if show_endpoints:
        all_endpoints = []
        for info in file_infos:
            for ep in info.get("endpoints", []):
                all_endpoints.append(ep)
        if all_endpoints:
            all_endpoints.sort(key=lambda e: (e["path"], e["method"]))
            max_method = max(len(e["method"]) for e in all_endpoints)
            max_path = max(len(e["path"]) for e in all_endpoints)
            out.append("// === REST Endpoints ===")
            for e in all_endpoints:
                out.append(
                    f"//   {e['method']:<{max_method}}  {e['path']:<{max_path}}  "
                    f"{e['handler']}  L{e['line']}"
                )
            out.append("//")

    if show_beans:
        bean_entries = []
        for info in file_infos:
            if info.get("bean_deps"):
                ann = next(
                    (a for a in info["annotations"] if a in (
                        "@Service", "@Component", "@Repository",
                        "@Controller", "@RestController", "@Configuration",
                    )),
                    "",
                )
                bean_entries.append((info["class_name"], ann, info["bean_deps"]))
        if bean_entries:
            out.append("// === Bean Dependencies ===")
            for name, ann, deps in sorted(bean_entries):
                ann_str = f" {ann}" if ann else ""
                out.append(f"//   {name}{ann_str} ← {', '.join(deps)}")
            out.append("//")

        # Bean producers (@Bean factory methods)
        producer_entries = []
        for info in file_infos:
            if info.get("bean_produces"):
                ann = next(
                    (a for a in info["annotations"] if a in (
                        "@Configuration", "@Component", "@Service",
                    )),
                    "",
                )
                producer_entries.append((info["class_name"], ann, info["bean_produces"]))
        if producer_entries:
            out.append("// === Bean Producers (@Bean) ===")
            for name, ann, produces in sorted(producer_entries):
                ann_str = f" {ann}" if ann else ""
                # Deduplicate while preserving order; show count for repeated types
                seen = {}
                for p in produces:
                    seen[p] = seen.get(p, 0) + 1
                deduped = []
                for p, count in seen.items():
                    deduped.append(f"{p}(x{count})" if count > 1 else p)
                out.append(f"//   {name}{ann_str} → {', '.join(deduped)}")
            out.append("//")

        # Configuration properties
        config_entries = []
        for info in file_infos:
            if info.get("config_prefix"):
                fields = [f"{f['type']} {f['name']}" for f in info.get("fields_detail", [])]
                config_entries.append((info["config_prefix"], info["class_name"], fields))
        if config_entries:
            out.append("// === Configuration Properties ===")
            for prefix, name, fields in sorted(config_entries):
                if fields:
                    out.append(f"//   {prefix}.* ({name}): {', '.join(fields)}")
                else:
                    out.append(f"//   {prefix}.* ({name})")
            out.append("//")

    return "\n".join(out)


def _parse_args(argv):
    """Parse CLI arguments."""
    src_dir = None
    show_deps = False
    show_endpoints = False
    show_beans = False
    pkg_filter = None
    ann_filter = None
    ext_filter = None
    impl_filter = None
    callers_target = None
    impact_target = None
    depth = 1
    i = 0
    while i < len(argv):
        if argv[i] == "--deps":
            show_deps = True
            i += 1
        elif argv[i] == "--endpoints":
            show_endpoints = True
            i += 1
        elif argv[i] == "--beans":
            show_beans = True
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
        elif argv[i] == "--implements" and i + 1 < len(argv):
            impl_filter = argv[i + 1]
            i += 2
        elif argv[i] == "--callers" and i + 1 < len(argv):
            callers_target = argv[i + 1]
            i += 2
        elif argv[i] == "--impact" and i + 1 < len(argv):
            impact_target = argv[i + 1]
            i += 2
        elif argv[i] == "--depth" and i + 1 < len(argv):
            try:
                depth = max(0, int(argv[i + 1]))
            except ValueError:
                depth = 1
            i += 2
        elif src_dir is None:
            src_dir = argv[i]
            i += 1
        else:
            i += 1
    return (
        src_dir, show_deps, show_endpoints, show_beans,
        pkg_filter, ann_filter, ext_filter, impl_filter,
        callers_target, impact_target, depth,
    )


def _filter_infos(file_infos, pkg_filter, ann_filter, ext_filter, impl_filter=None):
    """Filter file infos by package, annotation, superclass, or implemented interface."""
    result = file_infos
    if pkg_filter:
        result = [i for i in result if i["package"] and i["package"].startswith(pkg_filter)]
    if ann_filter:
        ann = ann_filter if ann_filter.startswith("@") else "@" + ann_filter
        result = [i for i in result if any(a.startswith(ann) for a in i["annotations"])]
    if ext_filter:
        result = [i for i in result if i["extends"] and ext_filter in i["extends"]]
    if impl_filter:
        result = [i for i in result if any(
            impl_filter in iface.split("<")[0] for iface in i.get("implements", [])
        )]
    return result


def main():
    if len(sys.argv) < 2:
        print(
            "Usage: python3 jskim_project.py <src_dir> [--deps] [--endpoints] [--beans]"
            " [--package pkg] [--annotation @Ann] [--extends Class] [--implements Interface]"
            " [--callers Class.method] [--impact Class.method] [--depth N]",
            file=sys.stderr,
        )
        sys.exit(1)

    (
        src_dir_str, show_deps, show_endpoints, show_beans,
        pkg_filter, ann_filter, ext_filter, impl_filter,
        callers_target, impact_target, depth,
    ) = (
        _parse_args(sys.argv[1:])
    )

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

    if pkg_filter or ann_filter or ext_filter or impl_filter:
        file_infos = _filter_infos(file_infos, pkg_filter, ann_filter, ext_filter, impl_filter)

    if callers_target and impact_target:
        print("Error: use only one of --callers or --impact", file=sys.stderr)
        sys.exit(1)

    if callers_target:
        print(format_callers_output(file_infos, callers_target, depth=depth))
        return

    if impact_target:
        print(format_impact_output(file_infos, impact_target, depth=depth))
        return

    print(format_output(file_infos, show_deps, show_endpoints, show_beans))


if __name__ == "__main__":
    main()
