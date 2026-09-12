"""jskim project - compact project structure map for Java source trees.

Usage: jskim <src_dir> [options]

Options:
  --deps                    Show package-to-package dependencies (import-based)
  --endpoints               Show REST endpoints (resolved paths, guards)
  --beans                   Show Spring DI wiring, @Bean producers, config properties
  --package <text>          Filter by package (substring match)
  --annotation <@Ann>       Filter by class-level annotation
  --extends <ClassName>     Filter by superclass name
  --implements <Name>       Filter by implemented interface name
  --callers <Class.method>  Show upstream callers for a method
  --impact <Class.method>   Show callers and callees for a method
  --depth <N>               Traversal depth for --callers/--impact (default: 1)
"""

import sys
import textwrap
from collections import defaultdict
from pathlib import Path

from .util import (
    parse_java_source, instance_fields, format_enum_constants, format_annotation,
    extract_mapping_paths, extract_request_method, extract_first_annotation_string,
    walk_types, HTTP_MAPPING_ANNOTATIONS, LOMBOK_SET, LOMBOK_CONSTRUCTOR_ANNOTATIONS,
    SPRING_STEREOTYPES, CONTROLLER_ANNOTATIONS, INJECTION_ANNOTATIONS,
    KEY_CLASS_ANNOTATIONS, ENUM_CONSTANTS_MAP_MAX, MAP_COLLAPSED_KINDS, MAP_LINE_WIDTH, SKIP_DIRS,
)


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------

def _join_paths(base, method_path):
    """Join a base path and method path into a full endpoint path."""
    if not base and not method_path:
        return "/"
    if not base:
        return method_path if method_path.startswith("/") else "/" + method_path
    if not method_path:
        return base if base.startswith("/") else "/" + base
    return base.rstrip("/") + "/" + method_path.lstrip("/")


def _strip_type_details(type_name):
    """Strip generics and array suffixes from a type reference."""
    if not type_name:
        return None
    cleaned = type_name.split("<", 1)[0].strip()
    while cleaned.endswith("[]"):
        cleaned = cleaned[:-2].strip()
    return cleaned


def _bean_dependencies(t, is_bean):
    """Derive a Spring bean's injected dependencies from a parsed type.

    Constructor parameters are the dependency list. Without an explicit
    constructor, a Lombok constructor annotation makes every final instance
    field a dependency. Fields annotated @Autowired/@Inject always count.
    """
    if not is_bean:
        return []
    deps = []

    def _add(type_text):
        if type_text and type_text not in deps:
            deps.append(type_text)

    constructors = [m for m in t["methods"] if m["kind"] == "constructor" and m["params"]]
    for m in constructors:
        for p in m["params"]:
            _add(p["type"])
    if not constructors and any(a in LOMBOK_CONSTRUCTOR_ANNOTATIONS for a in t["annotation_names"]):
        for f in instance_fields(t):
            if f["final"]:
                _add(f["type"])
    for f in instance_fields(t):
        if any(a in INJECTION_ANNOTATIONS for a in f["annotations"]):
            _add(f["type"])
    return deps


def _bean_producers(t):
    """Return types produced by @Bean methods in a type and its nested types."""
    return [
        _strip_type_details(m["return_type"])
        for _, nested in walk_types([t])
        for m in nested["methods"]
        if m["return_type"] and any(a["name"] == "@Bean" for a in m["annotations"])
    ]


def _type_info(t, filepath, parsed):
    """Flatten one parsed type plus its file context into a project row dict."""
    anns = t["annotation_names"]
    is_bean = any(a in SPRING_STEREOTYPES for a in anns)
    config_prefix = None
    for a in t["annotations"]:
        if a["name"] == "@ConfigurationProperties":
            config_prefix = extract_first_annotation_string(a["node"])
    fields = instance_fields(t)

    return {
        "filepath": filepath,
        "package": parsed["package"],
        "imports": parsed["imports"],
        "total_lines": parsed["total_lines"],
        "class_type": t["kind"],
        "class_name": t["name"],
        "annotations": anns,
        "type_annotations": t["annotations"],
        "lombok": [a for a in anns if a in LOMBOK_SET],
        "extends": t["extends"],
        "implements": t["implements"],
        "field_count": len(fields),
        "method_count": len(t["methods"]),
        "inner_types": [f"{i['kind']} {i['name']}" for i in t["inner_types"]],
        "enum_constants": t["enum_constants"],
        "static_initializers": t["static_initializers"],
        "constants": t["constants"],
        "is_controller": any(a in CONTROLLER_ANNOTATIONS for a in anns),
        "endpoints": [],
        "bean_deps": _bean_dependencies(t, is_bean),
        "bean_produces": _bean_producers(t),
        "config_prefix": config_prefix,
        "fields_detail": [{"type": f["type"], "name": f["name"]} for f in fields],
        "methods_detail": t["methods"],
    }


