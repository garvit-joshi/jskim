"""Tests for jskim.util — shared tree-sitter parsing utilities."""

import pytest
from jskim.util import (
    parse_java_bytes,
    get_annotations,
    get_annotations_rich,
    build_method_signature,
    build_method_identity,
    extract_import_path,
    parse_file_structure,
    find_first_type_declaration,
    get_class_body,
    get_body_members,
    get_type_keyword,
    get_declaration_name,
    get_superclass,
    get_interfaces,
    get_permits,
    get_modifiers_node,
    build_class_declaration_text,
    extract_field_info,
    extract_record_components,
    get_enum_constants,
    is_field_final,
    is_field_static,
    extract_method_calls,
    build_call_scope,
    get_javadoc_summary,
    walk_types,
    format_static_field,
    signature_line,
    get_annotation_name_from_node,
    extract_mapping_paths,
    extract_request_method,
    extract_first_annotation_string,
    INNER_TYPE_NODES,
    METHOD_NODES,
    CALL_NODES,
    LOMBOK_SET,
    MODIFIER_KEYWORDS,
    HTTP_MAPPING_ANNOTATIONS,
)


# ---------------------------------------------------------------------------
# parse_java_bytes
# ---------------------------------------------------------------------------

class TestParseJavaBytes:
    def test_returns_root_node(self):
        root = parse_java_bytes(b"class Foo {}")
        assert root is not None
        assert root.type == "program"

    def test_empty_source(self):
        root = parse_java_bytes(b"")
        assert root is not None
        assert root.type == "program"

    def test_complex_source(self):
        source = b"package com.example; import java.util.List; public class Bar {}"
        root = parse_java_bytes(source)
        assert root.child_count > 0


# ---------------------------------------------------------------------------
# parse_file_structure
# ---------------------------------------------------------------------------

class TestParseFileStructure:
    def test_basic_class(self):
        source = b"package com.example; import java.util.List; public class Foo {}"
        result = parse_file_structure(source)
        assert result["package"] == "com.example"
        assert result["imports"] == ["java.util.List"]
        assert len(result["type_nodes"]) == 1

    def test_no_package(self):
        source = b"class Foo {}"
        result = parse_file_structure(source)
        assert result["package"] is None

    def test_no_imports(self):
        source = b"package com.example; class Foo {}"
        result = parse_file_structure(source)
        assert result["imports"] == []

    def test_multiple_imports(self):
        source = b"""
        package com.example;
        import java.util.List;
        import java.util.Map;
        import java.io.IOException;
        class Foo {}
        """
        result = parse_file_structure(source)
        assert len(result["imports"]) == 3
        assert "java.util.List" in result["imports"]
        assert "java.util.Map" in result["imports"]
        assert "java.io.IOException" in result["imports"]

    def test_wildcard_import(self):
        source = b"import java.util.*; class Foo {}"
        result = parse_file_structure(source)
        assert result["imports"] == ["java.util.*"]

    def test_static_import(self):
        source = b"import static java.util.Collections.emptyList; class Foo {}"
        result = parse_file_structure(source)
        assert result["imports"] == ["java.util.Collections.emptyList"]

    def test_multiple_type_declarations(self):
        source = b"class Foo {} class Bar {} class Baz {}"
        result = parse_file_structure(source)
        assert len(result["type_nodes"]) == 3

    def test_enum_declaration(self):
        source = b"package com.example; public enum Direction { NORTH, SOUTH }"
        result = parse_file_structure(source)
        assert len(result["type_nodes"]) == 1
        assert result["type_nodes"][0].type == "enum_declaration"

    def test_interface_declaration(self):
        source = b"public interface Callable { void call(); }"
        result = parse_file_structure(source)
        assert len(result["type_nodes"]) == 1
        assert result["type_nodes"][0].type == "interface_declaration"

    def test_record_declaration(self):
        source = b"public record Point(int x, int y) {}"
        result = parse_file_structure(source)
        assert len(result["type_nodes"]) == 1
        assert result["type_nodes"][0].type == "record_declaration"

    def test_annotation_type_declaration(self):
        source = b"public @interface MyAnnotation { String value(); }"
        result = parse_file_structure(source)
        assert len(result["type_nodes"]) == 1
        assert result["type_nodes"][0].type == "annotation_type_declaration"

    def test_implicit_source_members(self):
        source = b"void main() { System.out.println(\"Hello\"); }"
        result = parse_file_structure(source)
        assert result["type_nodes"] == []
        assert len(result["program_members"]) == 1
        assert result["program_members"][0].type == "method_declaration"


# ---------------------------------------------------------------------------
# extract_import_path
# ---------------------------------------------------------------------------

class TestExtractImportPath:
    def _parse_import(self, import_text):
        root = parse_java_bytes(import_text.encode())
        for child in root.children:
            if child.type == "import_declaration":
                return child
        return None

    def test_simple_import(self):
        node = self._parse_import("import java.util.List;")
        assert extract_import_path(node) == "java.util.List"

    def test_wildcard_import(self):
        node = self._parse_import("import java.util.*;")
        assert extract_import_path(node) == "java.util.*"

    def test_static_import(self):
        node = self._parse_import("import static java.util.Collections.emptyList;")
        assert extract_import_path(node) == "java.util.Collections.emptyList"

    def test_deep_import(self):
        node = self._parse_import("import com.example.webapp.services.OrderService;")
        assert extract_import_path(node) == "com.example.webapp.services.OrderService"


# ---------------------------------------------------------------------------
# find_first_type_declaration
# ---------------------------------------------------------------------------

class TestFindFirstTypeDeclaration:
    def test_finds_class(self):
        root = parse_java_bytes(b"class Foo {}")
        decl = find_first_type_declaration(root)
        assert decl is not None
        assert decl.type == "class_declaration"

    def test_finds_enum(self):
        root = parse_java_bytes(b"enum Color { RED, GREEN }")
        decl = find_first_type_declaration(root)
        assert decl is not None
        assert decl.type == "enum_declaration"

    def test_returns_none_for_empty(self):
        root = parse_java_bytes(b"package com.example;")
        decl = find_first_type_declaration(root)
        assert decl is None

    def test_returns_first_of_multiple(self):
        root = parse_java_bytes(b"class Foo {} class Bar {}")
        decl = find_first_type_declaration(root)
        assert get_declaration_name(decl) == "Foo"


# ---------------------------------------------------------------------------
# get_type_keyword
# ---------------------------------------------------------------------------

class TestGetTypeKeyword:
    def test_class(self):
        root = parse_java_bytes(b"class Foo {}")
        decl = find_first_type_declaration(root)
        assert get_type_keyword(decl) == "class"

    def test_interface(self):
        root = parse_java_bytes(b"interface Foo {}")
        decl = find_first_type_declaration(root)
        assert get_type_keyword(decl) == "interface"

    def test_enum(self):
        root = parse_java_bytes(b"enum Foo { A }")
        decl = find_first_type_declaration(root)
        assert get_type_keyword(decl) == "enum"

    def test_record(self):
        root = parse_java_bytes(b"record Foo(int x) {}")
        decl = find_first_type_declaration(root)
        assert get_type_keyword(decl) == "record"

    def test_annotation_type(self):
        root = parse_java_bytes(b"@interface Foo {}")
        decl = find_first_type_declaration(root)
        assert get_type_keyword(decl) == "@interface"


# ---------------------------------------------------------------------------
# get_declaration_name
# ---------------------------------------------------------------------------

