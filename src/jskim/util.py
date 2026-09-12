"""Shared tree-sitter utilities for the jskim toolkit.

This module owns the parser and every AST traversal. Feature modules
(skim, method, project, diff) consume the plain dicts produced by
``parse_java_source`` and only format them.
"""

import re
from pathlib import Path

import tree_sitter_java as tsjava
import tree_sitter

JAVA_LANGUAGE = tree_sitter.Language(tsjava.language())
_PARSER = tree_sitter.Parser(JAVA_LANGUAGE)


# ---------------------------------------------------------------------------
# Node type constants
# ---------------------------------------------------------------------------

INNER_TYPE_NODES = {
    "class_declaration", "interface_declaration",
    "enum_declaration", "record_declaration",
    "annotation_type_declaration",
}

PROGRAM_STRUCTURE_NODES = {"package_declaration", "import_declaration"}

METHOD_NODES = {
    "method_declaration", "constructor_declaration",
    "compact_constructor_declaration", "annotation_type_element_declaration",
}

CONSTRUCTOR_NODES = {"constructor_declaration", "compact_constructor_declaration"}

IMPLICIT_CLASS_MEMBER_NODES = METHOD_NODES | {"field_declaration", "static_initializer"}

PARAMETER_NODES = {"formal_parameter", "spread_parameter", "receiver_parameter"}

ANNOTATION_NODES = {"marker_annotation", "annotation"}

BODY_NODES = {"block", "constructor_body"}

TYPE_BODY_NODES = {"class_body", "interface_body", "enum_body", "annotation_type_body"}

MODIFIER_KEYWORDS = {
    "public", "private", "protected", "static", "final",
    "abstract", "synchronized", "native", "default",
    "strictfp", "volatile", "transient", "sealed", "non-sealed",
}

TYPE_KEYWORDS = {
    "class_declaration": "class",
    "interface_declaration": "interface",
    "enum_declaration": "enum",
    "record_declaration": "record",
    "annotation_type_declaration": "@interface",
}

BOILERPLATE_METHOD_NAMES = {"toString", "hashCode", "equals", "compareTo", "clone"}

# Calls allowed on the right-hand side of a wiring constructor assignment
# (``this.x = Objects.requireNonNull(x)``, ``this.items = List.copyOf(items)``).
WIRING_CALL_METHODS = {"requireNonNull", "requireNonNullElse", "copyOf"}

# Directory names skipped when scanning a source tree (build output, VCS).
SKIP_DIRS = {"target", "build", "out", ".git", ".gradle", ".idea", "node_modules"}


# ---------------------------------------------------------------------------
# Annotation constants
# ---------------------------------------------------------------------------

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

LOMBOK_SET = set(LOMBOK_ANNOTATIONS)

LOMBOK_CONSTRUCTOR_ANNOTATIONS = {"@RequiredArgsConstructor", "@AllArgsConstructor"}

SPRING_STEREOTYPES = {
    "@Service", "@Component", "@Repository",
    "@Controller", "@RestController", "@Configuration",
}

CONTROLLER_ANNOTATIONS = {"@RestController", "@Controller"}

INJECTION_ANNOTATIONS = {"@Autowired", "@Inject"}

# Class-level annotations worth surfacing in the project map row.
KEY_CLASS_ANNOTATIONS = SPRING_STEREOTYPES | {"@Entity", "@Data", "@Value", "@Builder"}

HTTP_MAPPING_ANNOTATIONS = {
    "@GetMapping": "GET",
    "@PostMapping": "POST",
    "@PutMapping": "PUT",
    "@DeleteMapping": "DELETE",
    "@PatchMapping": "PATCH",
    "@RequestMapping": None,  # determined from method= param
}

HTTP_METHODS = ("GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS")

# Documentation-only annotations. They never change behaviour, so they are
# dropped from every summary (OpenAPI/Swagger, compiler hints).
NOISE_ANNOTATIONS = {
    "@Operation", "@ApiResponse", "@ApiResponses", "@Parameter", "@Parameters",
    "@Schema", "@ArraySchema", "@Tag", "@Tags", "@Hidden", "@Content",
    "@ExampleObject", "@SecurityRequirement", "@SecurityRequirements",
    "@SuppressWarnings", "@Generated", "@SafeVarargs",
}

# Annotation arguments longer than this are truncated in summaries.
ANNOTATION_ARGS_MAX = 80


# ---------------------------------------------------------------------------
# Method call noise constants
# ---------------------------------------------------------------------------

# Object names whose calls are always noise: loggers, java.lang classes (never
# imported, so the import-based scope cannot classify them) and the JDK
# classes most often reached through wildcard imports (``java.util.*``).
NOISE_CALL_OBJECTS = {
    "log", "logger", "LOG", "LOGGER",
    "Objects", "StringUtils", "CollectionUtils", "MapUtils", "ArrayUtils",
    "Optional", "Collections", "Arrays", "Math", "System", "Thread",
    "String", "Integer", "Long", "Double", "Float", "Boolean", "Byte", "Short",
    "Character", "BigDecimal", "BigInteger", "StringBuilder", "Class", "Enum",
    "Runtime", "Record", "Void", "Number", "ScopedValue", "StackWalker",
    "Comparator", "Collectors", "Stream", "IntStream", "List", "Map", "Set",
    "UUID", "EnumSet", "Instant", "Duration", "LocalDate", "LocalDateTime",
    "LocalTime", "OffsetDateTime", "ZonedDateTime", "ZoneId", "ChronoUnit",
    "Files", "Paths", "Path", "Pattern", "Base64", "URI", "URL",
    "Executors", "CompletableFuture", "TimeUnit",
}

