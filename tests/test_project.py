"""Tests for jskim.project — directory-wide project map."""

import pytest
from pathlib import Path
from jskim.project import (
    scan_java_file,
    flatten_types,
    collect_endpoints,
    find_dependencies,
    format_output,
    format_callers_output,
    format_impact_output,
    filter_files,
    _join_paths,
)
from tests.conftest import fixture_path, FIXTURES_DIR


def types_of(path):
    return scan_java_file(path)["types"]


def files_of(*paths):
    return [scan_java_file(p) for p in paths]


def synthetic_file(*type_infos, package="com.example", filepath=Path("/tmp/X.java"), lines=10):
    """Wrap hand-built type dicts into a scanned-file dict."""
    for t in type_infos:
        t.setdefault("filepath", filepath)
        t.setdefault("package", package)
        t.setdefault("total_lines", lines)
    return {
        "filepath": filepath,
        "package": package,
        "package_annotations": [],
        "imports": [],
        "total_lines": lines,
        "types": list(type_infos),
    }


def synthetic_type(name, package="com.example", imports=(), extends=None, implements=(), anns=()):
    return {
        "class_name": name,
        "class_type": "class",
        "package": package,
        "imports": list(imports),
        "extends": extends,
        "implements": list(implements),
        "annotations": list(anns),
        "field_count": 0,
        "method_count": 0,
        "lombok": [],
        "enum_constants": [],
        "inner_types": [],
        "static_initializers": [],
        "total_lines": 10,
        "filepath": Path(f"/tmp/{package.replace('.', '/')}/{name}.java"),
    }


# ---------------------------------------------------------------------------
# _join_paths
# ---------------------------------------------------------------------------

class TestJoinPaths:
    @pytest.mark.parametrize("base,method,expected", [
        ("", "", "/"),
        ("/api", "", "/api"),
        ("", "/users", "/users"),
        ("/api", "/users", "/api/users"),
        ("/api/", "/users", "/api/users"),
        ("api", "users", "api/users"),
    ])
    def test_join(self, base, method, expected):
        assert _join_paths(base, method) == expected


# ---------------------------------------------------------------------------
# scan_java_file
# ---------------------------------------------------------------------------