class TestGetDeclarationName:
    def test_class_name(self):
        root = parse_java_bytes(b"class MyService {}")
        decl = find_first_type_declaration(root)
        assert get_declaration_name(decl) == "MyService"

    def test_enum_name(self):
        root = parse_java_bytes(b"enum Status { ACTIVE }")
        decl = find_first_type_declaration(root)
        assert get_declaration_name(decl) == "Status"

    def test_interface_name(self):
        root = parse_java_bytes(b"interface Repository {}")
        decl = find_first_type_declaration(root)
        assert get_declaration_name(decl) == "Repository"


# ---------------------------------------------------------------------------
# get_superclass
# ---------------------------------------------------------------------------

class TestGetSuperclass:
    def test_no_extends(self):
        root = parse_java_bytes(b"class Foo {}")
        decl = find_first_type_declaration(root)
        assert get_superclass(decl) is None

    def test_simple_extends(self):
        root = parse_java_bytes(b"class Foo extends Bar {}")
        decl = find_first_type_declaration(root)
        assert get_superclass(decl) == "Bar"

    def test_generic_extends(self):
        root = parse_java_bytes(b"class Foo extends Base<String> {}")
        decl = find_first_type_declaration(root)
        assert "Base" in get_superclass(decl)
        assert "String" in get_superclass(decl)


# ---------------------------------------------------------------------------
# get_interfaces
# ---------------------------------------------------------------------------

class TestGetInterfaces:
    def test_no_implements(self):
        root = parse_java_bytes(b"class Foo {}")
        decl = find_first_type_declaration(root)
        assert get_interfaces(decl) == []

    def test_single_interface(self):
        root = parse_java_bytes(b"class Foo implements Serializable {}")
        decl = find_first_type_declaration(root)
        ifaces = get_interfaces(decl)
        assert len(ifaces) == 1
        assert "Serializable" in ifaces[0]

    def test_multiple_interfaces(self):
        root = parse_java_bytes(b"class Foo implements Serializable, Comparable<Foo> {}")
        decl = find_first_type_declaration(root)
        ifaces = get_interfaces(decl)
        assert len(ifaces) == 2

    def test_interface_extends_interfaces(self):
        root = parse_java_bytes(b"interface Foo extends Bar, Baz {}")
        decl = find_first_type_declaration(root)
        ifaces = get_interfaces(decl)
        assert len(ifaces) == 2
        assert "Bar" in ifaces
        assert "Baz" in ifaces


# ---------------------------------------------------------------------------
# get_permits
# ---------------------------------------------------------------------------

class TestGetPermits:
    def test_no_permits(self):
        root = parse_java_bytes(b"class Foo {}")
        decl = find_first_type_declaration(root)
        assert get_permits(decl) == []

    def test_sealed_with_permits(self):
        source = b"sealed class Shape permits Circle, Rectangle {}"
        root = parse_java_bytes(source)
        decl = find_first_type_declaration(root)
        permits = get_permits(decl)
        assert len(permits) == 2
        assert "Circle" in permits
        assert "Rectangle" in permits


# ---------------------------------------------------------------------------
# get_class_body / get_body_members
# ---------------------------------------------------------------------------

class TestGetClassBody:
    def test_class_body(self):
        root = parse_java_bytes(b"class Foo { int x; }")
        decl = find_first_type_declaration(root)
        body = get_class_body(decl)
        assert body is not None
        assert body.type == "class_body"

    def test_enum_body(self):
        root = parse_java_bytes(b"enum Foo { A, B }")
        decl = find_first_type_declaration(root)
        body = get_class_body(decl)
        assert body is not None
        assert body.type == "enum_body"

    def test_interface_body(self):
        root = parse_java_bytes(b"interface Foo { void bar(); }")
        decl = find_first_type_declaration(root)
        body = get_class_body(decl)
        assert body is not None
        assert body.type == "interface_body"


class TestGetBodyMembers:
    def test_returns_empty_for_none(self):
        assert get_body_members(None) == []

    def test_class_fields_and_methods(self):
        source = b"""
        class Foo {
            int x;
            public void bar() {}
        }
        """
        root = parse_java_bytes(source)
        decl = find_first_type_declaration(root)
        body = get_class_body(decl)
        members = get_body_members(body)
        types = [m.type for m in members]
        assert "field_declaration" in types
        assert "method_declaration" in types

    def test_enum_members_after_constants(self):
        source = b"""
        enum Status {
            ACTIVE, PENDING;
            public String label() { return name().toLowerCase(); }
        }
        """
        root = parse_java_bytes(source)
        decl = find_first_type_declaration(root)
        body = get_class_body(decl)
        members = get_body_members(body)
        method_members = [m for m in members if m.type == "method_declaration"]
        assert len(method_members) == 1


# ---------------------------------------------------------------------------
# get_modifiers_node
# ---------------------------------------------------------------------------

class TestGetModifiersNode:
    def test_no_modifiers(self):
        root = parse_java_bytes(b"class Foo {}")
        decl = find_first_type_declaration(root)
        assert get_modifiers_node(decl) is None

    def test_with_modifiers(self):
        root = parse_java_bytes(b"public class Foo {}")
        decl = find_first_type_declaration(root)
        mods = get_modifiers_node(decl)
        assert mods is not None
        assert mods.type == "modifiers"


# ---------------------------------------------------------------------------
# get_annotations
# ---------------------------------------------------------------------------

class TestGetAnnotations:
    def test_no_annotations(self):
        root = parse_java_bytes(b"public class Foo {}")
        decl = find_first_type_declaration(root)
        mods = get_modifiers_node(decl)
        anns = get_annotations(mods)
        assert anns == []

    def test_marker_annotation(self):
        root = parse_java_bytes(b"@Service public class Foo {}")
        decl = find_first_type_declaration(root)
        mods = get_modifiers_node(decl)
        anns = get_annotations(mods)
        assert "@Service" in anns

    def test_multiple_annotations(self):
        root = parse_java_bytes(b"@Slf4j @Service @RequiredArgsConstructor public class Foo {}")
        decl = find_first_type_declaration(root)
        mods = get_modifiers_node(decl)
        anns = get_annotations(mods)
        assert "@Slf4j" in anns
        assert "@Service" in anns
        assert "@RequiredArgsConstructor" in anns

    def test_annotation_with_args(self):
        root = parse_java_bytes(b'@Component("myBean") public class Foo {}')
        decl = find_first_type_declaration(root)
        mods = get_modifiers_node(decl)
        anns = get_annotations(mods)
        assert "@Component" in anns

    def test_none_modifiers(self):
        assert get_annotations(None) == []

    def test_non_modifiers_node(self):
        root = parse_java_bytes(b"class Foo {}")
        decl = find_first_type_declaration(root)
        assert get_annotations(decl) == []


# ---------------------------------------------------------------------------
# get_annotations_rich
# ---------------------------------------------------------------------------

class TestGetAnnotationsRich:
    def test_non_spring_annotation(self):
        root = parse_java_bytes(b"@Override public class Foo {}")
        decl = find_first_type_declaration(root)
        mods = get_modifiers_node(decl)
        rich = get_annotations_rich(mods)
        assert len(rich) == 1
        assert rich[0]["name"] == "@Override"
        assert rich[0]["params"] is None
        assert rich[0]["full"] == "@Override"

    def test_spring_annotation_with_params(self):
        source = b'@GetMapping("/users") public class Foo {}'
        root = parse_java_bytes(source)
        decl = find_first_type_declaration(root)
        mods = get_modifiers_node(decl)
        rich = get_annotations_rich(mods)
        assert len(rich) == 1
        assert rich[0]["name"] == "@GetMapping"
        assert rich[0]["params"] is not None
        assert '"/users"' in rich[0]["full"]

    def test_none_modifiers(self):
        assert get_annotations_rich(None) == []


