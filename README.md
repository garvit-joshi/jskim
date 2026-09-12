# jskim

[![PyPI version](https://img.shields.io/pypi/v/jskim)](https://pypi.org/project/jskim/)
[![Python](https://img.shields.io/pypi/pyversions/jskim)](https://pypi.org/project/jskim/)
[![License](https://img.shields.io/github/license/garvit-joshi/jskim)](https://github.com/garvit-joshi/jskim/blob/main/LICENSE.txt)

Token-saving Java file reader for AI coding agents, optimized for Spring Boot. Summarizes Java files compactly using tree-sitter, saving 70-80% of input tokens compared to reading files directly. Zero setup, no index: every run parses the current working tree.

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

Java simple source files without an explicit type wrapper are summarized as `implicit class <FileStem>`. A `package-info.java` shows its package-level annotations (Spring Modulith `@ApplicationModule`).

The summary shows instance fields and static constants separately, keeps annotation arguments that change behaviour (`@RequiresPermission(Perms.X)`, `@Transactional(readOnly = true)`), drops OpenAPI/Swagger documentation annotations, and resolves mapping paths from class constants (`@PostMapping(path = ONE_TRIP + "/start")` → `@PostMapping("/trips/{tripId}/start")`).

### Project map

Generates a compact map of all Java files in a directory: packages (with `package-info.java` annotations), classes, annotations, field/method counts, Lombok usage, enum constants.

```bash
jskim <src_dir>
jskim <src_dir> --deps                 # import-based dependencies
jskim <src_dir> --endpoints             # REST endpoint map
jskim <src_dir> --beans                 # Spring bean DI graph + @Bean producers + config properties
jskim <src_dir> --callers Class.method  # upstream callers for a specific method
jskim <src_dir> --impact Class.method   # callers + direct callees for a specific method
jskim <src_dir> --impact Class.method --depth 2  # bounded hierarchy depth
jskim <src_dir> --package <prefix>      # filter by package
jskim <src_dir> --annotation <@Ann>     # filter by class annotation
jskim <src_dir> --extends <ClassName>   # filter by superclass
jskim <src_dir> --implements <Name>     # filter by implemented interface
```

**Spring Boot flags:**
- `--endpoints` — lists all REST endpoints: HTTP method, full path (base + method), handler, line number. Paths built from constants (`@RequestMapping(BASE_PATH)`, `TRIPS + "/{id}"`, `ApiPaths.ROOT`) are resolved across the project
- `--beans` — shows bean DI wiring (constructor parameters, or Lombok constructor + final fields, or `@Autowired`/`@Inject` fields), `@Bean` factory method producers, and `@ConfigurationProperties` with prefix + field details
- `--callers Class.method` — shows resolved upstream callers for a specific method; use a fully-qualified class name when class names collide
- `--impact Class.method` — shows both upstream callers and downstream calls from the target method
- `--depth N` — controls caller/impact traversal depth; defaults to 1 to keep output compact
- `--implements` — filter classes by implemented interface name
- `--deps` — uses fully-qualified names when simple class names would be ambiguous

Call hierarchy mode resolves same-class calls, static calls on project classes, and field calls such as `billingService.create()` when the field type points to a project class. It intentionally skips unresolved local-variable/parameter calls and ambiguous overload edges rather than guessing. Classes are shown by simple name and fully qualified only when the simple name is ambiguous.

Example:

```bash
jskim src/ --callers BillingService.create --depth 2
```

```text
// === Callers: BillingService.create (depth 2) ===
// target: BillingService.create(BillDTO)  src/.../BillingService.java:L45
//
// callers:
//   ← BillingController.createBill(BillDTO)  src/.../BillingController.java:L62
//     ← BillingJob.retryFailedBills()  src/.../BillingJob.java:L30
```

```bash
jskim src/ --impact BillingService.create
```

```text
// === Impact: BillingService.create (depth 1) ===
// target: BillingService.create(BillDTO)  src/.../BillingService.java:L45
//
// callers:
//   ← BillingController.createBill(BillDTO)  src/.../BillingController.java:L62
//
// calls:
//   → BillingRepository.save(Bill)  src/.../BillingRepository.java:L20
//   → BillingService.validate(BillDTO)  src/.../BillingService.java:L80
```

### Diff mode

Summarizes only the Java files and methods changed in a git diff. Ideal for PR reviews.

```bash
jskim --diff HEAD~1                    # changes since last commit
jskim --diff main                      # changes vs main branch
jskim --diff main...feature-branch     # merge-base comparison
jskim src/ --diff HEAD~1               # scoped to directory
git diff main | jskim --diff -         # read diff from stdin
```

Output marks methods as `[NEW]`, `[MODIFIED]`, or `[DELETED]`, and added/removed instance fields or record components as `[FIELDS] +Type name, -Type name`. Getters/setters/boilerplate changes are suppressed.
Deleted methods are shown with their previous signature when a base ref is available, so overload removals stay distinguishable.

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
//     L45-L62 ( 18 lines): @PostMapping("/bills") public Bill createBill(@RequestBody BillDTO dto)
//                → auditLogger.log, billingService.create, notifyStakeholders, validator.validate
//     L64-L80 ( 17 lines): @GetMapping("/bills/{id}") public Bill getBill(@PathVariable Long id)
//                → billingService.findById
```

Every `→` entry can be followed: an unqualified name is a method in the same class, `field.method` resolves through the `fields:` section (`billingService` → `BillingService`, so skim `BillingService.java` next), and `Class.method` is a static call. Calls on local variables and parameters, chained/fluent calls, logging, and collection plumbing are excluded because they cannot be followed from a summary.

## Usage in Skill-enabled Agents

Any coding agent that can run shell commands can use `jskim` directly. The repo also includes a `SKILL.md` definition for environments that support skill-style tool packaging and auto-triggering.

One published install path for skill-enabled environments is the [Vercel Skills Registry](https://skills.sh/garvit-joshi/jskim/jskim):

```bash
npx skills add garvit-joshi/jskim
```

In hosts that expose the skill as a slash command, invoke it with `/jskim`:

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
6. **Impact** — `jskim src/ --callers Class.method` or `--impact Class.method` to see resolved upstream/downstream method edges
7. **Filter** — `jskim File.java --grep billing` for large classes
8. **Focus** — `jskim File.java methodA methodB` to read specific methods
9. **Edit** — Read only the specific lines you need from the source file before editing

## Dependencies

- [tree-sitter](https://pypi.org/project/tree-sitter/) — Incremental parsing library
- [tree-sitter-java](https://pypi.org/project/tree-sitter-java/) — Java grammar for tree-sitter
