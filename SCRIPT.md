# Demo Script: Pinterest Ad Agent on Temporal

**Audience**: Pinterest engineering leadership and platform team
**Duration**: 25-30 minutes
**Goal**: Show why Temporal is the right foundation for Pinterest's production agentic applications

---

## Pre-Demo Setup (do before the call)

```bash
# Terminal 1: Temporal dev server
temporal server start-dev

# Terminal 2: Worker
python3 worker.py

# Have Temporal UI open at http://localhost:8233
# Have your editor open to the project
# Have run_demo.py ready in Terminal 3
```

---

## Act 1: The Problem (3 minutes)

> "Let me set the stage. Pinterest is building agentic AI applications — ad campaign optimization, content moderation, shopping recommendations — where an LLM makes decisions and calls APIs autonomously over hours or days.
>
> The hard part isn't the LLM. It's everything around it:
>
> - What happens when your agent is mid-campaign-optimization and the process crashes?
> - How do you add human approval gates before the AI increases a budget?
> - When 10,000 campaigns are running agents simultaneously, how do you scale?
> - How do you trace exactly what the agent did, why, and when?
> - And when you want to add new tools — a new API, a new data source — how do you do that without rewriting the agent?
>
> Let me show you a working answer to all of those."

---

## Act 2: Launch the Agent (5 minutes)

> "This is a Pinterest ad campaign agent. It uses Claude as its brain and Temporal as its backbone. I'm going to launch a campaign and you'll see the full lifecycle — setup, monitoring, optimization — running autonomously."

**Run in terminal:**

```bash
DEMO_MODE=true python3 starter.py --campaign "Pinterest Demo — Spring 2026" --cycles 3
```

> "A few things to notice in what just happened:
>
> 1. We started a **Temporal Workflow** — not a script, not a Lambda, not a cron job. This is a durable execution that will survive any infrastructure failure.
>
> 2. We passed it a **configuration** — the campaign name, budget, tools. The workflow itself is generic. It has zero Pinterest knowledge. All Pinterest logic lives in the tools and the system prompt.
>
> 3. Let me show you the Temporal UI."

**Switch to Temporal UI at localhost:8233**

> "Here's our workflow. You can see it's running. Let's look at the event history — every Activity, every decision, every tool call is recorded. This is your complete audit trail."

**Click into the workflow, show the event history expanding in real-time**

---

## Act 3: Watch the Agentic Loop (7 minutes)

**Run in another terminal:**

```bash
python3 run_demo.py -w pinterest-agent-pinterest-demo-—-spring-2026
```

> "Now watch what's happening. The demo follows the agent in real-time, showing every tool call and result as they happen:"

**Narrate as the output updates:**

> "**Cycle 1 — Campaign Setup:**
> The LLM decided it needs to generate creatives first. It called `generate_creatives` — that's an Activity, so Temporal handles retries if Claude is rate-limited. Now it's creating the campaign container, the ad group...
>
> And look at this — **four `create_pin` calls running in parallel**. The LLM recognized these are independent and batched them. Same for `create_ad` — four ads promoted concurrently. This isn't hardcoded parallelism. The LLM decided to do this based on the tool definitions."

**Wait for cycle 1 to complete, then:**

> "Cycle 1 is done. Campaign set up. The demo shows it in real-time — every tool call with context, every result formatted. Now the agent is sleeping — in production this would be 6 hours, for the demo it's 15 seconds. When it wakes up, it'll start the optimization loop."

**Wait for cycle 2 to start:**

> "**Cycle 2 — Optimization:**
> The agent pulls analytics and checks ad review statuses — again, in parallel because they're independent. It sees the performance data: impressions, clicks, saves, ROAS. Then it makes a decision. In early cycles, it's conservative — Pinterest's algorithm needs time to learn, and the agent knows that. It's encoded in the system prompt, not in code.
>
> Every tool call, every result, every LLM decision is in the conversation history. This is queryable in real-time via Temporal Queries. Your ops team can inspect any agent, any campaign, at any time — without stopping it."