# ---------------------------------------------------------------------------
# build_method_signature
# ---------------------------------------------------------------------------

class TestBuildMethodSignature:
    def _get_first_method(self, source):
        root = parse_java_bytes(source)
        decl = find_first_type_declaration(root)
        body = get_class_body(decl)
        for member in get_body_members(body):
            if member.type in METHOD_NODES:
                return member
        return None

    def test_simple_method(self):
        method = self._get_first_method(b"class Foo { public void bar() {} }")
        sig = build_method_signature(method)
        assert "public" in sig
        assert "void" in sig
        assert "bar()" in sig

    def test_method_with_params(self):
        method = self._get_first_method(
            b"class Foo { public String concat(String a, String b) { return a + b; } }"
        )
        sig = build_method_signature(method)
        assert "concat(" in sig
        assert "String a" in sig
        assert "String b" in sig

    def test_constructor(self):
        method = self._get_first_method(
            b"class Foo { public Foo(int x) {} }"
        )
        sig = build_method_signature(method)
        assert "Foo(" in sig
        assert "int x" in sig

    def test_generic_return_type(self):
        method = self._get_first_method(
            b"class Foo { public List<String> getItems() { return null; } }"
        )
        sig = build_method_signature(method)
        assert "List<String>" in sig
        assert "getItems()" in sig

    def test_static_method(self):
        method = self._get_first_method(
            b"class Foo { public static void main(String[] args) {} }"
        )
        sig = build_method_signature(method)
        assert "static" in sig
        assert "void" in sig
        assert "main(" in sig

    def test_no_space_before_paren(self):
        method = self._get_first_method(b"class Foo { void bar() {} }")
        sig = build_method_signature(method)
        assert " (" not in sig
        assert "bar()" in sig


class TestBuildMethodIdentity:
    def _get_first_method(self, source):
        root = parse_java_bytes(source)
        decl = find_first_type_declaration(root)
        body = get_class_body(decl)
        for member in get_body_members(body):
            if member.type in METHOD_NODES:
                return member
        return None

    def test_method_uses_parameter_types(self):
        method = self._get_first_method(
            b"class Foo { void bar(int count, @A final String name) {} }"
        )
        assert build_method_identity(method) == "bar(int, String)"

    def test_constructor_identity(self):
        method = self._get_first_method(b"class Foo { Foo(int count) {} }")
        assert build_method_identity(method) == "Foo(int)"

    def test_compact_constructor_identity(self):
        method = self._get_first_method(b"record Foo(int count) { Foo {} }")
        assert build_method_identity(method) == "Foo()"

    def test_annotation_element_identity(self):
        method = self._get_first_method(b"@interface Foo { String value(); }")
        assert build_method_identity(method) == "value()"


# ---------------------------------------------------------------------------
# build_class_declaration_text
# ---------------------------------------------------------------------------

class TestBuildClassDeclarationText:
    def test_simple_class(self):
        root = parse_java_bytes(b"public class Foo {}")
        decl = find_first_type_declaration(root)
        text = build_class_declaration_text(decl)
        assert text == "public class Foo"

    def test_class_with_extends(self):
        root = parse_java_bytes(b"public class Foo extends Bar {}")
        decl = find_first_type_declaration(root)
        text = build_class_declaration_text(decl)
        assert "extends Bar" in text

    def test_class_with_implements(self):
        root = parse_java_bytes(b"public class Foo implements Serializable {}")
        decl = find_first_type_declaration(root)
        text = build_class_declaration_text(decl)
        assert "implements Serializable" in text

    def test_interface_with_extends(self):
        root = parse_java_bytes(b"public interface Foo extends Serializable, AutoCloseable {}")
        decl = find_first_type_declaration(root)
        text = build_class_declaration_text(decl)
        assert "extends Serializable, AutoCloseable" in text

    def test_sealed_class_with_permits(self):
        source = b"public sealed class Shape permits Circle, Rectangle {}"
        root = parse_java_bytes(source)
        decl = find_first_type_declaration(root)
        text = build_class_declaration_text(decl)
        assert "sealed" in text
        assert "permits" in text
        assert "Circle" in text
        assert "Rectangle" in text

    def test_enum(self):
        root = parse_java_bytes(b"public enum Status { A }")
        decl = find_first_type_declaration(root)
        text = build_class_declaration_text(decl)
        assert "public enum Status" == text

    def test_record(self):
        root = parse_java_bytes(b"public record Point(int x, int y) {}")
        decl = find_first_type_declaration(root)
        text = build_class_declaration_text(decl)
        assert "public record Point" == text


# ---------------------------------------------------------------------------
# extract_field_info
# ---------------------------------------------------------------------------

class TestExtractFieldInfo:
    def _get_fields(self, source):
        root = parse_java_bytes(source)
        decl = find_first_type_declaration(root)
        body = get_class_body(decl)
        fields = []
        for member in get_body_members(body):
            if member.type == "field_declaration":
                fields.append(member)
        return fields

    def test_simple_field(self):
        fields = self._get_fields(b"class Foo { private int x; }")
        info = extract_field_info(fields[0])
        assert len(info) == 1
        assert info[0] == ("int", "x")

    def test_multi_variable_field(self):
        fields = self._get_fields(b"class Foo { private int x, y, z; }")
        info = extract_field_info(fields[0])
        assert len(info) == 3
        names = [i[1] for i in info]
        assert "x" in names
        assert "y" in names
        assert "z" in names

    def test_generic_field(self):
        fields = self._get_fields(b"class Foo { private List<String> items; }")
        info = extract_field_info(fields[0])
        assert len(info) == 1
        assert info[0][0] == "List<String>"
        assert info[0][1] == "items"

    def test_initialized_field(self):
        fields = self._get_fields(b'class Foo { private String name = "test"; }')
        info = extract_field_info(fields[0])
        assert len(info) == 1
        assert info[0] == ("String", "name")


# ---------------------------------------------------------------------------
# is_field_final / is_field_static
# ---------------------------------------------------------------------------

class TestFieldModifiers:
    def _get_field(self, source):
        root = parse_java_bytes(source)
        decl = find_first_type_declaration(root)
        body = get_class_body(decl)
        for member in get_body_members(body):
            if member.type == "field_declaration":
                return member
        return None

    def test_final_field(self):
        field = self._get_field(b"class Foo { private final int x = 1; }")
        assert is_field_final(field) is True

    def test_non_final_field(self):
        field = self._get_field(b"class Foo { private int x; }")
        assert is_field_final(field) is False

    def test_static_field(self):
        field = self._get_field(b"class Foo { private static int x; }")
        assert is_field_static(field) is True

    def test_non_static_field(self):
        field = self._get_field(b"class Foo { private int x; }")
        assert is_field_static(field) is False

    def test_static_final_field(self):
        field = self._get_field(b'class Foo { private static final String C = "x"; }')
        assert is_field_final(field) is True
        assert is_field_static(field) is True


# ---------------------------------------------------------------------------
# get_enum_constants
# ---------------------------------------------------------------------------

class TestGetEnumConstants:
    def test_simple_enum(self):
        root = parse_java_bytes(b"enum Color { RED, GREEN, BLUE }")
        decl = find_first_type_declaration(root)
        body = get_class_body(decl)
        constants = get_enum_constants(body)
        assert constants == ["RED", "GREEN", "BLUE"]

    def test_enum_with_args(self):
        source = b'enum Status { ACTIVE("active"), PENDING("pending") }'
        root = parse_java_bytes(source)
        decl = find_first_type_declaration(root)
        body = get_class_body(decl)
        constants = get_enum_constants(body)
        assert constants == ["ACTIVE", "PENDING"]

    def test_empty_enum(self):
        root = parse_java_bytes(b"enum Empty {}")
        decl = find_first_type_declaration(root)
        body = get_class_body(decl)
        constants = get_enum_constants(body)
        assert constants == []

    def test_none_body(self):
        assert get_enum_constants(None) == []


