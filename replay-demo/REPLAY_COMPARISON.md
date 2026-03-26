# Replay Model Comparison: Temporal vs Restate

## The Scenario

A campaign budget optimizer runs 5 cycles. Each cycle checks ROAS and decides whether to increase the budget.

**Version 1** (deployed at start): increase budget when `ROAS > 2.0`
**Version 2** (deployed mid-flight): increase budget when `ROAS > 3.0`

The critical moment: **Cycle 1 has `ROAS = 2.5`**.
- Under v1: `2.5 > 2.0` → `increase_budget` is called
- Under v2: `2.5 < 3.0` → `hold_steady` is called

The workflow starts under v1, completes cycle 1 (budget increased), then the service restarts with v2 code.

## What Happens

### Temporal: NonDeterminismError

```
Cycle 1 (v1): check_metrics → ROAS=2.5 → increase_budget ✓  (recorded in event history)
--- Worker restarts with v2 ---
Temporal replays CODE through event history:
  v2 code says: ROAS=2.5 < 3.0 → should call hold_steady
  Event history says: increase_budget was called
  MISMATCH → NonDeterminismError ✗
```

Temporal replays by **re-executing the workflow code** against the event history. When the code path diverges from what was recorded, it halts immediately with a clear error identifying the exact divergence point.

**The workflow is protected.** No mixed-version decisions. The operator sees the error and can use `workflow.patched()` or worker versioning to handle the migration safely.

### Restate: Silent Completion

```
Cycle 1 (v1): check_metrics → ROAS=2.5 → increase_budget  (journaled)
--- Handler restarts with v2 ---
Restate replays JOURNAL:
  Cycle 1 results returned from journal (increase_budget result)
  v2 code never re-evaluates the ROAS=2.5 decision
Cycle 2 (v2): check_metrics → ROAS=1.8 < 3.0 → hold_steady  (new, v2 logic)
Cycle 3 (v2): check_metrics → ROAS=3.2 > 3.0 → increase_budget  (new, v2 logic)
...
Execution completes "successfully" ✓  (but with mixed v1/v2 decisions)
```

Restate replays by **returning journaled results** for completed steps. The new code is never evaluated for those steps. There is no comparison between what the old code did and what the new code would do.

**The workflow drifted silently.** Cycle 1 used a 2.0 threshold, cycles 2-5 used a 3.0 threshold. No error, no warning.

## Why This Matters for Pinterest

| Scenario | Temporal | Restate |
|----------|----------|---------|
| Deploy threshold change mid-campaign | Error caught, operator notified | Budget increased under stale rules |
| Deploy targeting logic change | Error caught at divergence point | Old targeting persists for past steps |
| Deploy bid strategy update | Halted before executing wrong strategy | Mixed bid strategies in same campaign |
| Compliance audit: "which rules applied?" | Event history shows exact code path | Journal shows results, not decision logic |

### Financial Impact

With ROAS=2.5 and a $75/day budget:
- **v1 decision**: Increase budget (ROAS=2.5 > 2.0) → more spend
- **v2 decision**: Hold steady (ROAS=2.5 < 3.0) → conservative

If Restate silently applies v1's "increase budget" for cycle 1 but v2's "hold steady" for cycle 4 (also ROAS=2.7), the campaign has inconsistent budget management within a single execution. At scale across thousands of campaigns, this drift is undetectable without external auditing.

## Running the Demo

### Prerequisites

```bash
# From the project root
source .venv/bin/activate
pip install restate-sdk hypercorn  # For Restate side
# Docker required for Restate server
```

### Temporal Side (detects divergence)

```bash
cd replay-demo/temporal

# Terminal 1: Start v1 worker
python worker.py v1

# Terminal 2: Start workflow
python starter.py

# Wait for cycle 1 to complete (~15s), then in Terminal 1:
# Ctrl+C to kill v1 worker, then:
python worker.py v2

# Terminal 2 shows: NonDeterminismError
```

Or run the automated script:
```bash
bash break_it.sh
```

### Restate Side (silent drift)

```bash
cd replay-demo/restate

# Automated:
bash break_it.sh

# Watch it complete "successfully" with mixed v1/v2 decisions
```

## Temporal's Safe Migration Path

Temporal provides first-class tools for evolving workflow logic safely:

### `workflow.patched()` — Inline Version Gates

```python
if roas > (3.0 if workflow.patched("roas-threshold-v2") else 2.0):
    await workflow.execute_activity(increase_budget, ...)
```

Existing workflows continue under v1 rules. New workflows use v2. No drift.

### Worker Versioning — Deploy-Level Isolation

Route in-flight workflows to v1 workers, new workflows to v2 workers. Zero code changes, zero drift.

### The Key Insight

Temporal forces you to **explicitly handle version transitions**. This feels like friction during development, but it's a safety net in production. When you're managing thousands of campaigns with real ad spend, "the system caught my mistake" is worth infinitely more than "it silently continued."

Restate's approach — replaying journal entries without re-evaluating decision logic — is simpler but provides no guardrails against code changes that alter control flow. The journal records *what happened*, not *why it happened*.

## Architecture Comparison

```
TEMPORAL                              RESTATE
═══════                               ═══════

Event History                         Journal
┌──────────────────┐                  ┌──────────────────┐
│ ActivityScheduled │                  │ RunCompleted     │
│ ActivityCompleted │                  │   result: {...}  │
│ ActivityScheduled │                  │ RunCompleted     │
│ ActivityCompleted │                  │   result: {...}  │
└──────────────────┘                  └──────────────────┘
        │                                     │
        ▼                                     ▼
  Re-execute CODE                       Return RESULTS
  against history                       from journal
        │                                     │
        ▼                                     ▼
  Code says "hold"                      Returns old result
  History says "increase"               (increase_budget)
        │                                     │
        ▼                                     ▼
  ╔═══════════════════╗               ╔═══════════════════╗
  ║ NonDeterminismError║               ║ Silent success    ║
  ║ Drift CAUGHT       ║               ║ Drift UNDETECTED  ║
  ╚═══════════════════╝               ╚═══════════════════╝
```
