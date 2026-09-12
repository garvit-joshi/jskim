# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**jskim** is a token-saving Java file reader for Claude Code. It uses tree-sitter to parse and summarize Java files compactly, reducing token usage by 70-80%. Optimized for Spring Boot projects: REST controllers, DI wiring, configuration properties, Lombok, records, Spring Modulith packages.

**You are both the builder and the primary user of this tool.** Every output format decision, every new feature, every piece of information included or excluded — evaluate it from the perspective of "does this help me (Claude) understand Java codebases faster with fewer tokens?" If a feature sounds good in theory but won't change how you actually work with code, it's not worth building.

Published as a PyPI package (`pip install jskim`). Python 3.10+ required.

## Build & Development Commands

```bash
pip install -e .              # Install locally in editable mode (the .venv otherwise pins an old wheel)
python -m build               # Build distribution artifacts
pytest                        # Run all tests
pytest tests/test_diff.py     # Run specific test file
pytest tests/test_diff.py::TestParseDiffOutput::test_modified_file  # Run single test
```

**Dependencies:** `tree-sitter>=0.25.0`, `tree-sitter-java>=0.23.0`. Build backend: `hatchling`.

## Architecture

`cli.py` owns the single argparse parser and picks the mode from the positional arguments. Every mode module exposes `main(args)` taking the parsed namespace and only formats output; all parsing lives in `util.py`.

```
cli.py (argparse, mode auto-detection, warns about flags the mode does not use)
├── skim.py      — Single file summary
├── project.py   — Directory-wide project map, Spring reports, call hierarchy
├── method.py    — Method listing / extraction with context
└── diff.py      — Git diff mode (changed files, fields, methods)

util.py — the only module that imports tree_sitter:
  parse_java_source(content) -> {"package", "package_annotations", "imports", "types", "total_lines"}
    parse_type(decl)         -> {"kind", "name", "declaration", "annotations", "annotation_names",
                                 "fields", "methods", "inner_types", "static_initializers",
                                 "enum_constants", "constants", "extends", "implements", ...}
      parse_type_members()   -> fields (parse_field), methods (parse_method), inner types
```

**Key design patterns:**
- `util.parse_java_source` is the one parse chain. skim/method/project/diff consume its dicts and never walk the AST themselves. Adding information to the output means adding a key in `parse_type`/`parse_method`/`parse_field`, then rendering it in the modules that care.
- Annotation rendering is centralized in `util.get_annotations_rich`: noise annotations (`NOISE_ANNOTATIONS`) are dropped, repeats deduped, arguments whitespace-normalized and capped at `ANNOTATION_ARGS_MAX`. HTTP mapping annotations render only their path, resolved through `resolve_string_expression` against the class's `static final String` constants (`extract_string_constants`).
- `extract_method_calls(node, field_names)` keeps only calls that can be followed from a summary: same-class, `field.method`, `Class.method`, `super.method`. Calls on locals/parameters are dropped.
- `fields` carry `static`/`final`/`component` flags. Every consumer separates instance fields from constants via `instance_fields()`/`static_fields()`.
- `project.py` keeps file-level dicts (`scan_java_file` → `{"filepath", "package", "package_annotations", "types": [...]}`) so `package-info.java` annotations reach the package header; `flatten_types()` gives the per-type rows used by dependency, endpoint and call-graph code. Endpoints are resolved in a post-pass (`collect_endpoints`) so constants in other classes resolve.
- Bean dependencies come from constructor parameters; Lombok constructor annotations fall back to final fields; `@Autowired`/`@Inject` fields always count.
- `diff.py` compares old vs new `parse_java_source` results: methods by `Type.identity`, instance fields by `Type:type name`.

**Source layout:** All modules are under `src/jskim/`. Version is in `src/jskim/__init__.py` and extracted by hatchling at build time.

## CLI Modes & Flags

| Input | Mode | Module |
|---|---|---|
| `jskim File.java` | File summary | `skim.py` |
| `jskim File.java methodName` | Method extraction | `method.py` |
| `jskim File.java --list` | List methods | `method.py` |
| `jskim src/` | Project map | `project.py` |
| `jskim src/ --callers Class.method` | Upstream caller hierarchy | `project.py` |
| `jskim src/ --impact Class.method` | Callers + callees impact view | `project.py` |
| `jskim --diff HEAD~1` | Diff summary | `diff.py` |