def scan_java_file(filepath):
    """Parse one Java file into a file dict with one row per top-level type."""
    content = filepath.read_text(encoding="utf-8", errors="replace")
    parsed = parse_java_source(content, source_name=filepath)
    return {
        "filepath": filepath,
        "package": parsed["package"],
        "package_annotations": [a["full"] for a in parsed["package_annotations"]],
        "imports": parsed["imports"],
        "total_lines": parsed["total_lines"],
        "types": [_type_info(t, filepath, parsed) for t in parsed["types"]],
    }


def find_java_files(src_dir):
    """Return the .java files under ``src_dir``, skipping SKIP_DIRS (build output, VCS)."""
    return sorted(
        f for f in src_dir.rglob("*.java")
        if not SKIP_DIRS.intersection(f.relative_to(src_dir).parts[:-1])
    )


def flatten_types(file_infos):
    """Return every type row across a list of scanned files."""
    return [t for f in file_infos for t in f["types"]]


def _global_constants(type_infos):
    """Map ``Class.CONSTANT`` to its value across the whole project."""
    result = {}
    for info in type_infos:
        for name, value in info["constants"].items():
            result[f"{info['class_name']}.{name}"] = value
    return result


def collect_endpoints(type_infos, constant_types=None):
    """Resolve REST endpoints for every controller, filling ``info["endpoints"]``.

    Paths and guard annotations referencing constants in other classes
    resolve through the project-wide constant table built from
    ``constant_types`` (default: ``type_infos``; pass the unfiltered project
    when ``type_infos`` is a filtered subset). ``guards`` holds the handler's
    remaining annotations (``@RequiresPermission("x")``, ``@ResponseStatus(...)``).
    """
    global_constants = _global_constants(constant_types or type_infos)
    for info in type_infos:
        if not info["is_controller"]:
            continue
        constants = {**global_constants, **info["constants"]}
        base_paths = [""]
        for a in info["type_annotations"]:
            if a["name"] == "@RequestMapping":
                base_paths = extract_mapping_paths(a["node"], constants) or [""]

        endpoints = []
        for m in info["methods_detail"]:
            guards = " ".join(
                format_annotation(a["node"], constants)["full"]
                for a in m["annotations"] if a["name"] not in HTTP_MAPPING_ANNOTATIONS
            )
            for a in m["annotations"]:
                if a["name"] not in HTTP_MAPPING_ANNOTATIONS:
                    continue
                http_method = HTTP_MAPPING_ANNOTATIONS[a["name"]]
                if http_method is None:
                    http_method = extract_request_method(a["node"]) or "REQUEST"
                method_paths = extract_mapping_paths(a["node"], constants) or [""]
                for bp in base_paths:
                    for mp in method_paths:
                        endpoints.append({
                            "method": http_method,
                            "path": _join_paths(bp, mp),
                            "handler": f"{info['class_name']}.{m['name']}()",
                            "line": m["start"],
                            "guards": guards,
                        })
        info["endpoints"] = endpoints


# ---------------------------------------------------------------------------
# Dependency resolution
# ---------------------------------------------------------------------------

def _qualified_name(info):
    """Build a fully-qualified name for a project type info dict."""
    name = info.get("class_name")
    if not name:
        return None
    pkg = info.get("package")
    return f"{pkg}.{name}" if pkg else name


def _build_dependency_indexes(type_infos):
    """Build lookup indexes for dependency resolution."""
    fq_names = set()
    package_to_fqns = defaultdict(set)
    simple_to_fqns = defaultdict(set)
    explicit_imports = {}
    wildcard_imports = defaultdict(set)

    for info in type_infos:
        fq_name = _qualified_name(info)
        if not fq_name:
            continue
        fq_names.add(fq_name)
        package_to_fqns[info.get("package") or ""].add(fq_name)
        simple_to_fqns[info["class_name"]].add(fq_name)
        for imp in info.get("imports", []):
            if imp.endswith(".*"):
                wildcard_imports[fq_name].add(imp[:-2])
            else:
                explicit_imports.setdefault(fq_name, {})[imp.rsplit(".", 1)[-1]] = imp

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


