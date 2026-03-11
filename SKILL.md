---
name: jskim
description: Token-saving Java file reader. Use when working with Java files (.java) to reduce token usage. Auto-triggers when exploring, reading, or understanding Java classes, services, controllers, entities, or any .java files. Run jskim before using the Read tool on Java files to understand structure first, then Read only the lines you need.
argument-hint: [file-path or src-directory]
---

# jskim — Java Token Saver

You have access to three Python scripts in `${CLAUDE_SKILL_DIR}` that summarize Java files compactly, saving 70-80% of input tokens.

## Tools

### 1. Single file summary: `jskim.py`
Summarizes a Java file — collapses imports, fields, boilerplate (getters/setters/equals/hashCode), and shows method signatures with line ranges.

```bash
python3 ${CLAUDE_SKILL_DIR}/jskim.py <file.java>
python3 ${CLAUDE_SKILL_DIR}/jskim.py <file.java> --grep <pattern>       # filter methods by name/signature
python3 ${CLAUDE_SKILL_DIR}/jskim.py <file.java> --annotation <@Ann>    # filter methods by annotation
python3 ${CLAUDE_SKILL_DIR}/jskim.py A.java B.java C.java               # multiple files
```

**Filters** (useful for large files with many methods):
- `--grep billing` — show only methods whose signature contains "billing" (case-insensitive)
- `--annotation @Transactional` — show only methods with that annotation
- Filters apply to the method listing only. Header, fields, and inner types are always shown.
- Filters can be combined: `--grep create --annotation @PostMapping`

### 2. Project map: `jskim_project.py`
Generates a compact map of all Java files in a directory — packages, classes, annotations, field/method counts, Lombok usage.

```bash
python3 ${CLAUDE_SKILL_DIR}/jskim_project.py <src_dir>
python3 ${CLAUDE_SKILL_DIR}/jskim_project.py <src_dir> --deps                          # import-based dependencies
python3 ${CLAUDE_SKILL_DIR}/jskim_project.py <src_dir> --package <prefix>               # filter by package
python3 ${CLAUDE_SKILL_DIR}/jskim_project.py <src_dir> --annotation <@Ann>              # filter by class annotation
python3 ${CLAUDE_SKILL_DIR}/jskim_project.py <src_dir> --extends <ClassName>            # filter by superclass
```

**Filters** (essential for large projects with hundreds of files):
- `--package com.stw.server.tripsheet` — only show classes in that package (prefix match)
- `--annotation @RestController` — only show classes with that annotation
- `--extends BaseService` — only show classes extending that superclass
- `--deps` — show which classes depend on which (uses imports, runs in seconds even on 2000+ files)
- Filters can be combined: `--package com.example --annotation @Service --deps`

### 3. Method extraction: `jskim_method.py`
Extracts method source code with context (fields, called methods, annotations, Javadoc).

```bash
python3 ${CLAUDE_SKILL_DIR}/jskim_method.py <file.java> --list                         # list all methods
python3 ${CLAUDE_SKILL_DIR}/jskim_method.py <file.java> <method_name>                   # extract one method
python3 ${CLAUDE_SKILL_DIR}/jskim_method.py <file.java> <method1> <method2> <method3>   # extract multiple
```

**Multiple methods** — pass all names in one call instead of running the script multiple times. This is useful when you need a method and the methods it calls:
- Deduplicates results automatically
- Reports any names that weren't found: `// not found: methodX`
- Shows "called methods in same class" across all extracted methods

## Reading the output

### `jskim.py` output format

```
// path/to/File.java
// com.example.billing | 12 imports: java.util(3), jakarta.persistence(2), ...
// lombok: @Data: getters, setters, toString, equals, hashCode
// @Service @Transactional
// public class BillingService extends BaseService implements Auditable
//
// fields:
//   BillingRepository billingRepo (@Autowired)
//   String tenantId
//
// getters: getName, getStatus              ← collapsed, names only
// setters: setName, setStatus              ← collapsed, names only
// boilerplate: toString, hashCode, equals  ← collapsed, names only
// methods:
//     L45-L62 ( 18 lines): @PostMapping public Bill createBill(BillDTO dto)
//     L64-L80 ( 17 lines): public void processBill(Long id)
//
// inner types:
//   L90: public static enum Status
//
// other classes in file:
//   L100: class BillingHelper [2F, 3M]     ← 2F = 2 fields, 3M = 3 methods
//
// total: 120 lines
```

- `L45-L62` = line range in the file (use with `Read` offset/limit)
- `( 18 lines)` = method body length
- getters/setters/boilerplate are collapsed to names only — no line ranges, not worth reading
- `NF` = N fields, `NM` = N methods (used for inner/extra types)

