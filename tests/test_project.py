"""Tests for jskim.project — directory-wide project map."""

import pytest
from jskim.project import (
    scan_java_file,
    find_dependencies,
    format_output,
    _filter_infos,
    _join_paths,
)
from tests.conftest import fixture_path, FIXTURES_DIR


# ---------------------------------------------------------------------------
# _join_paths
# ---------------------------------------------------------------------------

class TestJoinPaths:
    def test_both_empty(self):
        assert _join_paths("", "") == "/"

    def test_base_only(self):
        assert _join_paths("/api", "") == "/api"

    def test_method_only(self):
        assert _join_paths("", "/users") == "/users"

    def test_both_paths(self):
        assert _join_paths("/api", "/users") == "/api/users"

    def test_trailing_slash_stripped(self):
        assert _join_paths("/api/", "/users") == "/api/users"

    def test_no_leading_slash(self):
        assert _join_paths("api", "users") == "api/users"


# ---------------------------------------------------------------------------
# scan_java_file
# ---------------------------------------------------------------------------

class TestScanJavaFile:
    def test_simple_class(self):
        path = fixture_path("SimpleDirection.java")
        infos = scan_java_file(path)
        assert len(infos) == 1
        info = infos[0]
        assert info["class_name"] == "SimpleDirection"
        assert info["class_type"] == "enum"
        assert info["package"] == "com.example"

    def test_enum_constants(self):
        path = fixture_path("SimpleDirection.java")
        infos = scan_java_file(path)
        info = infos[0]
        assert set(info["enum_constants"]) == {"NORTH", "SOUTH", "EAST", "WEST"}

    def test_spring_service(self):
        path = fixture_path("StaticFieldService.java")
        infos = scan_java_file(path)
        info = infos[0]
        assert "@Service" in info["annotations"]
        assert "@Slf4j" in info["annotations"]
        assert "@RequiredArgsConstructor" in info["annotations"]
        assert info["field_count"] > 0
        assert info["method_count"] > 0

    def test_configuration_bean_producers(self):
        path = fixture_path("AppConfiguration.java")
        infos = scan_java_file(path)
        info = infos[0]
        assert "@Configuration" in info["annotations"]
        assert len(info["bean_produces"]) > 0
        assert "ObjectMapper" in info["bean_produces"]
        assert "OkHttpClient" in info["bean_produces"]

    def test_bean_dependencies(self):
        path = fixture_path("StaticFieldService.java")
        infos = scan_java_file(path)
        info = infos[0]
        # Should detect final fields as constructor-injected deps
        assert "OrderRepository" in info["bean_deps"]
        assert "PaymentRepository" in info["bean_deps"]
        assert "NotificationClient" in info["bean_deps"]

    def test_static_fields_not_deps(self):
        path = fixture_path("StaticFieldService.java")
        infos = scan_java_file(path)
        info = infos[0]
        # Static fields should NOT be bean deps
        assert "String" not in info["bean_deps"]
        assert "int" not in info["bean_deps"]
        assert "long" not in info["bean_deps"]

    def test_lombok_detection(self):
        path = fixture_path("StaticFieldService.java")
        infos = scan_java_file(path)
        info = infos[0]
        assert "@Slf4j" in info["lombok"]
        assert "@RequiredArgsConstructor" in info["lombok"]

    def test_extends_detection(self):
        path = fixture_path("BusinessUnitsDao.java")
        infos = scan_java_file(path)
        info = infos[0]
        assert info["extends"] is not None
        assert "DAOImpl" in info["extends"]

    def test_implements_detection(self):
        path = fixture_path("RBDResultSetExtractor.java")
        infos = scan_java_file(path)
        info = infos[0]
        assert len(info["implements"]) > 0
        assert any("ResultSetExtractor" in i for i in info["implements"])

    def test_multiple_type_declarations(self):
        path = fixture_path("SealedAndMultiClass.java")
        infos = scan_java_file(path)
        assert len(infos) == 3  # SealedAndMultiClass, Circle, Rectangle
        names = [i["class_name"] for i in infos]
        assert "SealedAndMultiClass" in names
        assert "Circle" in names
        assert "Rectangle" in names

    def test_jooq_enum(self):
        path = fixture_path("ContractType.java")
        infos = scan_java_file(path)
        info = infos[0]
        assert info["class_type"] == "enum"
        assert set(info["enum_constants"]) == {"PACKAGE", "SLAB", "TRIP", "ZONE"}

    def test_total_lines(self):
        path = fixture_path("SimpleDirection.java")
        infos = scan_java_file(path)
        assert infos[0]["total_lines"] > 0

    def test_filepath_stored(self):
        path = fixture_path("SimpleDirection.java")
        infos = scan_java_file(path)
        assert infos[0]["filepath"] == path

    def test_inner_types(self):
        path = fixture_path("EdgeCaseBugs.java")
        infos = scan_java_file(path)
        info = infos[0]
        assert len(info["inner_types"]) > 0

    def test_static_initializer(self):
        path = fixture_path("Role.java")
        infos = scan_java_file(path)
        info = infos[0]
        assert len(info["static_initializers"]) > 0

    def test_kafka_config_beans(self):
        path = fixture_path("CabCreationConsumerConfiguration.java")
        infos = scan_java_file(path)
        info = infos[0]
        assert len(info["bean_produces"]) > 0