---

## Act 4: The Durability Story (5 minutes)

> "Now let me show you why Temporal matters. I'm going to kill the worker."

**Kill the worker process (Ctrl+C in the worker terminal)**

> "The worker is dead. In a normal system, your agent is gone — mid-campaign, half the ads created, no way to recover. With Temporal..."

**Wait 5 seconds for dramatic effect, then restart:**

```bash
python3 worker.py
```

> "The worker reconnects and **picks up exactly where it left off**. No duplicate API calls. No lost state. The campaign didn't skip a beat. The agent resumes from the last completed Activity.
>
> This is durable execution. Temporal persisted every step. The workflow code is deterministic — it replays to rebuild state, then continues forward. For a Pinterest agent managing a \$50K campaign, this is the difference between 'we lost the state' and 'we recovered in milliseconds.'"

**Show the Temporal UI — the workflow is still running, event history continues**

---

## Act 5: Human-in-the-Loop (3 minutes)

> "Now, the agent doesn't have to be fully autonomous. Let's say Pinterest policy requires human approval before the agent increases budget above a threshold.
>
> In the configuration, you set `require_confirmation=True` or flag specific tools. The workflow pauses and waits for a Signal — that could come from a Slack bot, an internal dashboard, or a CLI:"

> "When the agent encounters a tool that requires confirmation — like increasing budget — the demo will prompt us inline. We just type 'y' to approve or 'n' to deny, right here in the terminal."

> "This is a Temporal Signal. The workflow was sleeping — not polling, not burning compute — genuinely suspended. The signal wakes it up and it continues. The timeout is configurable; if no one approves in 4 hours, it skips.
>
> This pattern scales to any approval flow: budget changes, creative launches, targeting updates, campaign pauses."

---

## Act 6: The Architecture (5 minutes)

> "Let me show you why this architecture matters for Pinterest at scale."

**Open `pinterest/config.py` in the editor:**

> "This is the **entire Pinterest-specific configuration**. The goal, the system prompt, the initial prompt, and the follow-up prompt for optimization cycles. That's it. No orchestration logic."

**Open `pinterest/tools/__init__.py`:**

> "Here's the tool registry. 13 tools — campaign CRUD, analytics, optimization, creative generation, notifications. Each one is a Python file with a schema and a handler. The LLM sees the schema, the dynamic Activity calls the handler."

**Open a tool file like `pinterest/tools/analytics.py`:**

> "Each tool is self-contained. The `ToolDefinition` is what the LLM sees — name, description, argument schema. The handler is what actually runs. Adding a new tool is two steps: write the file, register it. Zero changes to the workflow."

**Open `agent/workflow.py`:**

> "And this is the generic workflow. It has **no Pinterest knowledge**. It implements the agentic loop — prompt, LLM planning, tool execution, history accumulation, HITL gates, ContinueAsNew for long-running agents. You use this same workflow for ad optimization, content moderation, merchant onboarding — any agentic application."

> "Let me call out a few patterns that matter for production:
>
> 1. **Dynamic Activities** — `@activity.defn(dynamic=True)`. Tool calls are dispatched by name at runtime. The workflow doesn't know what tools exist. This is how you decouple teams — the Ads team adds tools, the Shopping team adds tools, nobody touches the core workflow.
>
> 2. **Claude's native tool_use API** — not manual JSON parsing. The LLM returns structured `tool_use` blocks. Multiple tools in one response get executed in parallel via `asyncio.gather`. Reliable, no prompt engineering hacks.
>
> 3. **`workflow.info().is_continue_as_new_suggested()`** — for campaigns running weeks or months, the event history grows. Temporal tells us when it's time to reset, and we carry the conversation across via `ContinueAsNew`. The agent never stops; the history stays manageable.
>
> 4. **Temporal retries, not LLM retries** — we set `max_retries=0` on the Anthropic client. If Claude rate-limits or the Pinterest API 500s, Temporal's retry policy handles it with exponential backoff. This means correct, durable error handling instead of the 'retry and pray' pattern."

