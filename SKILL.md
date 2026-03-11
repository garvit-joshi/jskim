---
name: jskim
description: Token-saving Java file reader. Use when working with Java files (.java) to reduce token usage. Auto-triggers when exploring, reading, or understanding Java classes, services, controllers, entities, or any .java files. Run jskim before using the Read tool on Java files to understand structure first, then Read only the lines you need.
argument-hint: [file-path or src-directory]
---

# jskim — Java Token Saver for Spring Boot

You have access to three Python scripts in `${CLAUDE_SKILL_DIR}` that summarize Java files compactly, saving 70-80% of input tokens. Optimized for Spring Boot projects with Lombok, REST controllers, DI wiring, and configuration properties.

## Requirements

Python 3.10+ with these packages (install once):
```bash
pip install tree-sitter==0.25.2 tree-sitter-java==0.23.5
```

## Tools

### 1. Single file summary: `jskim.py`
Summarizes a Java file — collapses imports, fields, boilerplate (getters/setters/equals/hashCode), and shows method signatures with line ranges. Shows annotation parameters for key Spring annotations (`@GetMapping("/path")`, `@Value("${key}")`, `@ConfigurationProperties("prefix")`, etc.).

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
Generates a compact map of all Java files in a directory — packages, classes, annotations, field/method counts, Lombok usage, enum constants.

```bash
python3 ${CLAUDE_SKILL_DIR}/jskim_project.py <src_dir>
python3 ${CLAUDE_SKILL_DIR}/jskim_project.py <src_dir> --deps                          # import-based dependencies
python3 ${CLAUDE_SKILL_DIR}/jskim_project.py <src_dir> --endpoints                     # REST endpoint map
python3 ${CLAUDE_SKILL_DIR}/jskim_project.py <src_dir> --beans                         # Spring bean DI graph + config properties
python3 ${CLAUDE_SKILL_DIR}/jskim_project.py <src_dir> --package <prefix>               # filter by package
python3 ${CLAUDE_SKILL_DIR}/jskim_project.py <src_dir> --annotation <@Ann>              # filter by class annotation
python3 ${CLAUDE_SKILL_DIR}/jskim_project.py <src_dir> --extends <ClassName>            # filter by superclass
python3 ${CLAUDE_SKILL_DIR}/jskim_project.py <src_dir> --implements <Interface>        # filter by implemented interface
```

**Filters** (essential for large projects with hundreds of files):
- `--package com.stw.server.tripsheet` — only show classes in that package (prefix match)
- `--annotation @RestController` — only show classes with that annotation
- `--extends BaseService` — only show classes extending that superclass
- `--implements EventPublisher` — only show classes implementing that interface
- `--deps` — show which classes depend on which (uses imports, runs in seconds even on 2000+ files)
- `--endpoints` — list all REST endpoints: HTTP method, path, handler method, line number
- `--beans` — show Spring bean dependency injection graph + `@ConfigurationProperties` with field details
- Filters can be combined: `--package com.example --annotation @Service --deps --endpoints --beans`

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
// @RestController @RequestMapping("/api/v1/billing")
// public class BillingController extends BaseController
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
//     L64-L80 ( 17 lines): @GetMapping("/{id}") public Bill getBill(Long id)
//
// inner types:
//   L90: public static enum Status
//
// other classes in file:
//   L100: class BillingHelper [2F, 3M]     ← 2F = 2 fields, 3M = 3 methods
//
// total: 120 lines
```

For enums:
```
// public enum BillStatus
//
// constants: DRAFT, PENDING, APPROVED, REJECTED
//
// fields:
//   String label
```

- `L45-L62` = line range in the file (use with `Read` offset/limit)
- `( 18 lines)` = method body length
- Spring annotation parameters are preserved: `@GetMapping("/{id}")`, `@Value("${config.key}")`
- getters/setters/boilerplate are collapsed to names only — no line ranges, not worth reading
- `NF` = N fields, `NM` = N methods (used for inner/extra types)
- Enum constants are listed inline
- Static initializer blocks shown with line ranges: `// static initializer (L10-L25, 16 lines)`

