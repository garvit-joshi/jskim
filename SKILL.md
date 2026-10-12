---
name: jskim
description: Token-saving Java file reader. Use when working with Java files (.java) to reduce token usage. Auto-triggers when exploring, reading, or understanding Java classes, services, controllers, entities, or any .java files. Run jskim before reading raw Java source when you need structural context first, then inspect only the lines you need.
argument-hint: [file-path or src-directory]
allowed-tools: Bash(jskim:*)
---

# jskim — Java Token Saver for Spring Boot

A CLI tool that summarizes Java files compactly, saving 70-80% of input tokens. Optimized for Spring Boot projects: REST controllers, DI wiring, configuration properties, Lombok, records, Spring Modulith packages.

## Requirements

Python 3.10+ — install via pip:
```bash
pip install jskim
```

**Before first use**, verify jskim is installed by running `jskim --version`. If you get "command not found", tell the user:
> jskim is not installed. Install it with: `pip install jskim`

Do not attempt to run jskim commands until it is confirmed installed. Fall back to your normal file-reading tools if the user declines to install it.

## Usage

`jskim` auto-detects whether you're pointing at a file or directory, and whether you're asking for a summary or method extraction. A flag that does not apply to the detected mode is reported on stderr (`Warning: --grep not used in project mode, ignored`), never silently dropped.

### Single file summary
Summarizes a Java file — drops imports, collapses boilerplate (wiring constructors, getters/setters/equals/hashCode), and shows the class Javadoc's first sentence, method signatures with line ranges, annotations with their arguments, nested types with their members, and traceable method calls.

```bash
jskim <file.java>
jskim <file.java> --grep <pattern>       # filter methods by name/signature
jskim <file.java> --annotation <@Ann>    # filter methods by annotation
jskim A.java B.java C.java               # multiple files
```

Java simple source files without an explicit type wrapper are summarized as `implicit class <FileStem>`. A `package-info.java` shows its package-level annotations (Spring Modulith `@ApplicationModule`, `@NamedInterface`).

**Filters** (useful for large files with many methods):
- `--grep billing` — show only methods whose signature contains "billing" (case-insensitive)
- `--annotation @Transactional` — show only methods with that annotation
- Filters apply to the method listing only. Header, fields, and inner types are always shown.
- Filters can be combined: `--grep create --annotation @PostMapping`

### Project map
Generates a compact map of all Java files in a directory — packages (with package-level annotations), classes, annotations, field/method counts, Lombok usage, enum constants; records are listed by name only. Build output (`target/`, `build/`, `out/`) is skipped, so pointing at a repo root is safe.

```bash
jskim <src_dir>
jskim <src_dir> --deps                          # package-to-package dependencies
jskim <src_dir> --endpoints                     # REST endpoint map with resolved paths
jskim <src_dir> --beans                         # Spring bean DI graph + @Bean producers + config properties
jskim <src_dir> --callers Class.method          # upstream callers for a specific method
jskim <src_dir> --impact Class.method           # callers + direct callees for a specific method
jskim <src_dir> --impact Class.method --depth 2 # bounded caller/callee hierarchy depth
jskim <src_dir> --package <text>                 # filter by package (substring)
jskim <src_dir> --annotation <@Ann>              # filter by class annotation
jskim <src_dir> --extends <ClassName>            # filter by superclass
jskim <src_dir> --implements <Interface>        # filter by implemented interface
```

**Filters** (essential for large projects with hundreds of files):
- `--package logistics.internal` — only show classes whose package contains that text
- `--annotation @RestController` — only show classes with that annotation
- `--extends BaseService` — only show classes extending that superclass
- `--implements EventPublisher` — only show classes implementing that interface
- `--deps` — show which packages depend on which other packages and through which types (the Spring Modulith boundary view; same-package references are not listed)
- `--endpoints` — list all REST endpoints: HTTP method, full path, handler method, line number, and the handler's remaining annotations (`@RequiresPermission("trip.create")`, `@ResponseStatus(...)`). Paths and annotation constants (`@RequestMapping(BASE_PATH)`, `path = TRIPS + "/{id}"`, `ApiPaths.ROOT`, `Perms.TRIP_CREATE`) are resolved across the whole project.
- `--beans` — show Spring bean DI graph (constructor parameters, Lombok constructor + final fields, or `@Autowired`/`@Inject` fields), `@Bean` factory method producers, and `@ConfigurationProperties` with instance field details
- `--callers BillingService.create` — show resolved upstream callers for a class-qualified method target
- `--impact BillingService.create` — show callers plus resolved downstream calls from the target method
- `--depth 2` — follow caller/callee edges beyond direct neighbors; default is 1 and usually best
- Filters can be combined: `--package com.example --annotation @Service --deps --endpoints --beans`

