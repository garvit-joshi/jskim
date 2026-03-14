"""Tests for jskim.method — method extraction with context."""

import pytest
from jskim.method import parse_methods, list_methods, extract_methods
from tests.conftest import load_fixture


# ---------------------------------------------------------------------------
# parse_methods
# ---------------------------------------------------------------------------

class TestParseMethods:
    def test_basic_parsing(self):
        content = """
        package com.example;
        public class Foo {
            private int x;
            public void bar() {}
            public String getName() { return ""; }
        }
        """
        parsed = parse_methods(content)
        assert parsed["package"] == "com.example"
        assert parsed["class_name"] == "Foo"
        assert "class Foo" in parsed["class_declaration"]
        assert len(parsed["fields"]) == 1
        assert len(parsed["methods"]) == 2

    def test_method_names(self):
        content = """
        class Foo {
            public void process() {}
            public void validate() {}
            public void save() {}
        }
        """
        parsed = parse_methods(content)
        names = [m["name"] for m in parsed["methods"]]
        assert "process" in names
        assert "validate" in names
        assert "save" in names

    def test_method_line_ranges(self):
        content = "class Foo {\n    void bar() {\n        int x = 1;\n    }\n}\n"
        parsed = parse_methods(content)
        method = parsed["methods"][0]
        assert method["start"] > 0
        assert method["end"] >= method["start"]

    def test_method_annotations(self):
        content = """
        class Foo {
            @Override
            public String toString() { return ""; }
        }
        """
        parsed = parse_methods(content)
        method = parsed["methods"][0]
        assert "@Override" in method["annotations"]

    def test_constructor_parsed(self):
        content = """
        class Foo {
            public Foo(int x) {}
        }
        """
        parsed = parse_methods(content)
        assert len(parsed["methods"]) == 1
        assert parsed["methods"][0]["name"] == "Foo"

    def test_fields_as_strings(self):
        content = """
        class Foo {
            private int count;
            private String name;
        }
        """
        parsed = parse_methods(content)
        assert len(parsed["fields"]) == 2
        assert any("int count" in f for f in parsed["fields"])
        assert any("String name" in f for f in parsed["fields"])

    def test_fixture_billing_calculator(self):
        content = load_fixture("BillingCalculator.java")
        parsed = parse_methods(content)
        assert parsed["class_name"] == "BillingCalculator"
        names = [m["name"] for m in parsed["methods"]]
        assert "calculate" in names
        assert "isSingleEscortTrip" in names
        assert "zeroCostResult" in names

    def test_fixture_rbd_result_set_extractor(self):
        content = load_fixture("RBDResultSetExtractor.java")
        parsed = parse_methods(content)
        names = [m["name"] for m in parsed["methods"]]
        assert "extractData" in names
        assert "mapRow" in names
        assert "parseEnum" in names

    def test_fixture_edge_case_bugs(self):
        content = load_fixture("EdgeCaseBugs.java")
        parsed = parse_methods(content)
        names = [m["name"] for m in parsed["methods"]]
        assert "getaway" in names
        assert "isolate" in names
        assert "processData" in names
        assert "reset" in names

    def test_multiple_type_declarations(self):
        content = load_fixture("SealedAndMultiClass.java")
        parsed = parse_methods(content)
        # Should collect methods from all type declarations
        names = [m["name"] for m in parsed["methods"]]
        assert "area" in names  # present in multiple classes
        assert "getColor" in names


# ---------------------------------------------------------------------------
# list_methods
# ---------------------------------------------------------------------------

class TestListMethods:
    def test_basic_listing(self):
        content = """
        class Foo {
            public void process() {}
            public void validate() {}
        }
        """
        parsed = parse_methods(content)
        output = list_methods(parsed)
        assert "process()" in output
        assert "validate()" in output
        assert output.startswith("//")

    def test_line_ranges_shown(self):
        content = load_fixture("ScheduleServiceProxy.java")
        parsed = parse_methods(content)
        output = list_methods(parsed)
        assert "L" in output  # line number markers
        assert "lines" in output

    def test_annotations_shown(self):
        content = """
        class Foo {
            @Override
            public String toString() { return ""; }
        }
        """
        parsed = parse_methods(content)
        output = list_methods(parsed)
        assert "@Override" in output

    def test_fixture_cab_creation_config(self):
        content = load_fixture("CabCreationConsumerConfiguration.java")
        parsed = parse_methods(content)
        output = list_methods(parsed)
        assert "cabUpdateEventKafkaListenerContainerFactory" in output
        assert "cabCreationEventConsumerFactory" in output


