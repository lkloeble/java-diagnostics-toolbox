
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Quick start

```bash
# Clone the toolbox
git clone https://github.com/lkloeble/java-diagnostics-toolbox.git
cd java-diagnostics-toolbox/tools/thread_diagnostic

# Run on a jstack file
python3 get-thread-diagnostic.py /path/to/thread.dump

# Or pipe jstack directly
jstack <pid> | python3 get-thread-diagnostic.py -

# Markdown output
python3 get-thread-diagnostic.py --format md /path/to/thread.dump
```

Output → two files created in current directory:

- `thread-diagnostic.md`
- `thread-diagnostic.txt`

---

## What is get-thread-diagnostic ?

A tiny "first aid kit" for Java thread dumps — designed to answer one question fast during a production fire:

**"What are the most likely usual suspects right now, and what is the cheapest next data to collect to confirm or rule them out?"**

This is **not** a full thread dump analyzer. It is a **first-responder triage tool** — seconds to run, short readable report, focused on the handful of patterns that account for most Java threading incidents.

---

## Why this exists

In production, thread issues are rarely exotic.
Teams lose time because they start by assuming "it could be anything".

This tool is intentionally opinionated:

- It looks for a small set of **high-frequency patterns**
- It marks them **DETECTED** or **NOT DETECTED** with a confidence level
- It recommends the **next lowest-effort data** to collect
- It always shows a **thread inventory** so you can compare against your nominal baseline

No slides. No dashboards. Just a quick triage artifact.

---

## Supported input

- **jstack output** — any Java version 8 through 21+
- File path or stdin (`-`)

The tool validates that the input looks like a jstack dump before analyzing. It will not attempt to parse arbitrary text.

---

## What it detects

The tool runs **5 detectors** on every dump:

| Suspect | What it looks for | Confidence |
|---------|-------------------|------------|
| **Deadlock** | Circular lock dependency, or JVM-reported `Found N deadlock` marker | high (always, when detected) |
| **Lock contention** | 3+ threads BLOCKED on the same lock address | low / medium / high (scales with waiter count) |
| **Thread pool saturation** | 80%+ of a pool's threads in WAITING / TIMED_WAITING / BLOCKED | medium / high |
| **Stuck threads** | 3+ threads with identical top-2 stack frames | medium / high (scales with count) |
| **CPU storm** | RUNNABLE ratio > 50% **and** 3+ RUNNABLE threads clustering at the same frame | medium / high |
| **I/O stalls** | 3+ RUNNABLE threads blocked on socket or file reads (`SocketDispatcher`, `SocketInputStream`, `FileDispatcher`) | medium / high |

### Always shown (informational)

In addition to the suspects, the report **always** displays:

- **Thread statistics** — total threads, daemon count, state breakdown with RUNNABLE%
- **Thread group inventory** — threads grouped by name prefix (e.g. `http-nio-8080-exec` × 15), sorted by count, with state breakdown per group

The inventory has no detection threshold — it shows the facts and asks you to compare against your nominal baseline. An unusual count is the signal; you decide if it is normal for your application.

---

## Example output

```
=== Thread Dump Diagnostic Report ===
Timestamp: 2026-02-21 11:25:03
JVM: Full thread dump OpenJDK 64-Bit Server VM (21+35-LTS mixed mode):
Summary: 🔴 2 issues DETECTED → Thread Pool Saturation, Stuck Threads

Thread Statistics
  Total:         39
  Daemon:        10
  RUNNABLE:      8 (21%)
  WAITING:       29
  TIMED_WAITING: 2
  BLOCKED:       0

  By group (compare with nominal baseline):
    pool-sat-worker                   28 threads  WAITING: 28
    pool-sat-main                      1 thread   TIMED_WAITING: 1
    ...
  Note: Unusual thread counts may indicate a thread leak.

🟢 DEADLOCK - NOT DETECTED
🟢 LOCK CONTENTION - NOT DETECTED

🔴 THREAD POOL SATURATION - DETECTED
Confidence: high

Evidence:
  - pool-sat-worker: 28/28 threads waiting (100%)

Business note:
THREAD POOL SATURATION: Worker threads are starved. Requests are likely queuing up or timing out.

Next data to collect:
  - Check pool queue size (may be full)
  - Increase pool size if CPU/memory allows
  - Look for blocking I/O in worker threads
  - Check downstream dependencies (DB, external APIs)

---
Slack summary (copy-paste):
🔴 CRITICAL: Pool saturation (1 pools), Stuck threads (1 locations) | 39 threads
```

---

## What it will NOT do

It will not replace VisualVM, JMC, async-profiler, or a full thread dump analyzer.

It will not detect issues that require comparing multiple dumps over time (thread count trends, progress detection).

It will not support non-jstack formats (JFR recordings, flight recorder exports).

It will not make decisions for you on "is this thread count normal?" — that depends on your application.

This tool is a first responder: triage and orientation.

---

## Parameters

```bash
--format <md|txt>
```

Output format for the generated report.

- **txt** (default): plain text, no Markdown syntax
- **md**: Markdown, readable as plain text and suitable for repositories

```bash
# Read from file
python3 get-thread-diagnostic.py thread.dump

# Read from stdin (jstack piped directly)
jstack <pid> | python3 get-thread-diagnostic.py -
```

---

## Exit codes

The tool returns exit codes for easy integration into scripts and runbooks:

| Code | Status | Meaning |
|------|--------|---------|
| 0 | HEALTHY | No issues detected |
| 1 | WARNING | Issues detected, investigation recommended |
| 2 | CRITICAL | Immediate action required |

**CRITICAL (2)** is returned when:
- A deadlock is detected (application is frozen)
- Any suspect reaches high confidence

Example usage in scripts:
```bash
jstack <pid> | python3 get-thread-diagnostic.py - > /dev/null 2>&1
case $? in
  0) echo "All good" ;;
  1) echo "Warning - check report" ;;
  2) echo "CRITICAL - alert oncall" && send-alert.sh ;;
esac
```

---

## Development setup

```bash
# From repo root
python3 -m venv .venv
source .venv/bin/activate
pip install pytest

# Run tests
pytest tools/thread_diagnostic/tests/
```
