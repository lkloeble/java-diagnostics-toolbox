
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Quick start

```bash
# Clone the toolbox
git clone https://github.com/lkloeble/java-diagnostics-toolbox.git
cd java-diagnostics-toolbox/tools/async_profiler_diagnostic

# Profile a running JVM (30s CPU profile)
asprof -d 30 -e cpu -o collapsed -f cpu.collapsed <pid>

# Analyze
python3 get-async-profiler-diagnostic.py cpu.collapsed --app-prefix com.example.myapp

# Markdown output, top 20 hot stacks
python3 get-async-profiler-diagnostic.py cpu.collapsed --app-prefix com.example.myapp --top 20 --format md
```

Output → two files created in current directory:

- `async-profiler-diagnostic.md`
- `async-profiler-diagnostic.txt`

---

## What is get-async-profiler-diagnostic ?

A structured reader for [async-profiler](https://github.com/async-profiler/async-profiler) collapsed stacks output.

It answers one question: **"Where is CPU time actually going in this application, broken down by layer?"**

This is **not** a performance advisor. It does not tell you what to fix.
It gives you a clear, layered picture of the profile so you can read it in seconds instead of minutes.

---

## Why this exists

async-profiler produces collapsed stacks files with thousands of lines, each containing a full call chain.
Reading them raw is slow and error-prone.

This tool:

- Groups CPU samples by architectural layer (your code / Spring / Hibernate / JDBC / JDK / JVM)
- Shows the top N hot stacks with their call chain, trimmed to the leaf end
- Separates your application code from infrastructure with a single `--app-prefix` argument

No advice. No thresholds. Just the facts, structured.

---

## Supported input

- **async-profiler collapsed stacks** (`-o collapsed`) — CPU and alloc modes
- async-profiler 2.x, 3.x, 4.x
- File path or stdin (`-`)

The tool validates that the input looks like a collapsed stacks file before analyzing.

---

## Layer distribution

Every stack's **leaf frame** (the hot frame — rightmost in the collapsed format) is classified into a layer:

| Layer | Matched prefixes |
|-------|-----------------|
| **App** | your `--app-prefix` (e.g. `com/example/myapp`) |
| **Spring** | `org/springframework` |
| **Hibernate** | `org/hibernate`, `jakarta/persistence`, `javax/persistence` |
| **JDBC** | `java/sql`, `javax/sql`, `com/mysql`, `org/postgresql`, `oracle/jdbc`, `com/zaxxer`, `org/h2` |
| **JDK** | `java/`, `javax/`, `jdk/`, `sun/`, `com/sun/` |
| **JVM/Native** | frames with no `/` (C/C++ symbols, OS calls, JIT stubs) |
| **Other** | everything else |

The `--app-prefix` accepts both dot notation (`com.example.myapp`) and slash notation (`com/example/myapp`).

---

## Hot stacks

The top N stacks (configurable, default 10) are shown sorted by sample count.
Each stack displays its **leaf end** — the last 4 frames, with `... →` prefix if truncated.

```
#1  [40 samples — 27.2%]  JDBC
  ... → UserService.findById → AbstractProducedQuery.list → ClientPreparedStatement.executeQuery → NativeSession.execSQL
```

Reading left to right: context → hot frame. The rightmost frame is where the CPU was at sample time.

---

## Example output

```
============================================================
ASYNC-PROFILER DIAGNOSTIC
File   : cpu.collapsed
Samples: 147  |  Stacks: 10
Prefix : com/example/myapp
============================================================

LAYER DISTRIBUTION  (by leaf / hot frame)
------------------------------------------------------------
  App                 50   34.0%  ████████████████████████████
  JDBC                40   27.2%  ██████████████████████
  JDK                 25   17.0%  ██████████████
  Hibernate           15   10.2%  ████████
  JVM/Native          10    6.8%  █████
  Spring               5    3.4%  ██
  Other                2    1.4%  █

TOP 10 HOT STACKS
------------------------------------------------------------
#1  [40 samples — 27.2%]  JDBC
  ... → UserService.findById → AbstractProducedQuery.list → ClientPreparedStatement.executeQuery → NativeSession.execSQL

#2  [30 samples — 20.4%]  App
  ... → OrderController.listOrders → OrderService.filterByStatus → Order.isEligible

#3  [25 samples — 17.0%]  JDK
  ... → ReportController.exportCsv → ReportService.buildCsv → java/lang/StringBuilder.append

#4  [20 samples — 13.6%]  App
  ReportGenerator.computeMetrics → Statistics.mean

#5  [15 samples — 10.2%]  Hibernate
  ... → PaymentService.processPayment → Loader.loadEntityBatch → DefaultLoadEventListener.proxyOrLoad
```

---

## What it will NOT do

It will not replace async-profiler's flamegraph view for deep exploration of individual stacks.

It will not tell you whether a percentage is "too high" or whether a hot path is a problem.
That depends on your application, your SLOs, and what you were doing during the profiling window.

It will not support JFR recordings or other profiler formats.

This tool is a **structured first read** — orientation before investigation.

---

## Notes on profiling environment

**Apple Silicon (ARM64 macOS):** profiles often show a large `JVM/Native` percentage dominated by `pthread_jit_write_protect_np`. This is a JVM overhead specific to Apple Silicon (memory page write-protection required for JIT on ARM64). It is not present on Linux x86_64. If you see this pattern, focus on the non-JVM/Native layers for application-level analysis.

**Profiling window matters:** profile under representative load. An idle application produces only JVM infrastructure frames (thread pools waiting, GC threads sleeping) with very few samples. Use a load generator or capture during peak traffic.

---

## Parameters

```
positional:
  collapsed_file        Path to collapsed stacks file, or '-' for stdin

optional:
  --app-prefix PREFIX   Package prefix of your application code.
                        Accepts dot or slash notation: com.example.myapp or com/example/myapp.
                        Without this, your code falls into the Other layer.

  --top N               Number of hot stacks to display (default: 10)

  --format txt|md       Output format (default: txt)
```

---

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success — report generated |
| 1 | Error — file not found or invalid format |

---

## Development setup

```bash
# From repo root
python3 -m venv .venv
source .venv/bin/activate
pip install pytest

# Run tests
pytest tools/async_profiler_diagnostic/tests/
```