# ---------------------------------------------------------------------------
# extract_methods
# ---------------------------------------------------------------------------

class TestExtractMethods:
    def test_exact_match(self):
        content = load_fixture("ScheduleServiceProxy.java")
        parsed = parse_methods(content)
        output = extract_methods(parsed, ["fetchOfficesForBusinessUnitId"])
        assert "fetchOfficesForBusinessUnitId" in output
        assert "|" in output  # line number format

    def test_fuzzy_match(self):
        content = load_fixture("ScheduleServiceProxy.java")
        parsed = parse_methods(content)
        output = extract_methods(parsed, ["fetch"])
        # Should fuzzy match methods containing "fetch"
        assert "fetch" in output.lower()

    def test_not_found(self):
        content = """
        class Foo {
            public void bar() {}
        }
        """
        parsed = parse_methods(content)
        output = extract_methods(parsed, ["nonexistent"])
        assert "not found" in output.lower()

    def test_multiple_methods(self):
        content = load_fixture("ScheduleServiceProxy.java")
        parsed = parse_methods(content)
        output = extract_methods(
            parsed, ["fetchOfficesForBusinessUnitId", "fetchShiftsForBusinessUnitId"]
        )
        assert "fetchOfficesForBusinessUnitId" in output
        assert "fetchShiftsForBusinessUnitId" in output

    def test_called_methods_shown(self):
        content = load_fixture("RBDResultSetExtractor.java")
        parsed = parse_methods(content)
        output = extract_methods(parsed, ["extractData"])
        # extractData calls mapRow, isValidCabId, isValidString
        assert "called methods" in output.lower()

    def test_fields_shown(self):
        content = load_fixture("StaticFieldService.java")
        parsed = parse_methods(content)
        output = extract_methods(parsed, ["processOrder"])
        assert "fields:" in output

    def test_source_lines_included(self):
        content = load_fixture("BillingCalculator.java")
        parsed = parse_methods(content)
        output = extract_methods(parsed, ["isSingleEscortTrip"])
        # Source code should be included with line numbers
        assert "contractConfiguration" in output  # from method body

    def test_annotations_preserved(self):
        content = load_fixture("CabUpdateKafkaConsumer.java")
        parsed = parse_methods(content)
        output = extract_methods(parsed, ["processCabUpdate"])
        assert "@KafkaListener" in output

    def test_partially_found(self):
        content = load_fixture("ScheduleServiceProxy.java")
        parsed = parse_methods(content)
        output = extract_methods(parsed, ["fetchOfficesForBusinessUnitId", "nonexistent"])
        assert "fetchOfficesForBusinessUnitId" in output
        assert "not found" in output

    def test_comment_captured_in_walk_back(self):
        """Javadoc and annotations above a method should be included."""
        content = load_fixture("BillingCalculator.java")
        parsed = parse_methods(content)
        output = extract_methods(parsed, ["isSingleEscortTrip"])
        # The Javadoc above isSingleEscortTrip should be captured
        assert "single escort trip" in output.lower()


# ---------------------------------------------------------------------------
# Record and @interface support
# ---------------------------------------------------------------------------

class TestModernJavaFeatures:
    def test_record_components_as_fields(self):
        content = """
        package com.example;
        public record UserDTO(String name, int age) {
            public String displayName() { return name.toUpperCase(); }
        }
        """
        parsed = parse_methods(content)
        assert any("String name" in f for f in parsed["fields"])
        assert any("int age" in f for f in parsed["fields"])
        names = [m["name"] for m in parsed["methods"]]
        assert "displayName" in names

    def test_annotation_type_elements(self):
        content = load_fixture("AnnotationType.java")
        parsed = parse_methods(content)
        names = [m["name"] for m in parsed["methods"]]
        assert "value" in names
        assert "priority" in names
        assert "tags" in names
        assert "enabled" in names

    def test_annotation_type_list_methods(self):
        content = load_fixture("AnnotationType.java")
        parsed = parse_methods(content)
        output = list_methods(parsed)
        assert "value()" in output
        assert "priority()" in output

    def test_generic_class_declaration(self):
        content = """
        package com.example;
        public class Container<T extends Comparable<T>> {
            private T value;
            public T getValue() { return value; }
        }
        """
        parsed = parse_methods(content)
        assert "Container<T extends Comparable<T>>" in parsed["class_declaration"]

    def test_modern_java_features_fixture(self):
        content = load_fixture("ModernJavaFeatures.java")
        parsed = parse_methods(content)
        names = [m["name"] for m in parsed["methods"]]
        assert "area" in names
        assert "perimeter" in names
        assert "describe" in names
        assert "distance" in names
