import streamlit as st
import pandas as pd

# --- Core simulation logic ---

def simulate_contract(
    list_price: float,
    discount: float,
    monthly_oled_delivery_plan,
    initial_component_inventory: int,
    monthly_production_plan,
    payment_terms_days: int,
    doa_rate: float = 0.0175,
    doa_replacement_mode: str = "Next month",
    customization: bool = True,
    technical_support_weeks: float = 3.0,
    ecolowrap: bool = True,
    cost_of_capital: float = 0.10,
    # extra economics to mirror the class simulator
    transport_cost_per_unit_from_cda: float = 13.1,
    transport_cost_per_unit_to_cda: float = 0.0,
    insurance_cost_per_unit: float = 2.67,
    field_failure_rate: float = 0.0185,
    final_product_price: float = 678.0,
    monthly_demand_units: int = 6029,
    prod_cost_per_unit_excl_oled: float = 257.4,
    initial_final_inventory: int = 500,
    neginfo_cost: float = 0.0,
):
    """Simulate 12-month OLED supply, production and P&L under a given deal.

    monthly_oled_delivery_plan and monthly_production_plan are lists of 12
    integers (one per month).
    """

    final_price_component = list_price * (1 - discount / 100.0)

    records = []
    comp_inv = initial_component_inventory
    final_inv = initial_final_inventory
    prev_month_doa = 0

    total_oleds_purchased = 0
    total_units_produced = 0
    total_units_sold = 0

    inventory_comp_snapshots = []
    inventory_final_snapshots = []

    total_transport_from_cda_cost = 0.0
    total_transport_to_cda_cost = 0.0
    total_insurance_cost = 0.0

    total_sales_revenue = 0.0
    total_prod_cost_excl_oled = 0.0

    for month in range(1, 13):
        # --- COMPONENT SIDE (OLEDs) ---
        comp_start_inv = comp_inv

        received_from_cda = monthly_oled_delivery_plan[month - 1]
        total_oleds_purchased += received_from_cda

        doa_units = int(received_from_cda * doa_rate)

        # replacements arrive this month for last month's DOA
        if doa_replacement_mode in {"Next month", "Next delivery"}:
            replacements_arrive = prev_month_doa
        else:
            replacements_arrive = 0

        usable_now = received_from_cda - doa_units + replacements_arrive
        prev_month_doa = doa_units

        # --- FINAL PRODUCT PRODUCTION ---
        production = monthly_production_plan[month - 1]
        total_units_produced += production

        comp_end_inv = comp_start_inv + usable_now - production
        comp_inv = comp_end_inv

        # --- FINAL PRODUCT SIDE ---
        final_start_inv = final_inv
        available_for_sale = final_start_inv + production
        demand = monthly_demand_units
        sales_units = min(available_for_sale, demand)
        total_units_sold += sales_units

        final_end_inv = available_for_sale - sales_units
        final_inv = final_end_inv

        # --- QUALITY PROBLEMS (field failures at end consumer) ---
        field_failures = int(sales_units * field_failure_rate)

        # --- TRANSPORT & INSURANCE ---
        volume_from_cda_due_doa = replacements_arrive
        total_volume_from_cda = received_from_cda + volume_from_cda_due_doa
        transport_from_cda_cost = total_volume_from_cda * transport_cost_per_unit_from_cda
        total_transport_from_cda_cost += transport_from_cda_cost

        volume_to_cda = field_failures
        transport_to_cda_cost = volume_to_cda * transport_cost_per_unit_to_cda
        total_transport_to_cda_cost += transport_to_cda_cost

        total_volume_for_insurance = total_volume_from_cda + volume_to_cda
        insurance_cost = total_volume_for_insurance * insurance_cost_per_unit
        total_insurance_cost += insurance_cost

        # --- ECONOMICS ---
        sales_revenue = sales_units * final_product_price
        total_sales_revenue += sales_revenue

        prod_cost_excl_oled = production * prod_cost_per_unit_excl_oled
        total_prod_cost_excl_oled += prod_cost_excl_oled

        inventory_comp_snapshots.append(comp_start_inv)
        inventory_final_snapshots.append(final_start_inv)

        records.append(
            {
                "Month": month,
                # price / volume
                "OLEDs bought from CDA": received_from_cda,
                # quality
                "Field failures at end consumer": field_failures,
                "DOA units": doa_units,
                "DOA replacements received": replacements_arrive,
                # inventory
                "Component inventory start": comp_start_inv,
                "Component inventory end": comp_end_inv,
                "Final product inventory start": final_start_inv,
                "Final product inventory end": final_end_inv,
                # transport & insurance
                "Volume from CDA due DOA": volume_from_cda_due_doa,
                "Total volume from CDA": total_volume_from_cda,
                "Transport cost from CDA (€)": transport_from_cda_cost,
                "Volume to CDA (returns)": volume_to_cda,
                "Transport cost to CDA (€)": transport_to_cda_cost,
                "Insurance cost (€)": insurance_cost,
                # final product
                "Demand (units)": demand,
                "Sales (units)": sales_units,
                "Sales revenue (€)": sales_revenue,
                "Production (units)": production,
            }
        )

    inventory_comp_snapshots.append(comp_inv)
    inventory_final_snapshots.append(final_inv)

    avg_comp_inv = sum(inventory_comp_snapshots) / len(inventory_comp_snapshots)
    avg_final_inv = sum(inventory_final_snapshots) / len(inventory_final_snapshots)

    component_purchase_cost = total_oleds_purchased * final_price_component
    inventory_comp_capital_cost = avg_comp_inv * final_price_component * cost_of_capital
    inventory_final_capital_cost = avg_final_inv * prod_cost_per_unit_excl_oled * cost_of_capital

    ecolowrap_subsidy = 200_000 if ecolowrap else 0

    total_inventory_cost = inventory_comp_capital_cost + inventory_final_capital_cost

    total_costs = (
        component_purchase_cost
        + total_prod_cost_excl_oled
        + total_transport_from_cda_cost
        + total_transport_to_cda_cost
        + total_insurance_cost
        + total_inventory_cost
        + neginfo_cost
        - ecolowrap_subsidy
    )

    negotiation_profit = total_sales_revenue - total_costs

    kpis = {
        "Component final price (€/unit)": round(final_price_component, 2),
        "Total OLEDs purchased": int(total_oleds_purchased),
        "Total units produced": int(total_units_produced),
        "Total units sold": int(total_units_sold),
        "Average component inventory (units)": round(avg_comp_inv, 1),
        "Average final inventory (units)": round(avg_final_inv, 1),
        "Component purchase cost (€/year)": round(component_purchase_cost, 0),
        "Production cost excl. OLEDs (€/year)": round(total_prod_cost_excl_oled, 0),
        "Transport from CDA (€/year)": round(total_transport_from_cda_cost, 0),
        "Transport to CDA (€/year)": round(total_transport_to_cda_cost, 0),
        "Insurance cost (€/year)": round(total_insurance_cost, 0),
        "Inventory capital cost (€/year)": round(total_inventory_cost, 0),
        "Ecolowrap subsidy (€/year)": ecolowrap_subsidy,
        "NEGINFO cost (€/year)": neginfo_cost,
        "Total sales revenue (€/year)": round(total_sales_revenue, 0),
        "Profit from negotiation (€/year)": round(negotiation_profit, 0),
        "Payment terms (days)": payment_terms_days,
        "Customization included": customization,
        "Technical support (weeks)": technical_support_weeks,
        "Ecolowrap": ecolowrap,
    }

    df = pd.DataFrame(records)
    return df, kpis


