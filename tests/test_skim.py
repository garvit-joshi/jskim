"""Tests for jskim.skim — single file summarization."""

import pytest
from jskim.skim import format_output
from jskim.util import parse_java_source
from tests.conftest import load_fixture


def primary(content, source_name=None):
    """Parse source and return (parsed, primary type)."""
    parsed = parse_java_source(content, source_name=source_name)
    return parsed, parsed["types"][0]


def skim(content, filepath="Test.java", **kwargs):
    parsed = parse_java_source(content, source_name=filepath)
    return format_output(parsed, filepath, **kwargs)


# ---------------------------------------------------------------------------
# parse_java_source through the skim lens
# ---------------------------------------------------------------------------

class TestParseJava:
    def test_simple_class(self):
        parsed, t = primary("package com.example; public class Foo { private int x; public void bar() {} }")
        assert parsed["package"] == "com.example"
        assert len(t["fields"]) == 1
        assert len(t["methods"]) == 1

    def test_enum_constants(self):
        parsed, t = primary(load_fixture("SimpleDirection.java"))
        assert parsed["package"] == "com.example"
        assert set(t["enum_constants"]) >= {"NORTH", "SOUTH", "EAST", "WEST"}
        assert len(t["methods"]) == 2  # isVertical, isHorizontal

    def test_enum_with_body_methods(self):
        _, t = primary(load_fixture("StatusEnum.java"))
        assert {"ACTIVE", "PENDING", "DONE"} <= set(t["enum_constants"])
        methods = [m["sig"] for m in t["methods"]]
        assert any("getLabel" in m for m in methods)
        assert any("isTerminal" in m for m in methods)

    def test_class_with_lombok(self):
        _, t = primary(load_fixture("StaticFieldService.java"))
        names = t["annotation_names"]
        assert "@Slf4j" in names
        assert "@Service" in names
        assert "@RequiredArgsConstructor" in names

    def test_interface_parsing(self):
        _, t = primary(load_fixture("BillingCalculator.java"))
        assert "interface" in t["declaration"]
        methods = [m["sig"] for m in t["methods"]]
        assert any("calculate" in m for m in methods)
        assert any("isSingleEscortTrip" in m for m in methods)
        assert any("zeroCostResult" in m for m in methods)

    def test_multi_variable_fields(self):
        _, t = primary(load_fixture("EdgeCaseBugs.java"))
        field_names = [f["name"] for f in t["fields"]]
        assert {"x", "y", "z", "firstName", "lastName"} <= set(field_names)

    def test_inner_types(self):
        _, t = primary(load_fixture("EdgeCaseBugs.java"))
        inner_decls = [i["declaration"] for i in t["inner_types"]]
        assert any("Coordinate" in d for d in inner_decls)
        assert any("ValidInput" in d for d in inner_decls)

    def test_extra_types(self):
        parsed, _ = primary(load_fixture("SealedAndMultiClass.java"))
        extra = parsed["types"][1:]
        assert len(extra) == 2
        names = [e["declaration"] for e in extra]
        assert any("Circle" in n for n in names)
        assert any("Rectangle" in n for n in names)

    def test_sealed_class(self):
        _, t = primary(load_fixture("SealedAndMultiClass.java"))
        assert "sealed" in t["declaration"]
        assert "permits" in t["declaration"]

    @pytest.mark.parametrize("fixture,expected", [
        ("LambdaFields.java", {"comp", "task", "parser", "reversed"}),
        ("AnonClassFields.java", {"task", "map", "custom"}),
        ("TextBlockTest.java", {"query", "simple", "html"}),
        ("SwitchExprFields.java", {"x", "label", "category"}),
    ])
    def test_tricky_field_initializers(self, fixture, expected):
        _, t = primary(load_fixture(fixture))
        assert expected <= {f["name"] for f in t["fields"]}

    def test_configuration_with_beans(self):
        _, t = primary(load_fixture("AppConfiguration.java"))
        assert "@Configuration" in t["annotation_names"]
        methods = [m["sig"] for m in t["methods"]]
        assert any("objectMapper" in m for m in methods)
        assert any("httpClient" in m for m in methods)
        assert any("taskScheduler" in m for m in methods)

    def test_jooq_enum(self):
        _, t = primary(load_fixture("ContractType.java"))
        assert {"PACKAGE", "SLAB", "TRIP", "ZONE"} <= set(t["enum_constants"])

    def test_static_initializer(self):
        _, t = primary(load_fixture("Role.java"))
        assert len(t["static_initializers"]) > 0

    def test_method_calls_extracted(self):
        _, t = primary(load_fixture("ScheduleServiceProxy.java"))
        method = next(m for m in t["methods"] if "fetchOfficesForBusinessUnitId" in m["sig"])
        assert len(method["calls"]) > 0

    def test_complex_mixed_file(self):
        _, t = primary(load_fixture("ComplexMixed.java"))
        assert "@Entity" in t["annotation_names"]
        assert "@Data" in t["annotation_names"]
        field_names = [f["name"] for f in t["fields"]]
        assert "userName" in field_names
        assert "roles" in field_names

    def test_method_annotations(self):
        _, t = primary(load_fixture("CabUpdateKafkaConsumer.java"))
        assert any(a["name"] == "@KafkaListener" for a in t["methods"][0]["annotations"])

    def test_inline_and_nested_annotations(self):
        _, t = primary(load_fixture("InlineAnnotations.java"))
        assert len(t["fields"]) > 5
        assert len(t["methods"]) > 0
        _, t = primary(load_fixture("NestedAnnotations.java"))
        assert len(t["fields"]) > 3
        assert len(t["methods"]) > 0

    def test_total_lines(self):
        parsed, _ = primary("class Foo {\n    int x;\n    void bar() {}\n}")
        assert parsed["total_lines"] == 4

    def test_record_components_as_fields(self):
        _, t = primary("package com.example; public record UserDTO(String name, int age) {}")
        assert [(f["type"], f["name"]) for f in t["fields"]] == [("String", "name"), ("int", "age")]
        assert all(f["component"] for f in t["fields"])

    def test_generic_record_components(self):
        _, t = primary("package com.example; public record Response<T>(T data, String message, int code) {}")
        assert [f["name"] for f in t["fields"]] == ["data", "message", "code"]

    def test_record_with_body_methods(self):
        _, t = primary("""
        package com.example;
        public record Point(int x, int y) {
            public double distance() { return Math.sqrt(x * x + y * y); }
        }
        """)
        assert len(t["fields"]) == 2
        assert len(t["methods"]) == 1
        assert "distance" in t["methods"][0]["sig"]

    def test_implicitly_declared_class(self):
        parsed, t = primary('void main() { System.out.println("Hello"); }')
        assert t["declaration"] == "implicit class"
        assert t["methods"][0]["sig"] == "void main()"
        assert parsed["total_lines"] == 1

    def test_generic_type_in_declaration(self):
        _, t = primary("package com.example; public class Container<T extends Comparable<T>> {}")
        assert "Container<T extends Comparable<T>>" in t["declaration"]

    def test_annotation_type_elements(self):
        _, t = primary(load_fixture("AnnotationType.java"))
        assert "@interface" in t["declaration"]
        sigs = [m["sig"] for m in t["methods"]]
        for name in ("value()", "priority()", "tags()", "enabled()"):
            assert any(name in s for s in sigs)

    def test_sealed_interface(self):
        _, t = primary("""
        package com.example;
        public sealed interface Shape permits Circle, Rectangle {
            double area();
        }
        """)
        assert "sealed interface Shape permits Circle, Rectangle" in t["declaration"]

    def test_modern_java_features_fixture(self):
        parsed, t = primary(load_fixture("ModernJavaFeatures.java"))
        assert "sealed" in t["declaration"]
        assert "Shape<T>" in t["declaration"]
        assert len(parsed["types"]) >= 4

    def test_package_info_has_no_types(self):
        parsed = parse_java_source(
            '@ApplicationModule(displayName = "Evidence")\npackage com.example.evidence;\n'
            'import org.springframework.modulith.ApplicationModule;\n'
        )
        assert parsed["types"] == []
        assert parsed["package_annotations"][0]["full"] == '@ApplicationModule(displayName = "Evidence")'