### `jskim_project.py` output format

```
// Project Map: 42 files, 8500 lines
//
// com.example.billing (5 files, 600 lines)
//   class BillingService @Service [3F | 8M | 120L | lombok:Data]
//   class BillingRepository @Repository [0F | 5M | 45L]
//   class BillDTO @Data [7F | 0M | 30L | lombok:Data,Builder]
//   enum BillStatus { DRAFT, PENDING, APPROVED, REJECTED } [0F | 0M | 15L]
//   interface BillingPort [0F | 3M | 20L]
```

With `--endpoints`:
```
// === REST Endpoints ===
//   GET     /api/v1/billing         BillingController.list()      L45
//   POST    /api/v1/billing         BillingController.create()    L62
//   GET     /api/v1/billing/{id}    BillingController.get()       L70
//   PUT     /api/v1/billing/{id}    BillingController.update()    L80
//   DELETE  /api/v1/billing/{id}    BillingController.delete()    L90
```

With `--beans`:
```
// === Bean Dependencies ===
//   BillingService @Service ← BillingRepository, BillValidator, KafkaTemplate
//   BillingController @RestController ← BillingService, AuthService
//
// === Configuration Properties ===
//   billing.* (BillingProperties): BigDecimal taxRate, String currency, int maxRetries
```

With `--deps`:
```
// === Dependencies ===
//   BillingService → BillingRepository, BillDTO, BillingPort
```

- `NF` = N fields, `NM` = N methods, `NL` = N lines in file
- `lombok:Data,Builder` = Lombok annotations present on the class
- `inner:Foo,Bar` = inner classes/enums inside this class
- Enum constants shown inline: `enum Status { ACTIVE, INACTIVE }`
- Dependencies (`--deps`) = import-based class references
- Endpoints (`--endpoints`) = all `@GetMapping`/`@PostMapping`/etc. with full paths
- Beans (`--beans`) = DI wiring via `@Autowired`, `@RequiredArgsConstructor` + final fields

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
3. **Spring context** → `jskim_project.py src/ --endpoints --beans` to see REST API + DI wiring
4. **Understand** → `jskim.py File.java` to see class structure (fields, methods, line ranges)
5. **Filter** → `jskim.py File.java --grep billing` if the class has many methods
6. **Focus** → `jskim_method.py File.java methodA methodB` to read the methods you need
7. **Edit** → Use `Read` with `offset`/`limit` on only the lines that matter, then `Edit` normally

### When to use each tool

| Situation | Tool |
|---|---|
| New project, need orientation | `jskim_project.py src/` |
| Find all REST controllers | `jskim_project.py src/ --annotation @RestController` |
| See all API endpoints at a glance | `jskim_project.py src/ --endpoints` |
| See Spring bean DI wiring | `jskim_project.py src/ --beans` |
| Find all classes extending BaseService | `jskim_project.py src/ --extends BaseService` |
| Find all implementations of an interface | `jskim_project.py src/ --implements EventPublisher` |
| Understand a class structure | `jskim.py File.java` |
| Large class (500+ lines), looking for specific methods | `jskim.py File.java --grep keyword` |
| Need to read a method's source code | `jskim_method.py File.java methodName` |
| Need method + related methods together | `jskim_method.py File.java method1 method2 method3` |

### When NOT to use jskim

- **Small files (<100 lines)** — just use `Read` directly, skim overhead isn't worth it
- **You already have line numbers** — if `Grep` already told you the exact lines, use `Read` with offset/limit directly. Don't waste a tool call on jskim.
- **Generated code** — JOOQ output, Protobuf stubs, Swagger-generated clients. These are mechanical and don't benefit from summarization.
- **Non-Java files** — this tool only handles `.java` files
- **The user asked to read the full file** — respect the request, use `Read`

### Rules
- Run `jskim.py` before using the `Read` tool on a Java file when you don't already know where to look (no line numbers from grep, no prior context). Skip jskim if you already have the line range you need.
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