# --- Streamlit UI with two-scenario comparison ---

st.title("Negotiation Deal Simulator – Scenario Comparison")
st.markdown(
    "Compare two negotiation outcomes (Scenario A vs Scenario B) under the same "
    "game rules: price, volume, quality, logistics and P&L over 12 months."
)

# Global / environment parameters (same for both scenarios)
st.sidebar.header("Global parameters (same for both scenarios)")
doa_rate_global = st.sidebar.number_input("DOA rate at reception (%)", value=1.75, step=0.05) / 100.0
field_failure_rate_global = st.sidebar.number_input(
    "Field failure rate at consumer (%)", value=1.85, step=0.05
) / 100.0
transport_cost_per_unit_from_cda_global = st.sidebar.number_input(
    "Transport cost from CDA (€/unit)", value=13.1, step=0.1
)
transport_cost_per_unit_to_cda_global = st.sidebar.number_input(
    "Transport cost to CDA (€/unit)", value=0.0, step=0.1
)
insurance_cost_per_unit_global = st.sidebar.number_input(
    "Insurance cost (€/unit)", value=2.67, step=0.01
)
final_product_price_global = st.sidebar.number_input(
    "Final product selling price (€/unit)", value=678.0, step=1.0
)
monthly_demand_units_global = st.sidebar.number_input(
    "Monthly demand (units)", value=6029, step=50
)
prod_cost_per_unit_excl_oled_global = st.sidebar.number_input(
    "Production cost per unit excl. OLED (€/unit)", value=257.4, step=1.0
)
cost_of_capital_global = st.sidebar.number_input(
    "Cost of capital (yearly, %)", value=10.0, step=0.5, min_value=0.0, max_value=100.0
) / 100.0
neginfo_cost_global = st.sidebar.number_input(
    "NEGINFO total cost (€/year)", value=0.0, step=1000.0
)

