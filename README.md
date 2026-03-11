# jskim

Token-saving Java file reader for Claude Code. Summarizes Java files compactly using tree-sitter, saving 70-80% of input tokens compared to reading files directly.

> *A human counted the tokens. An AI counted the getters. Both decided life's too short.*

## Installation

```bash
pip install -r requirements.txt
```

Requires Python 3.8+.

## Tools

### `jskim.py` — Single file summary

Summarizes a Java file: collapses imports, fields, boilerplate (getters/setters/equals/hashCode), and shows method signatures with line ranges.

```bash
python3 jskim.py <file.java>
python3 jskim.py <file.java> --grep <pattern>        # filter methods by name/signature
python3 jskim.py <file.java> --annotation <@Ann>     # filter methods by annotation
python3 jskim.py A.java B.java C.java                # multiple files
```

### `jskim_project.py` — Project map

Generates a compact map of all Java files in a directory: packages, classes, annotations, field/method counts, Lombok usage.

```bash
python3 jskim_project.py <src_dir>
python3 jskim_project.py <src_dir> --deps                 # import-based dependencies
python3 jskim_project.py <src_dir> --package <prefix>      # filter by package
python3 jskim_project.py <src_dir> --annotation <@Ann>     # filter by class annotation
python3 jskim_project.py <src_dir> --extends <ClassName>   # filter by superclass
```

### `jskim_method.py` — Method extraction

Extracts method source code with context (fields, called methods, annotations, Javadoc).

```bash
python3 jskim_method.py <file.java> --list                          # list all methods
python3 jskim_method.py <file.java> <method_name>                    # extract one method
python3 jskim_method.py <file.java> <method1> <method2> <method3>    # extract multiple
```

### `jskim_util.py` — Shared utilities

Shared tree-sitter parsing utilities used by all three tools. Not invoked directly.

## Usage as a Claude Code Skill

This project is designed to be used as a [Claude Code skill](https://docs.anthropic.com/en/docs/claude-code/skills). The `SKILL.md` file configures the skill behavior, auto-triggering when working with Java files.

Install by adding the skill directory to your Claude Code configuration. Once installed, invoke with `/jskim`:

```
/jskim <file.java>              # summarize a file
/jskim <src_dir>                # project map
/jskim <file.java> <method>     # extract a method
```

## Workflow

1. **Explore** — `jskim_project.py src/` to understand project structure
2. **Narrow** — `jskim_project.py src/ --package com.example.billing` to focus on a package
3. **Understand** — `jskim.py File.java` to see class structure
4. **Filter** — `jskim.py File.java --grep billing` for large classes
5. **Focus** — `jskim_method.py File.java methodA methodB` to read specific methods
6. **Edit** — Use `Read` with `offset`/`limit` on only the lines that matter

## Dependencies

- [tree-sitter](https://pypi.org/project/tree-sitter/) — Incremental parsing library
- [tree-sitter-java](https://pypi.org/project/tree-sitter-java/) — Java grammar for tree-sitter
