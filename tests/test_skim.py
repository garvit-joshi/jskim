"""Tests for jskim.skim — single file summarization."""

import pytest
from jskim.skim import categorize_imports, classify_method, parse_java, format_output
from tests.conftest import load_fixture, fixture_path


# ---------------------------------------------------------------------------
# categorize_imports
# ---------------------------------------------------------------------------

class TestCategorizeImports:
    def test_empty(self):
        assert categorize_imports([]) == {}

    def test_java_core(self):
        imports = ["java.util.List", "java.util.Map", "java.io.IOException"]
        cats = categorize_imports(imports)
        assert cats["java.util"] == 2
        assert cats["java.io"] == 1

    def test_javax_imports(self):
        imports = ["javax.sql.DataSource"]
        cats = categorize_imports(imports)
        assert cats["javax.sql"] == 1

    def test_jakarta_imports(self):
        imports = ["jakarta.persistence.Entity", "jakarta.persistence.Column"]
        cats = categorize_imports(imports)
        assert cats["jakarta.persistence"] == 2

    def test_third_party(self):
        imports = [
            "org.springframework.stereotype.Service",
            "org.springframework.beans.factory.annotation.Autowired",
            "lombok.extern.slf4j.Slf4j",
        ]
        cats = categorize_imports(imports)
        assert cats["org.springframework.stereotype"] == 1
        assert cats["org.springframework.beans"] == 1
        assert cats["lombok.extern.slf4j"] == 1

    def test_short_import(self):
        imports = ["com"]
        cats = categorize_imports(imports)
        assert cats["com"] == 1


# ---------------------------------------------------------------------------
# classify_method
# ---------------------------------------------------------------------------

class TestClassifyMethod:
    def test_simple_getter(self):
        assert classify_method("public String getName()") == "getter"

    def test_boolean_getter(self):
        assert classify_method("public boolean isActive()") == "getter"

    def test_simple_setter(self):
        assert classify_method("public void setName(String name)") == "setter"

    def test_constructor(self):
        assert classify_method("public MyClass(int x)") == "constructor"

    def test_business_method(self):
        assert classify_method("public void processOrder(Order order)") == "business"

    def test_boilerplate_toString(self):
        assert classify_method("public String toString()") == "boilerplate"

    def test_boilerplate_equals(self):
        assert classify_method("public boolean equals(Object o)") == "boilerplate"

    def test_boilerplate_hashCode(self):
        assert classify_method("public int hashCode()") == "boilerplate"

    def test_getaway_not_getter(self):
        """getaway() is a word, not get+Away — should be business."""
        assert classify_method("public String getaway()") == "business"

    def test_isolate_not_getter(self):
        """isolate() is a word, not is+Olate — should be business."""
        assert classify_method("public boolean isolate()") == "business"

    def test_setter_with_multiple_params_is_business(self):
        assert classify_method("public void setCoordinates(int x, int y)") == "business"

    def test_setter_returning_non_void_is_business(self):
        assert classify_method("public MyClass setName(String name)") == "business"

    def test_getter_with_params_is_business(self):
        assert classify_method("public String getName(int id)") == "business"

    def test_void_getter_is_business(self):
        assert classify_method("public void getName()") == "business"

    def test_static_method(self):
        assert classify_method("public static void main(String[] args)") == "business"

    def test_default_method(self):
        assert classify_method("default boolean isSingleTrip(Input input)") == "business"

    def test_Boolean_wrapper_getter(self):
        assert classify_method("public Boolean isValid()") == "getter"

    def test_no_parens_constructor(self):
        """Compact constructor in records."""
        assert classify_method("public Coordinate") == "constructor"


# ---------------------------------------------------------------------------
# parse_java — with fixture files
# ---------------------------------------------------------------------------

