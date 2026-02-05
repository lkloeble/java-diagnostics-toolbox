# Java Diagnostics Toolbox

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Small, opinionated, immediately-useful diagnostic scripts for triaging production issues in Java monoliths.

This repository collects lightweight tools I (and hopefully others) use during performance / stability missions on large Java backends.

Focus: fast first-responder triage — minutes to insight, not hours of setup or analysis.

## Philosophy

- Minimal dependencies (mostly stdlib + pytest for tests)
- Opinionated defaults → no 50 flags
- Clear output: short, readable reports (Markdown + plain text)
- Strong emphasis on **business value**: detect the most common time-wasters first (leaks, GC thrashing, allocation pressure, etc.)
- Each tool lives in its own subdirectory under `/tools/`
- Easy to use standalone or as part of the full toolbox

## Current tools

### GC Flu Test (G1 GC log triage)

Quick "flu test" for G1 GC logs — detects usual suspects (retention patterns, allocation pressure, long pauses) and recommends the next low-effort data to collect.

→ [tools/gc_diagnostic/README.md](tools/gc_diagnostic/README.md)  
→ [Quick start & usage](tools/gc_diagnostic/README.md#quick-start)

More tools will be added over time (thread dumps, JFR helpers, allocation profiling helpers, etc.).

## Usage

Clone and jump into the tool you need:

```bash
git clone https://github.com/lkloeble/java-diagnostics-toolbox.git
cd java-diagnostics-toolbox/tools/<tool-name>
python3 <script>.py ...
```

Most tools are stdlib-only → no installation required.
For development / contribution:

Open the repo root in PyCharm (or your IDE)
Create/use .venv at root
pip install -r requirements-dev.txt
Tests: pytest tools/<tool>/tests/


## License
MIT — free to use, modify, distribute.