**Call hierarchy rules:**
- Always use a class-qualified target (`Class.method` or `com.example.Class.method`). Bare method names like `create` are intentionally rejected because they are too ambiguous in Java projects.
- If simple class names collide, rerun with the fully-qualified class name shown in the candidates list.
- Edges are resolved from same-class calls, static calls on project classes, and field calls where the field type is a project class, such as `billingService.create()`. Method references (`this::validate`, `billingService::create`, `OrderMapper::toDto`) are resolved identically to invocations.
- A call through an interface or superclass also counts as a call to every project implementation: `audit.write()` on an `AuditApi` field is a caller of both `AuditApi.write` and `AuditEventService.write`, so querying the concrete service works in Modulith codebases where every cross-module call goes through an `*Api` interface.
- Calls on local variables, parameters, or overloaded targets are skipped when they cannot be resolved safely. Treat missing edges as "not proven" rather than "not called."

### Diff mode
Summarizes only the Java files, fields and methods changed in a git diff. Ideal for PR reviews — instead of reading full files, get structural context for just the changed parts.

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
- `[DELETED]` — file or method that was removed (previous signature shown when the base ref is available)
- `[FIELDS]` — instance fields or record components added (`+`) or removed (`-`); this is how a DTO/record contract change shows up
- `→` calls shown for new/modified methods (same format as file summary)
- Getters, setters, boilerplate, wiring constructors and static constant changes are suppressed; a new constructor dependency shows up as a `[FIELDS]` entry instead
- Methods and fields of nested types are compared too, labelled `Outer.Inner.name`
- Unchanged methods are counted but not listed
- `(no field or method changes)` means only comments, imports, constants or bodies of trivial methods changed

### Method extraction
Extracts method source code with context (instance fields, called methods, behaviour annotations, Javadoc). Documentation annotations (`@Operation`, `@ApiResponse`, `@Schema`, ...) are skipped when printing the source, so a 3-line handler under 40 lines of OpenAPI stays 3 lines. Methods of nested types are extractable by name too.

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
// path/to/BillingController.java
// com.example.billing
// @RestController @RequestMapping("/api/v1/billing")
// class BillingController extends BaseController
// doc: The billing routes: create a bill, read one, and settle it.
//
// fields:
//   BillingService billingService
//   BillingValidator validator (@Autowired)
//   AuditLogger auditLogger
//
// static fields: BASE_PATH = "/api/v1/billing", LOG, MAX_PAGE_SIZE
//
// constructor: L18-L21 (2 params)          <- only stores its parameters; the fields above are the dependency list
// getters: getName, getStatus              <- collapsed, names only
// setters: setName, setStatus              <- collapsed, names only
// boilerplate: toString, hashCode, equals  <- collapsed, names only
// methods:
//     L60-L62 (  3 lines): @PostMapping("/bills") @RequiresPermission(Perms.BILL_CREATE) @ResponseStatus(HttpStatus.CREATED) Bill createBill(@Valid @RequestBody BillDTO dto)
//                → auditLogger.log, billingService.create, notifyStakeholders, validator.validate
//     L64-L80 ( 17 lines): @GetMapping("/bills/{id}") Bill getBill(@PathVariable Long id)
//                → billingService.findById
//
// inner types:
//   L90: public enum Status { DRAFT, PAID }
//   L95: record Claim implements Comparable<Claim>
//     fields: int count, @NotNull Integer last
//   L99: @Configuration static class S3Config
//     methods:
//              L101-L105 (  5 lines): @Bean S3Client client(BillingProperties props)
//
// other classes in file:
//   L120: class BillingHelper [2F, 3M]     <- 2F = 2 instance fields, 3M = 3 methods
//
// total: 130 lines
```

For Java simple source files:
```
// SomeScript.java
// (default)
// implicit class SomeScript
//
// methods:
//         L1-L3 (  3 lines): void main()
//
// total: 3 lines
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