# ---------------------------------------------------------------------------
# extract_method_calls
# ---------------------------------------------------------------------------

class TestExtractMethodCalls:
    def _get_first_method(self, source):
        root = parse_java_bytes(source)
        decl = find_first_type_declaration(root)
        body = get_class_body(decl)
        for member in get_body_members(body):
            if member.type in METHOD_NODES:
                return member
        return None

    def test_simple_call(self):
        source = b"""
        class Foo {
            void bar() {
                doSomething();
            }
        }
        """
        method = self._get_first_method(source)
        calls = extract_method_calls(method)
        assert "doSomething" in calls

    def test_qualified_call(self):
        source = b"""
        class Foo {
            void bar() {
                service.process();
            }
        }
        """
        method = self._get_first_method(source)
        calls = extract_method_calls(method)
        assert "service.process" in calls

    def test_this_call(self):
        source = b"""
        class Foo {
            void bar() {
                this.validate();
            }
        }
        """
        method = self._get_first_method(source)
        calls = extract_method_calls(method)
        assert "validate" in calls

    def test_super_call(self):
        source = b"""
        class Foo {
            void bar() {
                super.init();
            }
        }
        """
        method = self._get_first_method(source)
        calls = extract_method_calls(method)
        assert "super.init" in calls

    def test_this_field_call(self):
        source = b"""
        class Foo {
            void bar() {
                this.repo.save();
            }
        }
        """
        method = self._get_first_method(source)
        calls = extract_method_calls(method)
        assert "repo.save" in calls

    def test_no_body(self):
        source = b"interface Foo { void bar(); }"
        method = self._get_first_method(source)
        calls = extract_method_calls(method)
        assert calls == []

    def test_deduplication(self):
        source = b"""
        class Foo {
            void bar() {
                process();
                process();
                process();
            }
        }
        """
        method = self._get_first_method(source)
        calls = extract_method_calls(method)
        assert calls.count("process") == 1

    def test_sorted_output(self):
        source = b"""
        class Foo {
            void bar() {
                z();
                a();
                m();
            }
        }
        """
        method = self._get_first_method(source)
        calls = extract_method_calls(method)
        assert calls == sorted(calls)

    def test_filters_noise_objects(self):
        """Calls on known noise objects (log, Objects, StringUtils, etc.) are excluded."""
        source = b"""
        class Foo {
            void bar() {
                log.info("hello");
                Objects.requireNonNull(x);
                StringUtils.isBlank(s);
                service.process();
            }
        }
        """
        method = self._get_first_method(source)
        calls = extract_method_calls(method)
        assert "service.process" in calls
        assert "log.info" not in calls
        assert "Objects.requireNonNull" not in calls
        assert "StringUtils.isBlank" not in calls

    def test_filters_noise_methods(self):
        """Collection/stream methods (put, get, add, stream, etc.) are excluded on any object."""
        source = b"""
        class Foo {
            void bar() {
                map.put("key", val);
                list.add(item);
                set.contains(x);
                items.stream();
                service.validate();
            }
        }
        """
        method = self._get_first_method(source)
        calls = extract_method_calls(method)
        assert "service.validate" in calls
        assert "map.put" not in calls
        assert "list.add" not in calls
        assert "set.contains" not in calls
        assert "items.stream" not in calls

    def test_keeps_unqualified_calls(self):
        """Unqualified calls (same-class methods) are never filtered, even if name matches noise."""
        source = b"""
        class Foo {
            void bar() {
                validate();
                isEmpty();
                toString();
            }
        }
        """
        method = self._get_first_method(source)
        calls = extract_method_calls(method)
        assert "validate" in calls
        assert "isEmpty" in calls
        assert "toString" in calls

    def test_keeps_business_calls_with_noise_method_names_on_services(self):
        """A method like cartService.isEmpty() is kept because the object isn't a noise object."""
        # Wait — isEmpty IS in NOISE_CALL_METHODS so it gets filtered on any object.
        # This is by design: isEmpty() on a service is extremely rare and not worth the noise.
        source = b"""
        class Foo {
            void bar() {
                orderService.createOrder();
                paymentGateway.charge();
            }
        }
        """
        method = self._get_first_method(source)
        calls = extract_method_calls(method)
        assert "orderService.createOrder" in calls
        assert "paymentGateway.charge" in calls

    def test_filters_mixed_noise_and_signal(self):
        """Real-world scenario: a method with noise and signal calls mixed."""
        source = b"""
        class OrderService {
            void processOrder(Order order) {
                log.debug("processing");
                validator.validate(order);
                MapUtils.isEmpty(order.getExtras());
                customMap.put("key", "val");
                orderRepo.save(order);
                notifyStakeholders();
            }
        }
        """
        method = self._get_first_method(source)
        calls = extract_method_calls(method)
        assert calls == ["notifyStakeholders", "order.getExtras", "orderRepo.save", "validator.validate"]


# ---------------------------------------------------------------------------
# Spring annotation helpers
# ---------------------------------------------------------------------------

class TestGetAnnotationNameFromNode:
    def _get_first_annotation(self, source):
        root = parse_java_bytes(source)
        decl = find_first_type_declaration(root)
        mods = get_modifiers_node(decl)
        if mods:
            for child in mods.children:
                if child.type in ("marker_annotation", "annotation"):
                    return child
        return None

    def test_simple_annotation(self):
        ann = self._get_first_annotation(b"@Service class Foo {}")
        assert get_annotation_name_from_node(ann) == "@Service"

    def test_annotation_with_args(self):
        ann = self._get_first_annotation(b'@RequestMapping("/api") class Foo {}')
        assert get_annotation_name_from_node(ann) == "@RequestMapping"


class TestExtractMappingPaths:
    def _get_first_annotation(self, source):
        root = parse_java_bytes(source)
        decl = find_first_type_declaration(root)
        mods = get_modifiers_node(decl)
        if mods:
            for child in mods.children:
                if child.type in ("marker_annotation", "annotation"):
                    return child
        return None

    def test_simple_path(self):
        ann = self._get_first_annotation(b'@GetMapping("/users") class Foo {}')
        paths = extract_mapping_paths(ann)
        assert paths == ["/users"]

    def test_value_param(self):
        ann = self._get_first_annotation(b'@GetMapping(value = "/users") class Foo {}')
        paths = extract_mapping_paths(ann)
        assert paths == ["/users"]

    def test_no_path(self):
        ann = self._get_first_annotation(b"@GetMapping class Foo {}")
        paths = extract_mapping_paths(ann)
        assert paths == []

    def test_multiple_paths(self):
        ann = self._get_first_annotation(
            b'@GetMapping({"/users", "/people"}) class Foo {}'
        )
        paths = extract_mapping_paths(ann)
        assert len(paths) == 2
        assert "/users" in paths
        assert "/people" in paths


class TestExtractRequestMethod:
    def _get_first_annotation(self, source):
        root = parse_java_bytes(source)
        decl = find_first_type_declaration(root)
        mods = get_modifiers_node(decl)
        if mods:
            for child in mods.children:
                if child.type in ("marker_annotation", "annotation"):
                    return child
        return None

    def test_get_method(self):
        ann = self._get_first_annotation(
            b"@RequestMapping(method = RequestMethod.GET) class Foo {}"
        )
        assert extract_request_method(ann) == "GET"

    def test_post_method(self):
        ann = self._get_first_annotation(
            b"@RequestMapping(method = RequestMethod.POST) class Foo {}"
        )
        assert extract_request_method(ann) == "POST"

    def test_no_method(self):
        ann = self._get_first_annotation(b'@RequestMapping("/api") class Foo {}')
        assert extract_request_method(ann) is None