class TestParseJava:
    def test_simple_class(self):
        content = "package com.example; public class Foo { private int x; public void bar() {} }"
        parsed = parse_java(content)
        assert parsed["package"] == "com.example"
        assert len(parsed["fields"]) == 1
        assert len(parsed["methods"]) == 1

    def test_enum_constants(self):
        content = load_fixture("SimpleDirection.java")
        parsed = parse_java(content)
        assert parsed["package"] == "com.example"
        assert "NORTH" in parsed["enum_constants"]
        assert "SOUTH" in parsed["enum_constants"]
        assert "EAST" in parsed["enum_constants"]
        assert "WEST" in parsed["enum_constants"]
        assert len(parsed["methods"]) == 2  # isVertical, isHorizontal

    def test_enum_with_body_methods(self):
        content = load_fixture("StatusEnum.java")
        parsed = parse_java(content)
        assert "ACTIVE" in parsed["enum_constants"]
        assert "PENDING" in parsed["enum_constants"]
        assert "DONE" in parsed["enum_constants"]
        methods = [m["sig"] for m in parsed["methods"]]
        assert any("getLabel" in m for m in methods)
        assert any("isTerminal" in m for m in methods)

    def test_class_with_lombok(self):
        content = load_fixture("StaticFieldService.java")
        parsed = parse_java(content)
        assert "@Slf4j" in parsed["class_annotations"]
        assert "@Service" in parsed["class_annotations"]
        assert "@RequiredArgsConstructor" in parsed["class_annotations"]
        assert len(parsed["lombok_notes"]) > 0

    def test_interface_parsing(self):
        content = load_fixture("BillingCalculator.java")
        parsed = parse_java(content)
        assert "interface" in parsed["class_declaration"]
        methods = [m["sig"] for m in parsed["methods"]]
        assert any("calculate" in m for m in methods)
        assert any("isSingleEscortTrip" in m for m in methods)
        assert any("zeroCostResult" in m for m in methods)

    def test_multi_variable_fields(self):
        content = load_fixture("EdgeCaseBugs.java")
        parsed = parse_java(content)
        field_names = [f["name"] for f in parsed["fields"]]
        assert "x" in field_names
        assert "y" in field_names
        assert "z" in field_names
        assert "firstName" in field_names
        assert "lastName" in field_names

    def test_inner_types(self):
        content = load_fixture("EdgeCaseBugs.java")
        parsed = parse_java(content)
        inner_decls = [t["declaration"] for t in parsed["inner_types"]]
        assert any("Coordinate" in d for d in inner_decls)
        assert any("ValidInput" in d for d in inner_decls)

    def test_extra_types(self):
        content = load_fixture("SealedAndMultiClass.java")
        parsed = parse_java(content)
        assert len(parsed["extra_types"]) == 2
        extra_names = [e["class_declaration"] for e in parsed["extra_types"]]
        assert any("Circle" in n for n in extra_names)
        assert any("Rectangle" in n for n in extra_names)

    def test_sealed_class(self):
        content = load_fixture("SealedAndMultiClass.java")
        parsed = parse_java(content)
        assert "sealed" in parsed["class_declaration"]
        assert "permits" in parsed["class_declaration"]

    def test_lambda_fields(self):
        content = load_fixture("LambdaFields.java")
        parsed = parse_java(content)
        field_names = [f["name"] for f in parsed["fields"]]
        assert "comp" in field_names
        assert "task" in field_names
        assert "parser" in field_names
        assert "reversed" in field_names

    def test_anon_class_fields(self):
        content = load_fixture("AnonClassFields.java")
        parsed = parse_java(content)
        field_names = [f["name"] for f in parsed["fields"]]
        assert "task" in field_names
        assert "map" in field_names
        assert "custom" in field_names

    def test_text_block_fields(self):
        content = load_fixture("TextBlockTest.java")
        parsed = parse_java(content)
        field_names = [f["name"] for f in parsed["fields"]]
        assert "query" in field_names
        assert "simple" in field_names
        assert "html" in field_names

    def test_switch_expr_fields(self):
        content = load_fixture("SwitchExprFields.java")
        parsed = parse_java(content)
        field_names = [f["name"] for f in parsed["fields"]]
        assert "x" in field_names
        assert "label" in field_names
        assert "category" in field_names

    def test_configuration_with_beans(self):
        content = load_fixture("AppConfiguration.java")
        parsed = parse_java(content)
        assert "@Configuration" in parsed["class_annotations"]
        methods = [m["sig"] for m in parsed["methods"]]
        assert any("objectMapper" in m for m in methods)
        assert any("httpClient" in m for m in methods)
        assert any("taskScheduler" in m for m in methods)

    def test_jooq_enum(self):
        content = load_fixture("ContractType.java")
        parsed = parse_java(content)
        assert "PACKAGE" in parsed["enum_constants"]
        assert "SLAB" in parsed["enum_constants"]
        assert "TRIP" in parsed["enum_constants"]
        assert "ZONE" in parsed["enum_constants"]

    def test_static_initializer(self):
        content = load_fixture("Role.java")
        parsed = parse_java(content)
        assert len(parsed["static_initializers"]) > 0

    def test_method_calls_extracted(self):
        content = load_fixture("ScheduleServiceProxy.java")
        parsed = parse_java(content)
        # Find the fetchOfficesForBusinessUnitId method
        method = next(
            m for m in parsed["methods"]
            if "fetchOfficesForBusinessUnitId" in m["sig"]
        )
        assert len(method["calls"]) > 0

    def test_complex_mixed_file(self):
        content = load_fixture("ComplexMixed.java")
        parsed = parse_java(content)
        assert "@Entity" in parsed["class_annotations"]
        assert "@Data" in parsed["class_annotations"]
        field_names = [f["name"] for f in parsed["fields"]]
        assert "userName" in field_names
        assert "roles" in field_names

    def test_method_annotations(self):
        content = load_fixture("CabUpdateKafkaConsumer.java")
        parsed = parse_java(content)
        method = parsed["methods"][0]
        assert any("@KafkaListener" in a for a in method["annotations"])

    def test_inline_annotations(self):
        content = load_fixture("InlineAnnotations.java")
        parsed = parse_java(content)
        assert len(parsed["fields"]) > 5
        assert len(parsed["methods"]) > 0

    def test_nested_annotations(self):
        content = load_fixture("NestedAnnotations.java")
        parsed = parse_java(content)
        assert len(parsed["fields"]) > 3
        assert len(parsed["methods"]) > 0

    def test_total_lines(self):
        content = "class Foo {\n    int x;\n    void bar() {}\n}"
        parsed = parse_java(content)
        assert parsed["total_lines"] == 4

    def test_record_components_as_fields(self):
        content = "package com.example; public record UserDTO(String name, int age) {}"
        parsed = parse_java(content)
        field_names = [f["name"] for f in parsed["fields"]]
        assert "name" in field_names
        assert "age" in field_names
        field_types = [f["type"] for f in parsed["fields"]]
        assert "String" in field_types
        assert "int" in field_types

    def test_generic_record_components(self):
        content = "package com.example; public record Response<T>(T data, String message, int code) {}"
        parsed = parse_java(content)
        assert len(parsed["fields"]) == 3
        field_names = [f["name"] for f in parsed["fields"]]
        assert "data" in field_names
        assert "message" in field_names
        assert "code" in field_names

    def test_record_with_body_methods(self):
        content = """
        package com.example;
        public record Point(int x, int y) {
            public double distance() { return Math.sqrt(x * x + y * y); }
        }
        """
        parsed = parse_java(content)
        assert len(parsed["fields"]) == 2
        assert len(parsed["methods"]) == 1
        assert "distance" in parsed["methods"][0]["sig"]

    def test_implicitly_declared_class(self):
        content = 'void main() { System.out.println("Hello"); }'
        parsed = parse_java(content)
        assert parsed["class_declaration"] == "implicit class"
        assert len(parsed["methods"]) == 1
        assert parsed["methods"][0]["sig"] == "void main()"
        assert parsed["total_lines"] == 1

    def test_generic_type_in_declaration(self):
        content = "package com.example; public class Container<T extends Comparable<T>> {}"
        parsed = parse_java(content)
        assert "Container<T extends Comparable<T>>" in parsed["class_declaration"]

    def test_annotation_type_elements(self):
        content = load_fixture("AnnotationType.java")
        parsed = parse_java(content)
        assert "@interface" in parsed["class_declaration"]
        sigs = [m["sig"] for m in parsed["methods"]]
        assert any("value()" in s for s in sigs)
        assert any("priority()" in s for s in sigs)
        assert any("tags()" in s for s in sigs)
        assert any("enabled()" in s for s in sigs)

    def test_sealed_interface(self):
        content = """
        package com.example;
        public sealed interface Shape permits Circle, Rectangle {
            double area();
        }
        """
        parsed = parse_java(content)
        assert "sealed" in parsed["class_declaration"]
        assert "interface" in parsed["class_declaration"]
        assert "permits" in parsed["class_declaration"]

    def test_modern_java_features_fixture(self):
        content = load_fixture("ModernJavaFeatures.java")
        parsed = parse_java(content)
        assert "sealed" in parsed["class_declaration"]
        assert "Shape<T>" in parsed["class_declaration"]
        assert len(parsed["extra_types"]) >= 3