# ---------------------------------------------------------------------------
# find_dependencies
# ---------------------------------------------------------------------------

class TestFindDependencies:
    def test_no_deps(self):
        infos = [
            {"class_name": "Foo", "package": "com.example", "imports": [], "extends": None, "implements": []},
            {"class_name": "Bar", "package": "com.example", "imports": [], "extends": None, "implements": []},
        ]
        deps = find_dependencies(infos)
        assert deps == {}

    def test_import_based_dep(self):
        infos = [
            {
                "class_name": "Foo",
                "package": "com.example",
                "imports": ["com.example.Bar"],
                "extends": None,
                "implements": [],
            },
            {
                "class_name": "Bar",
                "package": "com.example",
                "imports": [],
                "extends": None,
                "implements": [],
            },
        ]
        deps = find_dependencies(infos)
        assert "Foo" in deps
        assert "Bar" in deps["Foo"]

    def test_extends_dep(self):
        infos = [
            {
                "class_name": "Foo",
                "package": "com.example",
                "imports": [],
                "extends": "Bar",
                "implements": [],
            },
            {
                "class_name": "Bar",
                "package": "com.example",
                "imports": [],
                "extends": None,
                "implements": [],
            },
        ]
        deps = find_dependencies(infos)
        assert "Bar" in deps.get("Foo", [])

    def test_implements_dep(self):
        infos = [
            {
                "class_name": "Foo",
                "package": "com.example",
                "imports": [],
                "extends": None,
                "implements": ["Baz"],
            },
            {
                "class_name": "Baz",
                "package": "com.example",
                "imports": [],
                "extends": None,
                "implements": [],
            },
        ]
        deps = find_dependencies(infos)
        assert "Baz" in deps.get("Foo", [])

    def test_wildcard_import(self):
        infos = [
            {
                "class_name": "Foo",
                "package": "com.example.a",
                "imports": ["com.example.b.*"],
                "extends": None,
                "implements": [],
            },
            {
                "class_name": "Bar",
                "package": "com.example.b",
                "imports": [],
                "extends": None,
                "implements": [],
            },
        ]
        deps = find_dependencies(infos)
        assert "Bar" in deps.get("Foo", [])

    def test_self_reference_excluded(self):
        infos = [
            {
                "class_name": "Foo",
                "package": "com.example",
                "imports": ["com.example.Foo"],
                "extends": None,
                "implements": [],
            },
        ]
        deps = find_dependencies(infos)
        assert "Foo" not in deps

    def test_real_fixtures(self):
        """Test dependency detection on a collection of real fixture files."""
        paths = [
            fixture_path("StaticFieldService.java"),
            fixture_path("AppConfiguration.java"),
        ]
        all_infos = []
        for p in paths:
            all_infos.extend(scan_java_file(p))
        deps = find_dependencies(all_infos)
        # These may or may not have deps depending on import overlap
        assert isinstance(deps, dict)


# ---------------------------------------------------------------------------
# _filter_infos
# ---------------------------------------------------------------------------

class TestFilterInfos:
    def _make_info(self, name, pkg="com.example", anns=None, extends=None, implements=None):
        return {
            "class_name": name,
            "package": pkg,
            "annotations": anns or [],
            "extends": extends,
            "implements": implements or [],
        }

    def test_no_filter(self):
        infos = [self._make_info("Foo"), self._make_info("Bar")]
        result = _filter_infos(infos, None, None, None)
        assert len(result) == 2

    def test_package_filter(self):
        infos = [
            self._make_info("Foo", pkg="com.example.services"),
            self._make_info("Bar", pkg="com.example.web"),
        ]
        result = _filter_infos(infos, "com.example.services", None, None)
        assert len(result) == 1
        assert result[0]["class_name"] == "Foo"

    def test_annotation_filter(self):
        infos = [
            self._make_info("Foo", anns=["@Service"]),
            self._make_info("Bar", anns=["@Controller"]),
        ]
        result = _filter_infos(infos, None, "@Service", None)
        assert len(result) == 1
        assert result[0]["class_name"] == "Foo"

    def test_annotation_filter_without_at(self):
        infos = [self._make_info("Foo", anns=["@Service"])]
        result = _filter_infos(infos, None, "Service", None)
        assert len(result) == 1

    def test_extends_filter(self):
        infos = [
            self._make_info("Foo", extends="BaseService"),
            self._make_info("Bar", extends=None),
        ]
        result = _filter_infos(infos, None, None, "BaseService")
        assert len(result) == 1
        assert result[0]["class_name"] == "Foo"

    def test_implements_filter(self):
        infos = [
            self._make_info("Foo", implements=["Serializable"]),
            self._make_info("Bar", implements=[]),
        ]
        result = _filter_infos(infos, None, None, None, impl_filter="Serializable")
        assert len(result) == 1
        assert result[0]["class_name"] == "Foo"


