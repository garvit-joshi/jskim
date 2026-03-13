"""Shared tree-sitter utilities for the jskim toolkit."""

import tree_sitter_java as tsjava
import tree_sitter

JAVA_LANGUAGE = tree_sitter.Language(tsjava.language())
_PARSER = tree_sitter.Parser(JAVA_LANGUAGE)


INNER_TYPE_NODES = {
    "class_declaration", "interface_declaration",
    "enum_declaration", "record_declaration",
    "annotation_type_declaration",
}

METHOD_NODES = {"method_declaration", "constructor_declaration", "compact_constructor_declaration"}

LOMBOK_SET = {
    "@Data", "@Value", "@Getter", "@Setter", "@Builder", "@SuperBuilder",
    "@NoArgsConstructor", "@AllArgsConstructor", "@RequiredArgsConstructor",
    "@ToString", "@EqualsAndHashCode", "@Slf4j", "@Log", "@Log4j2",
}

MODIFIER_KEYWORDS = {
    "public", "private", "protected", "static", "final",
    "abstract", "synchronized", "native", "default",
    "strictfp", "volatile", "transient", "sealed", "non-sealed",
}


def parse_java_bytes(source_bytes):
    """Parse Java source bytes and return the root node."""
    tree = _PARSER.parse(source_bytes)
    return tree.root_node


def get_annotations(modifiers_node):
    """Extract @AnnotationName strings from a modifiers node."""
    if modifiers_node is None or modifiers_node.type != "modifiers":
        return []
    anns = []
    for child in modifiers_node.children:
        if child.type in ("marker_annotation", "annotation"):
            name_node = child.child_by_field_name("name")
            if name_node:
                anns.append("@" + name_node.text.decode())
            else:
                for c in child.children:
                    if c.type == "identifier" or c.type == "scoped_identifier":
                        anns.append("@" + c.text.decode())
                        break
    return anns


def build_method_signature(node):
    """Build a clean one-line method signature from a method/constructor node.

    Concatenates all children before the body block, normalizes whitespace,
    and removes the space before '(' that tree-sitter's text concatenation creates.
    """
    body_types = {"block", "constructor_body"}
    parts = []
    for child in node.children:
        if child.type in body_types:
            break
        if child.type == "modifiers":
            anns = get_annotations(child)
            mods = _get_modifier_keywords(child)
            if mods:
                parts.append(" ".join(mods))
            continue
        if child.type == ";":
            break
        parts.append(child.text.decode())
    sig = " ".join(parts)
    sig = " ".join(sig.split())
    sig = sig.replace(" (", "(").replace("( ", "(")
    return sig


def extract_import_path(import_node):
    """Extract the import path string from an import_declaration node.

    Returns the path with 'static ' prefix stripped and wildcard expanded.
    E.g., 'import static java.util.Collections.emptyList;' -> 'java.util.Collections.emptyList'
          'import java.util.*;' -> 'java.util.*'
    """
    has_asterisk = False
    path = None
    for child in import_node.children:
        if child.type in ("scoped_identifier", "identifier"):
            path = child.text.decode()
        if child.type == "asterisk":
            has_asterisk = True
    if path and has_asterisk:
        return path + ".*"
    return path


def parse_file_structure(source_bytes):
    """Parse a Java file and extract the common top-level structure.

    Returns a dict with:
      - "package": package name string or None
      - "imports": list of import path strings
      - "type_nodes": list of top-level type declaration AST nodes
    """
    root = parse_java_bytes(source_bytes)
    package = None
    imports = []
    type_nodes = []

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
            type_nodes.append(child)

    return {"package": package, "imports": imports, "type_nodes": type_nodes}


def find_first_type_declaration(root):
    """Find the first class/interface/enum/record/@interface declaration in the AST."""
    for child in root.children:
        if child.type in INNER_TYPE_NODES:
            return child
    return None


def get_class_body(decl_node):
    """Get the body node from a type declaration (class_body, interface_body, enum_body, etc.)."""
    body_types = {"class_body", "interface_body", "enum_body", "record_body", "annotation_type_body"}
    for child in decl_node.children:
        if child.type in body_types:
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
            for sub in child.named_children:
                if sub.is_named:
                    members.append(sub)
        elif child.type != "enum_constant":
            members.append(child)
    return members


