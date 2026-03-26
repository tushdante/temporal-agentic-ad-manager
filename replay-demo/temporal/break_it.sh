#!/usr/bin/env bash
#
# Replay Divergence Demo — Temporal Side
#
# This script automates the full demo:
#   1. Starts a v1 worker (threshold=2.0)
#   2. Starts the workflow
#   3. Waits for cycle 1 to complete (ROAS=2.5 → increase_budget)
#   4. Kills the v1 worker
#   5. Starts a v2 worker (threshold=3.0)
#   6. Watches Temporal detect the divergence → NonDeterminismError
#
# Prerequisites:
#   - Temporal Cloud configured in ../../.env
#   - Python venv activated with temporalio installed
#
# Usage:
#   cd replay-demo/temporal
#   bash break_it.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  Temporal Replay Divergence Demo${NC}"
echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
echo

# Step 1: Start v1 worker
echo -e "${GREEN}[Step 1]${NC} Starting worker with VERSION 1 (threshold=2.0)..."
python worker.py v1 &
V1_PID=$!
sleep 3
echo -e "  Worker PID: ${V1_PID}"
echo

# Step 2: Start workflow
echo -e "${GREEN}[Step 2]${NC} Starting budget decision workflow..."
python starter.py --cycles 5 &
STARTER_PID=$!
echo

# Step 3: Wait for cycle 1 to complete
echo -e "${YELLOW}[Step 3]${NC} Waiting 15s for cycle 1 to complete..."
echo -e "  (cycle 1: ROAS=2.5 > 2.0 → increase_budget called under v1)"
sleep 15
echo

# Step 4: Kill v1 worker
echo -e "${RED}[Step 4]${NC} Killing v1 worker (simulating a deploy)..."
kill $V1_PID 2>/dev/null || true
wait $V1_PID 2>/dev/null || true
echo -e "  v1 worker stopped."
echo

# Step 5: Start v2 worker
echo -e "${GREEN}[Step 5]${NC} Starting worker with VERSION 2 (threshold=3.0)..."
echo -e "  ${YELLOW}The threshold changed: 2.0 → 3.0${NC}"
echo -e "  ${YELLOW}ROAS=2.5 triggered increase_budget in v1${NC}"
echo -e "  ${YELLOW}ROAS=2.5 would trigger hold_steady in v2${NC}"
echo -e "  ${YELLOW}Temporal will detect this mismatch on replay...${NC}"
echo
python worker.py v2 &
V2_PID=$!

# Step 6: Wait for result
echo -e "${CYAN}[Step 6]${NC} Watching for NonDeterminismError..."
echo
wait $STARTER_PID 2>/dev/null || true

echo
echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  Demo complete. Check the output above.${NC}"
echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"

# Cleanup
kill $V2_PID 2>/dev/null || true