class TestScanJavaFile:
    def test_simple_class(self):
        f = scan_java_file(fixture_path("SimpleDirection.java"))
        assert f["package"] == "com.example"
        assert f["total_lines"] > 0
        assert f["filepath"] == fixture_path("SimpleDirection.java")
        assert len(f["types"]) == 1
        info = f["types"][0]
        assert info["class_name"] == "SimpleDirection"
        assert info["class_type"] == "enum"
        assert set(info["enum_constants"]) == {"NORTH", "SOUTH", "EAST", "WEST"}

    def test_spring_service(self):
        info = types_of(fixture_path("StaticFieldService.java"))[0]
        assert {"@Service", "@Slf4j", "@RequiredArgsConstructor"} <= set(info["annotations"])
        assert info["field_count"] > 0
        assert info["method_count"] > 0
        assert "@Slf4j" in info["lombok"]

    def test_field_count_excludes_statics(self):
        f = scan_java_file(fixture_path("StaticFieldService.java"))
        info = f["types"][0]
        assert info["field_count"] == 4  # 3 injected repositories/clients + lastOrderId; 6 statics excluded

    def test_configuration_bean_producers(self):
        info = types_of(fixture_path("AppConfiguration.java"))[0]
        assert "@Configuration" in info["annotations"]
        assert "ObjectMapper" in info["bean_produces"]
        assert "OkHttpClient" in info["bean_produces"]

    def test_lombok_constructor_injection(self):
        info = types_of(fixture_path("StaticFieldService.java"))[0]
        assert info["bean_deps"] == ["OrderRepository", "PaymentRepository", "NotificationClient"]

    def test_explicit_constructor_injection(self, tmp_path):
        path = tmp_path / "TripService.java"
        path.write_text("""
        package demo;
        @Service
        class TripService {
            private static final String X = "x";
            private final TripRepository trips;
            private final Clock clock;
            TripService(TripRepository trips, Clock clock) { this.trips = trips; this.clock = clock; }
        }
        """, encoding="utf-8")
        info = types_of(path)[0]
        assert info["bean_deps"] == ["TripRepository", "Clock"]

    def test_field_injection(self, tmp_path):
        path = tmp_path / "S.java"
        path.write_text("@Component class S { @Autowired private Foo foo; private Bar bar; }", encoding="utf-8")
        assert types_of(path)[0]["bean_deps"] == ["Foo"]

    def test_non_bean_has_no_deps(self, tmp_path):
        path = tmp_path / "P.java"
        path.write_text("class P { P(Foo foo) {} }", encoding="utf-8")
        assert types_of(path)[0]["bean_deps"] == []

    def test_extends_detection(self):
        info = types_of(fixture_path("BusinessUnitsDao.java"))[0]
        assert "DAOImpl" in info["extends"]

    def test_implements_detection(self):
        info = types_of(fixture_path("RBDResultSetExtractor.java"))[0]
        assert any("ResultSetExtractor" in i for i in info["implements"])

    def test_multiple_type_declarations(self):
        names = [i["class_name"] for i in types_of(fixture_path("SealedAndMultiClass.java"))]
        assert names == ["SealedAndMultiClass", "Circle", "Rectangle"]

    def test_jooq_enum(self):
        info = types_of(fixture_path("ContractType.java"))[0]
        assert info["class_type"] == "enum"
        assert set(info["enum_constants"]) == {"PACKAGE", "SLAB", "TRIP", "ZONE"}

    def test_inner_types_and_static_initializer(self):
        assert types_of(fixture_path("EdgeCaseBugs.java"))[0]["inner_types"]
        assert types_of(fixture_path("Role.java"))[0]["static_initializers"]

    def test_kafka_config_beans(self):
        assert types_of(fixture_path("CabCreationConsumerConfiguration.java"))[0]["bean_produces"]

    def test_record_components_counted(self):
        infos = types_of(fixture_path("ModernJavaFeatures.java"))
        point = next(i for i in infos if i["class_name"] == "Point")
        assert point["class_type"] == "record"
        assert point["field_count"] == 2
        response = next(i for i in infos if i["class_name"] == "Response")
        assert response["field_count"] == 3

    def test_annotation_type_methods_counted(self):
        info = types_of(fixture_path("AnnotationType.java"))[0]
        assert info["class_type"] == "@interface"
        assert info["method_count"] == 4

    def test_sealed_interface_scanned(self):
        shape = next(i for i in types_of(fixture_path("ModernJavaFeatures.java")) if i["class_name"] == "Shape")
        assert shape["class_type"] == "interface"
        assert shape["method_count"] == 2

    def test_implicit_class_scanned(self):
        infos = types_of(fixture_path("ImplicitClass.java"))
        assert len(infos) == 1
        assert infos[0]["class_type"] == "implicit class"
        assert infos[0]["class_name"] == "ImplicitClass"
        assert infos[0]["method_count"] == 1

    def test_package_info_scanned(self, tmp_path):
        path = tmp_path / "package-info.java"
        path.write_text(
            '@ApplicationModule(displayName = "Evidence")\npackage demo.evidence;\n', encoding="utf-8"
        )
        f = scan_java_file(path)
        assert f["types"] == []
        assert f["package_annotations"] == ['@ApplicationModule(displayName = "Evidence")']


# ---------------------------------------------------------------------------
# collect_endpoints
# ---------------------------------------------------------------------------

class TestCollectEndpoints:
    def _controller(self, tmp_path):
        (tmp_path / "ApiPaths.java").write_text("""
        package demo;
        final class ApiPaths { static final String BASE = "/api/v1"; }
        """, encoding="utf-8")
        (tmp_path / "TripController.java").write_text("""
        package demo;
        @RestController
        @RequestMapping(ApiPaths.BASE)
        class TripController {
            private static final String TRIPS = "/trips";
            private static final String ONE_TRIP = TRIPS + "/{tripId}";
            @PostMapping(path = TRIPS, consumes = "application/json") void create() {}
            @GetMapping(ONE_TRIP + "/track") void track() {}
            @RequestMapping(method = RequestMethod.DELETE, value = ONE_TRIP) void remove() {}
            @GetMapping({"/a", "/b"}) void multi() {}
            @GetMapping(Unknown.PATH) void unresolved() {}
        }
        """, encoding="utf-8")
        types = flatten_types(files_of(*sorted(tmp_path.glob("*.java"))))
        collect_endpoints(types)
        return next(t for t in types if t["class_name"] == "TripController")["endpoints"]

    def test_paths_resolved_through_constants(self, tmp_path):
        eps = {(e["method"], e["path"]): e["handler"] for e in self._controller(tmp_path)}
        assert eps[("POST", "/api/v1/trips")] == "TripController.create()"
        assert eps[("GET", "/api/v1/trips/{tripId}/track")] == "TripController.track()"
        assert eps[("DELETE", "/api/v1/trips/{tripId}")] == "TripController.remove()"
        assert ("GET", "/api/v1/a") in eps and ("GET", "/api/v1/b") in eps

    def test_unresolved_constant_stays_visible(self, tmp_path):
        paths = [e["path"] for e in self._controller(tmp_path)]
        assert "/api/v1/Unknown.PATH" in paths

    def test_endpoint_section_in_output(self, tmp_path):
        self._controller(tmp_path)
        output = format_output(files_of(*sorted(tmp_path.glob("*.java"))), show_endpoints=True)
        assert "=== REST Endpoints ===" in output
        assert "POST    /api/v1/trips " in output