---

## Act 7: The Scale Story (2 minutes)

> "Now let's talk scale. Pinterest runs thousands of ad campaigns. Each campaign could have its own agent workflow.
>
> With Temporal, each workflow is an independent execution. You don't need a queue consumer or a state machine. Workers are stateless — you scale horizontally by adding worker pods. Temporal Cloud handles the state and routing.
>
> And because the workflow is generic, you deploy one workflow definition, one worker fleet, and N tool registries. The Ads team, the Shopping team, the Trust & Safety team — they all share the agentic framework and contribute tools independently.
>
> That's the Nexus story, too."

**Point to the `TODO [Nexus-readiness]` comments in the code:**

> "The codebase is already annotated for Nexus. Each tool could become a Nexus Operation behind a Nexus Service. The Ads API team publishes their tools as a Nexus endpoint. The ML team publishes theirs. The agent workflow calls them cross-namespace. Different teams, different deploy cycles, one agentic platform."

---

## Act 8: Show Final Results (2 minutes)

> "The demo has been showing us everything in real-time. Let's look at the Temporal UI to see the full picture."

**Show the Temporal UI — workflow detail page:**

> "Every tool call, every result, every LLM decision is in the event history. This is your audit trail. The cycle summaries are queryable via `get_cycle_summaries()` — you can inspect any agent, any campaign, at any time without stopping it. In production, you'd pipe this to your observability stack — Datadog, Grafana, your internal dashboards. Temporal gives you the event stream; you decide how to visualize it."

---

## Close: The Ask (2 minutes)

> "So here's what we showed:
>
> 1. **An autonomous AI agent** managing a Pinterest campaign end-to-end — setup, monitoring, optimization, with real LLM decision-making.
>
> 2. **Durable execution** — the agent survives crashes, restarts, and infrastructure failures without losing state or duplicating work.
>
> 3. **Human-in-the-loop** — via Signals, the agent can pause for approval at any step, from any system.
>
> 4. **Decoupled architecture** — the workflow is generic, the tools are pluggable, teams contribute independently.
>
> 5. **Production patterns** — parallel tool execution, ContinueAsNew for long-running agents, Temporal-managed retries, full audit trail.
>
> 6. **Nexus-ready** — designed to scale to a multi-team agentic platform.
>
> The question isn't 'can we build agentic AI at Pinterest.' You're already doing it. The question is: what's the foundation that makes it reliable, scalable, and auditable? That's Temporal.
>
> Happy to dive deeper into any of these patterns, or talk about how this maps to your specific use cases."

---

## Backup Talking Points (if asked)

**"How does this compare to LangGraph/CrewAI/etc.?"**
> "Those are LLM orchestration frameworks — they manage the conversation loop. Temporal manages the infrastructure: durability, retries, timeouts, scaling, observability. You'd use Temporal *instead of* LangGraph, not alongside it. As one of our engineers put it: 'Use LangChain in Activities, skip LangGraph — Temporal workflows eliminate the need for it.'"

**"What about cost? Each LLM call is an Activity."**
> "Activities are lightweight — they're just task dispatches. The cost is in the LLM calls themselves, not in Temporal's orchestration. And because Temporal handles retries correctly, you actually make *fewer* redundant LLM calls than a naive retry loop."

**"Can we use our own models instead of Claude?"**
> "The LLM planner is a single Activity. Swap the Anthropic client for OpenAI, Gemini, or your own model. The workflow, tools, and architecture don't change."

**"How does this handle 10K concurrent campaigns?"**
> "Each campaign is an independent workflow. Workers are stateless and horizontally scalable. Temporal Cloud is battle-tested at millions of concurrent executions — Snap, Netflix, and Stripe run critical workloads on it."

**"What about observability?"**
> "Every Activity, Signal, Query, and timer is in the event history. You can query any workflow's state in real-time via the SDK or Temporal UI. For aggregate monitoring, Temporal emits metrics to Prometheus/Datadog, and you can search workflows by type, status, or custom search attributes."