# Default plan helpers
def default_prod_plan():
    return [6000] + [5900] * 11


def default_supply_plan():
    return [6000] * 12


# Scenario tabs
tabA, tabB, tabCompare = st.tabs(["Scenario A", "Scenario B", "Comparison"])

with tabA:
    st.subheader("Scenario A – Contract Terms")
    col1, col2 = st.columns(2)
    with col1:
        list_price_A = st.number_input("List price A (€/unit)", value=178.0, step=1.0, key="lp_A")
        discount_A = st.number_input("Discount A (%)", value=0.0, step=0.1, key="disc_A")
        payment_terms_days_A = st.number_input("Payment terms A (days)", value=60, step=5, key="pt_A")
    with col2:
        initial_component_inventory_A = st.number_input(
            "Initial OLED inventory A (units)", value=500, step=50, key="inv_comp_A"
        )
        initial_final_inventory_A = st.number_input(
            "Initial final product inventory A (units)", value=500, step=50, key="inv_final_A"
        )
        doa_replacement_mode_A = st.selectbox(
            "DOA replacement timing A",
            ["Next month", "Next delivery"],
            key="doa_rep_A",
        )

    st.markdown("**Monthly OLED supply plan A (from CDA)**")
    monthly_supply_plan_A = []
    cols = st.columns(4)
    for i in range(12):
        with cols[i % 4]:
            monthly_supply_plan_A.append(
                st.number_input(
                    f"Sup A M{i + 1}",
                    value=default_supply_plan()[i],
                    step=50,
                    key=f"sup_A_{i}",
                )
            )

    st.markdown("**Monthly production plan A (final units)**")
    monthly_production_plan_A = []
    cols_prod_A = st.columns(4)
    for i in range(12):
        with cols_prod_A[i % 4]:
            monthly_production_plan_A.append(
                st.number_input(
                    f"Prod A M{i + 1}",
                    value=default_prod_plan()[i],
                    step=50,
                    key=f"prod_A_{i}",
                )
            )

    st.markdown("**Service & ESG A**")
    col1, col2 = st.columns(2)
    with col1:
        customization_A = st.checkbox("Customization included A", value=True, key="cust_A")
        ecolowrap_A = st.checkbox("Ecolowrap A", value=True, key="eco_A")
    with col2:
        technical_support_weeks_A = st.number_input(
            "Tech support A (engineer-weeks)", value=3.0, step=0.5, key="ts_A"
        )