def _referenced_types(info, indexes):
    """Fully-qualified project types one type references via imports, extends, implements."""
    fq_names, package_to_fqns, _, _, _ = indexes
    source_name = _qualified_name(info)
    referenced = set()
    for imp in info.get("imports", []):
        if imp.endswith(".*"):
            referenced.update(package_to_fqns.get(imp[:-2], ()))
        elif imp in fq_names:
            referenced.add(imp)
        elif imp.rsplit(".", 1)[0] in fq_names:
            referenced.add(imp.rsplit(".", 1)[0])  # static import of a member
    for ref in [info["extends"]] + list(info.get("implements", [])):
        resolved = _resolve_type_reference(ref, info, indexes) if ref else None
        if resolved:
            referenced.add(resolved)
    referenced.discard(source_name)
    return referenced


def find_package_dependencies(type_infos):
    """Map each package to the other project packages it depends on.

    Returns ``{source_pkg: {target_pkg: sorted simple type names}}``, built
    from imports (explicit, wildcard, static), ``extends`` and ``implements``.
    Same-package references are skipped: the interesting edges are the ones
    that cross a module boundary.
    """
    indexes = _build_dependency_indexes(type_infos)
    deps = defaultdict(lambda: defaultdict(set))
    for info in type_infos:
        if not _qualified_name(info):
            continue
        source_pkg = info.get("package") or ""
        for fq_name in _referenced_types(info, indexes):
            target_pkg, _, simple = fq_name.rpartition(".")
            if target_pkg != source_pkg:
                deps[source_pkg][target_pkg].add(simple)
    return {
        src: {dst: sorted(names) for dst, names in sorted(targets.items())}
        for src, targets in sorted(deps.items())
    }


# ---------------------------------------------------------------------------
# Call hierarchy / impact support
# ---------------------------------------------------------------------------

def _iter_method_nodes(type_infos):
    """Yield normalized method nodes from project scan results."""
    for info in type_infos:
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
                "start": method["start"],
                "calls": method.get("calls", []),
                "filepath": info.get("filepath"),
                "info": info,
                "fields_by_name": fields_by_name,
            }


def _method_key(method):
    """Build a unique key for a normalized method node."""
    return (str(method.get("filepath")), method["fq_class"], method["identity"], method["start"])


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
    if owner == "super":
        type_name = source_method["info"].get("extends")
    elif owner in source_method["fields_by_name"]:
        type_name = source_method["fields_by_name"][owner]
    elif owner[:1].isupper():
        # Static calls such as FooFactory.create() use the class name as owner.
        type_name = owner
    else:
        type_name = None

    if not type_name:
        return None
    fq_class = _resolve_type_reference(type_name, source_method["info"], indexes)
    if not fq_class:
        return None
    return fq_class, method_name


def _subtypes_index(type_infos, indexes):
    """Map each project type to the project types that extend or implement it."""
    subtypes = defaultdict(set)
    for info in type_infos:
        fq_name = _qualified_name(info)
        if not fq_name:
            continue
        for ref in [info["extends"]] + list(info.get("implements", [])):
            resolved = _resolve_type_reference(ref, info, indexes) if ref else None
            if resolved and resolved != fq_name:
                subtypes[resolved].add(fq_name)
    return subtypes


def _with_subtypes(fq_class, subtypes):
    """A class plus every project type below it in the hierarchy (transitively)."""
    result = []
    pending = [fq_class]
    while pending:
        current = pending.pop()
        if current in result:
            continue
        result.append(current)
        pending.extend(subtypes.get(current, ()))
    return result