# ---------------------------------------------------------------------------
# format_output
# ---------------------------------------------------------------------------

class TestFormatOutput:
    def test_basic_output_structure(self):
        content = load_fixture("SimpleDirection.java")
        parsed = parse_java(content)
        output = format_output(parsed, "SimpleDirection.java")
        lines = output.split("\n")
        assert lines[0] == "// SimpleDirection.java"
        assert any("total:" in l for l in lines)

    def test_enum_constants_in_output(self):
        content = load_fixture("SimpleDirection.java")
        parsed = parse_java(content)
        output = format_output(parsed, "SimpleDirection.java")
        assert "constants:" in output
        assert "NORTH" in output

    def test_lombok_in_output(self):
        content = load_fixture("StaticFieldService.java")
        parsed = parse_java(content)
        output = format_output(parsed, "StaticFieldService.java")
        assert "lombok:" in output

    def test_fields_in_output(self):
        content = load_fixture("StaticFieldService.java")
        parsed = parse_java(content)
        output = format_output(parsed, "StaticFieldService.java")
        assert "fields:" in output

    def test_methods_in_output(self):
        content = load_fixture("StaticFieldService.java")
        parsed = parse_java(content)
        output = format_output(parsed, "StaticFieldService.java")
        assert "methods:" in output
        assert "processOrder" in output

    def test_getter_collapsed(self):
        content = load_fixture("LambdaEdgeCases.java")
        parsed = parse_java(content)
        output = format_output(parsed, "LambdaEdgeCases.java")
        assert "getters:" in output
        assert "getName" in output

    def test_boilerplate_collapsed(self):
        content = load_fixture("EdgeCaseBugs.java")
        parsed = parse_java(content)
        output = format_output(parsed, "EdgeCaseBugs.java")
        assert "boilerplate:" in output
        assert "toString" in output

    def test_inner_types_in_output(self):
        content = load_fixture("EdgeCaseBugs.java")
        parsed = parse_java(content)
        output = format_output(parsed, "EdgeCaseBugs.java")
        assert "inner types:" in output

    def test_extra_types_in_output(self):
        content = load_fixture("SealedAndMultiClass.java")
        parsed = parse_java(content)
        output = format_output(parsed, "SealedAndMultiClass.java")
        assert "other classes in file:" in output
        assert "Circle" in output
        assert "Rectangle" in output

    def test_static_initializer_in_output(self):
        content = load_fixture("Role.java")
        parsed = parse_java(content)
        output = format_output(parsed, "Role.java")
        assert "static initializer" in output

    def test_grep_filter(self):
        content = load_fixture("ScheduleServiceProxy.java")
        parsed = parse_java(content)
        output = format_output(parsed, "ScheduleServiceProxy.java", grep="fetch")
        # Only methods matching "fetch" should appear in business methods
        lines = output.split("\n")
        method_lines = [l for l in lines if "lines):" in l]
        assert len(method_lines) > 0, "grep filter should still show matching methods"
        for ml in method_lines:
            assert "fetch" in ml.lower(), f"Non-matching method leaked through grep filter: {ml}"

    def test_annotation_filter(self):
        content = load_fixture("AppConfiguration.java")
        parsed = parse_java(content)
        output = format_output(parsed, "AppConfiguration.java", annotation="@Bean")
        # Only @Bean methods should appear
        lines = output.split("\n")
        method_lines = [l for l in lines if "lines):" in l]
        for ml in method_lines:
            assert "@Bean" in ml

    def test_method_call_tracing_in_output(self):
        content = load_fixture("ScheduleServiceProxy.java")
        parsed = parse_java(content)
        output = format_output(parsed, "ScheduleServiceProxy.java")
        # Method calls should show with →
        assert "→" in output

    def test_many_enum_constants_truncated(self):
        content = load_fixture("Role.java")
        parsed = parse_java(content)
        output = format_output(parsed, "Role.java")
        # Role has 12 constants, should truncate
        assert "more" in output

    def test_class_annotations_in_output(self):
        content = load_fixture("CabUpdateKafkaConsumer.java")
        parsed = parse_java(content)
        output = format_output(parsed, "CabUpdateKafkaConsumer.java")
        assert "@Slf4j" in output
        assert "@Component" in output

    def test_all_comment_prefixed(self):
        """All output lines should start with //."""
        content = load_fixture("SimpleDirection.java")
        parsed = parse_java(content)
        output = format_output(parsed, "SimpleDirection.java")
        for line in output.split("\n"):
            assert line.startswith("//"), f"Line not prefixed: {line!r}"

    def test_record_fields_in_output(self):
        content = "package com.example; public record UserDTO(String name, int age) {}"
        parsed = parse_java(content)
        output = format_output(parsed, "UserDTO.java")
        assert "fields:" in output
        assert "String name" in output
        assert "int age" in output

    def test_generic_class_declaration_in_output(self):
        content = "package com.example; public class Foo<T> extends Bar<T> {}"
        parsed = parse_java(content)
        output = format_output(parsed, "Foo.java")
        assert "Foo<T>" in output
        assert "extends Bar<T>" in output

    def test_annotation_type_elements_in_output(self):
        content = load_fixture("AnnotationType.java")
        parsed = parse_java(content)
        output = format_output(parsed, "AnnotationType.java")
        assert "value()" in output
        assert "priority()" in output

    def test_implicit_class_output(self):
        content = load_fixture("ImplicitClass.java")
        parsed = parse_java(content, source_name="ImplicitClass.java")
        output = format_output(parsed, "ImplicitClass.java")
        assert output.startswith("//")
        assert "implicit class ImplicitClass" in output
        assert "void main()" in output
        assert "total:" in output