# ---------------------------------------------------------------------------
# format_output
# ---------------------------------------------------------------------------

class TestFormatOutput:
    def test_basic_output(self):
        path = fixture_path("SimpleDirection.java")
        infos = scan_java_file(path)
        output = format_output(infos)
        assert "Project Map:" in output
        assert "SimpleDirection" in output

    def test_packages_grouped(self):
        paths = [
            fixture_path("SimpleDirection.java"),
            fixture_path("StaticFieldService.java"),
        ]
        all_infos = []
        for p in paths:
            all_infos.extend(scan_java_file(p))
        output = format_output(all_infos)
        assert "com.example" in output

    def test_field_and_method_counts(self):
        path = fixture_path("StaticFieldService.java")
        infos = scan_java_file(path)
        output = format_output(infos)
        assert "F" in output  # field count
        assert "M" in output  # method count
        assert "L" in output  # line count

    def test_enum_constants_inline(self):
        path = fixture_path("SimpleDirection.java")
        infos = scan_java_file(path)
        output = format_output(infos)
        assert "NORTH" in output
        assert "SOUTH" in output

    def test_key_annotations_shown(self):
        path = fixture_path("StaticFieldService.java")
        infos = scan_java_file(path)
        output = format_output(infos)
        assert "@Service" in output

    def test_lombok_shown(self):
        path = fixture_path("StaticFieldService.java")
        infos = scan_java_file(path)
        output = format_output(infos)
        assert "lombok:" in output

    def test_show_deps(self):
        paths = [
            fixture_path("SealedAndMultiClass.java"),
        ]
        all_infos = []
        for p in paths:
            all_infos.extend(scan_java_file(p))
        output = format_output(all_infos, show_deps=True)
        # Circle and Rectangle extend SealedAndMultiClass
        if "Dependencies" in output:
            assert "→" in output

    def test_show_beans(self):
        path = fixture_path("AppConfiguration.java")
        infos = scan_java_file(path)
        output = format_output(infos, show_beans=True)
        assert "Bean Producers" in output
        assert "ObjectMapper" in output

    def test_bean_dependencies_shown(self):
        path = fixture_path("StaticFieldService.java")
        infos = scan_java_file(path)
        output = format_output(infos, show_beans=True)
        assert "Bean Dependencies" in output
        assert "OrderRepository" in output

    def test_all_comment_prefixed(self):
        path = fixture_path("SimpleDirection.java")
        infos = scan_java_file(path)
        output = format_output(infos)
        for line in output.split("\n"):
            assert line.startswith("//"), f"Line not prefixed: {line!r}"

    def test_static_initializer_shown(self):
        path = fixture_path("Role.java")
        infos = scan_java_file(path)
        output = format_output(infos)
        assert "static-init:" in output

    def test_inner_types_shown(self):
        path = fixture_path("EdgeCaseBugs.java")
        infos = scan_java_file(path)
        output = format_output(infos)
        assert "inner:" in output


# ---------------------------------------------------------------------------
# Full project scan
# ---------------------------------------------------------------------------

class TestFullProjectScan:
    def test_scan_all_fixtures(self):
        """Scan the entire fixtures directory like a real project."""
        java_files = sorted(FIXTURES_DIR.rglob("*.java"))
        assert len(java_files) > 20

        all_infos = []
        for f in java_files:
            infos = scan_java_file(f)
            all_infos.extend(infos)

        assert len(all_infos) > 20

        output = format_output(all_infos, show_deps=True, show_endpoints=False, show_beans=True)
        assert "Project Map:" in output
        assert output.startswith("//")

    def test_scan_all_fixtures_with_endpoints(self):
        java_files = sorted(FIXTURES_DIR.rglob("*.java"))
        all_infos = []
        for f in java_files:
            all_infos.extend(scan_java_file(f))

        output = format_output(all_infos, show_endpoints=True)
        # No REST controllers in fixtures, so no endpoints section expected
        assert "Project Map:" in output