# Method names that are noise when called on any object (collection ops,
# identity methods, type conversions). Unqualified calls (same-class methods)
# are never filtered by this set.
NOISE_CALL_METHODS = {
    "put", "putAll", "get", "getOrDefault", "add", "addAll", "remove",
    "removeAll", "contains", "containsKey", "containsAll", "size", "isEmpty",
    "clear", "entrySet", "keySet", "values", "stream", "iterator",
    "toString", "valueOf", "hashCode", "equals", "compareTo",
    "parseInt", "parseLong", "parseDouble", "parseFloat",
    "of", "ofNullable", "orElse", "orElseGet", "orElseThrow",
    "isPresent", "ifPresent",
    "format", "trim", "strip", "toLowerCase", "toUpperCase",
    "substring", "startsWith", "endsWith", "charAt", "length",
    "append", "insert", "delete", "replace",
    "collect", "map", "filter", "flatMap", "forEach", "reduce",
    "findFirst", "findAny", "anyMatch", "allMatch", "noneMatch",
    "toList", "toSet", "toMap", "sorted", "distinct", "count",
    "min", "max", "sum", "average",
}


# ---------------------------------------------------------------------------
# Parsing primitives
# ---------------------------------------------------------------------------

def parse_java_bytes(source_bytes):
    """Parse Java source bytes and return the root node."""
    tree = _PARSER.parse(source_bytes)
    return tree.root_node


def _normalize_ws(text):
    """Collapse all whitespace runs into single spaces."""
    return " ".join(text.split())


def _strip_quotes(s):
    """Strip surrounding double quotes."""
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return s[1:-1]
    return s


def _get_modifier_keywords(modifiers_node):
    """Extract keyword modifiers (public, static, etc.) from a modifiers node."""
    result = []
    for child in modifiers_node.children:
        if child.type in MODIFIER_KEYWORDS:
            result.append(child.type)
    return result


def get_modifiers_node(decl_node):
    """Get the modifiers child node from a declaration, or None."""
    for child in decl_node.children:
        if child.type == "modifiers":
            return child
    return None


def get_annotation_name_from_node(ann_node):
    """Extract @AnnotationName from a marker_annotation or annotation node."""
    name_node = ann_node.child_by_field_name("name")
    if name_node:
        return "@" + name_node.text.decode()
    for c in ann_node.children:
        if c.type in ("identifier", "scoped_identifier"):
            return "@" + c.text.decode()
    return None


def _iter_annotation_nodes(parent):
    """Yield annotation nodes that are direct children of ``parent``."""
    if parent is None:
        return
    for child in parent.children:
        if child.type in ANNOTATION_NODES:
            yield child


def get_annotations(modifiers_node):
    """Extract every @AnnotationName from a modifiers node (unfiltered)."""
    if modifiers_node is None or modifiers_node.type != "modifiers":
        return []
    anns = []
    for child in _iter_annotation_nodes(modifiers_node):
        name = get_annotation_name_from_node(child)
        if name:
            anns.append(name)
    return anns


def _annotation_argument_list(ann_node):
    """Return the annotation_argument_list child of an annotation, or None."""
    for child in ann_node.children:
        if child.type == "annotation_argument_list":
            return child
    return None


def _resolved_annotation_values(args, constants):
    """Resolve a positional annotation argument list to string values, or None.

    Handles ``@Ann(CONST)``, ``@Ann(Other.CONST)`` and ``@Ann({A, B})`` when
    every element is a compile-time string; anything else returns None so
    the caller falls back to the source text.
    """
    if not constants:
        return None
    values = []
    for child in args.named_children:
        if child.type == "element_value_pair":
            return None
        elements = child.named_children if child.type == "element_value_array_initializer" else [child]
        for element in elements:
            if element.type == "string_literal":
                return None  # already readable as source text
            value = resolve_string_expression(element, constants)
            if value is None:
                return None
            values.append(value)
    return values or None


def format_annotation(ann_node, constants=None):
    """Render one annotation for a summary, or None if it is noise.

    Returns a dict ``{"name", "params", "full", "node"}``. HTTP mapping
    annotations show only their (resolved) path and, for @RequestMapping,
    the HTTP method. Every other annotation shows its arguments: constant
    references that resolve through ``constants`` render as their string
    value (``@RequiresPermission("trip.create")``); otherwise the source
    text is whitespace-normalized and truncated to ANNOTATION_ARGS_MAX.
    """
    name = get_annotation_name_from_node(ann_node)
    if not name or name in NOISE_ANNOTATIONS:
        return None

    params = None
    if name in HTTP_MAPPING_ANNOTATIONS:
        parts = []
        if name == "@RequestMapping":
            http_method = extract_request_method(ann_node)
            if http_method:
                parts.append(http_method)
        paths = extract_mapping_paths(ann_node, constants)
        if paths:
            parts.append(", ".join(f'"{p}"' for p in paths))
        if parts:
            params = f"({' '.join(parts)})"
    else:
        args = _annotation_argument_list(ann_node)
        if args is not None:
            resolved = _resolved_annotation_values(args, constants)
            if resolved is not None:
                text = "(" + ", ".join(f'"{v}"' for v in resolved) + ")"
            else:
                text = _normalize_ws(args.text.decode()).replace("( ", "(").replace(" )", ")")
            if len(text) > ANNOTATION_ARGS_MAX:
                text = text[: ANNOTATION_ARGS_MAX - 4] + "...)"
            params = text

    return {
        "name": name,
        "params": params,
        "full": f"{name}{params}" if params else name,
        "node": ann_node,
    }


def get_annotations_rich(parent_node, constants=None):
    """Extract summary-worthy annotations from a modifiers (or package) node.

    Drops NOISE_ANNOTATIONS, de-duplicates repeated annotations, and renders
    arguments via ``_format_annotation``. Returns a list of dicts
    ``{"name", "params", "full", "node"}``.
    """
    result = []
    seen = set()
    for child in _iter_annotation_nodes(parent_node):
        rendered = format_annotation(child, constants)
        if rendered is None or rendered["full"] in seen:
            continue
        seen.add(rendered["full"])
        result.append(rendered)
    return result


# ---------------------------------------------------------------------------
# String constant resolution (for @RequestMapping(BASE_PATH) etc.)
# ---------------------------------------------------------------------------