For `package-info.java`:
```
// src/main/java/com/example/evidence/package-info.java
// com.example.evidence
// @ApplicationModule(displayName = "Evidence")
//
// total: 65 lines
```

- `L60-L62` = line range from the signature line to the closing brace (use with `Read` offset/limit). Annotations above the signature are not counted, so `( 3 lines)` is the real size of the method even when 40 lines of `@ApiResponse` sit above it. `jskim File.java method` prints the annotations and Javadoc too.
- `doc:` = first sentence of the type's Javadoc, when there is one. This is where the design intent lives; read it before the methods.
- `fields:` = instance fields only, with their non-documentation annotations (`@NotNull @Size` on a record component are validation rules). `static fields:` lists constants by name, with the value inline for short non-private string constants (`EVENT_READ = "audit.event.read"`) so permission keys and paths other classes reference are readable without opening the file; private constants stay names only. A record's components appear under `fields:`.
- `constructor:` = constructors that only store their parameters into fields (dependency-injection wiring). Their parameter list is the `fields:` list, so the signature is not repeated. A constructor that does anything else stays under `methods:`.
- `inner types:` show their own members indented: record components as a one-line `fields:`, enum constants inline, methods in the usual format. A nested `@Configuration` with `@Bean` methods, a nested `record Claim(...)` and a nested `enum Mode` are all readable without opening the file.
- Annotations keep their arguments for everything that changes behaviour: `@RequiresPermission(Perms.X)`, `@ResponseStatus(HttpStatus.CREATED)`, `@Transactional(readOnly = true)`, `@Scheduled(cron = "...")`. Long argument lists are truncated with `...)`. Repeated annotations are shown once.
- Mapping annotations show only the path, resolved from same-class constants: `@PostMapping(path = ONE_TRIP + "/start", consumes = ...)` renders as `@PostMapping("/trips/{tripId}/start")`. `@RequestMapping(method = GET, ...)` renders as `@RequestMapping(GET "/path")`. A constant defined in another class stays as its source text, e.g. `@RequestMapping(ApiPaths.BASE)`; `--endpoints` resolves those across the project.
- Documentation-only annotations are dropped everywhere: OpenAPI/Swagger (`@Operation`, `@ApiResponse`, `@Parameter`, `@Schema`, `@Tag`), `@SuppressWarnings`, `@Generated`.
- Parameter annotations keep the marker and lose their arguments: `@RequestParam(required = false) Integer size` renders as `@RequestParam Integer size`.
- `→` = traceable method calls made by this method (sorted alphabetically). See the next section.
- getters/setters/boilerplate are collapsed to names only — no line ranges, no calls, not worth reading
- `NF` = N instance fields, `NM` = N methods (used for inner/extra types)
- Static initializer blocks shown with line ranges: `// static initializer (L10-L25, 16 lines)`

### Interpreting `→` method calls

The `→` line lists only calls you can follow from the summary:

