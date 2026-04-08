# Changelog

All notable changes to jskim are documented here.

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