def resolve_string_expression(node, constants=None):
    """Resolve a compile-time String expression to its value, or None.

    Handles string literals, identifiers and ``Class.FIELD`` references
    looked up in ``constants`` (a ``{name: value}`` dict that may also hold
    ``"Class.FIELD"`` keys), ``+`` concatenation and parentheses.
    """
    if node is None:
        return None
    constants = constants or {}
    if node.type == "string_literal":
        return _strip_quotes(node.text.decode())
    if node.type == "identifier":
        return constants.get(node.text.decode())
    if node.type == "field_access":
        obj = node.child_by_field_name("object")
        field = node.child_by_field_name("field")
        if obj is None or field is None:
            return None
        qualified = f"{obj.text.decode()}.{field.text.decode()}"
        if qualified in constants:
            return constants[qualified]
        return constants.get(field.text.decode())
    if node.type == "parenthesized_expression":
        for child in node.named_children:
            return resolve_string_expression(child, constants)
        return None
    if node.type == "binary_expression":
        op = node.child_by_field_name("operator")
        if op is None or op.type != "+":
            return None
        left = resolve_string_expression(node.child_by_field_name("left"), constants)
        right = resolve_string_expression(node.child_by_field_name("right"), constants)
        if left is None or right is None:
            return None
        return left + right
    return None


def extract_string_constants(members):
    """Collect ``static final String`` constants from a member list.

    Returns ``{name: value}`` for every constant whose initializer resolves
    to a compile-time string (literals, other constants, concatenation).
    """
    candidates = []
    for member in members:
        if member.type != "field_declaration" or not is_field_static(member):
            continue
        type_node = member.child_by_field_name("type")
        if type_node is None or type_node.text.decode() != "String":
            continue
        for child in member.named_children:
            if child.type == "variable_declarator":
                name = child.child_by_field_name("name")
                value = child.child_by_field_name("value")
                if name is not None and value is not None:
                    candidates.append((name.text.decode(), value))

    constants = {}
    # Constants may reference constants declared later; iterate to a fixpoint.
    for _ in range(len(candidates) + 1):
        progressed = False
        for name, value_node in candidates:
            if name in constants:
                continue
            value = resolve_string_expression(value_node, constants)
            if value is not None:
                constants[name] = value
                progressed = True
        if not progressed:
            break
    return constants


# ---------------------------------------------------------------------------
# Spring annotation argument extraction
# ---------------------------------------------------------------------------

def _get_evp_key(evp_node):
    """Get the key identifier from an element_value_pair node."""
    for c in evp_node.children:
        if c.type == "identifier":
            return c.text.decode()
    return None


def _resolve_or_raw(node, constants):
    """Resolve a string expression, falling back to its normalized source text."""
    value = resolve_string_expression(node, constants)
    if value is not None:
        return value
    return _normalize_ws(node.text.decode())


def _path_values(node, constants):
    """Expand one annotation argument value into a list of path strings."""
    if node.type == "element_value_array_initializer":
        return [_resolve_or_raw(c, constants) for c in node.named_children]
    return [_resolve_or_raw(node, constants)]


def extract_mapping_paths(ann_node, constants=None):
    """Extract URL path(s) from a Spring @*Mapping annotation.

    Handles literals, constants (``BASE_PATH``, ``Api.BASE``), concatenation,
    ``value=``/``path=`` pairs and array initializers. Unresolvable
    expressions are returned as their source text so they stay visible.
    Returns a list of path strings; empty if no path is specified.
    """
    args = _annotation_argument_list(ann_node)
    if args is None:
        return []
    paths = []
    for child in args.named_children:
        if child.type == "element_value_pair":
            key = _get_evp_key(child)
            value = child.child_by_field_name("value")
            if key in ("value", "path") and value is not None:
                paths.extend(_path_values(value, constants))
        else:
            paths.extend(_path_values(child, constants))
    return paths


def extract_request_method(ann_node):
    """Extract HTTP method from @RequestMapping's method= parameter.

    Returns "GET", "POST", etc. or None.
    """
    args = _annotation_argument_list(ann_node)
    if args is None:
        return None
    for arg in args.named_children:
        if arg.type == "element_value_pair" and _get_evp_key(arg) == "method":
            text = arg.text.decode()
            for m in HTTP_METHODS:
                if m in text:
                    return m
    return None


def _find_string_literals(node):
    """Recursively collect all string literal values from a node subtree."""
    results = []
    if node.type == "string_literal":
        results.append(_strip_quotes(node.text.decode()))
    for c in node.named_children:
        results.extend(_find_string_literals(c))
    return results


def extract_first_annotation_string(ann_node):
    """Extract the first string literal value from an annotation's arguments.

    Useful for @ConfigurationProperties("prefix"), @Qualifier("name"), etc.
    """
    args = _annotation_argument_list(ann_node)
    if args is None:
        return None
    strings = _find_string_literals(args)
    return strings[0] if strings else None


# ---------------------------------------------------------------------------
# Type declaration helpers
# ---------------------------------------------------------------------------

def find_first_type_declaration(root):
    """Find the first class/interface/enum/record/@interface declaration in the AST."""
    for child in root.children:
        if child.type in INNER_TYPE_NODES:
            return child
    return None


def get_class_body(decl_node):
    """Get the body node from a type declaration (class_body, interface_body, enum_body, etc.)."""
    for child in decl_node.children:
        if child.type in TYPE_BODY_NODES:
            return child
    return None


def get_body_members(body_node):
    """Get all member declarations from a class/enum body.

    For enums, members are inside enum_body_declarations (after the constants).
    """
    if body_node is None:
        return []
    members = []
    for child in body_node.named_children:
        if child.type == "enum_body_declarations":
            members.extend(sub for sub in child.named_children if sub.is_named)
        elif child.type != "enum_constant":
            members.append(child)
    return members