- **Same-class calls (no dot):** `notifyStakeholders` → a method in this class. Use `jskim File.java notifyStakeholders` to read it.
- **Field calls (`field.method`):** `billingService.create` → look up `billingService` in `fields:` to get the type (`BillingService`), then skim that class.
- **Static calls (`Class.method`):** `AuditEvent.now`, `Ids.newId` → a static method on a project class (same package, or imported from the project's root package).
- **`super.method`** → the parent class.

Not shown, because they cannot be followed from the summary: calls on local variables and parameters (`dto.getName()`, `row.status()`), calls on JDK/Spring/library classes (`Collectors.groupingBy`, `OffsetDateTime.now`, `DSL.noCondition`, `SecurityContextHolder.getContext`), calls on or to static-imported members (`TRIP.fields()`, `assertThat(...)`), calls on static fields and ALL_CAPS constants (`RANDOM.nextInt`, `ID.eq`), collection ops (`put`, `get`, `stream`, `collect`), logging (`log.info`), type conversions (`toString`, `valueOf`), and chained/fluent calls. Calls are capped at 10 per method; overflow shown as `... +N more`. Abstract methods and methods with no traceable calls have no `→` line.

### Project map output format

```
// Project Map: 42 files, 8500 lines | packages under com.example
//
// billing (8 files, 900 lines) @ApplicationModule(displayName = "Billing")
//   class BillingService @Service [3F | 8M | 120L | lombok:Data]
//   class BillingRepository @Repository [5M | 45L]
//   class BillDTO @Data [7F | 30L | lombok:Data,Builder]
//   enum BillStatus { DRAFT, PENDING, APPROVED, REJECTED } [15L]
//   interface BillingPort [3M | 20L]
//   records: BillView, CreateBillRequest, SettleBillRequest
```

With `--endpoints`:
```
// === REST Endpoints ===
//   GET     /api/v1/billing         BillingController.list()    L45  @RequiresPermission("billing.read")
//   POST    /api/v1/billing         BillingController.create()  L62  @ResponseStatus(HttpStatus.CREATED) @RequiresPermission("billing.create")
//   GET     /api/v1/billing/{id}    BillingController.get()     L70  @RequiresPermission("billing.read")
//   DELETE  /api/v1/billing/{id}    BillingController.delete()  L90  @PreAuthorize("hasRole('ADMIN')")
```

With `--beans`:
```
// === Bean Dependencies ===
//   BillingService @Service ← BillingRepository, BillValidator, KafkaTemplate<String, Event>
//   BillingController @RestController ← BillingService, AuthService
//
// === Bean Producers (@Bean) ===
//   AppConfig @Configuration → ObjectMapper, TaskScheduler, NotificationClient
//
// === Configuration Properties ===
//   billing.* (BillingProperties): BigDecimal taxRate, String currency, int maxRetries
```

With `--deps`:
```
// === Package Dependencies ===
//   billing.internal →
//     audit: AuditApi, AuditEvent
//     billing: BillingPort, BillingPermissions
//     shared.problem: Problem
```

With `--callers BillingService.create --depth 2`:
```
// === Callers: BillingService.create (depth 2) ===
// target: BillingService.create(BillDTO)  src/.../BillingService.java:L45
//
// callers:
//   ← BillingController.createBill(BillDTO)  src/.../BillingController.java:L62
//     ← BillingJob.retryFailedBills()  src/.../BillingJob.java:L30
```

With `--impact BillingService.create`:
```
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

- Package names are shown relative to the common root package named in the header (`billing.internal` under `com.example`); the root package itself keeps its full name
- Package header carries the annotations from that package's `package-info.java` (Spring Modulith module boundaries)
- `records:` = the package's records by name (DTOs, requests, views, rows). Skim the file when you need the components; the controller/service signatures already name the ones that matter
- `NF` = N instance fields (statics excluded), `NM` = N methods, `NL` = N lines in file
- `lombok:Data,Builder` = Lombok annotations present on the class
- `inner:Foo,Bar` = inner classes/enums inside this class
- Enum constants shown inline: `enum Status { ACTIVE, INACTIVE }`
- Dependencies (`--deps`) = which packages import, extend or implement types from which other packages, and which types cross the boundary. Same-package references are omitted. Use it to check Modulith boundaries: an `internal` package appearing as a target of another module is a violation
- Endpoints (`--endpoints`) = all `@GetMapping`/`@PostMapping`/etc. with full paths, constants resolved project-wide; an unresolvable expression stays visible as source text (`/api/Unknown.PATH`). The trailing annotations are the route's guards and status: read the security model of the whole API from this one table
- Beans (`--beans`) = DI wiring, `@Bean` factory method producers (nested `@Configuration` classes included), and `@ConfigurationProperties`
- Callers/impact (`--callers`, `--impact`) = resolved method call edges only; classes show as simple names, fully qualified only when the simple name is ambiguous in the project; the file path is always shown

### Method extraction output format

**With `--list`:**
```
// public class BillingService extends BaseService
//
//     L45-L62 ( 18 lines): @PostMapping("/bills") public Bill createBill(BillDTO dto)
//     L64-L80 ( 17 lines): public void processBill(Long id)
```

**With method names:**
```
// public class BillingService extends BaseService
// fields: BillingRepository billingRepo, String tenantId
//
// @PostMapping("/bills") public Bill createBill(BillDTO dto) (L45-L62)
//
//   45 |     @PostMapping
//   46 |     public Bill createBill(BillDTO dto) {
//        ...full method source with line numbers...
//   62 |     }
//
// --- called methods in same class ---
//   L64-L80: public void processBill(Long id)
```

- Shows full method source with line numbers, including the Javadoc and behaviour annotations directly above it; documentation-only annotations (`@Operation`, `@ApiResponse`, `@Schema`, `@SuppressWarnings`) are skipped, which is why line numbers can jump
- `fields:` lists instance fields for context (constants omitted)
- `called methods in same class` shows other methods referenced in the extracted method bodies
- `// not found: methodX` appears if a requested method name wasn't found
- Simple source files use the same format with an `implicit class <FileStem>` header

## Workflow

Follow this order to minimize tokens:

1. **Explore** -> `jskim src/` to understand project structure
2. **Narrow** -> `jskim src/ --package com.example.billing` to focus on relevant package
3. **Spring context** -> `jskim src/ --endpoints --beans` to see REST API + DI wiring
4. **Understand** -> `jskim File.java` to see class structure (fields, methods, line ranges, and method calls)
5. **Trace** -> Use `→` calls to follow execution: match `fieldName.method` against `fields:` to find the target class type, then skim that class to continue
6. **Impact** -> `jskim src/ --callers Class.method` or `--impact Class.method` to see resolved upstream/downstream method edges
7. **Filter** -> `jskim File.java --grep billing` if the class has many methods
8. **Focus** -> `jskim File.java methodA methodB` to read the methods you need
9. **Edit** -> Read only the lines that matter from the source file, then edit normally

### Tracing call flow across files (step-by-step example)

**Goal:** Understand what happens when `POST /api/v1/billing` is called.

```
Step 1: jskim src/ --endpoints
        → See: POST /api/v1/billing  BillingController.createBill()  L62

Step 2: jskim BillingController.java
        → See: createBill() calls billingService.create, validator.validate
        → See fields: BillingService billingService, BillingValidator validator

Step 3: jskim BillingService.java
        → See: create() calls billingRepo.save, eventPublisher.publish, calculateTax
        → See fields: BillingRepository billingRepo, EventPublisher eventPublisher

Step 4: jskim BillingService.java calculateTax
        → Read the method source to understand the tax logic

Done — you traced Endpoint → Controller → Service → Repository in 4 tool calls,
reading ~60 lines of skim output instead of ~500 lines of raw Java.
```

### Finding callers (reverse lookup)

The `→` calls show what a method calls (downstream). To find what calls a specific method (upstream), use call hierarchy mode with a class-qualified target:

```
Goal: Who calls billingService.create()?

Step 1: jskim src/ --callers BillingService.create
        → See resolved direct callers

Step 2: jskim src/ --callers BillingService.create --depth 2
        → See callers of the callers when you need a broader impact view
```

Use `--impact BillingService.create` when you need both upstream callers and downstream calls from the target in one compact view.

Fallback for unresolved/ambiguous cases (calls through local variables, parameters, interfaces with several implementations):
- `rg "\.create\(" -g "*.java"` — raw text search

### When to use each tool

| Situation | Tool |
|---|---|
| PR review / what changed? (large diff, 1000+ lines) | `jskim --diff develop` to triage, then `git diff` for details |
| PR review / what changed? (small diff, < 1000 lines) | `git diff develop...HEAD` directly — skip jskim |
| New project, need orientation | `jskim src/` |
| Find all REST controllers | `jskim src/ --annotation @RestController` |
| See all API endpoints at a glance | `jskim src/ --endpoints` |
| See Spring bean DI wiring + producers | `jskim src/ --beans` |
| Find all classes extending BaseService | `jskim src/ --extends BaseService` |
| Find all implementations of an interface | `jskim src/ --implements EventPublisher` |
| Check module boundaries (what imports what across packages) | `jskim src/ --deps` |
| See which permission guards each route | `jskim src/ --endpoints` |
| Understand a class structure | `jskim File.java` |
| Trace call flow downstream | Skim the class → follow `→` field calls → skim the dependency class |
| Find callers (upstream) | `jskim src/ --callers Class.method` |
| Assess impact of a change | `jskim src/ --impact Class.method --depth 1` first; increase depth only if needed |
| Large class (500+ lines), looking for specific methods | `jskim File.java --grep keyword` |
| Need to read a method's source code | `jskim File.java methodName` |
| Need method + related methods together | `jskim File.java method1 method2 method3` |

### When to use `jskim --diff` vs `git diff`

`jskim --diff` gives **structural context** — which fields and methods were added, modified, or deleted, with signatures and call graphs. `git diff` gives the **actual code changes**. They serve different purposes:

**Use `jskim --diff` when:**
- The diff is large (1000+ lines, 10+ files) and you need to triage what changed before diving in
- Changed files are large (300+ lines each) — skim tells you which methods were affected without reading entire files
- You need to understand the shape/scope of changes across many files before reviewing details
- You want to identify which modified methods call what, to assess blast radius
- Records/DTOs changed and you want the contract delta (`[FIELDS]`) without reading every file

**Use `git diff` directly (skip `jskim --diff`) when:**
- The diff is small (< ~1000 lines total) — you can read the entire diff faster than running jskim and then reading the diff anyway
- All changed files are small (< 150 lines each) — the skim output is roughly the same size as the raw diff, so it saves nothing
- You've already read the full `git diff` — running jskim after is redundant
- You need to review actual code logic, not just structure — jskim shows signatures and call graphs, not the changed lines themselves. For bug hunting and code review, you still need the real diff

**Key insight:** `jskim --diff` is a **triage tool**, not a replacement for reading the diff. Use it first on large diffs to decide where to focus, then read the actual changes with `git diff` or your normal diff/file viewer. On small diffs, skip it entirely and go straight to `git diff`.

### When NOT to use jskim

- **Small files (<100 lines)** — just read the file directly, skim overhead isn't worth it
- **Small diffs (< ~1000 lines)** — `git diff` is faster and gives you more useful information than `jskim --diff`
- **You already have line numbers** — if search already told you the exact lines, go straight to that slice of the file. Don't waste a tool call on jskim.
- **You already read the full diff** — don't run `jskim --diff` after reading `git diff`; the structural info is already in context
- **Generated code** — JOOQ output, Protobuf stubs, Swagger-generated clients. These are mechanical and don't benefit from summarization.
- **Non-Java files** — this tool only handles `.java` files
- **The user asked to read the full file** — respect the request and read the full file directly

### Rules
- Run `jskim` before reading a Java file directly when you don't already know where to look (no line numbers from search, no prior context). Skip jskim if you already have the line range you need.
- Use the line ranges from skim output to read only the relevant slice of the file — never read the whole file when you only need one method
- When exploring a new Java project, start with `jskim <src_dir>` to understand the structure
- For large projects (500+ files), use `--package` to scope project map output (substring match: `--package logistics.internal`)
- For caller/impact checks, use class-qualified targets and keep `--depth` at 1 until you know you need more context
- For large classes (300+ lines, many methods), use `--grep` or `--annotation` to filter output
- For editing: read the exact lines you need first, then edit normally — skim is for understanding, not for editing
- When you need multiple related methods, extract them all in one `jskim File.java method1 method2` call
- When tracing call flow, every `→` entry is followable: unqualified → same class, `field.x` → the field's type in `fields:`, `Class.x` → that class

## Fallback — if jskim crashes

If `jskim` fails (syntax error, unexpected Java construct, Python not found, etc.), **do not stop or ask the user to fix it**. Fall back to your native tools:

1. Read the Java file directly with your normal file-reading tool
2. Produce a similar compact summary yourself — list the package, key annotations, fields (type + name), and method signatures with line ranges
3. Continue with the workflow as normal

The goal is always: understand the Java file's structure with minimal tokens. jskim is the fast path, but you can always do it yourself if it breaks.

## What $ARGUMENTS is for

If the host skill environment invokes this skill with arguments:
- If argument is a `.java` file -> run `jskim $ARGUMENTS`
- If argument is a directory -> run `jskim $ARGUMENTS`
- If argument is `<file.java> <method>` -> run `jskim $ARGUMENTS`
- If no arguments -> explain the available jskim modes
