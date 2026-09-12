# Changelog

All notable changes to jskim are documented here.

## [0.3.0] - 2026-09-12

Output format changed throughout; no backward compatibility is kept. Every change was driven by running the tool against a 470-file Spring Boot 4 / Java 25 backend and reading the result as the consumer.

### Fixes
- **REST endpoint paths were wrong whenever a controller used constants** — `@RequestMapping(TripController.BASE_PATH)` and `path = ONE_TRIP + "/assign"` produced `/` and `/assign`. Paths now resolve `static final String` constants, `Class.CONSTANT` references and `+` concatenation across the whole project; unresolvable expressions stay visible as source text
- **Bean dependencies were empty without Lombok** — constructor injection is now read from constructor parameters; Lombok constructor annotations fall back to final fields; `@Autowired`/`@Inject` fields still count
- **`package-info.java` was dropped** — package-level annotations (Spring Modulith `@ApplicationModule`, `@NamedInterface`) now appear on the project-map package header and in the file summary
- **`@ConfigurationProperties` listings included static constants** — only instance fields and record components are shown
- **`--grep` on a directory was silently ignored** — every mode now warns on stderr about flags it does not use
- **Varargs identities** — `String... names` renders as `String...` instead of `?`

### Output
- `fields:` lists instance fields only; a new `static fields:` line lists constants by name
- Annotation arguments are shown for every behaviour-changing annotation (`@RequiresPermission(...)`, `@ResponseStatus(...)`, `@Transactional(readOnly = true)`), whitespace-normalized and capped; repeats are deduped; the old whitelist is gone
- OpenAPI/Swagger documentation annotations (`@Operation`, `@ApiResponse`, `@Parameter`, `@Schema`, `@Tag`, ...) are dropped everywhere
- Mapping annotations render only their (resolved) path: `@PostMapping("/trips/{tripId}/start")`; `@RequestMapping(GET "/x")` when a method is given
- Parameter annotations keep the marker and lose their arguments: `@RequestParam Integer size`
- `→` calls list only followable calls: same-class, `field.method`, `Class.method`, `super.method`. Calls on locals and parameters (46% of all entries on the reference backend) are dropped
- Import category breakdown replaced by a bare count: `// com.example | 45 imports`
- `--callers`/`--impact` show simple class names (fully qualified only on collision) next to the file path
- Diff mode reports added/removed instance fields and record components as `[FIELDS] +Type name, -Type name`; `(non-method changes only)` became `(no field or method changes)`
- Project-map `NF` counts instance fields only

### Internals
- One parse chain in `util.py` (`parse_java_source` → `parse_type` → `parse_type_members`); skim, method, project and diff only format. Three duplicated member walkers, the regex-based `classify_method`, and the module-to-module import from `diff.py` to `skim.py` are gone
- Single argparse parser in `cli.py`; modules take the parsed namespace via `main(args)`
- Spring stereotype, Lombok and noise-annotation constants centralized in `util.py`

### Dependencies
- Verified against `tree-sitter` 0.26.0 (its removed APIs were never used) and 0.25.2, with `tree-sitter-java` 0.23.5; the declared ranges are unchanged

### Tests
- Suite rewritten for the new API and extended to 435 tests covering constant resolution, annotation rendering, call filtering, constructor injection, endpoint resolution, package annotations, mode-flag warnings and field diffs

## [0.2.5] - 2026-05-16

### Features
- **Method caller/impact mode** — project mode now supports `--callers Class.method` for bounded upstream call hierarchies and `--impact Class.method` for callers plus downstream callees, with `--depth` controlling traversal size
- **Qualified target safety** — caller/impact mode requires class-qualified method targets and reports ambiguous simple class names instead of guessing

### Tests
- Added coverage for caller/impact formatting, class-qualified target validation, ambiguous simple class names, CLI routing, and bounded hierarchy output
- Expanded the suite to 401 tests

### CI
- Updated `pypa/gh-action-pypi-publish` from `v1.13.0` to `v1.14.0`

### Docs
- Updated `README.md`, `SKILL.md`, and `CLAUDE.md` with caller/impact usage, output examples, and agent workflow guidance

## [0.2.4] - 2026-04-08

### Fixes
- **Dependency graph disambiguation** — `--deps` now resolves project references by package and import context instead of collapsing everything to simple class names, so duplicate type names like `Config` no longer produce ambiguous or incorrect dependency edges
- **Conditional fully-qualified dependency names** — dependency output stays compact when names are unique, and only switches to fully-qualified names when a collision would otherwise make the graph unclear