def get_type_keyword(decl_node):
    """Get the type keyword (class/interface/enum/record/@interface) from a declaration node."""
    return TYPE_KEYWORDS[decl_node.type]


def get_declaration_name(decl_node):
    """Get the identifier name from a declaration node."""
    name_node = decl_node.child_by_field_name("name")
    if name_node:
        return name_node.text.decode()
    for child in decl_node.children:
        if child.type == "identifier":
            return child.text.decode()
    return None


def build_implicit_class_declaration(source_name=None):
    """Build a display label for a Java simple source file's implicit class."""
    if source_name:
        stem = Path(str(source_name)).stem
        if stem:
            return f"implicit class {stem}"
    return "implicit class"


def get_superclass(decl_node):
    """Extract the extends clause text (just the type, not the 'extends' keyword)."""
    for child in decl_node.children:
        if child.type == "superclass":
            for sub in child.children:
                if sub.type != "extends":
                    return sub.text.decode()
    return None


def _type_list(decl_node, wrapper_types):
    """Extract the names from a type_list nested in one of ``wrapper_types``."""
    for child in decl_node.children:
        if child.type in wrapper_types:
            for sub in child.children:
                if sub.type == "type_list":
                    return [t.text.decode() for t in sub.named_children]
    return []


def get_interfaces(decl_node):
    """Extract related interface names as a list of strings.

    For classes/records, this returns implemented interfaces.
    For interfaces, this returns extended interfaces.
    """
    return _type_list(decl_node, ("super_interfaces", "extends_interfaces"))


def get_permits(decl_node):
    """Extract permitted subclass names as a list of strings."""
    return _type_list(decl_node, ("permits",))


def _get_type_parameters(decl_node):
    """Extract the type_parameters text (e.g. '<T extends Comparable<T>>') from a declaration."""
    for child in decl_node.children:
        if child.type == "type_parameters":
            return child.text.decode()
    return None


def build_class_declaration_text(decl_node):
    """Reconstruct a clean class declaration line (without the body)."""
    parts = []
    mods = get_modifiers_node(decl_node)
    if mods:
        kws = _get_modifier_keywords(mods)
        if kws:
            parts.append(" ".join(kws))

    parts.append(get_type_keyword(decl_node))

    name = get_declaration_name(decl_node)
    type_params = _get_type_parameters(decl_node)
    parts.append(f"{name}{type_params}" if type_params else name)

    superclass = get_superclass(decl_node)
    if superclass:
        parts.append("extends")
        parts.append(_normalize_ws(superclass))

    ifaces = get_interfaces(decl_node)
    if ifaces:
        parts.append("extends" if decl_node.type == "interface_declaration" else "implements")
        parts.append(", ".join(_normalize_ws(i) for i in ifaces))

    permits = get_permits(decl_node)
    if permits:
        parts.append("permits")
        parts.append(", ".join(_normalize_ws(p) for p in permits))

    return " ".join(parts)


def get_enum_constants(body_node):
    """Extract enum constant names from an enum body node."""
    if body_node is None:
        return []
    constants = []
    for child in body_node.named_children:
        if child.type == "enum_constant":
            name_node = child.child_by_field_name("name")
            if name_node:
                constants.append(name_node.text.decode())
            else:
                for c in child.children:
                    if c.type == "identifier":
                        constants.append(c.text.decode())
                        break
    return constants


# ---------------------------------------------------------------------------
# Field helpers
# ---------------------------------------------------------------------------

def extract_field_info(field_node):
    """Extract type and names from a field_declaration node.

    Returns a list of (type_str, name_str) tuples, one per declared variable.
    E.g., 'int x, y, z;' -> [('int', 'x'), ('int', 'y'), ('int', 'z')]
    Returns an empty list if unparseable.
    """
    type_text = None
    names = []
    for child in field_node.named_children:
        if child.type == "modifiers":
            continue
        if child.type == "variable_declarator":
            for sub in child.children:
                if sub.type == "identifier":
                    names.append(sub.text.decode())
                    break
        elif type_text is None:
            type_text = _normalize_ws(child.text.decode())
    return [(type_text, name) for name in names]


def _has_modifier(node, keyword):
    """Check whether a declaration carries the given modifier keyword."""
    mods = get_modifiers_node(node)
    return mods is not None and keyword in _get_modifier_keywords(mods)


def is_field_final(field_node):
    """Check if a field_declaration has the 'final' modifier."""
    return _has_modifier(field_node, "final")


def is_field_static(field_node):
    """Check if a field_declaration has the 'static' modifier."""
    return _has_modifier(field_node, "static")


def parse_field(field_node):
    """Parse a field_declaration into one dict per declared variable.

    Each dict: ``{"type", "name", "annotations", "static", "final", "private", "line"}``
    where ``annotations`` is a list of ``@Name`` strings.
    """
    anns = get_annotations(get_modifiers_node(field_node))
    static = is_field_static(field_node)
    final = is_field_final(field_node)
    private = _has_modifier(field_node, "private")
    line = field_node.start_point[0] + 1
    return [
        {
            "type": ftype,
            "name": fname,
            "annotations": anns,
            "static": static,
            "final": final,
            "private": private,
            "line": line,
        }
        for ftype, fname in extract_field_info(field_node)
    ]


def extract_record_components(decl_node):
    """Extract the components of a record declaration.

    Returns one ``{"type", "name", "annotations"}`` dict per component (the
    ``parse_parameters`` shape), e.g. ``record Point(int x, @NotNull int y)``
    -> ``[{"type": "int", "name": "x", "annotations": []}, {..., "annotations": ["@NotNull"]}]``.
    Returns an empty list for non-record declarations.
    """
    if decl_node.type != "record_declaration":
        return []
    for child in decl_node.children:
        if child.type == "formal_parameters":
            return [p for p in parse_parameters(child) if p["type"] and p["name"]]
    return []


# ---------------------------------------------------------------------------
# Method helpers
# ---------------------------------------------------------------------------