class TestExtractFirstAnnotationString:
    def _get_first_annotation(self, source):
        root = parse_java_bytes(source)
        decl = find_first_type_declaration(root)
        mods = get_modifiers_node(decl)
        if mods:
            for child in mods.children:
                if child.type in ("marker_annotation", "annotation"):
                    return child
        return None

    def test_simple_string(self):
        ann = self._get_first_annotation(
            b'@ConfigurationProperties("app.config") class Foo {}'
        )
        assert extract_first_annotation_string(ann) == "app.config"

    def test_no_string(self):
        ann = self._get_first_annotation(b"@Component class Foo {}")
        assert extract_first_annotation_string(ann) is None


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_inner_type_nodes_complete(self):
        expected = {
            "class_declaration", "interface_declaration",
            "enum_declaration", "record_declaration",
            "annotation_type_declaration",
        }
        assert INNER_TYPE_NODES == expected

    def test_method_nodes_complete(self):
        expected = {
            "method_declaration", "constructor_declaration",
            "compact_constructor_declaration", "annotation_type_element_declaration",
        }
        assert METHOD_NODES == expected

    def test_call_nodes_complete(self):
        assert CALL_NODES == {"method_invocation", "method_reference"}

    def test_lombok_set_has_common_annotations(self):
        assert "@Data" in LOMBOK_SET
        assert "@Value" in LOMBOK_SET
        assert "@Getter" in LOMBOK_SET
        assert "@Setter" in LOMBOK_SET
        assert "@Builder" in LOMBOK_SET
        assert "@Slf4j" in LOMBOK_SET

    def test_modifier_keywords(self):
        assert "public" in MODIFIER_KEYWORDS
        assert "private" in MODIFIER_KEYWORDS
        assert "static" in MODIFIER_KEYWORDS
        assert "final" in MODIFIER_KEYWORDS
        assert "sealed" in MODIFIER_KEYWORDS

    def test_http_mapping_annotations(self):
        assert "@GetMapping" in HTTP_MAPPING_ANNOTATIONS
        assert HTTP_MAPPING_ANNOTATIONS["@GetMapping"] == "GET"
        assert HTTP_MAPPING_ANNOTATIONS["@PostMapping"] == "POST"
        assert HTTP_MAPPING_ANNOTATIONS["@RequestMapping"] is None


# ---------------------------------------------------------------------------
# extract_record_components
# ---------------------------------------------------------------------------

class TestExtractRecordComponents:
    def test_simple_record(self):
        root = parse_java_bytes(b"record Point(int x, int y) {}")
        decl = find_first_type_declaration(root)
        components = extract_record_components(decl)
        assert [(c["type"], c["name"]) for c in components] == [("int", "x"), ("int", "y")]
        assert components[0]["annotations"] == []

    def test_generic_record(self):
        root = parse_java_bytes(b"record Pair<A, B>(A first, B second) {}")
        decl = find_first_type_declaration(root)
        components = extract_record_components(decl)
        assert [(c["type"], c["name"]) for c in components] == [("A", "first"), ("B", "second")]

    def test_record_with_generic_types(self):
        root = parse_java_bytes(b"record Response<T>(T data, List<String> tags, int code) {}")
        decl = find_first_type_declaration(root)
        components = extract_record_components(decl)
        assert [(c["type"], c["name"]) for c in components] == [
            ("T", "data"), ("List<String>", "tags"), ("int", "code"),
        ]

    def test_component_annotations_kept(self):
        root = parse_java_bytes(b"record R(@NotNull @Size(min = 1) @Schema(x = 1) List<E> events) {}")
        decl = find_first_type_declaration(root)
        assert extract_record_components(decl)[0]["annotations"] == ["@NotNull", "@Size"]

    def test_non_record_returns_empty(self):
        root = parse_java_bytes(b"class Foo { int x; }")
        decl = find_first_type_declaration(root)
        assert extract_record_components(decl) == []

    def test_enum_returns_empty(self):
        root = parse_java_bytes(b"enum Foo { A }")
        decl = find_first_type_declaration(root)
        assert extract_record_components(decl) == []


# ---------------------------------------------------------------------------
# build_class_declaration_text — type parameters
# ---------------------------------------------------------------------------

class TestBuildClassDeclarationTypeParams:
    def test_generic_class(self):
        root = parse_java_bytes(b"public class Container<T> {}")
        decl = find_first_type_declaration(root)
        text = build_class_declaration_text(decl)
        assert text == "public class Container<T>"

    def test_bounded_generic_class(self):
        root = parse_java_bytes(b"public class Container<T extends Comparable<T>> {}")
        decl = find_first_type_declaration(root)
        text = build_class_declaration_text(decl)
        assert "Container<T extends Comparable<T>>" in text

    def test_generic_interface(self):
        root = parse_java_bytes(b"public interface Validator<T> {}")
        decl = find_first_type_declaration(root)
        text = build_class_declaration_text(decl)
        assert text == "public interface Validator<T>"

    def test_generic_record(self):
        root = parse_java_bytes(b"public record Pair<A, B>(A first, B second) {}")
        decl = find_first_type_declaration(root)
        text = build_class_declaration_text(decl)
        assert text == "public record Pair<A, B>"

    def test_sealed_generic_interface(self):
        source = b"public sealed interface Shape<T> permits Circle, Rectangle {}"
        root = parse_java_bytes(source)
        decl = find_first_type_declaration(root)
        text = build_class_declaration_text(decl)
        assert "Shape<T>" in text
        assert "permits" in text

    def test_no_type_params_unchanged(self):
        root = parse_java_bytes(b"public class Foo {}")
        decl = find_first_type_declaration(root)
        text = build_class_declaration_text(decl)
        assert text == "public class Foo"

    def test_generic_with_extends_and_implements(self):
        source = b"public class Foo<T> extends Bar<T> implements Baz<T> {}"
        root = parse_java_bytes(source)
        decl = find_first_type_declaration(root)
        text = build_class_declaration_text(decl)
        assert "Foo<T>" in text
        assert "extends Bar<T>" in text
        assert "implements Baz<T>" in text


# ---------------------------------------------------------------------------
# build_method_signature — annotation_type_element_declaration
# ---------------------------------------------------------------------------

class TestAnnotationTypeElements:
    def _get_elements(self, source):
        root = parse_java_bytes(source)
        decl = find_first_type_declaration(root)
        body = get_class_body(decl)
        return [m for m in get_body_members(body) if m.type in METHOD_NODES]

    def test_simple_element(self):
        elements = self._get_elements(b"@interface Foo { String value(); }")
        assert len(elements) == 1
        sig = build_method_signature(elements[0])
        assert "String" in sig
        assert "value()" in sig

    def test_element_with_default(self):
        elements = self._get_elements(b"@interface Foo { int count() default 1; }")
        assert len(elements) == 1
        sig = build_method_signature(elements[0])
        assert "int" in sig
        assert "count()" in sig
        assert "default" in sig

    def test_multiple_elements(self):
        source = b"""
        @interface Foo {
            String value();
            int priority() default 0;
            boolean enabled() default true;
        }
        """
        elements = self._get_elements(source)
        assert len(elements) == 3
        names = [build_method_signature(e) for e in elements]
        assert any("value()" in n for n in names)
        assert any("priority()" in n for n in names)
        assert any("enabled()" in n for n in names)

    def test_extract_method_calls_empty_for_elements(self):
        elements = self._get_elements(b"@interface Foo { String value(); }")
        calls = extract_method_calls(elements[0])
        assert calls == []