def _build_call_graph(type_infos):
    """Build resolved method-level incoming and outgoing call edges.

    A call resolved to an interface or superclass method also produces an
    edge to the same-named method of every implementing/extending project
    type, so callers of a Modulith ``*Api`` interface show up as callers of
    the service that implements it.

    Returns ``(methods, methods_by_key, incoming, outgoing, display)`` where
    ``display`` renders a method as ``Class.identity``, fully qualified only
    when the simple class name is ambiguous in the project.
    """
    methods = list(_iter_method_nodes(type_infos))
    methods_by_key = {_method_key(method): method for method in methods}

    methods_by_class_name = defaultdict(list)
    for method in methods:
        methods_by_class_name[(method["fq_class"], method["name"])].append(method)

    indexes = _build_dependency_indexes(type_infos)
    simple_to_fqns = indexes[2]
    subtypes = _subtypes_index(type_infos, indexes)
    incoming = defaultdict(list)
    outgoing = defaultdict(list)
    seen_edges = set()

    for source in methods:
        source_key = _method_key(source)
        for call in source.get("calls", []):
            resolved = _resolve_call_target(call, source, indexes)
            if not resolved:
                continue
            fq_class, method_name = resolved
            for target_class in _with_subtypes(fq_class, subtypes):
                candidates = methods_by_class_name.get((target_class, method_name), [])
                if len(candidates) != 1:
                    continue
                target_key = _method_key(candidates[0])
                edge = (source_key, target_key)
                if edge in seen_edges:
                    continue
                seen_edges.add(edge)
                outgoing[source_key].append(target_key)
                incoming[target_key].append(source_key)

    def display(method):
        cls = _dependency_display_name(method["fq_class"], simple_to_fqns)
        return f"{cls}.{method['identity']}"

    return methods, methods_by_key, incoming, outgoing, display


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


def _append_call_tree(out, root, edges, methods_by_key, display, depth, arrow, indent_level=1, seen=None):
    """Append a bounded caller/callee tree rooted at a method."""
    if seen is None:
        seen = {_method_key(root)}
    if depth <= 0:
        return

    next_keys = [key for key in edges.get(_method_key(root), []) if key not in seen]
    next_methods = sorted(
        (methods_by_key[key] for key in next_keys),
        key=lambda m: (display(m), _method_location(m)),
    )

    if not next_methods and indent_level == 1:
        out.append("//   (none found)")
        return

    prefix = "  " * indent_level
    for method in next_methods:
        out.append(f"// {prefix}{arrow} {display(method)}  {_method_location(method)}")
        _append_call_tree(
            out, method, edges, methods_by_key, display, depth - 1, arrow,
            indent_level + 1, seen | {_method_key(method)},
        )


def _format_hierarchy(type_infos, target, depth, title, include_callees):
    """Shared renderer for --callers and --impact."""
    methods, methods_by_key, incoming, outgoing, display = _build_call_graph(type_infos)
    target_method, candidates, error = _resolve_target_method(methods, target)

    out = [f"// === {title}: {target} (depth {depth}) ==="]
    if error:
        out.append(f"// {error}")
        if candidates:
            out.append("// candidates:")
            for method in sorted(candidates, key=lambda m: (m["fq_class"], _method_location(m))):
                out.append(f"//   {method['fq_class']}.{method['identity']}  {_method_location(method)}")
            out.append("// use the fully-qualified class name to disambiguate")
        return "\n".join(out)

    out.append(f"// target: {display(target_method)}  {_method_location(target_method)}")
    out.append("//")
    out.append("// callers:")
    _append_call_tree(out, target_method, incoming, methods_by_key, display, depth, "←")
    if include_callees:
        out.append("//")
        out.append("// calls:")
        _append_call_tree(out, target_method, outgoing, methods_by_key, display, depth, "→")
    return "\n".join(out)


def format_callers_output(type_infos, target, depth=1):
    """Format a bounded upstream caller hierarchy for a Class.method target."""
    return _format_hierarchy(type_infos, target, depth, "Callers", include_callees=False)


def format_impact_output(type_infos, target, depth=1):
    """Format bounded upstream callers and downstream callees for a target."""
    return _format_hierarchy(type_infos, target, depth, "Impact", include_callees=True)


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def _type_row(info):
    """Render one project-map row for a type."""
    name = info["class_name"] or "(unknown)"
    ctype = info["class_type"] or "?"

    if ctype == "enum" and info["enum_constants"]:
        desc = f"{ctype} {name} {{ {format_enum_constants(info['enum_constants'], ENUM_CONSTANTS_MAP_MAX)} }}"
    else:
        desc = f"{ctype} {name}"
    if info["extends"]:
        desc += f" extends {info['extends']}"
    if info["implements"]:
        keyword = "extends" if ctype == "interface" else "implements"
        desc += f" {keyword} {', '.join(info['implements'])}"

    key_anns = [a for a in info["annotations"] if a in KEY_CLASS_ANNOTATIONS]
    ann_str = f" {' '.join(key_anns)}" if key_anns else ""

    extras = []
    if info["field_count"]:
        extras.append(f"{info['field_count']}F")
    if info["method_count"]:
        extras.append(f"{info['method_count']}M")
    extras.append(f"{info['total_lines']}L")
    if info["lombok"]:
        extras.append(f"lombok:{','.join(a.lstrip('@') for a in info['lombok'])}")
    if info["static_initializers"]:
        ranges = ", ".join(f"L{s['start']}-L{s['end']}" for s in info["static_initializers"])
        extras.append(f"static-init:{ranges}")
    if info["inner_types"]:
        extras.append(f"inner:{','.join(t.split()[-1] for t in info['inner_types'])}")

    return f"//   {desc}{ann_str} [{' | '.join(extras)}]"


