# jskim

[![PyPI version](https://img.shields.io/pypi/v/jskim)](https://pypi.org/project/jskim/)
[![Python](https://img.shields.io/pypi/pyversions/jskim)](https://pypi.org/project/jskim/)
[![License](https://img.shields.io/github/license/garvit-joshi/jskim)](https://github.com/garvit-joshi/jskim/blob/main/LICENSE.txt)

Token-saving Java file reader for Claude Code, optimized for Spring Boot. Summarizes Java files compactly using tree-sitter, saving 70-80% of input tokens compared to reading files directly.

> *A human counted the tokens. An AI counted the getters. Both decided life's too short.*

## Installation

```bash
pip install jskim
```

Requires Python 3.10+.

## Usage

`jskim` auto-detects the mode based on whether you pass a file or directory.

### Summarize a Java file

```bash
jskim <file.java>
jskim <file.java> --grep <pattern>        # filter methods by name/signature
jskim <file.java> --annotation <@Ann>     # filter methods by annotation
jskim A.java B.java C.java                # multiple files
```

### Project map

Generates a compact map of all Java files in a directory: packages, classes, annotations, field/method counts, Lombok usage, enum constants.

```bash
jskim <src_dir>
jskim <src_dir> --deps                 # import-based dependencies
jskim <src_dir> --endpoints             # REST endpoint map
jskim <src_dir> --beans                 # Spring bean DI graph + @Bean producers + config properties
jskim <src_dir> --package <prefix>      # filter by package
jskim <src_dir> --annotation <@Ann>     # filter by class annotation
jskim <src_dir> --extends <ClassName>   # filter by superclass
jskim <src_dir> --implements <Name>     # filter by implemented interface
```

**Spring Boot flags:**
- `--endpoints` — lists all REST endpoints: HTTP method, full path (base + method), handler, line number
- `--beans` — shows bean DI wiring (via `@Autowired` and `@RequiredArgsConstructor` + final fields), `@Bean` factory method producers, and `@ConfigurationProperties` with prefix + field details
- `--implements` — filter classes by implemented interface name

### Diff mode

Summarizes only the Java files and methods changed in a git diff. Ideal for PR reviews.

```bash
jskim --diff HEAD~1                    # changes since last commit
jskim --diff main                      # changes vs main branch
jskim --diff main...feature-branch     # merge-base comparison
jskim src/ --diff HEAD~1               # scoped to directory
git diff main | jskim --diff -         # read diff from stdin
```

Output marks methods as `[NEW]`, `[MODIFIED]`, or `[DELETED]`. Getters/setters/boilerplate changes are suppressed.

### Extract methods

```bash
jskim <file.java> --list                          # list all methods
jskim <file.java> <method_name>                    # extract one method
jskim <file.java> <method1> <method2> <method3>    # extract multiple
```

## Method calls (`→`)

Each method in the skim output shows its direct method invocations:

```
// methods:
//     L45-L62 ( 18 lines): @PostMapping public Bill createBill(BillDTO dto)
//                → auditLogger.log, billingService.create, notifyStakeholders, validator.validate
//     L64-L80 ( 17 lines): @GetMapping("/{id}") public Bill getBill(Long id)
//                → billingService.findById
```

Cross-reference the `→` calls with the `fields:` section to trace call flow across files — if a method calls `billingService.create`, the fields show `BillingService billingService`, so skim `BillingService.java` next. Chained/fluent calls (streams, builders) are excluded to keep output compact.

## Usage as a Claude Code Skill

This project is designed to be used as a [Claude Code skill](https://docs.anthropic.com/en/docs/claude-code/skills). The `SKILL.md` file configures the skill behavior, auto-triggering when working with Java files.

Install from the [Vercel Skills Registry]([https://skills.claudecode.dev](https://skills.sh/garvit-joshi/jskim/jskim)):

```bash
npx skills add garvit-joshi/jskim
```

Once installed, invoke with `/jskim`:

```
/jskim <file.java>              # summarize a file
/jskim <src_dir>                # project map
/jskim <file.java> <method>     # extract a method
```

## Workflow

1. **Explore** — `jskim src/` to understand project structure
2. **Narrow** — `jskim src/ --package com.example.billing` to focus on a package
3. **Spring context** — `jskim src/ --endpoints --beans` to see REST API + DI wiring
4. **Understand** — `jskim File.java` to see class structure, fields, methods, and calls
5. **Trace** — Follow `→` calls by matching field types to find the next class to skim
6. **Filter** — `jskim File.java --grep billing` for large classes
7. **Focus** — `jskim File.java methodA methodB` to read specific methods
8. **Edit** — Use `Read` with `offset`/`limit` on only the lines that matter

## Dependencies

- [tree-sitter](https://pypi.org/project/tree-sitter/) — Incremental parsing library
- [tree-sitter-java](https://pypi.org/project/tree-sitter-java/) — Java grammar for tree-sitter
