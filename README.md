# Temporal vs Restate: Replay Model Comparison

A focused demo comparing how Temporal and Restate handle **code changes to in-flight executions**.

## The Scenario

A budget decision workflow runs 5 cycles. Each cycle checks ROAS and decides whether to increase the budget.

- **v1 logic**: `if ROAS > 2.0 → increase budget`
- **v2 logic**: `if ROAS > 3.0 → increase budget` (threshold raised)

After cycle 1 completes under v1 (budget was increased at ROAS=2.5), the worker is killed and restarted with v2 code.

### What Happens

| | Temporal | Restate |
|---|---|---|
| **Behavior** | Replays event history, detects that v2 would not have called `increase_budget` at ROAS=2.5, raises `NonDeterminismError` | Replays journal for completed steps, then continues under v2 for new steps. No error. |
| **Result** | Workflow halted at divergence point. Operator alerted. | Workflow completes with mixed v1/v2 decisions. Silent drift. |
| **Financial impact** | Prevented — execution stopped before further damage | Budget increased under stale rules, undetected |

## Prerequisites

- Python 3.10+
- Temporal CLI (`brew install temporal`)
- Restate CLI (`brew install restatedev/tap/restate`)

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Run the Demos

### Temporal (strict replay — catches divergence)

```bash
cd replay-demo/temporal
bash break_it.sh
```

Expected output: `NonDeterminismError` after the v2 worker replays cycle 1.

### Restate (loose replay — silent drift)

```bash
cd replay-demo/restate
bash break_it.sh
```

Expected output: Workflow completes "successfully" with cycle 1 under v1 rules and cycles 2-5 under v2 rules.

## Event Timeline

See [REPLAY_COMPARISON.md](replay-demo/REPLAY_COMPARISON.md) for the full side-by-side event table.

## Project Structure

```
replay-demo/
  temporal/
    workflow.py       # Temporal workflow with budget threshold
    activities.py     # check_metrics + increase_budget activities
    worker.py         # Worker with v1/v2 version switching
    starter.py        # Start workflow + query state
    break_it.sh       # Automated demo script
  restate/
    handler_v1.py     # Restate handler with threshold=2.0
    handler_v2.py     # Restate handler with threshold=3.0
    handler.py        # Hot-swappable handler (imports v1 or v2)
    invoke.py         # Start and poll workflow
    break_it.sh       # Automated demo script
  REPLAY_COMPARISON.md  # Side-by-side event comparison table
```
