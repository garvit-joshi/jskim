---
name: jskim
description: Token-saving Java file reader. Use when working with Java files (.java) to reduce token usage. Auto-triggers when exploring, reading, or understanding Java classes, services, controllers, entities, or any .java files. Run jskim before using the Read tool on Java files to understand structure first, then Read only the lines you need.
argument-hint: [file-path or src-directory]
---

# jskim — Java Token Saver for Spring Boot

A CLI tool that summarizes Java files compactly, saving 70-80% of input tokens. Optimized for Spring Boot projects with Lombok, REST controllers, DI wiring, and configuration properties.

## Requirements

Python 3.10+ — install via pip:
```bash
pip install jskim
```

## Usage

`jskim` auto-detects whether you're pointing at a file or directory, and whether you're asking for a summary or method extraction.

### Single file summary
Summarizes a Java file — collapses imports, fields, boilerplate (getters/setters/equals/hashCode), and shows method signatures with line ranges. Shows annotation parameters for key Spring annotations (`@GetMapping("/path")`, `@Value("${key}")`, `@ConfigurationProperties("prefix")`, etc.).

```bash
jskim <file.java>
jskim <file.java> --grep <pattern>       # filter methods by name/signature
jskim <file.java> --annotation <@Ann>    # filter methods by annotation
jskim A.java B.java C.java               # multiple files
```

**Filters** (useful for large files with many methods):
- `--grep billing` — show only methods whose signature contains "billing" (case-insensitive)
- `--annotation @Transactional` — show only methods with that annotation
- Filters apply to the method listing only. Header, fields, and inner types are always shown.
- Filters can be combined: `--grep create --annotation @PostMapping`

### Project map
Generates a compact map of all Java files in a directory — packages, classes, annotations, field/method counts, Lombok usage, enum constants.

```bash
jskim <src_dir>
jskim <src_dir> --deps                          # import-based dependencies
jskim <src_dir> --endpoints                     # REST endpoint map
jskim <src_dir> --beans                         # Spring bean DI graph + @Bean producers + config properties
jskim <src_dir> --package <prefix>               # filter by package
jskim <src_dir> --annotation <@Ann>              # filter by class annotation
jskim <src_dir> --extends <ClassName>            # filter by superclass
jskim <src_dir> --implements <Interface>        # filter by implemented interface
```

**Filters** (essential for large projects with hundreds of files):
- `--package com.stw.server.tripsheet` — only show classes in that package (prefix match)
- `--annotation @RestController` — only show classes with that annotation
- `--extends BaseService` — only show classes extending that superclass
- `--implements EventPublisher` — only show classes implementing that interface
- `--deps` — show which classes depend on which (uses imports, runs in seconds even on 2000+ files)
- `--endpoints` — list all REST endpoints: HTTP method, path, handler method, line number
- `--beans` — show Spring bean DI graph, `@Bean` factory method producers, and `@ConfigurationProperties` with field details
- Filters can be combined: `--package com.example --annotation @Service --deps --endpoints --beans`

### Diff mode
Summarizes only the Java files and methods changed in a git diff. Ideal for PR reviews — instead of reading full files, get structural context for just the changed parts.

```bash
jskim --diff HEAD~1                    # changes since last commit
jskim --diff main                      # changes vs main branch
jskim --diff main...feature-branch     # merge-base comparison
jskim src/ --diff HEAD~1               # scoped to directory
git diff main | jskim --diff -         # read diff from stdin
```

**Output markers**:
- `[NEW]` — file or method that was added
- `[MODIFIED]` — method whose body was changed
- `[DELETED]` — file or method that was removed
- Getters, setters, and boilerplate changes are suppressed (not interesting)
- Unchanged methods are counted but not listed

### Method extraction
Extracts method source code with context (fields, called methods, annotations, Javadoc).

```bash
jskim <file.java> --list                         # list all methods
jskim <file.java> <method_name>                   # extract one method
jskim <file.java> <method1> <method2> <method3>   # extract multiple
```

**Multiple methods** — pass all names in one call instead of running the script multiple times. This is useful when you need a method and the methods it calls:
- Deduplicates results automatically
- Reports any names that weren't found: `// not found: methodX`
- Shows "called methods in same class" across all extracted methods

## Reading the output

### File summary output format

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
// getters: getName, getStatus              <- collapsed, names only
// setters: setName, setStatus              <- collapsed, names only
// boilerplate: toString, hashCode, equals  <- collapsed, names only
// methods:
//     L45-L62 ( 18 lines): @PostMapping public Bill createBill(BillDTO dto)
//     L64-L80 ( 17 lines): @GetMapping("/{id}") public Bill getBill(Long id)
//
// inner types:
//   L90: public static enum Status
//
// other classes in file:
//   L100: class BillingHelper [2F, 3M]     <- 2F = 2 fields, 3M = 3 methods
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