with tabB:
    st.subheader("Scenario B – Contract Terms")
    col1, col2 = st.columns(2)
    with col1:
        list_price_B = st.number_input("List price B (€/unit)", value=178.0, step=1.0, key="lp_B")
        discount_B = st.number_input("Discount B (%)", value=0.0, step=0.1, key="disc_B")
        payment_terms_days_B = st.number_input("Payment terms B (days)", value=60, step=5, key="pt_B")
    with col2:
        initial_component_inventory_B = st.number_input(
            "Initial OLED inventory B (units)", value=500, step=50, key="inv_comp_B"
        )
        initial_final_inventory_B = st.number_input(
            "Initial final product inventory B (units)", value=500, step=50, key="inv_final_B"
        )
        doa_replacement_mode_B = st.selectbox(
            "DOA replacement timing B",
            ["Next month", "Next delivery"],
            key="doa_rep_B",
        )

    st.markdown("**Monthly OLED supply plan B (from CDA)**")
    monthly_supply_plan_B = []
    cols = st.columns(4)
    for i in range(12):
        with cols[i % 4]:
            monthly_supply_plan_B.append(
                st.number_input(
                    f"Sup B M{i + 1}",
                    value=default_supply_plan()[i],
                    step=50,
                    key=f"sup_B_{i}",
                )
            )

    st.markdown("**Monthly production plan B (final units)**")
    monthly_production_plan_B = []
    cols_prod_B = st.columns(4)
    for i in range(12):
        with cols_prod_B[i % 4]:
            monthly_production_plan_B.append(
                st.number_input(
                    f"Prod B M{i + 1}",
                    value=default_prod_plan()[i],
                    step=50,
                    key=f"prod_B_{i}",
                )
            )

    st.markdown("**Service & ESG B**")
    col1, col2 = st.columns(2)
    with col1:
        customization_B = st.checkbox("Customization included B", value=True, key="cust_B")
        ecolowrap_B = st.checkbox("Ecolowrap B", value=True, key="eco_B")
    with col2:
        technical_support_weeks_B = st.number_input(
            "Tech support B (engineer-weeks)", value=3.0, step=0.5, key="ts_B"
        )

run = st.button("Run simulation for both scenarios")