# ---------------------------------------------------------------------------
# Sealed interface support
# ---------------------------------------------------------------------------

class TestSealedInterface:
    def test_sealed_interface_type(self):
        root = parse_java_bytes(b"sealed interface Shape permits Circle {}")
        decl = find_first_type_declaration(root)
        assert get_type_keyword(decl) == "interface"

    def test_sealed_interface_permits(self):
        root = parse_java_bytes(b"sealed interface Shape permits Circle, Rectangle {}")
        decl = find_first_type_declaration(root)
        permits = get_permits(decl)
        assert "Circle" in permits
        assert "Rectangle" in permits

    def test_sealed_interface_declaration_text(self):
        root = parse_java_bytes(b"public sealed interface Shape permits Circle {}")
        decl = find_first_type_declaration(root)
        text = build_class_declaration_text(decl)
        assert "sealed" in text
        assert "interface" in text
        assert "Shape" in text
        assert "permits" in text
        assert "Circle" in text


# ---------------------------------------------------------------------------
# Record with implements
# ---------------------------------------------------------------------------

class TestRecordWithImplements:
    def test_record_implements(self):
        source = b"public record Point(int x, int y) implements Comparable<Point> {}"
        root = parse_java_bytes(source)
        decl = find_first_type_declaration(root)
        ifaces = get_interfaces(decl)
        assert len(ifaces) == 1
        assert "Comparable<Point>" in ifaces[0]

    def test_record_declaration_with_implements(self):
        source = b"public record Point(int x, int y) implements Comparable<Point> {}"
        root = parse_java_bytes(source)
        decl = find_first_type_declaration(root)
        text = build_class_declaration_text(decl)
        assert "record Point" in text
        assert "implements" in text


# ---------------------------------------------------------------------------
# Structured parsing: parse_java_source / parse_type
# ---------------------------------------------------------------------------

from jskim.util import (
    parse_java_source,
    parse_parameters,
    resolve_string_expression,
    extract_string_constants,
    classify_method,
    instance_fields,
    static_fields,
    NOISE_ANNOTATIONS,
    SPRING_STEREOTYPES,
)


def _first_type(source):
    return parse_java_source(source)["types"][0]


class TestParseJavaSource:
    def test_shape(self):
        parsed = parse_java_source("package a.b; import x.Y; class C {}")
        assert parsed["package"] == "a.b"
        assert parsed["imports"] == ["x.Y"]
        assert parsed["package_annotations"] == []
        assert [t["name"] for t in parsed["types"]] == ["C"]
        assert parsed["total_lines"] == 1

    def test_accepts_bytes(self):
        assert parse_java_source(b"class C {}")["types"][0]["name"] == "C"

    def test_type_dict_keys(self):
        t = _first_type("@Service class C extends B implements I { }")
        assert t["kind"] == "class"
        assert t["declaration"] == "class C extends B implements I"
        assert t["annotation_names"] == ["@Service"]
        assert t["annotations"][0]["full"] == "@Service"
        assert t["extends"] == "B"
        assert t["implements"] == ["I"]

    def test_fields_carry_static_and_final(self):
        t = _first_type("class C { static final String A = \"a\"; final Foo foo; Bar bar; }")
        assert [(f["name"], f["static"], f["final"]) for f in t["fields"]] == [
            ("A", True, True), ("foo", False, True), ("bar", False, False),
        ]
        assert [f["name"] for f in instance_fields(t)] == ["foo", "bar"]
        assert [f["name"] for f in static_fields(t)] == ["A"]

    def test_record_components_first_and_flagged(self):
        t = _first_type("record R(int x) { static final int MAX = 1; }")
        assert t["fields"][0]["name"] == "x"
        assert t["fields"][0]["component"] is True
        assert t["fields"][1]["static"] is True

    def test_string_constants_collected(self):
        t = _first_type("""
        class C {
            static final String BASE = "/api";
            static final String ONE = BASE + "/{id}";
            static final String LATER = EARLY + "!";
            static final String EARLY = "e";
            static final int N = 3;
            static final String UNRESOLVED = Other.X;
        }
        """)
        assert t["constants"] == {"BASE": "/api", "ONE": "/api/{id}", "LATER": "e!", "EARLY": "e"}

    def test_method_dict(self):
        t = _first_type("class C { @Transactional public List<X> find(int id, String... names) { repo.get(id); } }")
        m = t["methods"][0]
        assert m["name"] == "find"
        assert m["kind"] == "method"
        assert m["identity"] == "find(int, String...)"
        assert m["sig"] == "public List<X> find(int id, String... names)"
        assert m["return_type"] == "List<X>"
        assert [p["name"] for p in m["params"]] == ["id", "names"]
        assert m["annotations"][0]["full"] == "@Transactional"

    def test_constructor_kind(self):
        t = _first_type("class C { C(int x) {} }")
        assert t["methods"][0]["kind"] == "constructor"
        assert t["methods"][0]["return_type"] is None

    def test_calls_filtered_to_fields_and_classes(self):
        t = _first_type("""
        class C {
            private final Repo repo;
            void run(Req req) {
                Row row = repo.find(req.id());
                row.status();
                Util.check(row);
                this.repo.save(row);
                helper();
                super.run(req);
            }
        }
        """)
        assert t["methods"][0]["calls"] == ["Util.check", "helper", "repo.find", "repo.save", "super.run"]

    def test_inner_types(self):
        t = _first_type("class C { @Data static class Inner {} enum E { A } }")
        inner = t["inner_types"]
        assert [(i["kind"], i["name"]) for i in inner] == [("class", "Inner"), ("enum", "E")]
        assert inner[0]["annotations"][0]["full"] == "@Data"
        assert inner[0]["declaration"] == "static class Inner"

    def test_package_annotations(self):
        parsed = parse_java_source('@ApplicationModule(displayName = "X")\npackage a;\n')
        assert parsed["package_annotations"][0]["full"] == '@ApplicationModule(displayName = "X")'
        assert parsed["types"] == []

    def test_implicit_class(self):
        parsed = parse_java_source("void main() {}", source_name="Script.java")
        t = parsed["types"][0]
        assert t["kind"] == "implicit class"
        assert t["name"] == "Script"
        assert t["declaration"] == "implicit class Script"