def get_method_name(node):
    """Extract the simple method/constructor name from a method-like node."""
    name_node = node.child_by_field_name("name")
    if not name_node:
        for child in node.children:
            if child.type == "identifier":
                name_node = child
                break
    return name_node.text.decode() if name_node else "unknown"


def _get_formal_parameters(node):
    """Return the formal_parameters node of a method-like node, or None."""
    params = node.child_by_field_name("parameters")
    if params is not None:
        return params
    for child in node.children:
        if child.type == "formal_parameters":
            return child
    return None


def parse_parameters(params_node):
    """Parse a formal_parameters node into a list of parameter dicts.

    Each dict: ``{"type", "name", "annotations"}``. ``type`` carries ``...``
    for varargs; ``annotations`` lists non-noise ``@Name`` markers only
    (arguments are dropped, they are documentation in practice).
    """
    result = []
    if params_node is None:
        return result
    for param in params_node.named_children:
        if param.type not in PARAMETER_NODES:
            continue
        type_node = param.child_by_field_name("type")
        name_node = param.child_by_field_name("name")
        for child in param.named_children:
            if child.type in ("modifiers", "dimensions"):
                continue
            if child.type == "identifier":
                name_node = name_node or child
            elif child.type == "variable_declarator":
                name_node = name_node or child.child_by_field_name("name") or child
            elif type_node is None:
                type_node = child  # spread_parameter has no "type" field
        type_text = _normalize_ws(type_node.text.decode()) if type_node is not None else None
        if type_text is None and name_node is None:
            type_text = _normalize_ws(param.text.decode())
        if param.type == "spread_parameter" and type_text is not None:
            type_text += "..."
        anns = []
        for ann in get_annotations(get_modifiers_node(param)):
            if ann not in NOISE_ANNOTATIONS and ann not in anns:
                anns.append(ann)
        result.append({
            "type": type_text,
            "name": name_node.text.decode() if name_node is not None else None,
            "annotations": anns,
        })
    return result


def _format_parameter(param):
    """Render one parsed parameter as ``@Ann Type name``."""
    parts = list(param["annotations"])
    if param["type"]:
        parts.append(param["type"])
    if param["name"]:
        parts.append(param["name"])
    return " ".join(parts)


def _get_return_type(node):
    """Return the normalized return type text of a method, or None for constructors."""
    type_node = node.child_by_field_name("type")
    if type_node is None:
        return None
    return _normalize_ws(type_node.text.decode())


def build_method_signature(node):
    """Build a clean one-line method signature from a method/constructor node.

    Method-level annotations are omitted (they are listed separately).
    Parameter annotations keep their marker but lose their arguments.
    """
    parts = []
    for child in node.children:
        if child.type in BODY_NODES or child.type == ";":
            break
        if child.type == "modifiers":
            mods = _get_modifier_keywords(child)
            if mods:
                parts.append(" ".join(mods))
            continue
        if child.type == "formal_parameters":
            params = ", ".join(_format_parameter(p) for p in parse_parameters(child))
            parts.append(f"({params})")
            continue
        parts.append(_normalize_ws(child.text.decode()))
    sig = " ".join(parts)
    return sig.replace(" (", "(").replace("( ", "(")


def build_method_identity(node):
    """Build a stable method identity using just the name and parameter types."""
    name = get_method_name(node)
    params = parse_parameters(_get_formal_parameters(node))
    return f"{name}({', '.join(p['type'] or '?' for p in params)})"


def _method_kind(node):
    """Classify the declaration node: method, constructor or annotation_element."""
    if node.type in CONSTRUCTOR_NODES:
        return "constructor"
    if node.type == "annotation_type_element_declaration":
        return "annotation_element"
    return "method"


def signature_line(node):
    """Line of a declaration's signature (return type or name), not its annotations."""
    for field in ("type", "name"):
        child = node.child_by_field_name(field)
        if child is not None:
            return child.start_point[0] + 1
    return node.start_point[0] + 1


def _noise_annotation_spans(modifiers_node):
    """Source spans of NOISE_ANNOTATIONS on a declaration, for extraction to skip.

    Each span is ``{"start", "end", "start_col", "end_col"}`` with 1-based
    lines and 0-based columns.
    """
    spans = []
    for ann in _iter_annotation_nodes(modifiers_node):
        if get_annotation_name_from_node(ann) in NOISE_ANNOTATIONS:
            spans.append({
                "start": ann.start_point[0] + 1, "start_col": ann.start_point[1],
                "end": ann.end_point[0] + 1, "end_col": ann.end_point[1],
            })
    return spans


def _is_wiring_constructor(node):
    """True when a constructor body only stores its parameters into fields.

    Allowed statements: ``this.x = x``, ``x = x``, ``this.x = Objects.requireNonNull(x)``
    (see WIRING_CALL_METHODS), ``super(...)``/``this(...)`` and comments. An
    empty body also counts (utility-class private constructors).
    """
    if node.type not in CONSTRUCTOR_NODES:
        return False
    body = node.child_by_field_name("body")
    if body is None:
        return False
    for stmt in body.named_children:
        if stmt.type in ("explicit_constructor_invocation", "line_comment", "block_comment"):
            continue
        if stmt.type != "expression_statement" or not stmt.named_children:
            return False
        expr = stmt.named_children[0]
        if expr.type != "assignment_expression":
            return False
        left = expr.child_by_field_name("left")
        right = expr.child_by_field_name("right")
        if left is None or right is None:
            return False
        if left.type == "field_access":
            obj = left.child_by_field_name("object")
            if obj is None or obj.type != "this":
                return False
        elif left.type != "identifier":
            return False
        if right.type == "method_invocation":
            name = right.child_by_field_name("name")
            if name is None or name.text.decode() not in WIRING_CALL_METHODS:
                return False
        elif right.type != "identifier":
            return False
    return True