def _is_collapsed(info):
    """Records (and other MAP_COLLAPSED_KINDS) without a key annotation are listed by name only."""
    return info["class_type"] in MAP_COLLAPSED_KINDS and not any(
        a in KEY_CLASS_ANNOTATIONS for a in info["annotations"]
    )


def _common_package_root(packages):
    """Longest shared dotted prefix of the given packages, or "" if under two segments."""
    split = [p.split(".") for p in packages if p]
    if not split:
        return ""
    root = split[0]
    for parts in split[1:]:
        n = 0
        while n < min(len(root), len(parts)) and root[n] == parts[n]:
            n += 1
        root = root[:n]
    return ".".join(root) if len(root) >= 2 else ""


def _relative_package(pkg, root):
    """Render a package name relative to the project root package."""
    if root and pkg.startswith(root + "."):
        return pkg[len(root) + 1:]
    return pkg


def _stereotype(info):
    """Return the Spring stereotype annotation of a type, or an empty string."""
    return next((a for a in info["annotations"] if a in SPRING_STEREOTYPES), "")


def _format_beans(out, type_infos):
    """Append the --beans sections: DI wiring, @Bean producers, config properties."""
    bean_entries = sorted(
        (info["class_name"], _stereotype(info), info["bean_deps"])
        for info in type_infos if info["bean_deps"]
    )
    if bean_entries:
        out.append("// === Bean Dependencies ===")
        for name, ann, deps in bean_entries:
            ann_str = f" {ann}" if ann else ""
            out.append(f"//   {name}{ann_str} ← {', '.join(deps)}")
        out.append("//")

    producer_entries = sorted(
        (info["class_name"], _stereotype(info), info["bean_produces"])
        for info in type_infos if info["bean_produces"]
    )
    if producer_entries:
        out.append("// === Bean Producers (@Bean) ===")
        for name, ann, produces in producer_entries:
            ann_str = f" {ann}" if ann else ""
            counts = {}
            for p in produces:
                counts[p] = counts.get(p, 0) + 1
            deduped = [f"{p}(x{c})" if c > 1 else p for p, c in counts.items()]
            out.append(f"//   {name}{ann_str} → {', '.join(deduped)}")
        out.append("//")

    config_entries = sorted(
        (info["config_prefix"], info["class_name"],
         [f"{f['type']} {f['name']}" for f in info["fields_detail"]])
        for info in type_infos if info["config_prefix"]
    )
    if config_entries:
        out.append("// === Configuration Properties ===")
        for prefix, name, fields in config_entries:
            suffix = f": {', '.join(fields)}" if fields else ""
            out.append(f"//   {prefix}.* ({name}){suffix}")
        out.append("//")