# ---------------------------------------------------------------------------
# find_dependencies
# ---------------------------------------------------------------------------

class TestFindDependencies:
    def test_no_deps(self):
        assert find_dependencies([synthetic_type("Foo"), synthetic_type("Bar")]) == {}

    def test_import_based_dep(self):
        deps = find_dependencies([synthetic_type("Foo", imports=["com.example.Bar"]), synthetic_type("Bar")])
        assert deps == {"Foo": ["Bar"]}

    def test_extends_dep(self):
        deps = find_dependencies([synthetic_type("Foo", extends="Bar"), synthetic_type("Bar")])
        assert deps["Foo"] == ["Bar"]

    def test_implements_dep(self):
        deps = find_dependencies([synthetic_type("Foo", implements=["Baz"]), synthetic_type("Baz")])
        assert deps["Foo"] == ["Baz"]

    def test_wildcard_import(self):
        deps = find_dependencies([
            synthetic_type("Foo", package="com.example.a", imports=["com.example.b.*"]),
            synthetic_type("Bar", package="com.example.b"),
        ])
        assert deps["Foo"] == ["Bar"]

    def test_self_reference_excluded(self):
        assert find_dependencies([synthetic_type("Foo", imports=["com.example.Foo"])]) == {}

    def test_duplicate_simple_names_use_qualified_dependency_names(self):
        deps = find_dependencies([
            synthetic_type("UseA", package="com.example.use", imports=["com.example.a.Config"]),
            synthetic_type("UseB", package="com.example.use", imports=["com.example.b.Config"]),
            synthetic_type("Config", package="com.example.a"),
            synthetic_type("Config", package="com.example.b"),
        ])
        assert deps["UseA"] == ["com.example.a.Config"]
        assert deps["UseB"] == ["com.example.b.Config"]

    def test_duplicate_simple_names_use_qualified_source_keys(self):
        deps = find_dependencies([
            synthetic_type("Foo", package="com.example.a", imports=["com.example.shared.Bar"]),
            synthetic_type("Foo", package="com.example.b", imports=["com.example.shared.Bar"]),
            synthetic_type("Bar", package="com.example.shared"),
        ])
        assert deps["com.example.a.Foo"] == ["Bar"]
        assert deps["com.example.b.Foo"] == ["Bar"]

    def test_same_package_extends_beats_ambiguous_simple_name(self):
        deps = find_dependencies([
            synthetic_type("Foo", package="com.example.a", extends="BaseConfig"),
            synthetic_type("BaseConfig", package="com.example.a"),
            synthetic_type("BaseConfig", package="com.example.b"),
        ])
        assert deps["Foo"] == ["com.example.a.BaseConfig"]

    def test_real_fixtures(self):
        types = flatten_types(files_of(fixture_path("StaticFieldService.java"), fixture_path("AppConfiguration.java")))
        assert isinstance(find_dependencies(types), dict)


# ---------------------------------------------------------------------------
# filter_files
# ---------------------------------------------------------------------------