def get_type_keyword(decl_node):
    """Get the type keyword (class/interface/enum/record/@interface) from a declaration node."""
    mapping = {
        "class_declaration": "class",
        "interface_declaration": "interface",
        "enum_declaration": "enum",
        "record_declaration": "record",
        "annotation_type_declaration": "@interface",
    }
    return mapping[decl_node.type]


def get_declaration_name(decl_node):
    """Get the identifier name from a declaration node."""
    name_node = decl_node.child_by_field_name("name")
    if name_node:
        return name_node.text.decode()
    for child in decl_node.children:
        if child.type == "identifier":
            return child.text.decode()
    return None


def get_superclass(decl_node):
    """Extract the extends clause text (just the type, not the 'extends' keyword)."""
    for child in decl_node.children:
        if child.type == "superclass":
            for sub in child.children:
                if sub.type != "extends":
                    return sub.text.decode()
    return None


def get_interfaces(decl_node):
    """Extract implemented interface names as a list of strings."""
    for child in decl_node.children:
        if child.type == "super_interfaces":
            for sub in child.children:
                if sub.type == "type_list":
                    return [t.text.decode() for t in sub.named_children]
    return []


def get_permits(decl_node):
    """Extract permitted subclass names as a list of strings."""
    for child in decl_node.children:
        if child.type == "permits":
            for sub in child.children:
                if sub.type == "type_list":
                    return [t.text.decode() for t in sub.named_children]
    return []


def get_modifiers_node(decl_node):
    """Get the modifiers child node from a declaration, or None."""
    for child in decl_node.children:
        if child.type == "modifiers":
            return child
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
    parts.append(get_declaration_name(decl_node))

    superclass = get_superclass(decl_node)
    if superclass:
        parts.append("extends")
        parts.append(" ".join(superclass.split()))

    ifaces = get_interfaces(decl_node)
    if ifaces:
        parts.append("implements")
        parts.append(", ".join(" ".join(i.split()) for i in ifaces))

    permits = get_permits(decl_node)
    if permits:
        parts.append("permits")
        parts.append(", ".join(" ".join(p.split()) for p in permits))

    return " ".join(parts)


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
            type_text = child.text.decode()
    return [(type_text, name) for name in names]


def _get_modifier_keywords(modifiers_node):
    """Extract keyword modifiers (public, static, etc.) from a modifiers node."""
    result = []
    for child in modifiers_node.children:
        if child.type in MODIFIER_KEYWORDS:
            result.append(child.type)
    return result


# ---------------------------------------------------------------------------
# Spring Boot annotation support
# ---------------------------------------------------------------------------

SPRING_PARAM_ANNOTATIONS = {
    "@GetMapping", "@PostMapping", "@PutMapping", "@DeleteMapping", "@PatchMapping",
    "@RequestMapping", "@Value", "@Qualifier", "@Bean", "@Profile", "@Scheduled",
    "@ConditionalOnProperty", "@ConfigurationProperties",
    "@Table", "@Column", "@JoinColumn", "@Query",
}

HTTP_MAPPING_ANNOTATIONS = {
    "@GetMapping": "GET",
    "@PostMapping": "POST",
    "@PutMapping": "PUT",
    "@DeleteMapping": "DELETE",
    "@PatchMapping": "PATCH",
    "@RequestMapping": None,  # determined from method= param
}


def get_annotation_name_from_node(ann_node):
    """Extract @AnnotationName from a marker_annotation or annotation node."""
    name_node = ann_node.child_by_field_name("name")
    if name_node:
        return "@" + name_node.text.decode()
    for c in ann_node.children:
        if c.type in ("identifier", "scoped_identifier"):
            return "@" + c.text.decode()
    return None


def get_annotations_rich(modifiers_node):
    """Extract annotations with parameters for key Spring annotations.

    Returns list of dicts:
      {"name": "@Foo", "params": "(\"bar\")" or None, "full": "@Foo(\"bar\")"}
    For non-Spring annotations, params is always None and full == name.
    """
    if modifiers_node is None or modifiers_node.type != "modifiers":
        return []
    result = []
    for child in modifiers_node.children:
        if child.type in ("marker_annotation", "annotation"):
            name = get_annotation_name_from_node(child)
            if not name:
                continue
            params = None
            if name in SPRING_PARAM_ANNOTATIONS:
                for sub in child.children:
                    if sub.type == "annotation_argument_list":
                        params = sub.text.decode()
                        break
            result.append({
                "name": name,
                "params": params,
                "full": f"{name}{params}" if params else name,
            })
    return result