### Project map output format

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
//   BillingService @Service <- BillingRepository, BillValidator, KafkaTemplate
//   BillingController @RestController <- BillingService, AuthService
//
// === Bean Producers (@Bean) ===
//   AppConfig @Configuration -> ObjectMapper, TaskScheduler, NotificationClient
//
// === Configuration Properties ===
//   billing.* (BillingProperties): BigDecimal taxRate, String currency, int maxRetries
```

With `--deps`:
```
// === Dependencies ===
//   BillingService -> BillingRepository, BillDTO, BillingPort
```

- `NF` = N fields, `NM` = N methods, `NL` = N lines in file
- `lombok:Data,Builder` = Lombok annotations present on the class
- `inner:Foo,Bar` = inner classes/enums inside this class
- Enum constants shown inline: `enum Status { ACTIVE, INACTIVE }`
- Dependencies (`--deps`) = import-based class references
- Endpoints (`--endpoints`) = all `@GetMapping`/`@PostMapping`/etc. with full paths
- Beans (`--beans`) = DI wiring, `@Bean` factory method producers, and `@ConfigurationProperties`

### Method extraction output format

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

1. **Explore** -> `jskim src/` to understand project structure
2. **Narrow** -> `jskim src/ --package com.example.billing` to focus on relevant package
3. **Spring context** -> `jskim src/ --endpoints --beans` to see REST API + DI wiring
4. **Understand** -> `jskim File.java` to see class structure (fields, methods, line ranges)
5. **Filter** -> `jskim File.java --grep billing` if the class has many methods
6. **Focus** -> `jskim File.java methodA methodB` to read the methods you need
7. **Edit** -> Use `Read` with `offset`/`limit` on only the lines that matter, then `Edit` normally

### When to use each tool

| Situation | Tool |
|---|---|
| PR review / what changed? | `jskim --diff HEAD~1` or `jskim --diff main` |
| New project, need orientation | `jskim src/` |
| Find all REST controllers | `jskim src/ --annotation @RestController` |
| See all API endpoints at a glance | `jskim src/ --endpoints` |
| See Spring bean DI wiring + producers | `jskim src/ --beans` |
| Find all classes extending BaseService | `jskim src/ --extends BaseService` |
| Find all implementations of an interface | `jskim src/ --implements EventPublisher` |
| Understand a class structure | `jskim File.java` |
| Large class (500+ lines), looking for specific methods | `jskim File.java --grep keyword` |
| Need to read a method's source code | `jskim File.java methodName` |
| Need method + related methods together | `jskim File.java method1 method2 method3` |

### When NOT to use jskim

- **Small files (<100 lines)** — just use `Read` directly, skim overhead isn't worth it
- **You already have line numbers** — if `Grep` already told you the exact lines, use `Read` with offset/limit directly. Don't waste a tool call on jskim.
- **Generated code** — JOOQ output, Protobuf stubs, Swagger-generated clients. These are mechanical and don't benefit from summarization.
- **Non-Java files** — this tool only handles `.java` files
- **The user asked to read the full file** — respect the request, use `Read`

### Rules
- Run `jskim` before using the `Read` tool on a Java file when you don't already know where to look (no line numbers from grep, no prior context). Skip jskim if you already have the line range you need.
- Use the line ranges from skim output to `Read` with `offset` and `limit` — never read the whole file when you only need one method
- When exploring a new Java project, start with `jskim <src_dir>` to understand the structure
- For large projects (500+ files), use `--package` to scope project map output
- For large classes (300+ lines, many methods), use `--grep` or `--annotation` to filter output
- For editing: use the `Read` tool with offset/limit to get the exact lines, then `Edit` normally — skim is for understanding, not for editing
- When you need multiple related methods, extract them all in one `jskim File.java method1 method2` call

## Fallback — if jskim crashes

If `jskim` fails (syntax error, unexpected Java construct, Python not found, etc.), **do not stop or ask the user to fix it**. Fall back to your native tools:

1. Use the `Read` tool to read the Java file directly
2. Produce a similar compact summary yourself — list the package, key annotations, fields (type + name), and method signatures with line ranges
3. Continue with the workflow as normal

The goal is always: understand the Java file's structure with minimal tokens. jskim is the fast path, but you can always do it yourself if it breaks.

## What $ARGUMENTS is for

If the user invokes `/jskim` with arguments:
- If argument is a `.java` file -> run `jskim $ARGUMENTS`
- If argument is a directory -> run `jskim $ARGUMENTS`
- If argument is `<file.java> <method>` -> run `jskim $ARGUMENTS`
- If no arguments -> explain the available tools
