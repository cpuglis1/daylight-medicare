---
name: daylight-debug
description: "Diagnose a concrete Daylight defect with a reproducible observation, targeted hypotheses and proportionate offline regression checks."
---

# Daylight Debug

Adapted from the diagnostic-loop concepts in Matt Pocock's diagnosing-bugs skill.

Read the scoped project instructions and the relevant feature/evidence contract. Establish a bounded observation that fails for the reported defect; minimize the fictional input where useful. List plausible causes and use targeted probes to distinguish them, changing one causal factor at a time.

Use existing offline tests, deterministic fixtures or read-only diagnostics. Do not run paid/live conversation probes, capture customer transcripts, change protected variants or weaken a source STOP. Avoid bisection/reset/stash in the heavily modified main workspace; isolate a deliberate snapshot if required.

Apply a targeted fix, run meaningful checks that exercise the failure and remove temporary instrumentation. Report the demonstrated cause, the exact checks, changed paths and remaining uncertainty. If no permitted observation can establish the bug, name the missing input rather than claiming a fix.