Flags: `--grep`, `--annotation`, `--package`, `--extends`, `--implements`, `--deps`, `--endpoints`, `--beans`, `--callers`, `--impact`, `--depth`, `--diff`, `--list`. `cli.MODE_FLAGS` says which flags each mode uses; the rest produce a stderr warning.

## Testing

Tests are in `tests/` using pytest, one file per module (`test_util.py`, `test_skim.py`, `test_method.py`, `test_project.py`, `test_diff.py`, `test_cli.py`) plus Java fixtures in `tests/fixtures/`. `test_cli.py` runs the CLI as a subprocess. No linting or formatting tools are configured.

After changing output, also run against a real Spring Boot codebase (hundreds of files, constructor injection, constant-based `@RequestMapping` paths, records, Spring Modulith `package-info.java`) and read the result as the consumer. Toy fixtures pass easily but miss the cases that made the output wrong before 0.3.0.

## CI/CD

GitHub Actions workflow (`.github/workflows/publish.yml`) publishes to PyPI on release using Python 3.12.

## Design Principles (Strictly Enforced by the User)

The user is meticulous about code quality and will reject sloppy work. Follow these principles without exception:

- **No code duplication** — never copy-paste logic across modules. If a helper exists in `util.py`, use it. If you need something that doesn't exist yet but is reusable, add it to `util.py` — not inline in a feature module.
- **All constants live in `util.py`** — node type sets (`INNER_TYPE_NODES`, `METHOD_NODES`), annotation sets (`LOMBOK_SET`, `SPRING_STEREOTYPES`, `NOISE_ANNOTATIONS`, `HTTP_MAPPING_ANNOTATIONS`), display limits (`CALLS_DISPLAY_MAX`) and any new domain constants belong in `util.py`. Do not scatter literals across modules.
- **All tree-sitter parsing goes through `util.py`** — no module should import `tree_sitter` or `tree_sitter_java` directly, and feature modules never import each other. `util.py` owns the parser instance, the `Language` object, and all AST traversal helpers. Feature modules consume parsed dicts only.
- **One module per CLI mode** — each operational mode (skim, project, method, diff) has its own module with a `main(args)` entry point. New modes follow this pattern: add a module, add its flags to `cli.build_parser` and `cli.MODE_FLAGS`, route from `cli.py`.
- **CLI parsing stays in `cli.py`** — flags are declared once in `build_parser`. Modules read the namespace; they never parse `sys.argv`.
- **Private functions are prefixed with `_`** — internal helpers not meant for cross-module use must be underscore-prefixed. Public `util.py` functions are the module API.
- **Functions return plain dicts, not custom classes** — the codebase uses dicts for parsed data structures (fields, methods, type info). Keep this convention. Don't introduce dataclasses or named tuples unless there's a compelling reason discussed with the user.
- **Don't assume — ask, but bring your perspective** — when requirements are ambiguous or there are multiple valid approaches, ask the user before implementing. But don't just ask — offer your opinion as the consumer of this tool. "This feature would/wouldn't help me because..." is more useful than "which approach do you prefer?"
- **Push back when something is wrong** — you are a user of this skill, not just a builder. If a proposed feature won't actually help you (the AI) work more effectively with Java codebases, say so bluntly. Evaluate feature requests from the perspective of "will this save me tokens, reduce tool calls, or give me information I can't get another way?" Similarly, push back on code changes that introduce code smells, break separation of concerns, or duplicate existing logic.
- **Always use existing helper functions** — check `util.py` before writing new tree-sitter traversal code.
- **No magic strings for node types or annotations** — use the constant sets in `util.py`.
- **New tree-sitter node support requires full-chain updates** — when adding support for a new Java construct, update `util.py` (constant set → extraction → key in the parsed dict) and then every module that renders that category (skim, project, method, diff). Missing a module causes silent omission in output.
- **Always update SKILL.md when changing output** — `SKILL.md` is what teaches future Claude instances how to use and interpret the tool's output. If you change output format, add a feature, or alter behavior, update `SKILL.md` to match, including output examples, interpretation guidance, workflow recommendations, and the "when to use" table.
- **Test on real codebases, not just toy examples** — after making changes, test on a real Spring Boot project with hundreds of files, large controllers, deep service layers, and Lombok-heavy or record-heavy DTOs.
- **No `@` mentions in commit messages** — GitHub interprets `@word` in commit messages as user mentions and sends notifications. Avoid bare `@` in commit subjects/bodies (e.g., write `annotation-type interface` instead of `@interface`). The `Co-Authored-By` trailer is fine since GitHub handles it specially.