# ---------------------------------------------------------------------------
# format_output
# ---------------------------------------------------------------------------

class TestFormatOutput:
    def test_basic_output_structure(self):
        output = skim(load_fixture("SimpleDirection.java"), "SimpleDirection.java")
        lines = output.split("\n")
        assert lines[0] == "// SimpleDirection.java"
        assert lines[1] == "// com.example"
        assert any("total:" in l for l in lines)

    def test_enum_constants_in_output(self):
        output = skim(load_fixture("SimpleDirection.java"))
        assert "// constants: NORTH, SOUTH, EAST, WEST" in output

    def test_lombok_annotations_stay_on_class_line(self):
        output = skim(load_fixture("StaticFieldService.java"))
        assert "@RequiredArgsConstructor" in output
        assert "lombok:" not in output

    def test_instance_and_static_fields_split(self):
        output = skim("""
        class Foo {
            static final String BASE = "/x";
            private static final String SECRET = "/y";
            private static final int MAX = 3;
            private final Bar bar;
            private Baz baz;
        }
        """)
        assert "// fields:\n//   Bar bar\n//   Baz baz" in output
        assert '// static fields: BASE = "/x", SECRET, MAX' in output
        assert "String BASE" not in output

    def test_methods_in_output(self):
        output = skim(load_fixture("StaticFieldService.java"))
        assert "methods:" in output
        assert "processOrder" in output

    def test_getter_collapsed(self):
        output = skim(load_fixture("LambdaEdgeCases.java"))
        assert "getters:" in output
        assert "getName" in output

    def test_boilerplate_collapsed(self):
        output = skim(load_fixture("EdgeCaseBugs.java"))
        assert "boilerplate:" in output
        assert "toString" in output

    def test_inner_types_in_output(self):
        output = skim(load_fixture("EdgeCaseBugs.java"))
        assert "inner types:" in output

    def test_extra_types_in_output(self):
        output = skim(load_fixture("SealedAndMultiClass.java"))
        assert "other classes in file:" in output
        assert "Circle" in output
        assert "Rectangle" in output

    def test_static_initializer_in_output(self):
        output = skim(load_fixture("Role.java"))
        assert "static initializer" in output

    def test_grep_filter(self):
        output = skim(load_fixture("ScheduleServiceProxy.java"), grep="fetch")
        method_lines = [l for l in output.split("\n") if "lines):" in l]
        assert method_lines, "grep filter should still show matching methods"
        for ml in method_lines:
            assert "fetch" in ml.lower(), f"Non-matching method leaked through grep filter: {ml}"

    def test_annotation_filter(self):
        output = skim(load_fixture("AppConfiguration.java"), annotation="@Bean")
        method_lines = [l for l in output.split("\n") if "lines):" in l]
        assert method_lines
        for ml in method_lines:
            assert "@Bean" in ml

    def test_method_call_tracing_in_output(self):
        output = skim(load_fixture("ScheduleServiceProxy.java"))
        assert "→" in output

    def test_method_reference_tracing_in_output(self):
        source = """
        package com.example;
        public class Processor {
            private final Handler handler;
            public void run(List<String> list) {
                list.forEach(this::validate);
                list.forEach(handler::process);
            }
            private void validate(String s) {}
        }
        """
        output = skim(source)
        assert "→ handler.process, validate" in output

    def test_many_enum_constants_truncated(self):
        output = skim(load_fixture("Role.java"))
        assert "...+" in output

    def test_class_annotations_in_output(self):
        output = skim(load_fixture("CabUpdateKafkaConsumer.java"))
        assert "@Slf4j" in output
        assert "@Component" in output

    def test_all_comment_prefixed(self):
        output = skim(load_fixture("SimpleDirection.java"))
        for line in output.split("\n"):
            assert line.startswith("//"), f"Line not prefixed: {line!r}"

    def test_record_fields_in_output(self):
        output = skim("package com.example; public record UserDTO(String name, int age) {}")
        assert "fields:" in output
        assert "String name" in output
        assert "int age" in output

    def test_generic_class_declaration_in_output(self):
        output = skim("package com.example; public class Foo<T> extends Bar<T> {}")
        assert "Foo<T>" in output
        assert "extends Bar<T>" in output

    def test_annotation_type_elements_in_output(self):
        output = skim(load_fixture("AnnotationType.java"))
        assert "value()" in output
        assert "priority()" in output

    def test_implicit_class_output(self):
        output = skim(load_fixture("ImplicitClass.java"), "ImplicitClass.java")
        assert output.startswith("//")
        assert "implicit class ImplicitClass" in output
        assert "void main()" in output
        assert "total:" in output

    def test_package_info_output(self):
        output = skim(
            '@ApplicationModule(displayName = "Evidence")\npackage com.example.evidence;\n',
            "package-info.java",
        )
        assert output == (
            "// package-info.java\n"
            "// com.example.evidence\n"
            '// @ApplicationModule(displayName = "Evidence")\n'
            "//\n"
            "// total: 3 lines"
        )

    def test_doc_line_after_declaration(self):
        output = skim("/** Plans trips. Details follow. */\n@Service\nclass TripService {}")
        assert "// @Service\n// class TripService\n// doc: Plans trips.\n" in output

    def test_wiring_constructor_collapsed(self):
        output = skim("""
        class S {
            private final A a; private final B b;
            S(A a, B b) { this.a = a; this.b = b; }
            S(A a) { this.a = a; this.b = build(); }
        }
        """)
        assert "// constructor: L4-L4 (2 params)" in output
        assert "S(A a, B b)" not in output
        assert "S(A a)" in output  # non-wiring constructor stays in methods

    def test_record_component_annotations_shown(self):
        output = skim("record B(@NotNull @Size(min = 1) @Valid List<E> events) {}")
        assert "//   List<E> events (@NotNull @Size @Valid)" in output

    def test_nested_types_show_members(self):
        output = skim("""
        class Outer {
            record Claim(int count, Integer last) {}
            enum Kind { A, B }
            @Configuration static class Cfg {
                static final String P = "x";
                @Bean Foo foo(Bar bar) { return bar.make(); }
            }
        }
        """)
        assert "//   L3: record Claim\n//     fields: int count, Integer last" in output
        assert "//   L4: enum Kind { A, B }" in output
        assert "//   L5: @Configuration static class Cfg\n" in output
        assert '//     static fields: P = "x"' in output
        assert "//     methods:\n//    " in output
        assert "L7-L7 (  1 lines): @Bean Foo foo(Bar bar)" in output

    def test_method_range_starts_at_signature(self):
        output = skim("""
        class C {
            @Operation(summary = "x")
            @ApiResponse(responseCode = "200")
            @Transactional
            public void go() {
            }
        }
        """)
        assert "L6-L7 (  2 lines): @Transactional public void go()" in output

    def test_mapping_paths_resolved_from_constants(self):
        output = skim("""
        @RestController
        @RequestMapping(TripController.BASE_PATH)
        class TripController {
            static final String BASE_PATH = "/api/v1/logistics";
            private static final String TRIPS = "/trips";
            private static final String ONE_TRIP = TRIPS + "/{tripId}";
            @PostMapping(path = ONE_TRIP + "/start", consumes = MediaType.APPLICATION_JSON_VALUE)
            void start() {}
        }
        """)
        assert '@RequestMapping("/api/v1/logistics")' in output
        assert '@PostMapping("/trips/{tripId}/start")' in output
        assert "consumes" not in output

    def test_doc_annotations_dropped_and_repeats_deduped(self):
        output = skim("""
        class C {
            @Operation(summary = "x")
            @ApiResponse(responseCode = "200")
            @ApiResponse(responseCode = "404")
            @RequiresPermission(Perms.READ)
            @ResponseStatus(HttpStatus.CREATED)
            void go(@Parameter(description = "long text") @RequestParam(required = false) Integer size) {}
        }
        """)
        assert "@Operation" not in output
        assert "@ApiResponse" not in output
        assert "@RequiresPermission(Perms.READ) @ResponseStatus(HttpStatus.CREATED) void go(@RequestParam Integer size)" in output

    def test_calls_on_locals_are_dropped(self):
        output = skim("""
        class S {
            private final Repo repo;
            void run(Request request) {
                Row row = repo.find(request.id());
                row.status();
                Helper.check(row);
                validate();
            }
            void validate() {}
        }
        """)
        assert "→ Helper.check, repo.find, validate" in output
        assert "request.id" not in output
        assert "row.status" not in output