def parse_method(node, call_scope=None, constants=None):
    """Parse a method-like node into a plain dict.

    Keys: ``name``, ``kind`` (method/constructor/annotation_element),
    ``identity``, ``sig``, ``start`` (signature line), ``decl_start`` (first
    annotation line), ``end``, ``annotations`` (rich dicts), ``noise_spans``
    (documentation annotations to skip when printing source), ``wiring``
    (constructor that only assigns fields), ``return_type``, ``params``
    (parsed parameter dicts), ``calls``.
    """
    mods = get_modifiers_node(node)
    return {
        "name": get_method_name(node),
        "kind": _method_kind(node),
        "identity": build_method_identity(node),
        "sig": build_method_signature(node),
        "start": signature_line(node),
        "decl_start": node.start_point[0] + 1,
        "end": node.end_point[0] + 1,
        "annotations": get_annotations_rich(mods, constants),
        "noise_spans": _noise_annotation_spans(mods),
        "wiring": _is_wiring_constructor(node),
        "return_type": _get_return_type(node),
        "params": parse_parameters(_get_formal_parameters(node)),
        "calls": extract_method_calls(node, call_scope),
    }


def classify_method(method):
    """Classify a parsed method dict.

    Returns ``wiring`` (constructor that only stores its parameters),
    ``constructor``, ``getter``, ``setter``, ``boilerplate`` or ``business``.
    """
    if method["kind"] == "constructor":
        return "wiring" if method.get("wiring") else "constructor"
    name = method["name"]
    if name in BOILERPLATE_METHOD_NAMES:
        return "boilerplate"

    return_type = method.get("return_type") or ""
    params = method.get("params") or []

    if not params:
        if name.startswith("get") and len(name) > 3 and name[3].isupper() and return_type != "void":
            return "getter"
        if (
            name.startswith("is") and len(name) > 2 and name[2].isupper()
            and return_type in ("boolean", "Boolean")
        ):
            return "getter"

    if (
        name.startswith("set") and len(name) > 3 and name[3].isupper()
        and return_type == "void" and len(params) == 1
    ):
        return "setter"

    return "business"


# ---------------------------------------------------------------------------
# Method call extraction
# ---------------------------------------------------------------------------

def _is_noise_call(call_str):
    """Return True if a call string is boilerplate noise (not business logic)."""
    if "." not in call_str:
        # Unqualified call (same-class method) — always keep
        return False
    obj, method = call_str.rsplit(".", 1)
    return obj in NOISE_CALL_OBJECTS or method in NOISE_CALL_METHODS


_CONSTANT_NAME_RE = re.compile(r"[A-Z0-9_]+")


def build_call_scope(package, imports, static_members, field_names=()):
    """Build the scope that decides which method calls are followable.

    ``foreign`` holds simple names imported from outside the project root
    (the first two segments of ``package``): JDK, Spring, libraries.
    ``static_members`` holds names brought in by ``import static``; calls on
    them (``TRIP.fields()``) or to them (``assertThat(...)``) lead outside
    the class. ``fields`` are the class's own instance field names; static
    fields are not followable because the summary lists them by name only.
    """
    root = ".".join(package.split(".")[:2]) if package else None
    foreign = set()
    for path in imports:
        if path.endswith(".*"):
            continue
        simple = path.rsplit(".", 1)[-1]
        if simple in static_members:
            continue
        if root is None or not path.startswith(root + "."):
            foreign.add(simple)
    return {
        "foreign": foreign,
        "static_members": set(static_members),
        "fields": set(field_names),
    }


def _is_traceable_call(call, scope):
    """Return True if a call can be followed from a summary within ``scope``."""
    if scope is None:
        return True
    if "." not in call:
        return call not in scope["static_members"]
    owner = call.rsplit(".", 1)[0]
    if owner == "super" or owner in scope["fields"]:
        return True
    if owner in scope["static_members"] or owner in scope["foreign"]:
        return False
    # CamelCase owners are classes (static calls); ALL_CAPS owners are constants.
    return owner[:1].isupper() and not _CONSTANT_NAME_RE.fullmatch(owner)


def extract_method_calls(method_node, call_scope=None):
    """Extract method calls from a method/constructor body.

    Returns a deduplicated sorted list of call strings like:
      ["orderRepo.save", "paymentService.charge", "validate"]

    Keeps unqualified calls (same class), calls on ``super``, calls on a
    simple object identifier and ``this.field.method()`` (as
    ``field.method``). Chained/fluent calls are skipped. With a
    ``call_scope`` (see ``build_call_scope``), qualified calls are kept only
    when the owner is a field or a project class (same package or imported
    from the project root); calls on locals, parameters, static-imported
    members and JDK/library classes are dropped because they cannot be
    followed from the summary.

    Boilerplate noise is filtered via NOISE_CALL_OBJECTS / NOISE_CALL_METHODS.
    """
    body = method_node.child_by_field_name("body")
    if body is None:
        return []
    calls = set()
    _collect_method_calls(body, calls)
    return [
        call for call in sorted(calls)
        if not _is_noise_call(call) and _is_traceable_call(call, call_scope)
    ]


def _collect_method_calls(node, calls):
    """Recursively collect method invocation strings from an AST subtree."""
    if node.type == "method_invocation":
        obj = node.child_by_field_name("object")
        name = node.child_by_field_name("name")
        if name:
            method_name = name.text.decode()
            if obj is None or obj.type == "this":
                calls.add(method_name)
            elif obj.type == "identifier":
                calls.add(f"{obj.text.decode()}.{method_name}")
            elif obj.type == "super":
                calls.add(f"super.{method_name}")
            elif obj.type == "field_access":
                # Handle this.field.method() → field.method
                inner_obj = obj.child_by_field_name("object")
                field = obj.child_by_field_name("field")
                if inner_obj and inner_obj.type == "this" and field:
                    calls.add(f"{field.text.decode()}.{method_name}")
            # else: chained call (object is method_invocation etc.), skip

    for child in node.children:
        _collect_method_calls(child, calls)


# ---------------------------------------------------------------------------
# Structured parsing: file -> types -> members
# ---------------------------------------------------------------------------

