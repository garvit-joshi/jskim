"""Tests for jskim.util — shared tree-sitter parsing utilities."""

import pytest
from jskim.util import (
    parse_java_bytes,
    get_annotations,
    get_annotations_rich,
    build_method_signature,
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
    get_enum_constants,
    is_field_final,
    is_field_static,
    extract_method_calls,
    get_annotation_name_from_node,
    extract_mapping_paths,
    extract_request_method,
    extract_first_annotation_string,
    INNER_TYPE_NODES,
    METHOD_NODES,
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
            "compact_constructor_declaration",
        }
        assert METHOD_NODES == expected

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