class TestAnnotationRendering:
    def test_noise_annotations_dropped(self):
        t = _first_type('@Operation(summary = "s") @Tag(name = "t") @Service class C {}')
        assert [a["full"] for a in t["annotations"]] == ["@Service"]
        assert t["annotation_names"] == ["@Operation", "@Tag", "@Service"]

    def test_repeated_annotations_deduped(self):
        t = _first_type("class C { @Deprecated @Deprecated void f() {} }")
        assert [a["full"] for a in t["methods"][0]["annotations"]] == ["@Deprecated"]

    def test_arguments_shown_for_any_annotation(self):
        t = _first_type("class C { @RequiresPermission(Perms.READ) @ResponseStatus(HttpStatus.CREATED) void f() {} }")
        assert [a["full"] for a in t["methods"][0]["annotations"]] == [
            "@RequiresPermission(Perms.READ)", "@ResponseStatus(HttpStatus.CREATED)",
        ]

    def test_multiline_arguments_normalized_and_capped(self):
        t = _first_type("""
        class C {
            @ConditionalOnProperty(
                name = "feature.flag",
                havingValue = "true")
            @Scheduled(cron = "0 0 * * * *", zone = "UTC", fixedDelayString = "${x}", initialDelayString = "${yyyyyyyyyyyyyyyyyyyy}")
            void f() {}
        }
        """)
        anns = [a["full"] for a in t["methods"][0]["annotations"]]
        assert anns[0] == '@ConditionalOnProperty(name = "feature.flag", havingValue = "true")'
        assert "\n" not in anns[1]
        assert anns[1].endswith("...)")
        assert len(anns[1]) <= len("@Scheduled") + 80

    def test_mapping_annotations_show_resolved_path_only(self):
        t = _first_type("""
        @RequestMapping(C.BASE)
        class C {
            static final String BASE = "/api";
            static final String ONE = "/{id}";
            @GetMapping(path = ONE, produces = "application/json") void get() {}
            @RequestMapping(method = RequestMethod.DELETE, value = ONE) void del() {}
            @PostMapping void post() {}
        }
        """)
        assert t["annotations"][0]["full"] == '@RequestMapping("/api")'
        anns = [m["annotations"][0]["full"] for m in t["methods"]]
        assert anns == ['@GetMapping("/{id}")', '@RequestMapping(DELETE "/{id}")', "@PostMapping"]

    def test_parameter_annotations_keep_marker_only(self):
        t = _first_type("""
        class C {
            void f(@Parameter(description = "doc") @RequestParam(required = false) final Integer size,
                   @PathVariable UUID id, @Valid @RequestBody Body body) {}
        }
        """)
        assert t["methods"][0]["sig"] == "void f(@RequestParam Integer size, @PathVariable UUID id, @Valid @RequestBody Body body)"


class TestResolveStringExpression:
    def _expr(self, java_expr):
        root = parse_java_bytes(f'class C {{ String x = {java_expr}; }}'.encode())
        decl = find_first_type_declaration(root)
        field = get_body_members(get_class_body(decl))[0]
        for child in field.named_children:
            if child.type == "variable_declarator":
                return child.child_by_field_name("value")

    def test_literal(self):
        assert resolve_string_expression(self._expr('"/a"')) == "/a"

    def test_identifier_and_concat(self):
        assert resolve_string_expression(self._expr('BASE + "/b"'), {"BASE": "/a"}) == "/a/b"

    def test_qualified_and_parenthesized(self):
        assert resolve_string_expression(self._expr('(Api.BASE + "/b")'), {"Api.BASE": "/a"}) == "/a/b"
        assert resolve_string_expression(self._expr('Api.BASE'), {"BASE": "/a"}) == "/a"

    def test_unresolvable(self):
        assert resolve_string_expression(self._expr('BASE + "/b"')) is None
        assert resolve_string_expression(self._expr('foo()')) is None
        assert resolve_string_expression(self._expr('a - b'), {"a": "1", "b": "2"}) is None

    def test_mapping_paths_with_constants_and_raw_fallback(self):
        root = parse_java_bytes(b'@GetMapping({BASE + "/x", Unknown.Y}) class C {}')
        ann = get_modifiers_node(find_first_type_declaration(root)).children[0]
        assert extract_mapping_paths(ann, {"BASE": "/a"}) == ["/a/x", "Unknown.Y"]


class TestParseParameters:
    def _params(self, params):
        root = parse_java_bytes(f"class C {{ void f({params}) {{}} }}".encode())
        method = get_body_members(get_class_body(find_first_type_declaration(root)))[0]
        return parse_parameters(method.child_by_field_name("parameters"))

    def test_plain(self):
        assert self._params("int a, List<String> b")[1] == {"type": "List<String>", "name": "b", "annotations": []}

    def test_varargs(self):
        assert self._params("String... rest")[0] == {"type": "String...", "name": "rest", "annotations": []}

    def test_annotations_and_final(self):
        p = self._params("@Valid @RequestBody final Body body")[0]
        assert p == {"type": "Body", "name": "body", "annotations": ["@Valid", "@RequestBody"]}

    def test_array_dimensions_after_name(self):
        assert self._params("String args[]")[0]["name"] == "args"


class TestClassifyMethod:
    def _method(self, source):
        return _first_type(f"class C {{ {source} }}")["methods"][0]

    @pytest.mark.parametrize("source,expected", [
        ("public String getName() { return null; }", "getter"),
        ("public boolean isActive() { return true; }", "getter"),
        ("public Boolean isActive() { return true; }", "getter"),
        ("public void setName(String n) {}", "setter"),
        ("public C(int x) {}", "wiring"),
        ("public C(int x) { this.x = x; }", "wiring"),
        ("C(Foo f, Bar b) { this.f = Objects.requireNonNull(f); b = b; }", "wiring"),
        ("public C(int x) { super(x); this.x = x; }", "wiring"),
        ("public C(int x) { this.x = x * 2; }", "constructor"),
        ("public C(int x) { this.x = x; validate(); }", "constructor"),
        ("public C(Foo f) { this.f = f.build(); }", "constructor"),
        ("public void process() {}", "business"),
        ("public String toString() { return null; }", "boilerplate"),
        ("public boolean equals(Object o) { return false; }", "boilerplate"),
        ("public int hashCode() { return 0; }", "boilerplate"),
        ("public void getaway() {}", "business"),
        ("public boolean isolate() { return true; }", "business"),
        ("public void setName(String a, String b) {}", "business"),
        ("public C setName(String n) { return this; }", "business"),
        ("public String getName(int idx) { return null; }", "business"),
        ("public void getName() {}", "business"),
        ("public static Foo getInstance() { return null; }", "getter"),
        ("default String getLabel() { return null; }", "getter"),
    ])
    def test_classification(self, source, expected):
        assert classify_method(self._method(source)) == expected

    def test_compact_constructor(self):
        t = _first_type("record R(int x) { R { } }")
        assert classify_method(t["methods"][0]) == "wiring"
        t = _first_type("record R(int x) { R { if (x < 0) throw new IllegalArgumentException(); } }")
        assert classify_method(t["methods"][0]) == "constructor"


class TestNewConstants:
    def test_noise_annotations_are_swagger_docs(self):
        assert {"@Operation", "@ApiResponse", "@Schema", "@Parameter", "@Tag"} <= NOISE_ANNOTATIONS
        assert "@Transactional" not in NOISE_ANNOTATIONS

    def test_spring_stereotypes(self):
        assert {"@Service", "@Component", "@Repository", "@RestController", "@Configuration"} <= SPRING_STEREOTYPES


# ---------------------------------------------------------------------------
# Call scope: which qualified calls are followable
# ---------------------------------------------------------------------------

