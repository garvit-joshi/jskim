#!/usr/bin/env python3
"""Shared tree-sitter utilities for the jskim toolkit."""

import tree_sitter_java as tsjava
import tree_sitter

JAVA_LANGUAGE = tree_sitter.Language(tsjava.language())
_PARSER = tree_sitter.Parser(JAVA_LANGUAGE)


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


def find_first_type_declaration(root):
    """Find the first class/interface/enum/record/@interface declaration in the AST."""
    type_decl_types = {
        "class_declaration", "interface_declaration",
        "enum_declaration", "record_declaration",
        "annotation_type_declaration",
    }
    for child in root.children:
        if child.type in type_decl_types:
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
    keywords = {
        "public", "private", "protected", "static", "final",
        "abstract", "synchronized", "native", "default",
        "strictfp", "volatile", "transient", "sealed", "non-sealed",
    }
    result = []
    for child in modifiers_node.children:
        if child.type in keywords:
            result.append(child.type)
    return result
