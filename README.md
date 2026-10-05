<div align="center">

# 🛡️ Agentic AI for Supply Chain Disruption Response & Recovery

### Five specialist AI agents, one orchestrator, and a human who always has the final word.

[![Open Live Demo](https://img.shields.io/badge/▶_OPEN_LIVE_DEMO-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://agentic-ai-supply-chain-recovery-dashboard-hks.streamlit.app/)

**[agentic-ai-supply-chain-recovery-dashboard-hks.streamlit.app](https://agentic-ai-supply-chain-recovery-dashboard-hks.streamlit.app/)**

</div>

---

## The problem

Picture a mid-size industrial equipment manufacturer — about 20 suppliers, 50 customers, 3 distribution
centers. A supplier ships a component eight days late. That one delay ripples outward immediately:

- **Is there enough inventory on hand** to absorb it, or will production actually stall?
- **Which production orders** need that component, and how many units are really at stake?
- **Which customer commitments** are now at risk — and which of those customers are contractually the
  ones you *cannot* afford to disappoint?
- **Is there a backup supplier**, and is it actually fast enough and cheap enough to matter?
- **What's the fastest way to move stock** once a sourcing decision is made?

Answering all five of those well, under time pressure, usually means several people pulling data from
several systems before anyone can make a decision. This project replaces that scramble with a coordinated
team of AI agents — while keeping a human firmly in charge of the final call.

## The system, end to end

A disruption is reported in plain English — *"Suntech delayed PO-00301 (500 units of CMP-007) by 8
days."* — and a hierarchical multi-agent AI system takes it from there:

```
                         ┌─────────────────────┐
   Plain-English  ─────▶ │   ORCHESTRATOR        │
   disruption report     │   OpenAI GPT-5-mini    │
                         └──────────┬───────────┘
                                     │ delegates to five specialists, in parallel
          ┌──────────────┬──────────┼──────────────┬──────────────┐
          ▼              ▼          ▼              ▼              ▼
     INVENTORY      PROCUREMENT  PRODUCTION   CUSTOMER IMPACT   LOGISTICS
   Claude Haiku 4.5  Groq gpt-oss  Gemini 3.1   Qwen 3.7 Flash   Gemini 3.1
          │              │          │              │              │
   "What do we      "Who else    "Which jobs    "Which          "What's the
    actually         can supply   need this      customers      fastest way
    have?"           this, and    part, and      do we          to move
                      how fast?"  how many        protect        stock?"
                                  units?"         first?"
          │              │          │              │              │
          ▼              ▼          ▼              ▼              ▼
     each agent queries its OWN read-only database tool — never guesses,
     never invents a number, never touches another agent's data
          │              │          │              │              │
          └──────────────┴──────────┴──────────────┴──────────────┘
                                     │
                                     ▼
                       ORCHESTRATOR assembles everything into
                       ONE six-part recovery plan:
                       1. Disruption summary
                       2. What inventory covers
                       3. How the shortfall gets sourced, and by when
                       4. Which customer commitments are protected vs. at risk
                       5. Recommended transport option
                       6. Final recommended action plan
                                     │
                                     ▼
                      Every proposed action is risk-tagged:
                      [RISK: Low] report only
                      [RISK: Medium] reallocate inventory / reschedule
                      [RISK: High] place a PO / pick a new supplier / book shipping
                                     │
                                     ▼
                         ⏸  STOPS HERE.  A human reviews the
                            plan and chooses Approve or Reject.
                           │                        │
                      ✅ Approve                 ❌ Reject + notes
                           │                        │
                           ▼                        ▼
                 Logged as executed        Rejection + feedback sent
                 (simulated — no real      straight back to the
                 system is touched)        Orchestrator for a revised plan
                           │                        │
                           ▼                        ▼
                         Both outcomes are written to a permanent,
                         timestamped audit trail — nothing disappears,
                         approved or not.
```

No agent ever acts on its own. The Orchestrator can't place an order, pick a supplier, or book a
shipment — it can only *propose*. A human approves or rejects every single time.

## Why five different AI models?

Each specialist agent runs on a **different LLM provider** — OpenAI, Anthropic, Groq, Google Gemini, and
Alibaba Qwen. That's deliberate, not accidental: it means the system's workload is spread across five
independent free-tier quotas instead of hammering a single provider's rate limit. It's also a practical
demonstration that the "agent" abstraction doesn't care which model sits behind it — the Orchestrator
talks to all five the same way, through the same tool-calling interface, regardless of what's actually
answering on the other end.

| Agent | Model | Answers questions about |
|---|---|---|
| **Orchestrator** | OpenAI GPT-5-mini | Delegation, synthesis, the final recovery plan |
| **Inventory** | Anthropic Claude Haiku 4.5 | On-hand stock, safety stock, reserved units, available-to-promise |
| **Procurement** | Groq — `gpt-oss-120b` | Purchase-order status, shipment delays, approved backup suppliers |
| **Production** | Google Gemini 3.1 Flash Lite | Which production orders need the affected part, and how many units |
| **Customer Impact** | Alibaba Qwen 3.7 Flash | Which customer orders are exposed, ranked by contractual priority |
| **Logistics** | Google Gemini 3.1 Flash Lite | Shipping mode, cost, ETA, and capacity for moving stock |

## A real example, not a staged one

The system has actually run this disruption end to end: *Suntech delayed PO-00301 (500 units of CMP-007)
by 8 days.* Its first recovery plan recommended expedited air freight. A human reviewer rejected it,
noting the cost wasn't justified given the actual numbers. The Orchestrator took that feedback, re-queried
its agents, and came back with a revised plan — regional road transport instead, at a fraction of the
cost, still meeting the deadline. That second plan was approved. Both the rejection and the approval are
permanently recorded. You can walk through this exact run on the **Sample Run** page of the dashboard.

## The dataset behind it

Every number in this dashboard — KPI tiles, charts, and every recovery plan the Disruption Console
generates — is computed from a real relational dataset modeling that manufacturer: roughly **1,600 rows**
across 12 tables — suppliers, products, bill-of-materials, purchase orders, shipments, inventory,
production orders, customer SLAs, customer orders, approved backup suppliers, transport options, and a
log of disruption events. Nothing in the dashboard is hand-scripted demo content; it's all read live off
this data.

## Explore it yourself

The live dashboard has seven pages:

- **🏠 Executive Overview** — the business at a glance: open purchase-order risk, disruption types,
  customer order health.
- **🧠 Agent Network** — an interactive map of all six agents, their real system prompts, and exactly how
  the human-approval step works.
- **📊 Data Explorer** — browse and search the full dataset behind every agent.
- **🚨 Disruption Console** — type a disruption yourself and watch a complete six-part recovery plan get
  generated from the real data.
- **✅ Approval & Audit Trail** — step into the reviewer's seat and approve or reject a plan yourself.
- **📁 Sample Run** — the real reject → revise → approve story, in full.
- **ℹ️ About & Deployment** — guardrails, safety design, and current limitations.

## Guardrails — because "agentic" should never mean "unsupervised"

- Every specialist agent is **strictly read-only** against the data — not one of them can write, change,
  or delete anything.
- **A human approves or rejects every plan.** There is no path to execution that skips this.
- Every proposed action is explicitly **risk-tagged** before a human ever sees it.
- Agents are instructed to **never fabricate** a number, supplier, date, or status their own data tool
  didn't actually return.
- Execution is **simulated by design** — this system proposes and logs, it never touches a real ERP,
  purchase-order system, or shipment carrier.
- Every decision, approved or rejected, is captured in a **permanent audit trail**, with the plan, the
  reviewer's notes, and the timestamp.

---

<div align="center">

**Harsh Kumar Sharma** · Data Analytics Internship, Project 3

</div>
