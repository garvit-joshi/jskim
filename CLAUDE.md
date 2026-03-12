# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**jskim** is a token-saving Java file reader for Claude Code. It uses tree-sitter to parse and summarize Java files compactly, reducing token usage by 70-80%. Optimized for Spring Boot projects with Lombok, REST controllers, DI wiring, and configuration properties.

**You are both the builder and the primary user of this tool.** Every output format decision, every new feature, every piece of information included or excluded — evaluate it from the perspective of "does this help me (Claude) understand Java codebases faster with fewer tokens?" If a feature sounds good in theory but won't change how you actually work with code, it's not worth building.

Published as a PyPI package (`pip install jskim`). Python 3.10+ required.

## Build & Development Commands

```bash
pip install -e .              # Install locally in editable mode
python -m build               # Build distribution artifacts
pytest                        # Run all tests
pytest tests/test_diff.py     # Run specific test file
pytest tests/test_diff.py::TestParseDiffOutput::test_modified_file  # Run single test
```

**Dependencies:** `tree-sitter>=0.25.0`, `tree-sitter-java>=0.23.0`. Build backend: `hatchling`.

## Architecture

The CLI entry point (`cli.py`) auto-detects the operation mode based on input and routes to one of four modules:

```
cli.py (entry point, auto-detection + flag parsing)
├── skim.py      — Single file summarization (imports, fields, methods with line ranges)
├── project.py   — Directory-wide project map (packages, classes, Spring metadata)
├── method.py    — Method extraction with context (fields, called methods, source)
└── diff.py      — Git diff mode (summarize only changed Java files/methods)

All modules share: util.py — tree-sitter parsing utilities (65+ functions)
```

**Key design patterns:**
- `util.py` is the shared foundation — all AST parsing, annotation extraction, field/method analysis, and Spring-specific logic lives here. Constants like `LOMBOK_SET`, `HTTP_MAPPING_ANNOTATIONS`, and `SPRING_PARAM_ANNOTATIONS` are centralized here.
- `skim.py` classifies methods as getter/setter/boilerplate/constructor/business-logic and collapses non-interesting ones to names only.
- `project.py` aggregates per-file summaries into package-level views and produces Spring-specific reports (`--endpoints`, `--beans`, `--deps`).
- `diff.py` parses unified diff format, tracks changed line numbers, then uses `util.py` to determine which methods overlap with changes. Marks output with `[NEW]`/`[MODIFIED]`/`[DELETED]`.

**Source layout:** All modules are under `src/jskim/`. Version is in `src/jskim/__init__.py` and extracted by hatchling at build time.

## CLI Modes & Flags

| Input | Mode | Module |
|---|---|---|
| `jskim File.java` | File summary | `skim.py` |
| `jskim File.java methodName` | Method extraction | `method.py` |
| `jskim File.java --list` | List methods | `method.py` |
| `jskim src/` | Project map | `project.py` |
| `jskim --diff HEAD~1` | Diff summary | `diff.py` |

Flags: `--grep`, `--annotation`, `--package`, `--extends`, `--implements`, `--deps`, `--endpoints`, `--beans`, `--diff`.

## Testing

Tests are in `tests/` using pytest. Currently covers `diff.py` (`test_diff.py`) with test classes for `parse_diff_output`, `_changes_overlap`, `format_diff_output`, `_resolve_base_ref`, and deletion line tracking edge cases. No linting or formatting tools are configured.

## CI/CD

GitHub Actions workflow (`.github/workflows/publish.yml`) publishes to PyPI on release using Python 3.12.

## Design Principles (Strictly Enforced by the User)

The user is meticulous about code quality and will reject sloppy work. Follow these principles without exception:

- **No code duplication** — never copy-paste logic across modules. If a helper exists in `util.py`, use it. If you need something that doesn't exist yet but is reusable, add it to `util.py` — not inline in a feature module.
- **All constants live in `util.py`** — node type sets (`INNER_TYPE_NODES`, `METHOD_NODES`), annotation sets (`LOMBOK_SET`, `SPRING_PARAM_ANNOTATIONS`, `HTTP_MAPPING_ANNOTATIONS`), and any new domain constants belong in `util.py`. Do not scatter literals across modules. If the value represents a domain concept, it goes in a constant.
- **All tree-sitter parsing goes through `util.py`** — no module should import `tree_sitter` or `tree_sitter_java` directly. `util.py` owns the parser instance, the `Language` object, and all AST traversal helpers. Feature modules consume parsed results only.
- **One module per CLI mode** — each operational mode (skim, project, method, diff) has its own module with a `main()` entry point. New modes follow this pattern: add a module, route from `cli.py`. Do not pile unrelated modes into an existing module.
- **CLI routing stays in `cli.py`** — auto-detection and flag routing logic lives exclusively in `cli.py`. Individual modules parse their own flags but never decide which mode to run.
- **Private functions are prefixed with `_`** — internal helpers not meant for cross-module use (e.g., `_get_modifier_keywords`, `_strip_quotes`, `_find_string_literals`) must be underscore-prefixed. Public `util.py` functions are the module API.
- **Functions return plain dicts, not custom classes** — the codebase uses dicts for parsed data structures (fields, methods, type info). Keep this convention. Don't introduce dataclasses or named tuples unless there's a compelling reason discussed with the user.
- **Don't assume — ask, but bring your perspective** — when requirements are ambiguous or there are multiple valid approaches, ask the user before implementing. But don't just ask — offer your opinion as the consumer of this tool. "This feature would/wouldn't help me because..." is more useful than "which approach do you prefer?" The user values being consulted, but also values your informed perspective on what actually makes the skill more effective.
- **Push back when something is wrong** — you are a user of this skill, not just a builder. If a proposed feature won't actually help you (the AI) work more effectively with Java codebases, say so bluntly. Evaluate feature requests from the perspective of "will this save me tokens, reduce tool calls, or give me information I can't get another way?" If the answer is no, push back and suggest what would actually help. Similarly, push back on code changes that introduce code smells, break separation of concerns, or duplicate existing logic. The user respects honest technical disagreement.
- **Always use existing helper functions** — if `util.py` has a function for an operation (e.g., `get_annotations()`, `extract_field_info()`, `build_method_signature()`), use it. Never reimplement the same AST traversal inline. Check `util.py` before writing new tree-sitter traversal code.
- **No magic strings for node types or annotations** — use the constant sets in `util.py` (`METHOD_NODES`, `INNER_TYPE_NODES`, `LOMBOK_SET`, etc.). If you need a new node type or annotation set, add it as a named constant.
- **New tree-sitter node support requires full-chain updates** — when adding support for a new Java construct (e.g., a new annotation type, a new declaration kind), update the entire chain: constant set in `util.py` → extraction helper in `util.py` → consumption in every module that handles that category (skim, project, method, diff). Missing any module causes silent omission in output.
- **Always update SKILL.md when changing output** — `SKILL.md` is what teaches future Claude instances how to use and interpret the tool's output. If you change output format, add a feature, or alter behavior, update `SKILL.md` to match. An outdated SKILL.md means future instances will misinterpret results or miss capabilities entirely. This includes: output format examples, interpretation guidance, workflow recommendations, and the "when to use" table.
- **Test on real codebases, not just toy examples** — after making changes, test on a real Spring Boot project with hundreds of files, large controllers, deep service layers, and Lombok-heavy DTOs. Toy 20-line examples pass easily but miss edge cases like massive import lists, deeply nested generics, enum services, and methods with 15+ calls. If the user has a project available, use it.
