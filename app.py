import json
import time
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

from data_utils import (
    load_all, inventory_lookup, procurement_lookup, supplier_shipment_lookup,
    production_lookup, customer_impact_lookup, logistics_lookup,
    build_recovery_plan, TODAY,
)

st.set_page_config(
    page_title="Agentic AI — Supply Chain Disruption Response & Recovery",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ----------------------------------------------------------------------
# Global style
# ----------------------------------------------------------------------
st.markdown("""
<style>
    .block-container {padding-top: 1.6rem;}
    .metric-card {
        background: linear-gradient(135deg, #10172a 0%, #1b2742 100%);
        border: 1px solid #2a3758;
        border-radius: 12px;
        padding: 1rem 1.2rem;
    }
    .agent-card {
        border-radius: 14px;
        padding: 1rem 1.1rem;
        border: 1px solid rgba(255,255,255,0.08);
        background: rgba(255,255,255,0.03);
        height: 100%;
    }
    .risk-low {color:#22c55e; font-weight:600;}
    .risk-medium {color:#f59e0b; font-weight:600;}
    .risk-high {color:#ef4444; font-weight:600;}
    .pill {
        display:inline-block; padding:2px 10px; border-radius:999px;
        font-size:0.78rem; font-weight:600; margin-right:6px;
    }
    .pill-done {background:rgba(34,197,94,.15); color:#22c55e;}
    .pill-wip {background:rgba(245,158,11,.15); color:#f59e0b;}
    .pill-planned {background:rgba(99,102,241,.15); color:#818cf8;}
    footer {visibility:hidden;}
</style>
""", unsafe_allow_html=True)

tables = load_all()

if "action_log" not in st.session_state:
    st.session_state.action_log = pd.DataFrame(columns=[
        "log_id", "disruption_summary", "component_id", "decision",
        "approved_at", "notes", "risk_summary",
    ])
if "last_plan" not in st.session_state:
    st.session_state.last_plan = None
if "plan_round" not in st.session_state:
    st.session_state.plan_round = 0

AGENTS = [
    dict(name="Orchestrator", model="OpenAI GPT-5-mini", role="Delegates to specialists, assembles the six-part recovery plan, and proposes risk-tagged actions for human approval.", tools=["Inventory Agent", "Procurement Agent", "Production Agent", "Customer Impact Agent", "Logistics Agent"]),
    dict(name="Inventory Agent", model="Anthropic Claude Haiku 4.5", role="Reports on-hand, safety stock, reserved, and available-to-promise per warehouse.", tools=["Tool - Inventory Lookup"]),
    dict(name="Procurement Agent", model="Groq · openai/gpt-oss-120b", role="Reports PO/shipment status and ranks approved alternative suppliers by capacity, cost premium, and lead time.", tools=["Tool - Procurement Lookup", "Tool - Supplier Shipment Lookup"]),
    dict(name="Production Agent", model="Google Gemini 3.1 Flash Lite", role="Finds every non-completed production order that needs the affected component, via the bill of materials.", tools=["Tool - Production Lookup"]),
    dict(name="Customer Impact Agent", model="Alibaba Qwen 3.7 Flash", role="Ranks affected customer orders by contractual SLA priority and penalty exposure.", tools=["Tool - Customer Impact Lookup"]),
    dict(name="Logistics Agent", model="Google Gemini 3.1 Flash Lite", role="Compares transport options on cost, ETA, and capacity against the required quantity.", tools=["Tool - Logistics Lookup"]),
]

# ----------------------------------------------------------------------
# Sidebar navigation
# ----------------------------------------------------------------------
st.sidebar.markdown("## 🛡️ Supply Chain Recovery")
st.sidebar.caption("Agentic AI — Disruption Response & Recovery")
page = st.sidebar.radio(
    "Navigate",
    [
        "🏠 Executive Overview",
        "🧠 Agent Network",
        "📊 Data Explorer",
        "🚨 Disruption Console",
        "✅ Approval & Audit Trail",
        "📁 Sample Run (Execution #326)",
        "ℹ️ About & Deployment",
    ],
    label_visibility="collapsed",
)

st.sidebar.markdown("---")
with st.sidebar.expander("⚙️ Connect live n8n webhook (optional)"):
    st.text_input(
        "Production chat webhook URL",
        key="webhook_url",
        placeholder="https://your-n8n-host.onrender.com/webhook/...",
        help="If set, the Disruption Console will call your real live Orchestrator instead of the offline simulator.",
    )
st.sidebar.markdown("---")
st.sidebar.caption(f"Dataset baseline date: **{TODAY.date()}**")
st.sidebar.caption("Author: Harsh Kumar Sharma")


def risk_class(level):
    return {"Low": "risk-low", "Medium": "risk-medium", "High": "risk-high"}.get(level, "")


# =======================================================================
# PAGE: Executive Overview
# =======================================================================
if page == "🏠 Executive Overview":
    st.title("Agentic AI for Supply Chain Disruption Response & Recovery")
    st.caption("A hierarchical multi-agent system (n8n + Snowflake + 5 LLM providers) that turns a plain-English disruption report into a human-approved, auditable recovery plan.")

    c1, c2, c3, c4, c5 = st.columns(5)
    n_suppliers = tables["suppliers"].shape[0]
    n_components = tables["products"][tables["products"]["product_type"] == "Component"].shape[0]
    n_fg = tables["products"][tables["products"]["product_type"] != "Component"].shape[0]
    n_customers = tables["customer_sla"].shape[0]
    total_rows = sum(df.shape[0] for df in tables.values())

    for col, label, value, help_ in zip(
        [c1, c2, c3, c4, c5],
        ["Approved Suppliers", "Components Tracked", "Finished Goods", "Customers (SLA)", "Total Dataset Rows"],
        [n_suppliers, n_components, n_fg, n_customers, total_rows],
        ["suppliers.csv", "products.csv (Component)", "products.csv (Finished Good)", "customer_sla.csv", "across 12 Snowflake tables"],
    ):
        with col:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric(label, f"{value:,}")
            st.caption(help_)
            st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("")
    left, right = st.columns([1.3, 1])

    with left:
        st.subheader("Open Risk: Purchase Orders")
        po = tables["purchase_orders"].copy()
        po_counts = po["status"].value_counts().reset_index()
        po_counts.columns = ["Status", "Count"]
        fig = px.bar(po_counts, x="Status", y="Count", color="Status",
                      color_discrete_map={"Received": "#22c55e", "Open": "#3b82f6", "Delayed": "#ef4444"},
                      text="Count")
        fig.update_layout(showlegend=False, height=320, margin=dict(t=10, b=0, l=0, r=0))
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Disruption Events by Type")
        de = tables["disruption_events"].copy()
        type_counts = de["event_type"].value_counts().reset_index()
        type_counts.columns = ["Event Type", "Count"]
        fig2 = px.pie(type_counts, names="Event Type", values="Count", hole=0.45)
        fig2.update_layout(height=340, margin=dict(t=10, b=0, l=0, r=0))
        st.plotly_chart(fig2, use_container_width=True)

    with right:
        st.subheader("Customer Orders — Status Mix")
        co = tables["customer_orders"].copy()
        status_counts = co["status"].value_counts().reset_index()
        status_counts.columns = ["Status", "Count"]
        fig3 = px.pie(status_counts, names="Status", values="Count", hole=0.5,
                      color="Status",
                      color_discrete_map={"Fulfilled": "#22c55e", "Open": "#3b82f6", "At Risk": "#ef4444"})
        fig3.update_layout(height=320, margin=dict(t=10, b=0, l=0, r=0))
        st.plotly_chart(fig3, use_container_width=True)

        st.subheader("Active / Re-planned Disruptions")
        active = de[de["status"].isin(["Active", "Re-planned"])]
        st.dataframe(
            active[["event_id", "event_type", "component_id", "affected_qty", "delay_days", "event_date", "status"]]
            .sort_values("event_date", ascending=False),
            use_container_width=True, height=260, hide_index=True,
        )

    st.markdown("---")
    st.subheader("How it works, end to end")
    steps = st.columns(6)
    flow = [
        ("💬", "Chat input", "Plain-English disruption report arrives via n8n Chat Trigger"),
        ("🧭", "Orchestrator", "GPT-5-mini plans delegation across 5 specialists"),
        ("🛰️", "5 Specialists", "Each queries its own read-only Snowflake tool"),
        ("📋", "6-part plan", "Summary → coverage → sourcing → customer risk → transport → recommendation"),
        ("🖐️", "Human approval", "Wait form: Approve / Reject + notes"),
        ("🗄️", "Audit log", "Decision + full plan written to Snowflake action_log"),
    ]
    for col, (icon, title, desc) in zip(steps, flow):
        with col:
            st.markdown(f"<div class='agent-card'><div style='font-size:1.6rem'>{icon}</div><b>{title}</b><div style='font-size:0.82rem;opacity:0.8;margin-top:4px'>{desc}</div></div>", unsafe_allow_html=True)

# =======================================================================
# PAGE: Agent Network
# =======================================================================
elif page == "🧠 Agent Network":
    st.title("Agent Network & Architecture")
    st.caption("One Orchestrator, five specialist agents-as-tools, six read-only Snowflake lookup workflows, five different LLM providers — chosen deliberately to avoid any single free-tier quota cap.")

    fig = go.Figure()
    node_x = {"Orchestrator": 0, "Inventory Agent": -2, "Procurement Agent": -1.1, "Production Agent": 1.1, "Customer Impact Agent": 2, "Logistics Agent": 0}
    node_y = {"Orchestrator": 1, "Inventory Agent": 0, "Procurement Agent": 0, "Production Agent": 0, "Customer Impact Agent": 0, "Logistics Agent": -1}
    for name in list(node_x.keys())[1:]:
        if name != "Logistics Agent":
            fig.add_trace(go.Scatter(x=[node_x["Orchestrator"], node_x[name]], y=[node_y["Orchestrator"], node_y[name]],
                                      mode="lines", line=dict(color="rgba(130,150,200,0.5)", width=2), showlegend=False, hoverinfo="skip"))
        else:
            fig.add_trace(go.Scatter(x=[node_x["Orchestrator"], node_x[name]], y=[node_y["Orchestrator"], node_y[name]],
                                      mode="lines", line=dict(color="rgba(130,150,200,0.5)", width=2), showlegend=False, hoverinfo="skip"))
    colors = {"Orchestrator": "#6366f1", "Inventory Agent": "#22c55e", "Procurement Agent": "#f59e0b",
              "Production Agent": "#06b6d4", "Customer Impact Agent": "#ec4899", "Logistics Agent": "#eab308"}
    for name, x in node_x.items():
        fig.add_trace(go.Scatter(x=[x], y=[node_y[name]], mode="markers+text", text=[name], textposition="bottom center",
                                  marker=dict(size=38, color=colors[name], line=dict(width=2, color="white")),
                                  showlegend=False, hovertext=name, hoverinfo="text"))
    fig.update_layout(height=420, margin=dict(t=10, b=10, l=10, r=10),
                       xaxis=dict(visible=False), yaxis=dict(visible=False),
                       plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Specialist roster")
    cols = st.columns(3)
    for i, agent in enumerate(AGENTS):
        with cols[i % 3]:
            st.markdown(f"""<div class="agent-card">
                <h4 style="margin-bottom:2px">{agent['name']}</h4>
                <span class="pill pill-done">{agent['model']}</span>
                <p style="font-size:0.88rem; margin-top:8px; opacity:0.9">{agent['role']}</p>
                <p style="font-size:0.78rem; opacity:0.65">🔧 {', '.join(agent['tools'])}</p>
            </div>""", unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("Human-in-the-loop approval flow")
    st.markdown("""
1. Orchestrator ends every plan with a **PROPOSED ACTIONS FOR APPROVAL** section, each line risk-tagged `[RISK: Low/Medium/High]`.
2. An n8n **Wait** node renders an **Approve Recovery Plan** form (Decision: Approve/Reject + Notes).
3. **If Approve** → `Action Executed (Simulated)` → logged to Snowflake `action_log` with `log_id = EXEC-<execution id>`.
4. **If Reject** → `Plan Rejected` → logged with `log_id = EXEC-<execution id>-R<round>` → `Prepare Re-plan` feeds the rejected plan + approver notes back into the Orchestrator for a revised plan.
    """)
    st.info("Risk definitions — **Low**: report/info only. **Medium**: reallocating inventory or rescheduling production. **High**: placing a PO, selecting a new supplier, or booking/expediting a shipment.")

    with st.expander("🔍 View exact system prompts (from the exported n8n JSON)"):
        tab_names = [a["name"] for a in AGENTS]
        tabs = st.tabs(tab_names)
        prompts = {
            "Orchestrator": "Decide which specialized agents to delegate to, call them with clear questions, assemble a six-part structured recovery plan, and end with a risk-tagged PROPOSED ACTIONS FOR APPROVAL section. Fixed 'today' = 2026-09-30; treats any non-final order with a past date as immediately overdue rather than confusing data.",
            "Inventory Agent": "Report on-hand, safety stock, reserved, and available-to-promise per warehouse, plus totals — precise, never estimated.",
            "Procurement Agent": "Requires an exact component_id (CMP-###) before calling any tool. Reports PO/shipment delay status, then ranks approved alternative suppliers by capacity, cost premium %, and lead time.",
            "Production Agent": "Looks up every non-completed production order needing the component via the BOM, reports planned quantities and schedules, and recomputes the total required quantity fresh each run.",
            "Customer Impact Agent": "Requires an exact component_id before calling any tool. Ranks affected, non-fulfilled customer orders by contractual SLA priority, flagging top-priority customers to protect.",
            "Logistics Agent": "Tool returns only transport_option_id, mode, lane, cost, eta_days, capacity_units — nothing about containers, ports or customs. Explicitly refuses to invent data outside that scope, and recommends the best cost/speed option that actually satisfies required capacity.",
        }
        for t, name in zip(tabs, tab_names):
            with t:
                st.write(prompts[name])

# =======================================================================
# PAGE: Data Explorer
# =======================================================================
elif page == "📊 Data Explorer":
    st.title("Data Explorer")
    st.caption("Direct view into the 12 source tables the agents' Snowflake tools query — `SUPPLY_CHAIN_DISRUPTION.CORE` schema.")

    table_name = st.selectbox("Choose a table", list(tables.keys()), format_func=lambda x: x.replace("_", " ").title())
    df = tables[table_name]

    c1, c2, c3 = st.columns(3)
    c1.metric("Rows", f"{df.shape[0]:,}")
    c2.metric("Columns", df.shape[1])
    c3.metric("Table", table_name)

    search = st.text_input("🔎 Filter rows (matches any column, case-insensitive)")
    view = df
    if search:
        mask = df.apply(lambda row: row.astype(str).str.contains(search, case=False, na=False).any(), axis=1)
        view = df[mask]

    st.dataframe(view, use_container_width=True, height=460, hide_index=True)
    st.download_button("⬇️ Download filtered CSV", view.to_csv(index=False), file_name=f"{table_name}_filtered.csv")

    if table_name == "inventory":
        st.markdown("### Available-to-Promise by component")
        inv = df.copy()
        inv["atp"] = inv["on_hand_qty"] - inv["safety_stock_qty"] - inv["reserved_qty"]
        agg = inv.groupby("component_id")["atp"].sum().reset_index().sort_values("atp").head(20)
        fig = px.bar(agg, x="component_id", y="atp", color="atp", color_continuous_scale="RdYlGn",
                     title="20 lowest Available-to-Promise components")
        st.plotly_chart(fig, use_container_width=True)
    elif table_name == "suppliers":
        st.markdown("### Supplier reliability")
        fig = px.histogram(df, x="reliability_score", nbins=20, title="Reliability score distribution")
        st.plotly_chart(fig, use_container_width=True)

# =======================================================================
# PAGE: Disruption Console
# =======================================================================
elif page == "🚨 Disruption Console":
    st.title("Disruption Console")
    st.caption("Describe a disruption and get a structured, multi-agent recovery plan. Uses your live n8n webhook if configured in the sidebar, otherwise runs the offline simulator (same Snowflake logic, no LLM call).")

    examples = {
        "Suntech PCB delay (8 days, 500 units)": "Suntech delayed PO-00301 (500 units of CMP-007) by 8 days.",
        "Custom component_id lookup": "",
    }
    choice = st.selectbox("Example disruptions", list(examples.keys()))
    default_text = examples[choice]
    disruption_text = st.text_area("Disruption description", value=default_text, height=90,
                                    placeholder="e.g. Meridian Electronics delayed PO-00412 (300 units of CMP-014) by 6 days.")
    component_id = st.text_input("Component ID to analyze (required for the offline simulator)",
                                  value="CMP-007" if "Suntech" in choice else "")

    run = st.button("🚀 Run recovery analysis", type="primary", use_container_width=True)

    if run:
        webhook = st.session_state.get("webhook_url", "").strip()
        if webhook:
            with st.spinner("Calling your live n8n Orchestrator..."):
                try:
                    resp = requests.post(webhook, json={"chatInput": disruption_text}, timeout=120)
                    resp.raise_for_status()
                    data = resp.json()
                    output = data.get("output") or data.get("text") or json.dumps(data, indent=2)
                    st.success("Live response received.")
                    st.markdown(output)
                    st.session_state.last_plan = {"mode": "live", "output": output, "disruption_summary": disruption_text}
                except Exception as e:
                    st.error(f"Could not reach the live webhook: {e}")
        elif not component_id:
            st.warning("Enter a component_id (e.g. CMP-007) to run the offline simulator, or configure a live webhook in the sidebar.")
        else:
            with st.spinner("Delegating to Inventory, Procurement, Production, Customer Impact & Logistics agents..."):
                time.sleep(0.6)
                plan = build_recovery_plan(tables, component_id, disruption_text)
                st.session_state.last_plan = {"mode": "offline", **plan}
                st.session_state.plan_round = 0

    plan = st.session_state.last_plan
    if plan and plan.get("mode") == "offline":
        st.markdown("---")
        st.success(f"Recovery plan assembled for **{plan['component_id']}**")

        t1, t2, t3, t4, t5, t6 = st.tabs([
            "1️⃣ Summary", "2️⃣ Inventory Coverage", "3️⃣ Sourcing Plan",
            "4️⃣ Customer Risk", "5️⃣ Transport", "6️⃣ Recommendation",
        ])
        with t1:
            st.write(f"**Disruption:** {plan['disruption_summary']}")
            st.write(f"**Component affected:** `{plan['component_id']}`")
            st.write(f"**Total production requirement:** {plan['total_required']:,} units")
            st.write(f"**Total available-to-promise:** {plan['total_atp']:,} units")
            st.write(f"**Shortfall:** {plan['shortfall']:,} units" if plan["shortfall"] > 0 else "**No shortfall** — inventory fully covers production demand.")

        with t2:
            if plan["inventory"].empty:
                st.warning("No inventory rows found for this component_id.")
            else:
                st.dataframe(plan["inventory"], use_container_width=True, hide_index=True)
                fig = px.bar(plan["inventory"], x="warehouse_location", y="available_to_promise",
                             color="available_to_promise", color_continuous_scale="RdYlGn", title="ATP by warehouse")
                st.plotly_chart(fig, use_container_width=True)

        with t3:
            st.markdown("**Affected purchase order / shipment status**")
            if plan["shipments"].empty:
                st.caption("No shipment records for this component_id.")
            else:
                st.dataframe(plan["shipments"], use_container_width=True, hide_index=True)
            st.markdown("**Approved alternative suppliers (ranked by lead time, then cost)**")
            if plan["procurement"].empty:
                st.caption("No alternative suppliers on file for this component_id.")
            else:
                st.dataframe(plan["procurement"].sort_values(["lead_time_days", "cost_premium_pct"]),
                             use_container_width=True, hide_index=True)
                if plan["best_alt_supplier"] is not None:
                    b = plan["best_alt_supplier"]
                    st.info(f"✅ Recommended: **{b['supplier_name']}** — {b['capacity_units_per_month']:.0f} units/month capacity, "
                            f"{b['cost_premium_pct']:.1f}% cost premium, {b['lead_time_days']:.0f}-day lead time.")

        with t4:
            if plan["customer_impact"].empty:
                st.caption("No open/at-risk customer orders depend on this component.")
            else:
                st.dataframe(
                    plan["customer_impact"][["customer_name", "sla_tier", "contractual_priority_rank",
                                              "penalty_per_day_late", "product_name", "qty_ordered",
                                              "requested_delivery_date", "status"]],
                    use_container_width=True, hide_index=True,
                )
                top = plan["at_risk_customers"]
                if not top.empty:
                    st.warning("🔺 Highest-priority customers to protect first: " +
                               ", ".join(top["customer_name"].dropna().unique()[:5]))

        with t5:
            st.dataframe(plan["transport_options"], use_container_width=True, hide_index=True)
            if plan["best_transport"] is not None:
                b = plan["best_transport"]
                st.info(f"✅ Recommended: **{b['mode']} — {b['lane']}** · ${b['cost']:,.0f} · {b['eta_days']:.0f}-day ETA · "
                        f"{b['capacity_units']:,.0f} unit capacity")

        with t6:
            risk_rows = []
            risk_rows.append(("Low", f"Report consolidated impact of the disruption to {plan['component_id']} across inventory, production, and customer orders."))
            if plan["shortfall"] > 0:
                if plan["best_alt_supplier"] is not None:
                    risk_rows.append(("High", f"Place a purchase order with {plan['best_alt_supplier']['supplier_name']} to cover the {plan['shortfall']:,}-unit shortfall."))
                risk_rows.append(("Medium", "Reallocate available-to-promise inventory to protect highest-priority customer commitments first."))
            if plan["best_transport"] is not None:
                risk_rows.append(("High", f"Book {plan['best_transport']['mode']} transport on {plan['best_transport']['lane']} to expedite delivery."))
            plan["risk_rows"] = risk_rows

            st.markdown("#### PROPOSED ACTIONS FOR APPROVAL")
            for level, desc in risk_rows:
                st.markdown(f"<span class='{risk_class(level)}'>[RISK: {level}]</span> {desc}", unsafe_allow_html=True)

            st.markdown("---")
            st.caption("Go to **✅ Approval & Audit Trail** to approve or reject this plan — exactly mirroring the n8n Wait-form step.")

    elif plan and plan.get("mode") == "live":
        pass
    else:
        st.info("Run an analysis above to see the six-part recovery plan.")

# =======================================================================
# PAGE: Approval & Audit Trail
# =======================================================================
elif page == "✅ Approval & Audit Trail":
    st.title("Approval & Audit Trail")
    st.caption("Mirrors the n8n `Wait` node's Approve Recovery Plan form, and the `action_log` Snowflake audit table.")

    plan = st.session_state.last_plan
    if not plan or plan.get("mode") != "offline":
        st.info("No pending offline plan. Go to 🚨 Disruption Console and run an analysis first.")
    else:
        st.subheader(f"Pending decision — component `{plan['component_id']}`")
        risk_rows = plan.get("risk_rows", [])
        for level, desc in risk_rows:
            st.markdown(f"<span class='{risk_class(level)}'>[RISK: {level}]</span> {desc}", unsafe_allow_html=True)

        with st.form("approval_form"):
            decision = st.selectbox("Decision", ["Approve", "Reject"])
            notes = st.text_area("Notes", placeholder="e.g. Approved — prioritize air freight for Platinum-tier customers.")
            submitted = st.form_submit_button("Submit decision", type="primary")

        if submitted:
            exec_id = f"{int(time.time())}"
            if decision == "Approve":
                log_id = f"EXEC-{exec_id}"
            else:
                st.session_state.plan_round += 1
                log_id = f"EXEC-{exec_id}-R{st.session_state.plan_round}"

            new_row = {
                "log_id": log_id,
                "disruption_summary": plan["disruption_summary"][:2000],
                "component_id": plan["component_id"],
                "decision": "Approved" if decision == "Approve" else "Rejected",
                "approved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "notes": notes[:2000],
                "risk_summary": " | ".join(f"[{lvl}] {d}" for lvl, d in risk_rows)[:2000],
            }
            st.session_state.action_log = pd.concat(
                [st.session_state.action_log, pd.DataFrame([new_row])], ignore_index=True
            )
            if decision == "Approve":
                st.success(f"✅ Logged as **{log_id}** — status: Executed (Simulated). No real ERP/PO/shipment system was modified.")
                st.session_state.last_plan = None
            else:
                st.warning(f"🔁 Logged as **{log_id}** — status: Rejected, no action taken. In the live system this would trigger `Prepare Re-plan`, feeding your notes back to the Orchestrator for a revised plan.")

    st.markdown("---")
    st.subheader("Audit log (`action_log`)")
    if st.session_state.action_log.empty:
        st.caption("No decisions logged yet this session.")
    else:
        st.dataframe(st.session_state.action_log, use_container_width=True, hide_index=True)
        st.download_button("⬇️ Export audit log", st.session_state.action_log.to_csv(index=False), "action_log.csv")

# =======================================================================
# PAGE: Sample Run
# =======================================================================
elif page == "📁 Sample Run (Execution #326)":
    st.title("Sample Tested Result — Execution #326")
    st.caption("A real, previously-recorded end-to-end run of the live n8n workflow, included as a reference example.")

    st.markdown("**Disruption input:** *Suntech delayed PO-00301 (500 units of CMP-007) by 8 days.*")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total ATP", "906 units")
    c2.metric("Production need", "720 units / 60 days")
    c3.metric("Orders affected", "34 orders / 1,235 units")
    c4.metric("Shortfall", "0 units (fully covered)")

    st.markdown("### Plan v1 → Rejected → Plan v2 → Approved")
    st.markdown("""
| Round | Recommendation | Decision | Notes |
|---|---|---|---|
| v1 | Expedited **air freight**, TRN option, high cost | ❌ Rejected | Approver asked for a lower-cost option given no shortfall |
| v2 | **TRN-010 — Regional Road**, 1-day ETA, \\$45,000, 900-unit capacity | ✅ Approved | Matched urgency without the air-freight premium |
    """)
    st.info("Logged as `EXEC-326-R1` (rejection) then `EXEC-326` (approval) in Snowflake `action_log` — 2 rows total, consistent with the project's reject-once-then-approve row-count rule.")

    with st.expander("Known gaps surfaced by this run"):
        st.markdown("""
- No in-chat approval link resurfaces automatically after a re-plan (this run needed a manual nudge).
- Rejected plans are truncated to 8,000 characters in the log — this run's revised plan (~16,000 chars) was only partially stored.
- No cap yet on re-plan iterations; no automated post-approval verification loop (execution is simulated only, by design).
        """)

# =======================================================================
# PAGE: About
# =======================================================================
elif page == "ℹ️ About & Deployment":
    st.title("About this project")
    st.markdown("""
**Agentic AI for Supply Chain Disruption Response & Recovery** is a hierarchical multi-agent system built for a mid-size
industrial equipment manufacturer scenario (~20 suppliers, ~50 customers, 3 distribution centers). A single plain-English
disruption report is triaged by an Orchestrator across five specialist agents, each backed by its own LLM provider and its
own read-only Snowflake lookup tool, before a human approves or rejects the assembled recovery plan.
    """)

    st.subheader("Technology stack")
    st.table(pd.DataFrame({
        "Layer": ["Workflow orchestration", "Data warehouse", "Orchestrator LLM", "Specialist LLMs", "Human approval", "This dashboard"],
        "Technology": ["n8n (self-hosted)", "Snowflake", "OpenAI GPT-5-mini", "Claude Haiku 4.5 · Groq gpt-oss-120b · Gemini 3.1 Flash Lite ×2 · Qwen 3.7 Flash", "n8n Wait node (form)", "Streamlit"],
    }))

    st.subheader("Deployment status")
    st.markdown("""
<span class="pill pill-done">Done</span> Project README & User Guide &nbsp;
<span class="pill pill-done">Done</span> Streamlit dashboard (this app) &nbsp;
<span class="pill pill-wip">In progress</span> Migrating n8n off its original host to a stable free/low-cost deployment &nbsp;
<span class="pill pill-planned">Planned</span> Production-grade hosting for the live webhook
    """, unsafe_allow_html=True)

    st.subheader("Guardrails")
    st.markdown("""
- Every specialist is **read-only** against Snowflake — no agent can write, update, or delete data.
- **Human-in-the-loop**: nothing executes without an explicit Approve decision.
- Every proposed action carries a **risk tag** (Low/Medium/High) with explicit definitions.
- Agents are instructed to **never invent** figures, suppliers, ETAs, or statuses their tools didn't return.
- Execution is **simulated only** — no real ERP, PO, or shipment system is ever modified.
- Full **audit trail**: every decision (approved or rejected), with notes and the full plan text, is logged to Snowflake.
    """)

    st.subheader("Known limitations")
    st.markdown("""
- No automated verification loop after approval (by design — execution is simulated).
- No cap yet on reject → re-plan iterations.
- Rejected plans are truncated to 8,000 characters in the audit log.
- In-chat approval links don't automatically resurface after a re-plan round.
    """)

    st.caption("Author: Harsh Kumar Sharma · Internship Project #3")