def _parse_import(import_node):
    """Return ``(path, is_static)`` for an import_declaration node.

    The path has the ``static`` keyword stripped and wildcards expanded:
    ``import static java.util.Collections.emptyList;`` -> ``("java.util.Collections.emptyList", True)``,
    ``import java.util.*;`` -> ``("java.util.*", False)``.
    """
    has_asterisk = False
    is_static = False
    path = None
    for child in import_node.children:
        if child.type in ("scoped_identifier", "identifier"):
            path = child.text.decode()
        elif child.type == "asterisk":
            has_asterisk = True
        elif child.type == "static":
            is_static = True
    if path and has_asterisk:
        path += ".*"
    return path, is_static


def extract_import_path(import_node):
    """Extract the import path string from an import_declaration node."""
    return _parse_import(import_node)[0]


def parse_file_structure(source_bytes):
    """Parse a Java file and extract the common top-level structure.

    Returns a dict with:
      - "package": package name string or None
      - "package_annotations": rich annotation dicts on the package declaration
      - "imports": list of import path strings (static imports included)
      - "static_members": simple names brought in by non-wildcard static imports
      - "type_nodes": list of top-level type declaration AST nodes
      - "program_members": implicit-class members when the file has loose
        top-level declarations (methods, fields, nested types, etc.)
    """
    root = parse_java_bytes(source_bytes)
    package = None
    package_annotations = []
    imports = []
    static_members = set()
    type_nodes = []
    program_members = []
    non_structure_nodes = []

    for child in root.named_children:
        if child.type == "package_declaration":
            package_annotations = get_annotations_rich(child)
            for sub in child.children:
                if sub.type in ("scoped_identifier", "identifier"):
                    package = sub.text.decode()
                    break
        elif child.type == "import_declaration":
            path, is_static = _parse_import(child)
            if path:
                imports.append(path)
                if is_static and not path.endswith(".*"):
                    static_members.add(path.rsplit(".", 1)[-1])
        elif child.type not in PROGRAM_STRUCTURE_NODES:
            non_structure_nodes.append(child)

    if any(child.type in IMPLICIT_CLASS_MEMBER_NODES for child in non_structure_nodes):
        program_members = [
            child for child in non_structure_nodes
            if child.type in IMPLICIT_CLASS_MEMBER_NODES or child.type in INNER_TYPE_NODES
        ]
    else:
        type_nodes = [child for child in non_structure_nodes if child.type in INNER_TYPE_NODES]

    return {
        "package": package,
        "package_annotations": package_annotations,
        "imports": imports,
        "static_members": static_members,
        "type_nodes": type_nodes,
        "program_members": program_members,
    }


_INLINE_TAG_RE = re.compile(r"\{@\w+\s*#?([^}]*)\}")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s")


def get_javadoc_summary(node):
    """First sentence of the Javadoc directly above a declaration, or None.

    Inline tags are unwrapped (``{@code x}`` -> ``x``), HTML tags dropped,
    block tags (``@param`` ...) ignored, and the result is capped at
    DOC_SUMMARY_MAX characters.
    """
    prev = node.prev_named_sibling
    if prev is None or prev.type != "block_comment":
        return None
    text = prev.text.decode()
    if not text.startswith("/**"):
        return None
    lines = []
    for raw in text[3:].removesuffix("*/").splitlines():
        line = raw.strip().lstrip("*").strip()
        if line.startswith("@"):
            break
        lines.append(line)
    text = _INLINE_TAG_RE.sub(r"\1", " ".join(lines))
    text = _normalize_ws(_HTML_TAG_RE.sub(" ", text))
    if not text:
        return None
    sentence = _SENTENCE_END_RE.split(text, 1)[0]
    if len(sentence) > DOC_SUMMARY_MAX:
        sentence = sentence[: DOC_SUMMARY_MAX - 3].rstrip() + "..."
    return sentence


def parse_type_members(members, call_scope=None, constants=None, component_names=()):
    """Parse fields, methods, nested types and static initializers from members.

    Returns ``{"fields", "methods", "inner_types", "static_initializers"}``.
    Methods see ``call_scope`` (the file scope from ``build_call_scope``)
    plus the type's own instance fields and ``component_names`` (record
    components); nested types get the bare file scope again, so an outer
    field never masks a nested type's parameter. Nested types are full
    ``parse_type`` dicts.
    """
    fields = []
    for member in members:
        if member.type == "field_declaration":
            fields.extend(parse_field(member))
    scope = dict(call_scope or build_call_scope(None, (), ()))
    scope["fields"] = scope["fields"] | set(component_names) | {f["name"] for f in fields if not f["static"]}

    methods = []
    inner_types = []
    static_initializers = []
    for member in members:
        if member.type in METHOD_NODES:
            methods.append(parse_method(member, scope, constants))
        elif member.type == "static_initializer":
            static_initializers.append({
                "start": member.start_point[0] + 1,
                "end": member.end_point[0] + 1,
            })
        elif member.type in INNER_TYPE_NODES:
            inner_types.append(parse_type(member, call_scope))

    return {
        "fields": fields,
        "methods": methods,
        "inner_types": inner_types,
        "static_initializers": static_initializers,
    }


def _empty_type(kind, name, declaration, line):
    """Build the skeleton dict shared by real and implicit types."""
    return {
        "kind": kind,
        "name": name,
        "declaration": declaration,
        "line": line,
        "doc": None,
        "annotations": [],
        "annotation_names": [],
        "modifiers": [],
        "extends": None,
        "implements": [],
        "permits": [],
        "enum_constants": [],
        "constants": {},
        "fields": [],
        "methods": [],
        "inner_types": [],
        "static_initializers": [],
    }


