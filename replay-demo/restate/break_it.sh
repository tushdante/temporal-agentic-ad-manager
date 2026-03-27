#!/usr/bin/env bash
#
# Replay Divergence Demo — Restate Side
#
# Demonstrates that Restate completes with mixed v1/v2 decisions
# when handler code changes mid-execution. No error, no warning.
#
# Uses handler.py with ROAS_THRESHOLD env var to control version.
# Same endpoint, code swap — simulates a real deploy.
#
# Prerequisites:
#   - Docker running (for Restate server)
#   - Python venv activated with restate-sdk and hypercorn installed
#
# Usage:
#   cd replay-demo/restate
#   source ../../.venv/bin/activate
#   bash break_it.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
mkdir -p log

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

cleanup() {
    echo ""
    echo -e "${CYAN}Cleaning up...${NC}"
    kill "$H_PID" 2>/dev/null || true
    # docker stop restate-demo 2>/dev/null || true
}
trap cleanup EXIT

echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  Restate Replay Divergence Demo${NC}"
echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
echo

# Step 1: Start Restate server (clean)
echo -e "${GREEN}[Step 1]${NC} Starting Restate server via Docker..."
docker stop restate-demo 2>/dev/null || true
docker rm restate-demo 2>/dev/null || true
sleep 1
docker run -d --name restate-demo --rm -p 8080:8080 -p 9070:9070 docker.io/restatedev/restate:latest >/dev/null 2>&1
sleep 4
echo -e "  Restate server ready."
echo

# Kill any leftover handler on port 9080
lsof -ti:9080 | xargs kill -9 2>/dev/null || true
sleep 1

# Step 2: Start v1 handler (threshold=2.0)
echo -e "${GREEN}[Step 2]${NC} Starting handler with VERSION 1 (threshold=2.0)..."
# Clear log from previous runs
> log/handler.log
ROAS_THRESHOLD=2.0 python3 handler.py >> log/handler.log 2>&1 &
H_PID=$!
sleep 3
echo -e "  Handler PID: ${H_PID}"
echo

# Step 3: Register service with Restate
echo -e "${GREEN}[Step 3]${NC} Registering service with Restate server..."
curl -s -X POST http://localhost:9070/deployments -H 'content-type: application/json' \
  -d '{"uri": "http://host.docker.internal:9080"}' > /dev/null 2>&1
echo -e "  Service registered."
echo

# Step 4: Invoke the handler (async — returns invocation ID)
echo -e "${GREEN}[Step 4]${NC} Invoking budget optimizer (5 cycles)..."
INVOCATION=$(curl -s -X POST "http://localhost:8080/BudgetOptimizer/demo-campaign/optimize/send" \
  -H 'content-type: application/json' -d '5')
INV_ID=$(echo "$INVOCATION" | python3 -c "import sys,json; print(json.load(sys.stdin)['invocationId'])")
echo -e "  Invocation ID: ${INV_ID}"
echo

# Step 5: Wait for cycle 1 and capture v1 handler logs
echo -e "${YELLOW}[Step 5]${NC} Waiting 15s for cycle 1 to complete..."
echo -e "  (cycle 1: ROAS=2.5 > 2.0 → increase_budget under v1)"
sleep 15
echo
echo -e "${GREEN}  v1 handler log (what ACTUALLY happened):${NC}"
grep -E "\[v1\].*\[DECIDED\]|\[v1\].*\[CYCLE" log/handler.log 2>/dev/null || echo "  (no v1 decision events yet — check log/handler.log)"
echo

# Step 6: Kill v1 handler
echo -e "${RED}[Step 6]${NC} Killing v1 handler (simulating a deploy)..."
kill -9 "$H_PID" 2>/dev/null || true
wait "$H_PID" 2>/dev/null || true
sleep 3
echo -e "  v1 handler stopped."
echo

# Step 7: Start v2 handler (same endpoint, new threshold)
echo -e "${GREEN}[Step 7]${NC} Starting handler with VERSION 2 (threshold=3.0)..."
echo -e "  ${YELLOW}The threshold changed: 2.0 → 3.0${NC}"
echo -e "  ${YELLOW}Under v1, ROAS=2.5 > 2.0 triggered budget_increased${NC}"
echo -e "  ${YELLOW}Under v2, ROAS=2.5 <= 3.0 would NOT trigger it${NC}"
echo -e "  ${YELLOW}But the budget was ALREADY increased in the real world${NC}"
echo
ROAS_THRESHOLD=3.0 python3 handler.py >> log/handler.log 2>&1 &
H_PID=$!
sleep 3
echo -e "  v2 handler PID: ${H_PID}"
echo

# Step 8: Poll for completion
echo -e "${CYAN}[Step 8]${NC} Polling for result (expect NO error — silent drift)..."
echo
for i in $(seq 1 20); do
    RESULT=$(curl -s "http://localhost:8080/restate/invocation/${INV_ID}/output" 2>&1)
    if echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d, indent=2))" 2>/dev/null | grep -q "decisions"; then
        echo ""
        echo -e "${RED}════════════════════════════════════════════════════════════${NC}"
        echo -e "${RED}  RESULT — COMPLETED 'SUCCESSFULLY'${NC}"
        echo -e "${RED}════════════════════════════════════════════════════════════${NC}"
        echo "$RESULT" | python3 -c "
import sys, json
data = json.loads(sys.stdin.read())
for d in data.get('decisions', []):
    print(f'  {d}')
print(f'  threshold at completion: {data.get(\"threshold_at_completion\")}')
"
        echo ""
        echo -e "${RED}  DRIFT: v1 executed budget_increased for cycle 1 (ROAS=2.5 > 2.0)${NC}"
        echo -e "${RED}  But v2 re-evaluated and recorded hold_steady (ROAS=2.5 <= 3.0)${NC}"
        echo -e "${RED}  The budget increase HAPPENED but the record says it didn't.${NC}"
        echo -e "${RED}  No error. No warning. History rewritten.${NC}"
        echo -e "${RED}════════════════════════════════════════════════════════════${NC}"
        echo ""
        echo -e "${YELLOW}  Full handler log (v1 + v2 entries): log/handler.log${NC}"
        echo -e "${YELLOW}  Compare [v1] entries with [v2] entries — the audit trail is wrong.${NC}"
        break
    elif echo "$RESULT" | grep -q '"message".*not completed'; then
        echo "  Still running... ($i/20)"
        sleep 10
    else
        echo "  Response: $RESULT"
        sleep 10
    fi
done