def format_output(file_infos, show_deps=False, show_endpoints=False, show_beans=False, all_file_infos=None):
    """Format the project map.

    ``all_file_infos`` is the unfiltered scan when ``file_infos`` was
    filtered, so endpoint constants still resolve project-wide.
    """
    type_infos = flatten_types(file_infos)
    packages = defaultdict(list)
    for f in file_infos:
        packages[f["package"] or "(default)"].append(f)
    root = _common_package_root(packages)

    header = f"// Project Map: {len(file_infos)} files, {sum(f['total_lines'] for f in file_infos)} lines"
    if root and len(packages) > 1:
        header += f" | packages under {root}"
    out = [header, "//"]

    for pkg in sorted(packages):
        files = packages[pkg]
        pkg_lines = sum(f["total_lines"] for f in files)
        pkg_anns = [a for f in files for a in f["package_annotations"]]
        line = f"// {_relative_package(pkg, root)} ({len(files)} files, {pkg_lines} lines)"
        if pkg_anns:
            line += f" {' '.join(pkg_anns)}"
        out.append(line)
        rows = sorted(flatten_types(files), key=lambda x: x["class_name"] or "")
        out.extend(_type_row(info) for info in rows if not _is_collapsed(info))
        for kind in MAP_COLLAPSED_KINDS:
            names = [info["class_name"] for info in rows if _is_collapsed(info) and info["class_type"] == kind]
            if names:
                out.extend(textwrap.wrap(
                    f"{kind}s: {', '.join(names)}", width=MAP_LINE_WIDTH,
                    initial_indent="//   ", subsequent_indent="//     ",
                ))
        out.append("//")

    if show_deps:
        deps = find_package_dependencies(type_infos)
        if deps:
            out.append("// === Package Dependencies ===")
            for src, targets in deps.items():
                out.append(f"//   {_relative_package(src, root)} →")
                for dst, names in targets.items():
                    out.append(f"//     {_relative_package(dst, root)}: {', '.join(names)}")
            out.append("//")

    if show_endpoints:
        collect_endpoints(type_infos, flatten_types(all_file_infos) if all_file_infos else None)
        all_endpoints = [ep for info in type_infos for ep in info["endpoints"]]
        if all_endpoints:
            all_endpoints.sort(key=lambda e: (e["path"], e["method"]))
            max_method = max(len(e["method"]) for e in all_endpoints)
            max_path = max(len(e["path"]) for e in all_endpoints)
            max_handler = max(len(e["handler"]) for e in all_endpoints)
            out.append("// === REST Endpoints ===")
            for e in all_endpoints:
                row = (
                    f"//   {e['method']:<{max_method}}  {e['path']:<{max_path}}  "
                    f"{e['handler']:<{max_handler}}  L{e['line']}"
                )
                if e["guards"]:
                    row += f"  {e['guards']}"
                out.append(row)
            out.append("//")

    if show_beans:
        _format_beans(out, type_infos)

    return "\n".join(out)


# ---------------------------------------------------------------------------
# Filtering and entry point
# ---------------------------------------------------------------------------

def _matches_type(info, ann_filter, ext_filter, impl_filter):
    if ann_filter:
        ann = ann_filter if ann_filter.startswith("@") else "@" + ann_filter
        if not any(a.startswith(ann) for a in info["annotations"]):
            return False
    if ext_filter and not (info["extends"] and ext_filter in info["extends"]):
        return False
    if impl_filter and not any(
        impl_filter in iface.split("<")[0] for iface in info.get("implements", [])
    ):
        return False
    return True


def filter_files(file_infos, pkg_filter=None, ann_filter=None, ext_filter=None, impl_filter=None):
    """Filter scanned files by package substring and their types by class-level filters.

    Files left with no matching type are dropped when a type-level filter
    is active; otherwise every file in the package (package-info included)
    is kept.
    """
    type_filter_active = bool(ann_filter or ext_filter or impl_filter)
    result = []
    for f in file_infos:
        if pkg_filter and pkg_filter not in (f["package"] or ""):
            continue
        types = [t for t in f["types"] if _matches_type(t, ann_filter, ext_filter, impl_filter)]
        if type_filter_active and not types:
            continue
        result.append({**f, "types": types})
    return result


def main(args):
    """Scan the directory in ``args.paths[0]`` and print the requested view."""
    src_dir = Path(args.paths[0])
    if not src_dir.is_dir():
        print(f"Error: {src_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    java_files = find_java_files(src_dir)
    if not java_files:
        print(f"No .java files found in {src_dir}", file=sys.stderr)
        sys.exit(1)

    all_file_infos = [scan_java_file(f) for f in java_files]
    file_infos = all_file_infos
    if args.package or args.annotation or args.extends or args.implements:
        file_infos = filter_files(all_file_infos, args.package, args.annotation, args.extends, args.implements)

    if args.callers and args.impact:
        print("Error: use only one of --callers or --impact", file=sys.stderr)
        sys.exit(1)

    depth = max(0, args.depth)
    type_infos = flatten_types(file_infos)
    if args.callers:
        print(format_callers_output(type_infos, args.callers, depth=depth))
        return
    if args.impact:
        print(format_impact_output(type_infos, args.impact, depth=depth))
        return

    print(format_output(file_infos, args.deps, args.endpoints, args.beans, all_file_infos))