def parse_type(decl_node, call_scope=None):
    """Parse a top-level or nested type declaration into a plain dict.

    Record components appear first in ``fields`` with ``"component": True``.
    ``annotations`` are rich dicts (noise dropped); ``annotation_names`` is
    the unfiltered list of ``@Name`` strings for detection logic.
    ``constants`` maps ``static final String`` names to resolved values.
    ``doc`` is the first sentence of the type's Javadoc. ``inner_types``
    are full ``parse_type`` dicts. ``line`` is the line of the type name.
    """
    mods = get_modifiers_node(decl_node)
    body = get_class_body(decl_node)
    members = get_body_members(body)
    constants = extract_string_constants(members)

    info = _empty_type(
        get_type_keyword(decl_node),
        get_declaration_name(decl_node),
        build_class_declaration_text(decl_node),
        signature_line(decl_node),
    )
    info["doc"] = get_javadoc_summary(decl_node)
    info["annotations"] = get_annotations_rich(mods, constants)
    info["annotation_names"] = get_annotations(mods)
    info["modifiers"] = _get_modifier_keywords(mods) if mods else []
    extends = get_superclass(decl_node)
    info["extends"] = _normalize_ws(extends) if extends else None
    info["implements"] = [_normalize_ws(i) for i in get_interfaces(decl_node)]
    info["permits"] = [_normalize_ws(p) for p in get_permits(decl_node)]
    info["constants"] = constants

    record_fields = [
        {
            "type": c["type"], "name": c["name"], "annotations": c["annotations"],
            "static": False, "final": True, "private": False, "component": True,
            "line": info["line"],
        }
        for c in extract_record_components(decl_node)
    ]
    parsed = parse_type_members(members, call_scope, constants, [f["name"] for f in record_fields])
    info["fields"] = record_fields + parsed["fields"]
    info["methods"] = parsed["methods"]
    info["inner_types"] = parsed["inner_types"]
    info["static_initializers"] = parsed["static_initializers"]

    if decl_node.type == "enum_declaration":
        info["enum_constants"] = get_enum_constants(body)
    return info


def parse_implicit_type(program_members, source_name=None, call_scope=None):
    """Parse the synthetic implicit class of a Java simple source file."""
    stem = Path(str(source_name)).stem if source_name else None
    constants = extract_string_constants(program_members)
    info = _empty_type(
        "implicit class",
        stem or "implicit class",
        build_implicit_class_declaration(source_name),
        1,
    )
    info["constants"] = constants
    parsed = parse_type_members(program_members, call_scope, constants)
    info.update(parsed)
    return info


def parse_java_source(content, source_name=None):
    """Parse Java source text into the shared structure every mode consumes.

    Returns ``{"package", "package_annotations", "imports", "types",
    "total_lines"}`` where ``types`` holds one ``parse_type`` dict per
    top-level type (or one implicit type for simple source files).
    """
    if isinstance(content, bytes):
        source_bytes = content
        text = content.decode("utf-8", errors="replace")
    else:
        source_bytes = content.encode("utf-8")
        text = content
    structure = parse_file_structure(source_bytes)
    scope = build_call_scope(structure["package"], structure["imports"], structure["static_members"])

    if structure["program_members"]:
        types = [parse_implicit_type(structure["program_members"], source_name, scope)]
    else:
        types = [parse_type(node, scope) for node in structure["type_nodes"]]

    return {
        "package": structure["package"],
        "package_annotations": structure["package_annotations"],
        "imports": structure["imports"],
        "types": types,
        "total_lines": len(text.split("\n")),
    }


def walk_types(types, prefix=""):
    """Yield ``(label, type)`` for every type and nested type, depth first.

    Labels are dotted: ``Outer``, ``Outer.Inner``, ``Outer.Inner.Deeper``.
    """
    for t in types:
        label = f"{prefix}{t['name']}"
        yield label, t
        yield from walk_types(t["inner_types"], f"{label}.")


def instance_fields(type_info):
    """Return the non-static fields of a parsed type."""
    return [f for f in type_info["fields"] if not f["static"]]


def static_fields(type_info):
    """Return the static fields of a parsed type."""
    return [f for f in type_info["fields"] if f["static"]]


def format_static_field(field, constants):
    """Render a static field as ``NAME``, or ``NAME = "value"`` for short non-private string constants.

    Non-private constants are contract (permission keys, paths, event names
    other classes reference); private ones are implementation detail.
    """
    value = constants.get(field["name"])
    if value is not None and not field["private"] and len(value) <= STATIC_VALUE_MAX:
        return f'{field["name"]} = "{value}"'
    return field["name"]


def format_method_annotations(method):
    """Render a parsed method's annotations as one space-joined string."""
    return " ".join(a["full"] for a in method["annotations"])


# ---------------------------------------------------------------------------
# Shared display helpers and limits
# ---------------------------------------------------------------------------

# Method calls shown per method before "... +N more".
CALLS_DISPLAY_MAX = 10
# Enum constants shown inline in a file summary / project map row.
ENUM_CONSTANTS_SKIM_MAX = 10
ENUM_CONSTANTS_MAP_MAX = 6
# Non-private static string constants at most this long show their value inline.
STATIC_VALUE_MAX = 40
# Javadoc first sentence cap.
DOC_SUMMARY_MAX = 160
# Type kinds collapsed to a names-only line per package in the project map.
MAP_COLLAPSED_KINDS = ("record",)
# Wrap width for those names-only lines.
MAP_LINE_WIDTH = 140


def format_calls(calls):
    """Render a call list as ``a, b, c`` with overflow collapsed to ``+N more``."""
    if len(calls) <= CALLS_DISPLAY_MAX:
        return ", ".join(calls)
    shown = ", ".join(calls[:CALLS_DISPLAY_MAX])
    return f"{shown}, ... +{len(calls) - CALLS_DISPLAY_MAX} more"


def format_enum_constants(constants, limit):
    """Render enum constants inline, collapsing the tail past ``limit``."""
    if len(constants) <= limit:
        return ", ".join(constants)
    head = max(limit - 2, 1)
    return f"{', '.join(constants[:head])}, ...+{len(constants) - head}"