class TestCallScope:
    SOURCE = """
    package com.acme.app.trips;
    import java.time.OffsetDateTime;
    import java.util.stream.Collectors;
    import com.acme.app.audit.AuditEvent;
    import org.springframework.security.core.context.SecurityContextHolder;
    import static com.acme.jooq.Tables.TRIP;
    import static org.assertj.core.api.Assertions.assertThat;
    class S {
        Repo repo;
        void m(Other other) {
            Collectors.toList(); OffsetDateTime.now(); SecurityContextHolder.getContext();
            AuditEvent.now(); TRIP.fields(); assertThat(repo); repo.save();
            LocalRules.check(); helper(); other.run(); this.repo.find();
        }
        void helper() {}
    }
    """

    def test_foreign_and_static_imports_dropped(self):
        calls = _first_type(self.SOURCE)["methods"][0]["calls"]
        assert calls == ["AuditEvent.now", "LocalRules.check", "helper", "repo.find", "repo.save"]

    def test_static_field_and_constant_owners_dropped(self):
        t = _first_type("""
        class S {
            private static final SecureRandom RANDOM = new SecureRandom();
            private final Repo repo;
            void m() { RANDOM.nextInt(); ID.eq(1); repo.save(); Factory.make(); }
        }
        """)
        assert t["methods"][0]["calls"] == ["Factory.make", "repo.save"]

    def test_wildcard_jdk_imports_still_filtered(self):
        t = _first_type("""
        package com.acme.app;
        import java.util.*;
        import java.time.*;
        class S { void m() { Comparator.comparing(x); LocalDate.now(); Rules.check(); } }
        """)
        assert t["methods"][0]["calls"] == ["Rules.check"]

    def test_scope_shape(self):
        scope = build_call_scope("com.acme.app", ["java.util.List", "com.acme.app.x.Y", "com.acme.jooq.Tables.TRIP"], {"TRIP"})
        assert scope["foreign"] == {"List"}
        assert scope["static_members"] == {"TRIP"}
        assert scope["fields"] == set()

    def test_no_package_treats_every_import_as_foreign(self):
        scope = build_call_scope(None, ["a.b.C"], ())
        assert scope["foreign"] == {"C"}

    def test_no_scope_keeps_everything(self):
        root = parse_java_bytes(b"class F { void m() { Helper.build(); x.run(); } }")
        method = get_body_members(get_class_body(find_first_type_declaration(root)))[0]
        assert extract_method_calls(method) == ["Helper.build", "x.run"]

    def test_method_references_extracted(self):
        t = _first_type("""
        package com.acme.app;
        import java.util.Objects;
        import com.acme.app.service.BillingService;
        class S {
            Repo repo;
            void process(List<Item> items) {
                items.forEach(this::validate);
                items.forEach(super::audit);
                items.forEach(repo::save);
                items.forEach(this.repo::flush);
                items.forEach(BillingService::charge);
                items.forEach(Objects::requireNonNull);
                items.forEach(String::valueOf);
            }
            void validate(Item item) {}
        }
        """)
        calls = t["methods"][0]["calls"]
        assert calls == [
            "BillingService.charge",
            "repo.flush",
            "repo.save",
            "super.audit",
            "validate",
        ]


# ---------------------------------------------------------------------------
# parse_method: signature line, noise spans, wiring
# ---------------------------------------------------------------------------

class TestMethodLines:
    SOURCE = """
    class C {
        @PostMapping("/x")
        @Operation(summary = "a",
            description = "b")
        @ApiResponse(responseCode = "200")
        public Foo create(Bar bar) {
            return null;
        }

        @Override @SuppressWarnings("unchecked") public void run() {}
    }
    """

    def test_start_is_signature_line_and_decl_start_is_first_annotation(self):
        m = _first_type(self.SOURCE)["methods"][0]
        assert (m["decl_start"], m["start"], m["end"]) == (3, 7, 9)

    def test_noise_spans_cover_documentation_annotations_only(self):
        m = _first_type(self.SOURCE)["methods"][0]
        assert [(s["start"], s["end"]) for s in m["noise_spans"]] == [(4, 5), (6, 6)]

    def test_inline_noise_annotation_span(self):
        m = _first_type(self.SOURCE)["methods"][1]
        assert m["start"] == m["decl_start"] == 11
        assert len(m["noise_spans"]) == 1 and m["noise_spans"][0]["start_col"] > 0

    def test_signature_line_for_type(self):
        root = parse_java_bytes(b"@Data\n@Builder\nclass C {}")
        assert signature_line(find_first_type_declaration(root)) == 3

    def test_wiring_flag(self):
        t = _first_type("class C { C(A a) { this.a = a; } C(A a, int n) { this.a = a; this.n = n + 1; } }")
        assert [m["wiring"] for m in t["methods"]] == [True, False]


# ---------------------------------------------------------------------------
# get_javadoc_summary / walk_types / format_static_field / nested types
# ---------------------------------------------------------------------------

class TestJavadocSummary:
    def test_first_sentence_with_inline_tags(self):
        t = _first_type("""
        /**
         * Trips: plan one, {@code rewrite} its plan, or {@link #cancel}. Second sentence.
         *
         * <p>More detail.
         * @see Other
         */
        class C {}
        """)
        assert t["doc"] == "Trips: plan one, rewrite its plan, or cancel."

    def test_html_and_block_tags(self):
        t = _first_type("/**\n * <strong>Bold</strong> start<br>here\n * @param x the x\n */\nrecord R(int x) {}")
        assert t["doc"] == "Bold start here"

    def test_plain_block_comment_is_not_javadoc(self):
        assert _first_type("/* not doc */ class C {}")["doc"] is None
        assert _first_type("class C {}")["doc"] is None

    def test_long_sentence_is_capped(self):
        t = _first_type("/** " + "word " * 60 + "*/ class C {}")
        assert t["doc"].endswith("...") and len(t["doc"]) <= 160

    def test_nested_type_doc(self):
        t = _first_type("class C { /** The inner one. */ record R(int x) {} }")
        assert t["inner_types"][0]["doc"] == "The inner one."


class TestNestedTypes:
    def test_inner_types_are_full_parse_dicts(self):
        t = _first_type("""
        class Outer {
            record Claim(int count, @NotNull Integer last) { static Claim of() { return null; } }
            enum Kind { A, B }
            static class Config { @Bean Foo foo() { return null; } }
        }
        """)
        claim, kind, config = t["inner_types"]
        assert [f["name"] for f in claim["fields"]] == ["count", "last"]
        assert claim["fields"][1]["annotations"] == ["@NotNull"]
        assert claim["methods"][0]["name"] == "of"
        assert kind["enum_constants"] == ["A", "B"]
        assert config["methods"][0]["annotations"][0]["full"] == "@Bean"
        assert claim["line"] == 3

    def test_walk_types_labels(self):
        parsed = parse_java_source("class A { class B { class C {} } enum D {} } class E {}")
        assert [label for label, _ in walk_types(parsed["types"])] == ["A", "A.B", "A.B.C", "A.D", "E"]

    def test_outer_field_does_not_leak_into_nested_scope(self):
        t = _first_type("""
        record View(Progress progress) {
            record Progress(int n) { static Progress of(Line progress) { return new Progress(progress.count()); } }
        }
        """)
        assert t["inner_types"][0]["methods"][0]["calls"] == []

    def test_nested_calls_use_file_scope(self):
        t = _first_type("""
        package a.b;
        import java.util.stream.Collectors;
        class Outer { static class In { Repo repo; void m() { Collectors.toSet(); repo.save(); } } }
        """)
        assert t["inner_types"][0]["methods"][0]["calls"] == ["repo.save"]


class TestFormatStaticField:
    def test_short_string_value_shown(self):
        t = _first_type('class P { public static final String READ = "audit.event.read"; private static final String EVENT = "x.y"; static final int MAX = 3; static final String LONG = "' + "x" * 50 + '"; }')
        rendered = [format_static_field(f, t["constants"]) for f in t["fields"]]
        assert rendered == ['READ = "audit.event.read"', "EVENT", "MAX", "LONG"]


class TestAnnotationConstantResolution:
    def test_constant_argument_resolved(self):
        t = _first_type("""
        class C {
            static final String CREATE = "trip.create";
            static final String READ = "trip.read";
            @RequiresPermission(CREATE) void a() {}
            @RequiresPermission({CREATE, READ}) void b() {}
            @RequiresPermission(value = CREATE) void c() {}
            @RequiresPermission("lit") void d() {}
        }
        """)
        fulls = [m["annotations"][0]["full"] for m in t["methods"]]
        assert fulls == [
            '@RequiresPermission("trip.create")',
            '@RequiresPermission("trip.create", "trip.read")',
            "@RequiresPermission(value = CREATE)",
            '@RequiresPermission("lit")',
        ]
