#!/usr/bin/env bash
#
# Replay Divergence Demo — Restate Side
#
# This script automates the Restate equivalent:
#   1. Starts Restate server (docker)
#   2. Starts v1 handler (threshold=2.0)
#   3. Registers the service and invokes the handler
#   4. Waits for cycle 1 to complete (ROAS=2.5 → increase_budget)
#   5. Kills v1 handler, starts v2 handler (threshold=3.0)
#   6. Shows Restate completing with mixed v1/v2 decisions — NO ERROR
#
# Prerequisites:
#   - Docker running (for Restate server)
#   - pip install restate-sdk hypercorn
#
# Usage:
#   cd replay-demo/restate
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
echo -e "${CYAN}  Restate Replay Divergence Demo${NC}"
echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
echo

# Step 1: Start Restate server
echo -e "${GREEN}[Step 1]${NC} Starting Restate server via Docker..."
docker run -d --name restate-demo --rm -p 8080:8080 -p 9070:9070 docker.io/restatedev/restate:latest 2>/dev/null || \
  echo "  (Restate container may already be running)"
sleep 3
echo

# Step 2: Start v1 handler
echo -e "${GREEN}[Step 2]${NC} Starting handler with VERSION 1 (threshold=2.0)..."
python handler_v1.py &
V1_PID=$!
sleep 2
echo -e "  Handler PID: ${V1_PID}"
echo

# Step 3: Register service with Restate
echo -e "${GREEN}[Step 3]${NC} Registering service with Restate server..."
curl -s -X POST http://localhost:9070/deployments -H 'content-type: application/json' \
  -d '{"uri": "http://host.docker.internal:9080"}' | python -m json.tool 2>/dev/null || \
  echo "  Service registered (or already registered)"
echo

# Step 4: Invoke the handler
echo -e "${GREEN}[Step 4]${NC} Invoking budget optimizer..."
curl -s -X POST http://localhost:8080/BudgetOptimizer/demo-campaign/optimize \
  -H 'content-type: application/json' \
  -d '5' &
INVOKE_PID=$!
echo

# Step 5: Wait for cycle 1
echo -e "${YELLOW}[Step 5]${NC} Waiting 15s for cycle 1 to complete..."
echo -e "  (cycle 1: ROAS=2.5 > 2.0 → increase_budget journaled under v1)"
sleep 15
echo

# Step 6: Kill v1, start v2
echo -e "${RED}[Step 6]${NC} Killing v1 handler (simulating a deploy)..."
kill $V1_PID 2>/dev/null || true
wait $V1_PID 2>/dev/null || true
echo -e "  v1 handler stopped."
echo

echo -e "${GREEN}[Step 7]${NC} Starting handler with VERSION 2 (threshold=3.0)..."
echo -e "  ${YELLOW}The threshold changed: 2.0 → 3.0${NC}"
echo -e "  ${YELLOW}ROAS=2.5 was journaled as increase_budget under v1${NC}"
echo -e "  ${YELLOW}Restate will replay that journal entry without checking${NC}"
echo -e "  ${YELLOW}whether v2 would have made the same decision...${NC}"
echo
python handler_v2.py &
V2_PID=$!

# Step 8: Wait for completion
echo -e "${CYAN}[Step 8]${NC} Watching for result (expect NO error — silent drift)..."
echo
wait $INVOKE_PID 2>/dev/null || true

echo
echo -e "${RED}════════════════════════════════════════════════════════════${NC}"
echo -e "${RED}  No error. No warning. Mixed v1/v2 decisions.${NC}"
echo -e "${RED}  Restate completed 'successfully' with silent drift.${NC}"
echo -e "${RED}════════════════════════════════════════════════════════════${NC}"

# Cleanup
kill $V2_PID 2>/dev/null || true
docker stop restate-demo 2>/dev/null || true