# ---------------------------------------------------------------------------
# Integration tests with real fixture files
# ---------------------------------------------------------------------------

class TestSkimFixtureFiles:
    """Every fixture file parses and formats without errors."""

    @pytest.fixture(params=[
        "AnnotationType.java", "AnonClassFields.java", "AppConfiguration.java",
        "BillingCalculator.java", "BillingTaskDefinitions.java", "BusinessUnitsDao.java",
        "CabCreationConsumerConfiguration.java", "CabUpdateKafkaConsumer.java",
        "ComplexMixed.java", "ContractType.java", "EdgeCaseBugs.java",
        "HealthConfiguration.java", "ImplicitClass.java", "InlineAnnotations.java",
        "LambdaEdgeCases.java", "LambdaFields.java",
        "MammothRawTripDataReportTaskDefinitions.java", "MammothRawTripRowMapper.java",
        "ModernJavaFeatures.java", "NestedAnnotations.java",
        "RawTripDataReportTaskDefinitions.java", "RawTripRowMapper.java",
        "RBDResultSetExtractor.java", "ReportStatus.java", "Role.java",
        "ScheduleServiceProxy.java", "SealedAndMultiClass.java", "SimpleDirection.java",
        "StaticFieldService.java", "StatusEnum.java", "SwitchExprFields.java",
        "TextBlockTest.java", "TripEndKafkaConsumer.java",
        "TripEndKafkaConsumerConfiguration.java",
    ])
    def java_file(self, request):
        return request.param

    def test_parse_and_format(self, java_file):
        output = skim(load_fixture(java_file), java_file)
        assert output.startswith("//")
        assert "total:" in output
