# Thread Dump Diagnostic Report

**Timestamp:** 2024-01-15 10:30:45
**JVM:** Full thread dump OpenJDK 64-Bit Server VM (17.0.1+12 mixed mode):

**Summary:** 🔴 2 issues DETECTED → Stuck Threads, Cpu Storm

## Thread Statistics
**Total threads:** 6
**Daemon threads:** 0

| State | Count |
|-------|-------|
| RUNNABLE | 6 (100%) |
| WAITING | 0 |
| TIMED_WAITING | 0 |
| BLOCKED | 0 |

**By group:**

| Group | Total | RUNNABLE | WAITING | TIMED_WAITING | BLOCKED |
|-------|-------|----------|---------|---------------|---------|
| worker | 5 | 5 | 0 | 0 | 0 |
| main | 1 | 1 | 0 | 0 | 0 |

> Compare group sizes with your nominal baseline — an unusual count may indicate a thread leak.

## 🟢 Deadlock - NOT DETECTED

## 🟢 Lock Contention - NOT DETECTED

## 🟢 Thread Pool Saturation - NOT DETECTED

## 🟡 Stuck Threads - DETECTED
**Confidence:** medium

**Evidence:**
  - 5 threads at: at com.example.HotLoop.spin(HotLoop.java:15)

**Business note:**
STUCK THREADS: Multiple threads blocked at same code location. Likely a bottleneck or blocked resource.

**Next data to collect:**
  - Check the common stack frame - what resource does it access?
  - Look for socket reads, DB queries, file I/O at that location
  - Compare multiple dumps to confirm threads aren't making progress

## 🔴 Cpu Storm - DETECTED
**Confidence:** high

**Evidence:**
  - 100% of threads RUNNABLE (6/6)
  - 5 RUNNABLE threads at: at com.example.HotLoop.spin(HotLoop.java:15)

**Business note:**
CPU STORM: 100% of threads are RUNNABLE and clustering at the same location. Likely a hot loop, spinlock, or runaway computation exhausting CPU.

**Next data to collect:**
  - Take a CPU profile (async-profiler, JFR) to confirm the hot method
  - Check if the clustering frame is a tight loop or busy-wait
  - Compare CPU% in top/jstat — high CPU confirms active spinning
  - Take multiple dumps 5s apart to confirm threads are not making progress

---
**Slack summary (copy-paste):**
```
🔴 CRITICAL: Stuck threads (1 locations) | 6 threads
```
