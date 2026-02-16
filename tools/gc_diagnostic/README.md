
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Quick start

```bash
# Clone the toolbox
git clone https://github.com/lkloeble/java-diagnostics-toolbox.git
cd java-diagnostics-toolbox/tools/gc_diagnostic

# Run on your log (most common case)
python3 get-gc-diagnostic.py /path/to/your/gc.log

# Or only last 30 minutes
python3 get-gc-diagnostic.py gc.log --tail-window 30

# Force plain text output
python3 get-gc-diagnostic.py gc.log --format txt
````

Output → two files created in current directory:

- gc-diagnostic.md
- gc-diagnostic.txt


________


## What is get-gc-diagnostic ?


A tiny “flu test” for G1 GC logs — designed to answer one question fast during a production fire:

**“What are the most likely usual suspects right now, and what is the cheapest next data to collect to confirm or rule them out?”**

This is **not** JMC, VisualVM, GC Easy, or a full analysis suite. It is a **first-responder triage tool** — 2–5 minutes to run, short readable report, strong focus on **retention/leak signals first** (the #1 time-waster in most Java incidents).


---

## Why this exists

In production, GC incidents are rarely exotic.  
Teams lose time because they start by assuming “it could be anything”.

This tool is intentionally opinionated:

- It looks for a small set of **high-frequency patterns**
- It marks them as **DETECTED** or **SUSPECTED**
- It recommends the **next lowest-effort data** to collect

No slides. No dashboards. Just a quick triage artifact.

---

## Supported input (v1)

This tool supports:

- **G1 GC logs**
- Java 9+ unified logging format: `-Xlog:gc*`

If your logs are not in this format, this tool won’t try to guess.

Recommended flags (example):
```bash
-Xlog:gc*,safepoint:file=gc.log:time,uptime,level,tags
```

### Special logging for TLAB analysis

To detect TLAB exhaustion (multi-threaded allocation contention), add TLAB debug logging:

```bash
-Xlog:gc*,gc+tlab=debug,safepoint:file=gc.log:time,uptime,level,tags
```

This is optional — TLAB issues are rare but impactful in heavily multi-threaded applications.
Without this flag, TLAB analysis will simply report "no TLAB data available".

Usage
```bash
./get-gc-diagnostic.py /path/to/gc.log
```


Outputs:

gc-diagnostic.md
gc-diagnostic.txt

Both are readable as plain text.

What it detects (v1)
The tool distinguishes between:

DETECTED: strong signals available directly in GC logs

SUSPECTED: plausible patterns, but confirmation requires additional data

DETECTED (high confidence from GC logs)

- **Allocation pressure / GC thrash**: Young collections are excessively frequent and/or GC time is high relative to uptime.
- **Humongous allocation pressure (G1)**: Humongous allocations/regions appear frequently and correlate with GC activity or pause spikes.
- **Long STW pauses (tail latency risk)**: Stop-the-world pauses exceed a threshold and are frequent enough to impact user experience.
- **GC Starvation / Finalizer backlog**: Long gaps between GCs despite high heap usage — classic symptom of finalizer blocking.
- **Metaspace leak (classloader issues)**: Metaspace grows continuously, often triggered by dynamic classloading (hot deploy, JSP, plugins).
- **TLAB exhaustion** (requires `-Xlog:gc+tlab=debug`): High slow-path allocations indicate multi-threaded contention for TLAB buffers.

SUSPECTED (triage only)

- **Retention / memory leak pattern**: Old-gen usage trends upward over time despite mixed cycles or repeated collections. GC logs can't prove a leak — but they can show "old not coming down".

The "usual suspects" (context)

Most GC-related production issues tend to fall into a few buckets.
Different buckets require different evidence sources.

This tool currently detects **7 suspects**:

| Suspect | Detection | Notes |
|---------|-----------|-------|
| Heap retention / memory leaks | Detected | Old gen trend analysis |
| Long STW pauses | Detected | Pause time analysis |
| Excessive allocation rate | Detected | Evacuation failure count |
| G1 humongous allocations | Detected | Humongous region frequency + peak |
| Finalizers / GC starvation | Detected | Long inter-GC gaps + heap analysis |
| Metaspace / classloader leaks | Detected | Metaspace growth + Metadata GC triggers |
| TLAB exhaustion | Detected | Requires special logging (`-Xlog:gc+tlab=debug`) |

The point is to identify which bucket you should investigate first.


Example output (excerpt)
GC FLU TEST — SUMMARY

DETECTED:
- Allocation pressure (young GC median interval: 0.38s)
- Long STW pauses (p99 pause: 1.4s, max: 2.8s)

SUSPECTED:
- Retention / leak pattern (old usage trending upward despite mixed cycles)

EVIDENCE (high level):
- Old gen: 6.2G → 7.9G over 28min
- Mixed cycles: 11, avg reclaimed: 2.1%
- Young GC count: 4,320 over 28min (median interval: 0.39s)

NEXT LOW-EFFORT DATA:
- jcmd `<pid>` GC.class_histogram
- Start a short JFR capture focused on allocations
- If the trend persists: heap dump for MAT analysis
What it will NOT do
It will not “prove a memory leak” from logs.

It will not replace JMC/JFR.

It will not recommend a collector switch blindly.

It will not attempt to support every GC or every log format.

This tool is a first responder: triage and orientation.

Notes
This repository is part of a broader production diagnostics toolbox.
The code is intentionally small and readable.




## Parameters

This tool is intentionally minimal.  
It exposes only a small number of parameters that directly impact the analysis.

There are no “advanced” or “expert” modes.

---
```bash
--tail-window  <minutes>
```

Analyze only the last **N minutes** of the GC log, based on JVM uptime.

- If the GC log covers **less than N minutes**, the full log is analyzed.
- If not provided, the **entire GC log** is analyzed.

This is useful when a long-running application behaves normally for hours
and then starts degrading shortly before an incident.

Example:

```bash
get-gc-diagnostic.py gc.log --tail-window 30
```

This analyzes only the last 30 minutes of the GC activity.

```bash
--old-trend-mb-per-min <value>
```

Threshold used to detect a retention / leak-like growth pattern.

The tool computes the trend of Old Generation usage after GC over the
analyzed window.

If the average growth rate exceeds this threshold, a retention pattern is
reported as DETECTED.

Default value:

10 MB per minute
This value is intentionally conservative:

low enough to catch real production issues early

high enough to avoid flagging normal noise

Example:

``` bash
get-gc-diagnostic.py gc.log --old-trend-mb-per-min 15 --format md
```


Output format for the generated report.

md (default): Markdown, readable as plain text and suitable for repositories

txt: plain text, no Markdown syntax

Example:

```bash
get-gc-diagnostic.py gc.log --format txt
```

Notes on confidence
The tool always uses all available data points within the analyzed window.

If the amount of data is limited or noisy, the report will reflect this by
lowering the confidence level of the detected signal.

The tool never suppresses a result because of “insufficient data”;
it reports what it can infer and states the confidence explicitly.

What is not configurable
Some aspects are deliberately not exposed as parameters:

minimum number of GC events

internal confidence scoring

smoothing or statistical heuristics

These are implementation details and may evolve without changing the
command-line interface.

The goal is to keep the tool predictable and easy to use during incidents.



## Development setup

```bash
# From repo root
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt   # contains pytest, ruff, black

# Run tests
pytest tools/gc_diagnostic/tests/

# Format & lint (optional)
black .
ruff check --fix
```