def _strip_quotes(s):
    """Strip surrounding double quotes."""
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return s[1:-1]
    return s


def _find_string_literals(node):
    """Recursively collect all string literal values from a node subtree."""
    results = []
    if node.type == "string_literal":
        results.append(_strip_quotes(node.text.decode()))
    for c in node.named_children:
        results.extend(_find_string_literals(c))
    return results


def _get_evp_key(evp_node):
    """Get the key identifier from an element_value_pair node."""
    for c in evp_node.children:
        if c.type == "identifier":
            return c.text.decode()
    return None


def extract_mapping_paths(ann_node):
    """Extract URL path(s) from a Spring @*Mapping annotation.

    Handles: @GetMapping("/p"), @GetMapping(value="/p"), @GetMapping({"/a","/b"})
    Returns list of path strings.  Empty list if no path specified.
    """
    args = None
    for child in ann_node.children:
        if child.type == "annotation_argument_list":
            args = child
            break
    if args is None:
        return []

    paths = []
    for child in args.named_children:
        if child.type == "string_literal":
            paths.append(_strip_quotes(child.text.decode()))
        elif child.type == "element_value_pair":
            key = _get_evp_key(child)
            if key in ("value", "path"):
                paths.extend(_find_string_literals(child))
        elif child.type == "element_value_array_initializer":
            paths.extend(_find_string_literals(child))
    return paths


def extract_request_method(ann_node):
    """Extract HTTP method from @RequestMapping's method= parameter.

    Returns "GET", "POST", etc. or None.
    """
    for child in ann_node.children:
        if child.type == "annotation_argument_list":
            for arg in child.named_children:
                if arg.type == "element_value_pair":
                    key = _get_evp_key(arg)
                    if key == "method":
                        text = arg.text.decode()
                        for m in ("GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"):
                            if m in text:
                                return m
    return None


def extract_first_annotation_string(ann_node):
    """Extract the first string literal value from an annotation's arguments.

    Useful for @ConfigurationProperties("prefix"), @Qualifier("name"), etc.
    """
    for child in ann_node.children:
        if child.type == "annotation_argument_list":
            strings = _find_string_literals(child)
            return strings[0] if strings else None
    return None


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


def is_field_final(field_node):
    """Check if a field_declaration has the 'final' modifier."""
    for child in field_node.children:
        if child.type == "modifiers":
            return "final" in _get_modifier_keywords(child)
    return False


def is_field_static(field_node):
    """Check if a field_declaration has the 'static' modifier."""
    for child in field_node.children:
        if child.type == "modifiers":
            return "static" in _get_modifier_keywords(child)
    return False


# ---------------------------------------------------------------------------
# Method call extraction
# ---------------------------------------------------------------------------

def extract_method_calls(method_node):
    """Extract method calls from a method/constructor body.

    Returns a deduplicated sorted list of call strings like:
      ["orderRepo.save", "paymentService.charge", "validate"]

    Only includes calls with a simple object (field/variable identifier) or
    unqualified calls (same-class methods). Chained/fluent calls (where the
    object is another method_invocation) are skipped — they are intermediate
    steps in builder/stream chains and add noise.

    Handles this.field.method() → field.method, this.method() → method.
    """
    body = method_node.child_by_field_name("body")
    if body is None:
        return []
    calls = set()
    _collect_method_calls(body, calls)
    return sorted(calls)


def _collect_method_calls(node, calls):
    """Recursively collect method invocation strings from an AST subtree."""
    if node.type == "method_invocation":
        obj = node.child_by_field_name("object")
        name = node.child_by_field_name("name")
        if name:
            method_name = name.text.decode()
            if obj is None:
                calls.add(method_name)
            elif obj.type == "identifier":
                calls.add(f"{obj.text.decode()}.{method_name}")
            elif obj.type == "this":
                calls.add(method_name)
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