### `jskim_project.py` output format

```
// Project Map: 42 files, 8500 lines
//
// com.example.billing (5 files, 600 lines)
//   class BillingService @Service [3F | 8M | 120L | lombok:Data]
//   class BillingRepository @Repository [0F | 5M | 45L]
//   class BillDTO @Data [7F | 0M | 30L | lombok:Data,Builder]
//   enum BillStatus [0F | 0M | 15L]
//   interface BillingPort [0F | 3M | 20L]
//
// === Dependencies ===
//   BillingService → BillingRepository, BillDTO, BillingPort
```

- `NF` = N fields, `NM` = N methods, `NL` = N lines in file
- `lombok:Data,Builder` = Lombok annotations present on the class
- `inner:Foo,Bar` = inner classes/enums inside this class
- Dependencies section (with `--deps`) shows import-based class references

### `jskim_method.py` output format

**With `--list`:**
```
// public class BillingService extends BaseService
//
//     L45-L62 ( 18 lines): @PostMapping public Bill createBill(BillDTO dto)
//     L64-L80 ( 17 lines): public void processBill(Long id)
```

**With method names:**
```
// public class BillingService extends BaseService
// fields: BillingRepository billingRepo, String tenantId
//
// @PostMapping public Bill createBill(BillDTO dto) (L45-L62)
//
//   45 |     @PostMapping
//   46 |     public Bill createBill(BillDTO dto) {
//        ...full method source with line numbers...
//   62 |     }
//
// --- called methods in same class ---
//   L64-L80: public void processBill(Long id)
```

- Shows full method source with line numbers
- `fields:` lists class fields for context
- `called methods in same class` shows other methods referenced in the extracted method bodies
- `// not found: methodX` appears if a requested method name wasn't found

## Workflow

Follow this order to minimize tokens:

1. **Explore** → `jskim_project.py src/` to understand project structure
2. **Narrow** → `jskim_project.py src/ --package com.example.billing` to focus on relevant package
3. **Understand** → `jskim.py File.java` to see class structure (fields, methods, line ranges)
4. **Filter** → `jskim.py File.java --grep billing` if the class has many methods
5. **Focus** → `jskim_method.py File.java methodA methodB` to read the methods you need
6. **Edit** → Use `Read` with `offset`/`limit` on only the lines that matter, then `Edit` normally

### When to use each tool

| Situation | Tool |
|---|---|
| New project, need orientation | `jskim_project.py src/` |
| Find all REST controllers | `jskim_project.py src/ --annotation @RestController` |
| Find all classes extending BaseService | `jskim_project.py src/ --extends BaseService` |
| Understand a class structure | `jskim.py File.java` |
| Large class (500+ lines), looking for specific methods | `jskim.py File.java --grep keyword` |
| Need to read a method's source code | `jskim_method.py File.java methodName` |
| Need method + related methods together | `jskim_method.py File.java method1 method2 method3` |
| Small file (<100 lines) | Just use `Read` directly — skim overhead isn't worth it |

### Rules
- ALWAYS run `jskim.py` before using the `Read` tool on a Java file, unless the file is small (<100 lines) or the user explicitly asks to read the full file
- Use the line ranges from skim output to `Read` with `offset` and `limit` — never read the whole file when you only need one method
- When exploring a new Java project, start with `jskim_project.py` to understand the structure
- For large projects (500+ files), use `--package` to scope `jskim_project.py` output
- For large classes (300+ lines, many methods), use `--grep` or `--annotation` to filter `jskim.py` output
- For editing: use the `Read` tool with offset/limit to get the exact lines, then `Edit` normally — skim is for understanding, not for editing
- When you need multiple related methods, extract them all in one `jskim_method.py` call

## Fallback — if a script crashes

If any jskim Python script fails (syntax error, unexpected Java construct, Python not found, etc.), **do not stop or ask the user to fix it**. Fall back to your native tools:

1. Use the `Read` tool to read the Java file directly
2. Produce a similar compact summary yourself — list the package, key annotations, fields (type + name), and method signatures with line ranges
3. Continue with the workflow as normal

The goal is always: understand the Java file's structure with minimal tokens. The Python scripts are the fast path, but you can always do it yourself if they break.

## What $ARGUMENTS is for

If the user invokes `/jskim` with arguments:
- If argument is a `.java` file → run `jskim.py $ARGUMENTS`
- If argument is a directory → run `jskim_project.py $ARGUMENTS`
- If argument is `<file.java> <method>` → run `jskim_method.py $ARGUMENTS`
- If no arguments → explain the available tools
