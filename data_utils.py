"""
Data loading and engine-lookup helpers for the Agentic AI Supply Chain
Disruption Response & Recovery dashboard.

These functions mirror, in pandas, exactly what the six n8n "Lookup" tool
sub-workflows query in Snowflake, so the dashboard's offline "Recovery
Plan Simulator" produces numbers consistent with what the real agents
would return.
"""
import os
import pandas as pd
import streamlit as st

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

TODAY = pd.Timestamp("2026-09-30")  # matches the fixed "today" baked into every agent's system prompt


@st.cache_data
def load_all():
    tables = {}
    for name in [
        "suppliers", "products", "bom", "purchase_orders", "supplier_shipments",
        "inventory", "production_orders", "customer_sla", "customer_orders",
        "alternative_suppliers", "transport_options", "disruption_events",
    ]:
        path = os.path.join(DATA_DIR, f"{name}.csv")
        df = pd.read_csv(path)
        tables[name] = df
    return tables


def to_date(series):
    return pd.to_datetime(series, errors="coerce")


# ----------------------------------------------------------------------
# Per-tool lookups — pandas equivalents of the 6 Snowflake "Tool -" workflows
# ----------------------------------------------------------------------

def inventory_lookup(tables, component_id):
    inv = tables["inventory"]
    df = inv[inv["component_id"] == component_id].copy()
    if df.empty:
        return df
    df["available_to_promise"] = df["on_hand_qty"] - df["safety_stock_qty"] - df["reserved_qty"]
    return df


def procurement_lookup(tables, component_id):
    alt = tables["alternative_suppliers"]
    sup = tables["suppliers"]
    df = alt[alt["component_id"] == component_id].copy()
    if df.empty:
        return df
    df = df.merge(
        sup, on="supplier_id", how="left",
        suffixes=("_alt_approval", "_supplier_approval"),
    )
    # alternative_suppliers.approved_status (this component-supplier pairing's
    # own approval) is the one the Procurement tool actually reports on
    df = df.rename(columns={"approved_status_alt_approval": "approved_status"})
    if "approved_status_supplier_approval" in df.columns:
        df = df.rename(columns={"approved_status_supplier_approval": "supplier_overall_approved_status"})
    return df


def supplier_shipment_lookup(tables, component_id):
    ship = tables["supplier_shipments"]
    sup = tables["suppliers"]
    po = tables["purchase_orders"]
    df = ship[ship["component_id"] == component_id].copy()
    if df.empty:
        return df
    df = df.merge(sup[["supplier_id", "supplier_name"]], on="supplier_id", how="left")
    df = df.merge(po[["po_id", "status"]], on="po_id", how="left", suffixes=("", "_po"))
    return df


def production_lookup(tables, component_id):
    bom = tables["bom"]
    po = tables["production_orders"]
    prod = tables["products"]
    affected_products = bom[bom["component_id"] == component_id]
    if affected_products.empty:
        return pd.DataFrame()
    merged = po.merge(affected_products, left_on="product_id", right_on="parent_product_id", how="inner")
    merged = merged.merge(prod[["product_id", "product_name"]], on="product_id", how="left")
    merged = merged[merged["status"] != "Completed"].copy()
    merged["component_qty_required"] = merged["qty_planned"] * merged["qty_required_per_unit"]
    return merged


def customer_impact_lookup(tables, component_id):
    """Customer orders affected by a shortage of component_id, via BOM -> production -> customer orders path
    is not directly modeled in the raw CSVs (customer_orders references product_id directly), so this mirrors
    the tool's real behavior: find finished products using this component, then find open customer orders for
    those products, excluding Fulfilled."""
    bom = tables["bom"]
    co = tables["customer_orders"]
    sla = tables["customer_sla"]
    prod = tables["products"]
    affected_products = bom[bom["component_id"] == component_id]["parent_product_id"].unique()
    if len(affected_products) == 0:
        return pd.DataFrame()
    df = co[co["product_id"].isin(affected_products) & (co["status"] != "Fulfilled")].copy()
    if df.empty:
        return df
    df = df.merge(sla, on="customer_id", how="left")
    df = df.merge(prod[["product_id", "product_name"]], on="product_id", how="left")
    df = df.sort_values("contractual_priority_rank", na_position="last")
    return df


def logistics_lookup(tables):
    return tables["transport_options"].copy()


# ----------------------------------------------------------------------
# High-level recovery-plan simulator (offline, deterministic, no LLM)
# ----------------------------------------------------------------------

def build_recovery_plan(tables, component_id, disruption_text=""):
    """Produce a structured six-part recovery plan using real data, mirroring
    the Orchestrator's own prompt format — WITHOUT calling any LLM. This lets
    the dashboard demo the full reasoning chain offline / for free."""
    inv = inventory_lookup(tables, component_id)
    proc = procurement_lookup(tables, component_id)
    ship = supplier_shipment_lookup(tables, component_id)
    prod = production_lookup(tables, component_id)
    cust = customer_impact_lookup(tables, component_id)
    log = logistics_lookup(tables)

    total_atp = int(inv["available_to_promise"].sum()) if not inv.empty else 0
    total_required = int(prod["component_qty_required"].sum()) if not prod.empty else 0
    shortfall = max(total_required - total_atp, 0)

    best_alt = None
    if not proc.empty:
        proc_sorted = proc[proc["approved_status"].astype(str).str.lower() == "yes"].sort_values(
            ["lead_time_days", "cost_premium_pct"]
        )
        if not proc_sorted.empty:
            best_alt = proc_sorted.iloc[0]

    best_transport = None
    if not log.empty and shortfall > 0:
        feasible = log[log["capacity_units"] >= shortfall].sort_values(["eta_days", "cost"])
        best_transport = feasible.iloc[0] if not feasible.empty else log.sort_values("cost").iloc[0]
    elif not log.empty:
        best_transport = log.sort_values("cost").iloc[0]

    at_risk_customers = cust.head(5) if not cust.empty else pd.DataFrame()

    plan = {
        "component_id": component_id,
        "disruption_summary": disruption_text or f"Disruption affecting component {component_id}.",
        "inventory": inv,
        "total_atp": total_atp,
        "procurement": proc,
        "shipments": ship,
        "best_alt_supplier": best_alt,
        "production": prod,
        "total_required": total_required,
        "shortfall": shortfall,
        "customer_impact": cust,
        "at_risk_customers": at_risk_customers,
        "transport_options": log,
        "best_transport": best_transport,
    }
    return plan


def risk_tag_for_action(kind):
    mapping = {
        "report": "Low",
        "reallocate": "Medium",
        "reschedule": "Medium",
        "purchase_order": "High",
        "new_supplier": "High",
        "expedite_shipment": "High",
    }
    return mapping.get(kind, "Medium")