class TestFilterFiles:
    def _files(self):
        return [
            synthetic_file(synthetic_type("Foo", package="com.example.services", anns=["@Service"],
                                          extends="BaseService", implements=["Serializable"]),
                           package="com.example.services"),
            synthetic_file(synthetic_type("Bar", package="com.example.web", anns=["@Controller"]),
                           package="com.example.web"),
        ]

    def _names(self, files):
        return [t["class_name"] for t in flatten_types(files)]

    def test_no_filter(self):
        assert self._names(filter_files(self._files())) == ["Foo", "Bar"]

    def test_package_filter(self):
        assert self._names(filter_files(self._files(), pkg_filter="com.example.services")) == ["Foo"]

    def test_annotation_filter(self):
        assert self._names(filter_files(self._files(), ann_filter="@Service")) == ["Foo"]
        assert self._names(filter_files(self._files(), ann_filter="Service")) == ["Foo"]

    def test_extends_filter(self):
        assert self._names(filter_files(self._files(), ext_filter="BaseService")) == ["Foo"]

    def test_implements_filter(self):
        assert self._names(filter_files(self._files(), impl_filter="Serializable")) == ["Foo"]

    def test_type_filter_drops_empty_files(self):
        assert len(filter_files(self._files(), ann_filter="@Service")) == 1

    def test_package_filter_keeps_typeless_files(self):
        files = self._files() + [synthetic_file(package="com.example.services")]
        assert len(filter_files(files, pkg_filter="com.example.services")) == 2


# ---------------------------------------------------------------------------
# format_output
# ---------------------------------------------------------------------------

class TestFormatOutput:
    def test_basic_output(self):
        output = format_output(files_of(fixture_path("SimpleDirection.java")))
        assert "Project Map: 1 files" in output
        assert "enum SimpleDirection { NORTH, SOUTH, EAST, WEST }" in output

    def test_packages_grouped(self):
        output = format_output(files_of(fixture_path("SimpleDirection.java"), fixture_path("StaticFieldService.java")))
        assert "// com.example (1 files," in output
        assert "// com.example.services (1 files," in output

    def test_field_method_line_counts(self):
        output = format_output(files_of(fixture_path("StaticFieldService.java")))
        assert "class StaticFieldService @Service [4F | 2M | 44L | " in output
        assert "lombok:Slf4j,RequiredArgsConstructor" in output

    def test_show_deps(self):
        output = format_output(files_of(fixture_path("SealedAndMultiClass.java")), show_deps=True)
        assert "=== Dependencies ===" in output
        assert "Circle → SealedAndMultiClass" in output

    def test_show_deps_disambiguates_duplicate_names(self):
        files = [
            synthetic_file(synthetic_type("UseA", package="com.example.use", imports=["com.example.a.Config"]),
                           package="com.example.use"),
            synthetic_file(synthetic_type("Config", package="com.example.a"), package="com.example.a"),
            synthetic_file(synthetic_type("Config", package="com.example.b"), package="com.example.b"),
        ]
        output = format_output(files, show_deps=True)
        assert "UseA → com.example.a.Config" in output

    def test_show_beans(self):
        output = format_output(files_of(fixture_path("AppConfiguration.java")), show_beans=True)
        assert "Bean Producers" in output
        assert "ObjectMapper" in output

    def test_bean_dependencies_shown(self):
        output = format_output(files_of(fixture_path("StaticFieldService.java")), show_beans=True)
        assert "StaticFieldService @Service ← OrderRepository, PaymentRepository, NotificationClient" in output

    def test_config_properties_exclude_statics(self, tmp_path):
        path = tmp_path / "P.java"
        path.write_text("""
        @ConfigurationProperties("app.x")
        record P(String bucket, Duration expiry) {
            static final String DEFAULT = "d";
        }
        """, encoding="utf-8")
        output = format_output(files_of(path), show_beans=True)
        assert "app.x.* (P): String bucket, Duration expiry" in output
        assert "DEFAULT" not in output

    def test_all_comment_prefixed(self):
        for line in format_output(files_of(fixture_path("SimpleDirection.java"))).split("\n"):
            assert line.startswith("//"), f"Line not prefixed: {line!r}"

    def test_static_initializer_and_inner_types_shown(self):
        assert "static-init:" in format_output(files_of(fixture_path("Role.java")))
        assert "inner:" in format_output(files_of(fixture_path("EdgeCaseBugs.java")))

    def test_implicit_class_output(self):
        assert "implicit class ImplicitClass" in format_output(files_of(fixture_path("ImplicitClass.java")))

    def test_multi_type_file_totals_count_files_once(self):
        output = format_output(files_of(fixture_path("SealedAndMultiClass.java")))
        assert "Project Map: 1 files, 70 lines" in output
        assert "com.example.edgecases (1 files, 70 lines)" in output

    def test_interface_extends_output(self, tmp_path):
        path = tmp_path / "Child.java"
        path.write_text("package demo;\npublic interface Child extends ParentA, ParentB {}\n", encoding="utf-8")
        assert "interface Child extends ParentA, ParentB" in format_output(files_of(path))

    def test_package_annotations_on_header(self, tmp_path):
        (tmp_path / "package-info.java").write_text(
            '@ApplicationModule(displayName = "Evidence")\npackage demo.evidence;\n', encoding="utf-8"
        )
        (tmp_path / "Api.java").write_text("package demo.evidence; interface Api {}", encoding="utf-8")
        output = format_output(files_of(*sorted(tmp_path.glob("*.java"))))
        assert '// demo.evidence (2 files, 4 lines) @ApplicationModule(displayName = "Evidence")' in output


