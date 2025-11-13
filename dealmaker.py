import streamlit as st
import pandas as pd

# --- Core simulation logic ---

def simulate_contract(
    list_price: float,
    discount: float,
    monthly_oled_delivery: int,
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

    This is an approximation of the classroom simulator using the same
    negotiable variables and core dynamics, not an exact replica of its
    internal formulas.
    """

    final_price_component = list_price * (1 - discount / 100.0)

    # time series containers
    records = []
    comp_inv = initial_component_inventory
    final_inv = initial_final_inventory
    pending_doa_replacements = 0
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

        received_from_cda = monthly_oled_delivery
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
        # From CDA: base delivery + replacements sent this month
        volume_from_cda_due_doa = replacements_arrive
        total_volume_from_cda = received_from_cda + volume_from_cda_due_doa
        transport_from_cda_cost = total_volume_from_cda * transport_cost_per_unit_from_cda
        total_transport_from_cda_cost += transport_from_cda_cost

        # To CDA: assume field failures are returned
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

    # include last end-of-year inventory in average
    inventory_comp_snapshots.append(comp_inv)
    inventory_final_snapshots.append(final_inv)

    avg_comp_inv = sum(inventory_comp_snapshots) / len(inventory_comp_snapshots)
    avg_final_inv = sum(inventory_final_snapshots) / len(inventory_final_snapshots)

    # Economic KPIs
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


# --- Streamlit UI ---

st.title("Negotiation Deal Simulator – IPB vs CDA")
st.markdown(
    "This app approximates the classroom simulator: set your negotiated terms "
    "and see volume, quality, logistics, P&L and inventory impact over 12 months."
)

st.sidebar.header("Price & Volume")
list_price = st.sidebar.number_input("List price per OLED (€/unit)", value=178.0, step=1.0)
discount = st.sidebar.number_input("Discount (%)", value=0.0, step=0.1, min_value=0.0, max_value=100.0)
monthly_oled_delivery = st.sidebar.number_input("Monthly OLED delivery from CDA (units)", value=6000, step=100)

st.sidebar.header("Inventories & Production")
initial_component_inventory = st.sidebar.number_input("Initial OLED inventory (units)", value=500, step=50)
initial_final_inventory = st.sidebar.number_input("Initial final product inventory (units)", value=500, step=50)

st.sidebar.subheader("Monthly production plan (final units)")

def default_plan():
    # First month slightly higher to absorb initial stock, then steady 5,900
    return [6000] + [5900] * 11

monthly_production_plan = []
for i in range(12):
    monthly_production_plan.append(
        st.sidebar.number_input(
            f"Month {i + 1}",
            value=default_plan()[i],
            step=50,
        )
    )

st.sidebar.header("Contract Terms")
payment_terms_days = st.sidebar.number_input("Payment terms (days)", value=60, step=5)
incoterm = st.sidebar.selectbox("Incoterm", ["EXW", "CIP"])

st.sidebar.subheader("DOA & Quality")
doa_replacement_mode = st.sidebar.selectbox(
    "DOA replacement timing",
    ["Next month", "Next delivery"],
)
field_failure_rate = st.sidebar.number_input(
    "Field failure rate at consumer (%)", value=1.85, step=0.1, min_value=0.0, max_value=100.0
) / 100.0

st.sidebar.header("Service & ESG")
customization = st.sidebar.checkbox("Customization included", value=True)
technical_support_weeks = st.sidebar.number_input(
    "Technical support (engineer-weeks)", value=3.0, step=0.5
)
ecolowrap = st.sidebar.checkbox("Ecolowrap packaging", value=True)

st.sidebar.header("Logistics & Finance")
transport_cost_per_unit_from_cda = st.sidebar.number_input(
    "Transport cost from CDA (€/unit)", value=13.1, step=0.1
)
transport_cost_per_unit_to_cda = st.sidebar.number_input(
    "Transport cost to CDA (€/unit)", value=0.0, step=0.1
)
insurance_cost_per_unit = st.sidebar.number_input(
    "Insurance cost (€/unit)", value=2.67, step=0.01
)
cost_of_capital = st.sidebar.number_input(
    "Cost of capital (yearly, %)", value=10.0, step=0.5, min_value=0.0, max_value=100.0
) / 100.0

st.sidebar.header("Final Product & Neginfo")
final_product_price = st.sidebar.number_input(
    "Final product selling price (€/unit)", value=678.0, step=1.0
)
monthly_demand_units = st.sidebar.number_input(
    "Monthly demand (units)", value=6029, step=50
)
prod_cost_per_unit_excl_oled = st.sidebar.number_input(
    "Production cost per unit excl. OLED (€/unit)", value=257.4, step=1.0
)
neginfo_cost = st.sidebar.number_input(
    "NEGINFO total cost (€/year)", value=0.0, step=1000.0
)

if st.button("Run Simulation"):
    df, kpis = simulate_contract(
        list_price=list_price,
        discount=discount,
        monthly_oled_delivery=monthly_oled_delivery,
        initial_component_inventory=initial_component_inventory,
        monthly_production_plan=monthly_production_plan,
        payment_terms_days=payment_terms_days,
        doa_rate=0.0175,
        doa_replacement_mode=doa_replacement_mode,
        customization=customization,
        technical_support_weeks=technical_support_weeks,
        ecolowrap=ecolowrap,
        cost_of_capital=cost_of_capital,
        transport_cost_per_unit_from_cda=transport_cost_per_unit_from_cda,
        transport_cost_per_unit_to_cda=transport_cost_per_unit_to_cda,
        insurance_cost_per_unit=insurance_cost_per_unit,
        field_failure_rate=field_failure_rate,
        final_product_price=final_product_price,
        monthly_demand_units=monthly_demand_units,
        prod_cost_per_unit_excl_oled=prod_cost_per_unit_excl_oled,
        initial_final_inventory=initial_final_inventory,
        neginfo_cost=neginfo_cost,
    )

    st.subheader("Monthly Results (similar structure to the class simulator)")
    st.dataframe(df)

    st.subheader("Component Inventory Over Time")
    st.line_chart(df.set_index("Month")["Component inventory end"])

    st.subheader("Key KPIs")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Component final price (€/unit)", kpis["Component final price (€/unit)"])
        st.metric("Total OLEDs purchased", kpis["Total OLEDs purchased"])
        st.metric("Total units produced", kpis["Total units produced"])
        st.metric("Total units sold", kpis["Total units sold"])
        st.metric("Average component inventory", kpis["Average component inventory (units)"])
    with col2:
        st.metric("Component purchase cost (€/year)", f"{kpis['Component purchase cost (€/year)']:,}".replace(",", " "))
        st.metric("Production cost excl. OLEDs (€/year)", f"{kpis['Production cost excl. OLEDs (€/year)']:,}".replace(",", " "))
        st.metric("Inventory capital cost (€/year)", f"{kpis['Inventory capital cost (€/year)']:,}".replace(",", " "))
        st.metric("Transport from CDA (€/year)", f"{kpis['Transport from CDA (€/year)']:,}".replace(",", " "))
        st.metric("Insurance cost (€/year)", f"{kpis['Insurance cost (€/year)']:,}".replace(",", " "))

    st.subheader("P&L Summary")
    st.metric("Total sales revenue (€/year)", f"{kpis['Total sales revenue (€/year)']:,}".replace(",", " "))
    st.metric("Profit from negotiation (€/year)", f"{kpis['Profit from negotiation (€/year)']:,}".replace(",", " "))

    st.subheader("Contract Features")
    st.write(
        f"**Incoterm:** {incoterm}  \
**Payment terms (days):** {kpis['Payment terms (days)']}  \
**Customization included:** {kpis['Customization included']}  \
**Technical support (weeks):** {kpis['Technical support (weeks)']}  \
**Ecolowrap:** {kpis['Ecolowrap']}  \
**Ecolowrap subsidy (€/year):** {kpis['Ecolowrap subsidy (€/year)']}  \
**NEGINFO cost (€/year):** {kpis['NEGINFO cost (€/year)']}"
    )

st.markdown(
    """
---
### How to use this app
1. Set your negotiated terms on the left (price, discount, volume, payment terms, etc.).  \
2. Define the monthly production plan you intend to run.  \
3. Click **Run Simulation** to see volume, quality, logistics and P&L over 12 months.  \
4. Save this script as `negotiation_sim_app.py`, push it to GitHub, and run locally with:

```bash
streamlit run negotiation_sim_app.py
```

You can then deploy it as a public Streamlit app linked to your GitHub repo.
"""
)