if run:
    df_A, kpis_A = simulate_contract(
        list_price=list_price_A,
        discount=discount_A,
        monthly_oled_delivery_plan=monthly_supply_plan_A,
        initial_component_inventory=initial_component_inventory_A,
        monthly_production_plan=monthly_production_plan_A,
        payment_terms_days=payment_terms_days_A,
        doa_rate=doa_rate_global,
        doa_replacement_mode=doa_replacement_mode_A,
        customization=customization_A,
        technical_support_weeks=technical_support_weeks_A,
        ecolowrap=ecolowrap_A,
        cost_of_capital=cost_of_capital_global,
        transport_cost_per_unit_from_cda=transport_cost_per_unit_from_cda_global,
        transport_cost_per_unit_to_cda=transport_cost_per_unit_to_cda_global,
        insurance_cost_per_unit=insurance_cost_per_unit_global,
        field_failure_rate=field_failure_rate_global,
        final_product_price=final_product_price_global,
        monthly_demand_units=monthly_demand_units_global,
        prod_cost_per_unit_excl_oled=prod_cost_per_unit_excl_oled_global,
        initial_final_inventory=initial_final_inventory_A,
        neginfo_cost=neginfo_cost_global,
    )

    df_B, kpis_B = simulate_contract(
        list_price=list_price_B,
        discount=discount_B,
        monthly_oled_delivery_plan=monthly_supply_plan_B,
        initial_component_inventory=initial_component_inventory_B,
        monthly_production_plan=monthly_production_plan_B,
        payment_terms_days=payment_terms_days_B,
        doa_rate=doa_rate_global,
        doa_replacement_mode=doa_replacement_mode_B,
        customization=customization_B,
        technical_support_weeks=technical_support_weeks_B,
        ecolowrap=ecolowrap_B,
        cost_of_capital=cost_of_capital_global,
        transport_cost_per_unit_from_cda=transport_cost_per_unit_from_cda_global,
        transport_cost_per_unit_to_cda=transport_cost_per_unit_to_cda_global,
        insurance_cost_per_unit=insurance_cost_per_unit_global,
        field_failure_rate=field_failure_rate_global,
        final_product_price=final_product_price_global,
        monthly_demand_units=monthly_demand_units_global,
        prod_cost_per_unit_excl_oled=prod_cost_per_unit_excl_oled_global,
        initial_final_inventory=initial_final_inventory_B,
        neginfo_cost=neginfo_cost_global,
    )

    # Show details inside each scenario tab
    with tabA:
        st.markdown("---")
        st.subheader("Scenario A – Monthly results")
        st.dataframe(df_A)
        st.subheader("Scenario A – Component inventory over time")
        st.line_chart(df_A.set_index("Month")["Component inventory end"])
        st.subheader("Scenario A – Key KPIs")
        st.json(kpis_A)

    with tabB:
        st.markdown("---")
        st.subheader("Scenario B – Monthly results")
        st.dataframe(df_B)
        st.subheader("Scenario B – Component inventory over time")
        st.line_chart(df_B.set_index("Month")["Component inventory end"])
        st.subheader("Scenario B – Key KPIs")
        st.json(kpis_B)

    # Comparison tab
    with tabCompare:
        st.subheader("KPI comparison – Scenario A vs Scenario B")
        compare_keys = [
            "Component final price (€/unit)",
            "Total OLEDs purchased",
            "Total units produced",
            "Total units sold",
            "Component purchase cost (€/year)",
            "Production cost excl. OLEDs (€/year)",
            "Transport from CDA (€/year)",
            "Insurance cost (€/year)",
            "Inventory capital cost (€/year)",
            "Ecolowrap subsidy (€/year)",
            "NEGINFO cost (€/year)",
            "Total sales revenue (€/year)",
            "Profit from negotiation (€/year)",
        ]

        rows = []
        for key in compare_keys:
            val_A = kpis_A.get(key, None)
            val_B = kpis_B.get(key, None)
            diff = None
            if isinstance(val_A, (int, float)) and isinstance(val_B, (int, float)):
                diff = val_B - val_A
            rows.append({"KPI": key, "Scenario A": val_A, "Scenario B": val_B, "B - A": diff})

        comp_df = pd.DataFrame(rows)
        st.dataframe(comp_df)

        st.markdown("---")
        st.subheader("Profit comparison")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(
                "Profit A (€/year)",
                f"{kpis_A['Profit from negotiation (€/year)']:,}".replace(",", " "),
            )
        with col2:
            st.metric(
                "Profit B (€/year)",
                f"{kpis_B['Profit from negotiation (€/year)']:,}".replace(",", " "),
            )
        with col3:
            delta_profit = kpis_B["Profit from negotiation (€/year)"] - kpis_A[
                "Profit from negotiation (€/year)"
            ]
            st.metric("B - A (€/year)", f"{delta_profit:,}".replace(",", " "))

st.markdown(
    """
---
### How to use this app
1. Set the *global game parameters* in the sidebar (DOA rate, demand, production cost, etc.).  \
2. In **Scenario A** and **Scenario B** tabs, enter contract terms, **monthly OLED supply plans** and production plans.  \
3. Click **Run simulation for both scenarios**.  \
4. Review each scenario in its tab, then open **Comparison** to see KPI and profit deltas.  \
5. Save this script as `negotiation_sim_app.py`, push it to GitHub, and run with:

```bash
streamlit run negotiation_sim_app.py
```
"""
)