# ---------------------------------------------------------------------------
# Call hierarchy / impact output
# ---------------------------------------------------------------------------

class TestCallHierarchyOutput:
    def _write_project(self, tmp_path):
        (tmp_path / "BillingService.java").write_text("""
            package demo;
            public class BillingService {
                private final BillingRepository repository = new BillingRepository();
                public void processBilling() {
                    validate();
                    repository.save();
                }
                private void validate() {}
            }
            """, encoding="utf-8")
        (tmp_path / "BillingController.java").write_text("""
            package demo;
            public class BillingController {
                private final BillingService billingService = new BillingService();
                public void create() { billingService.processBilling(); }
            }
            """, encoding="utf-8")
        (tmp_path / "BillingScheduler.java").write_text("""
            package demo;
            public class BillingScheduler {
                private final BillingController controller = new BillingController();
                public void run() { controller.create(); }
            }
            """, encoding="utf-8")
        (tmp_path / "BillingRepository.java").write_text("""
            package demo;
            public class BillingRepository {
                public void save() {}
            }
            """, encoding="utf-8")
        return flatten_types(files_of(*sorted(tmp_path.glob("*.java"))))

    def test_callers_requires_class_qualified_target(self, tmp_path):
        assert "requires Class.method" in format_callers_output(self._write_project(tmp_path), "processBilling")

    def test_callers_show_upstream_hierarchy(self, tmp_path):
        output = format_callers_output(self._write_project(tmp_path), "BillingService.processBilling", depth=2)
        assert "Callers: BillingService.processBilling" in output
        assert "target: BillingService.processBilling()  " in output
        assert "//   ← BillingController.create()  " in output
        assert "//     ← BillingScheduler.run()  " in output

    def test_callers_stop_on_ambiguous_class_name(self, tmp_path):
        (tmp_path / "a").mkdir()
        (tmp_path / "b").mkdir()
        (tmp_path / "a" / "Config.java").write_text(
            "package demo.a; public class Config { public void build() {} }\n", encoding="utf-8")
        (tmp_path / "b" / "Config.java").write_text(
            "package demo.b; public class Config { public void build() {} }\n", encoding="utf-8")
        output = format_callers_output(flatten_types(files_of(*sorted(tmp_path.rglob("*.java")))), "Config.build")
        assert "Ambiguous target: Config.build" in output
        assert "demo.a.Config.build()" in output
        assert "demo.b.Config.build()" in output

    def test_ambiguous_simple_names_display_qualified(self, tmp_path):
        (tmp_path / "a").mkdir()
        (tmp_path / "b").mkdir()
        (tmp_path / "a" / "Config.java").write_text(
            "package demo.a; public class Config { public void build() {} }\n", encoding="utf-8")
        (tmp_path / "b" / "Config.java").write_text(
            "package demo.b; public class Config { public void build() {} }\n", encoding="utf-8")
        (tmp_path / "User.java").write_text(
            "package demo; import demo.a.Config; class User { Config c; void go() { c.build(); } }\n",
            encoding="utf-8")
        output = format_callers_output(flatten_types(files_of(*sorted(tmp_path.rglob("*.java")))), "demo.a.Config.build")
        assert "target: demo.a.Config.build()" in output
        assert "← User.go()" in output

    def test_impact_shows_callers_and_callees(self, tmp_path):
        output = format_impact_output(self._write_project(tmp_path), "BillingService.processBilling", depth=1)
        assert "Impact: BillingService.processBilling" in output
        assert "← BillingController.create()" in output
        assert "→ BillingService.validate()" in output
        assert "→ BillingRepository.save()" in output


# ---------------------------------------------------------------------------
# Full project scan
# ---------------------------------------------------------------------------

class TestFullProjectScan:
    def test_scan_all_fixtures(self):
        files = files_of(*sorted(FIXTURES_DIR.rglob("*.java")))
        assert len(files) > 20
        output = format_output(files, show_deps=True, show_endpoints=True, show_beans=True)
        assert output.startswith("//")
        assert "Project Map: 34 files, 2003 lines" in output
