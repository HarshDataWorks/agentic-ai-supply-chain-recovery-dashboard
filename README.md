# Agentic AI — Supply Chain Disruption Response & Recovery (Streamlit Dashboard)

A professional, data-grounded Streamlit front-end for the n8n multi-agent
supply-chain disruption recovery system: an Orchestrator (GPT-5-mini)
delegating to 5 specialist agents (Inventory, Procurement, Production,
Customer Impact, Logistics), each backed by its own LLM and its own
read-only Snowflake lookup tool.

## Pages

1. **Executive Overview** — KPI tiles, PO/disruption/order-status charts, end-to-end flow strip.
2. **Agent Network** — interactive node diagram of the Orchestrator + 5 specialists, model/tool roster, exact system prompts, and the human-approval flow.
3. **Data Explorer** — browse/search/download all 12 source tables (the same ones the agents' Snowflake tools query).
4. **Disruption Console** — type a disruption, pick a component_id, and get a full six-part recovery plan:
   - Uses an **offline simulator** (pure pandas — same lookup logic as the 6 n8n "Tool -" workflows) by default, so it runs free with no LLM calls.
   - If you paste your **live n8n production webhook URL** into the sidebar, it calls your real deployed Orchestrator instead.
5. **Approval & Audit Trail** — mirrors the n8n `Wait` form (Approve/Reject + Notes) and writes a session-local `action_log`, exactly matching the real system's `EXEC-<id>` / `EXEC-<id>-R<round>` log-id scheme.
6. **Sample Run (Execution #326)** — the real, previously recorded end-to-end example (reject → re-plan → approve) from the live workflow.
7. **About & Deployment** — tech stack, guardrails, deployment status, known limitations.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy for free on Streamlit Community Cloud (no card required)

1. Create a new **public GitHub repository** (e.g. `supply-chain-agentic-dashboard`) and push everything in this folder (`app.py`, `data_utils.py`, `requirements.txt`, the `data/` folder with all 12 CSVs) to it.
2. Go to **https://share.streamlit.io** and sign in with your GitHub account.
3. Click **"New app"** → choose your repository and branch → set **Main file path** to `app.py`.
4. Click **Deploy**. Streamlit Cloud installs `requirements.txt` automatically and gives you a public `https://<your-app>.streamlit.app` URL.
5. (Optional) In the app's **Settings → Secrets**, you can pre-fill the n8n webhook URL so it doesn't need to be re-typed every visit — but the dashboard works fully standalone without it, via the offline simulator.

No billing, no card, and no server to keep alive — Streamlit Community Cloud's free tier is sufficient for this app's size.