# ---------------------------------------------------------------------------
# Integration tests with real fixture files
# ---------------------------------------------------------------------------

class TestSkimFixtureFiles:
    """Test that skim can parse and format every fixture file without errors."""

    @pytest.fixture(params=[
        "AnnotationType.java",
        "AnonClassFields.java",
        "AppConfiguration.java",
        "BillingCalculator.java",
        "BillingTaskDefinitions.java",
        "BusinessUnitsDao.java",
        "CabCreationConsumerConfiguration.java",
        "CabUpdateKafkaConsumer.java",
        "ComplexMixed.java",
        "ContractType.java",
        "EdgeCaseBugs.java",
        "HealthConfiguration.java",
        "ImplicitClass.java",
        "InlineAnnotations.java",
        "LambdaEdgeCases.java",
        "LambdaFields.java",
        "MammothRawTripDataReportTaskDefinitions.java",
        "MammothRawTripRowMapper.java",
        "ModernJavaFeatures.java",
        "NestedAnnotations.java",
        "RawTripDataReportTaskDefinitions.java",
        "RawTripRowMapper.java",
        "RBDResultSetExtractor.java",
        "ReportStatus.java",
        "Role.java",
        "ScheduleServiceProxy.java",
        "SealedAndMultiClass.java",
        "SimpleDirection.java",
        "StaticFieldService.java",
        "StatusEnum.java",
        "SwitchExprFields.java",
        "TextBlockTest.java",
        "TripEndKafkaConsumer.java",
        "TripEndKafkaConsumerConfiguration.java",
    ])
    def java_file(self, request):
        return request.param

    def test_parse_and_format(self, java_file):
        content = load_fixture(java_file)
        parsed = parse_java(content)
        output = format_output(parsed, java_file)
        assert output  # non-empty
        assert output.startswith("//")
        assert "total:" in output