### Tests
- Added regression coverage for duplicate dependency target names, duplicate source class names, same-package `extends` resolution, and `--deps` output formatting under name collisions

### Docs
- Updated `README.md` and `SKILL.md` to document that `--deps` shows fully-qualified names only when simple names are ambiguous

## [0.2.3] - 2026-04-04

### Fixes
- **Implicit class support completed** — Java simple source files without an explicit top-level type now show up consistently in skim, method, and project mode instead of being silently dropped
- **Project totals now count unique files** — project map headers and package summaries no longer double-count lines or files when a single Java file contains multiple top-level types
- **Interface inheritance preserved** — interface `extends` clauses are now parsed and rendered correctly in skim and project output
- **Overloaded diff detection fixed** — diff mode now matches methods by name plus parameter types, so overload additions and removals are reported as `[NEW]` and `[DELETED]` instead of collapsing into `[MODIFIED]`

### Tests
- Added regression coverage for implicit classes, unique project totals, interface inheritance, and overloaded diff handling
- Expanded the suite to 390 tests

### Docs
- **Generalized product positioning** — updated package metadata, README, and skill docs to describe jskim as a tool for AI coding agents instead of a Claude-specific tool
- **Skill guidance made more portable** — replaced host-specific `Read`/`Edit` wording in `SKILL.md` with generic file-reading and editing guidance
- **Release docs cleaned up** — clarified skill-enabled environment wording while keeping the published install path and slash-command examples accurate

## [0.2.2] - 2026-03-14

### Fixes
- **Records now show fields** — record components (e.g., `record Point(int x, int y)`) were showing 0 fields; now properly extracted and displayed
- **Generic type parameters preserved** — class declarations like `Container<T extends Comparable<T>>` no longer lose the `<T>` portion
- **Annotation-type interface support** — `@interface` element declarations (e.g., `String value(); int priority() default 0;`) are now handled as methods instead of being invisible
- **Implicit class crash fixed** — Java 23+ implicitly declared classes (no type declaration wrapper) no longer crash the parser

### Tests
- Added 45 new tests and 3 fixture files covering records, generics, annotation-type interfaces, and implicit classes
- Fixed weak assertion in `test_grep_filter` that could miss leaked methods (371 total tests)

## [0.2.1] - 2026-03-13

### Features
- **Filter noise from method call traces** — Collection ops (`put`, `get`, `add`), utility checks (`Objects.equals`, `StringUtils.isBlank`), logging (`log.info`), stream plumbing (`map`, `filter`, `collect`), and type conversions (`toString`, `valueOf`) are now auto-excluded from call traces. Only business-logic calls remain.

### Meta
- Added comprehensive test suite (326 tests) and CI workflow
- Added Vercel Skills Registry install command to README
- Added `allowed-tools` to SKILL.md for auto-permission of jskim commands

## [0.2.0] - 2026-03-12

### Features
- **Method call tracing** — each method in skim and diff output now shows its direct method invocations via `→` traces
- Cross-reference `→` calls with `fields:` section to trace call flow across files
- Chained/fluent calls (streams, builders) automatically excluded
- Calls capped at 10 per method with `+N more` overflow
- Works in both file skim and diff modes

### Docs
- Updated SKILL.md with signal vs noise guide, call flow tracing examples
- Added CLAUDE.md with project guidelines and architecture docs

## [0.1.1] - 2026-03-12

### Fixes
- **Deduplicate Bean producer types** — repeated return types now show a count (e.g., `ConcurrentKafkaListenerContainerFactory(x7)`) instead of listing duplicates
- **Exit code discipline** — `jskim` now exits with code 1 when files are not found
- **Deduplicate shared constants** — `INNER_TYPE_NODES`, `METHOD_NODES`, `LOMBOK_SET` moved to single source in `util.py`

### CI
- Pin `pypa/gh-action-pypi-publish` to `v1.13.0`

## [0.1.0] - 2026-03-12

Initial release. Token-saving Java file reader for AI coding agents.

### Features
- **File summary** — collapses imports, fields, boilerplate; shows method signatures with line ranges
- **Project map** — compact overview of all Java files with package grouping
- **Method extraction** — extract method source code with context (fields, called methods)
- **Diff mode** — summarize only files/methods changed in a git diff
- **Spring Boot support** — REST endpoint map, bean DI graph, Bean producers, ConfigurationProperties, Lombok awareness
- **Unified CLI** — single `jskim` command auto-detects mode
- **Agent skill definition** — supports skill-enabled environments when working with `.java` files
