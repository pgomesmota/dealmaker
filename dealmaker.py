import streamlit as st
import pandas as pd

# --- Core simulation logic ---

def simulate_contract(
    list_price: float,
    discount: float,
    monthly_oled_delivery: int,
    initial_inventory: int,
    monthly_production_plan,
    payment_terms_days: int,
    doa_rate: float = 0.0175,
    doa_replacement_mode: str = "Next month",
    customization: bool = True,
    technical_support_weeks: float = 3.0,
    ecolowrap: bool = True,
    cost_of_capital: float = 0.10,
):
    """Simulate 12-month OLED supply & production under a given deal.

    Args:
        list_price: OEM list price per OLED (€/unit).
        discount: commercial discount in % (e.g. 5 for 5%).
        monthly_oled_delivery: contractual OLED delivery per month (units).
        initial_inventory: initial good OLED inventory.
        monthly_production_plan: list of 12 integers (final units produced per month).
        payment_terms_days: payment term in days (e.g. 60).
        doa_rate: DOA rate as a fraction (e.g. 0.0175 for 1.75%).
        doa_replacement_mode: "Next month" or "Next delivery" (behave the same here
            because deliveries are monthly, but kept for rule-of-the-game clarity).
        customization: whether customization is included.
        technical_support_weeks: engineer-weeks of support.
        ecolowrap: whether Ecolowrap is used.
        cost_of_capital: yearly cost of capital (e.g. 0.10 = 10%).

    Returns:
        df: Month-by-month simulation dataframe.
        kpis: dict with aggregate KPIs.
    """

    final_price = list_price * (1 - discount / 100.0)

    records = []
    inventory = initial_inventory
    pending_doa_replacements = 0

    total_oleds_purchased = 0
    total_units_produced = 0
    inventory_snapshots = []

    for month in range(1, 13):
        start_inv = inventory

        # OLED delivery and DOA handling
        received = monthly_oled_delivery
        total_oleds_purchased += received

        doa_units = int(received * doa_rate)

        # Replacements arrive with the next scheduled delivery; in practice for
        # a monthly delivery schedule, "next delivery" and "next month" behave
        # the same, but we keep the parameter for transparency.
        usable_now = received - doa_units + pending_doa_replacements

        # Next month's replacements = this month's DOA
        pending_doa_replacements = doa_units

        production = monthly_production_plan[month - 1]
        end_inv = start_inv + usable_now - production

        total_units_produced += production
        inventory = end_inv

        # track both start & end for average inventory later
        inventory_snapshots.append(start_inv)
        records.append(
            {
                "Month": month,
                "Start Inventory": start_inv,
                "OLEDs Received": received,
                "DOA Units": doa_units,
                "DOA Replacements Available": usable_now - (received - doa_units),
                "Usable OLEDs": usable_now,
                "Production (final units)": production,
                "End Inventory": end_inv,
            }
        )

    # also consider last month end inventory for average
    inventory_snapshots.append(inventory)
    avg_inventory = sum(inventory_snapshots) / len(inventory_snapshots)

    # Economic KPIs
    component_purchase_cost = total_oleds_purchased * final_price
    inventory_capital_cost = avg_inventory * final_price * cost_of_capital

    ecolowrap_subsidy = 200_000 if ecolowrap else 0

    kpis = {
        "Final price (€/unit)": round(final_price, 2),
        "Total OLEDs purchased": int(total_oleds_purchased),
        "Total units produced": int(total_units_produced),
        "Average inventory (OLEDs)": round(avg_inventory, 1),
        "Component purchase cost (€/year)": round(component_purchase_cost, 0),
        "Inventory capital cost (€/year)": round(inventory_capital_cost, 0),
        "Payment terms (days)": payment_terms_days,
        "Customization included": customization,
        "Technical support (weeks)": technical_support_weeks,
        "Ecolowrap": ecolowrap,
        "Ecolowrap subsidy (€/year)": ecolowrap_subsidy,
    }

    df = pd.DataFrame(records)
    return df, kpis


# --- Streamlit UI ---

st.title("Negotiation Deal Simulation – OLED Supply & Production")
st.markdown(
    "Simulate the operational and financial impact of different contract terms "
    "(price, discount, volume, payment terms, customization, support, Ecolowrap)."
)

st.sidebar.header("Contract Economics")
list_price = st.sidebar.number_input("List price per OLED (€/unit)", value=179.0, step=1.0)
discount = st.sidebar.number_input("Discount (%)", value=0.0, step=0.1, min_value=0.0, max_value=100.0)

st.sidebar.header("Supply & Operations")
monthly_oled_delivery = st.sidebar.number_input("Monthly OLED delivery (units)", value=6000, step=100)
initial_inventory = st.sidebar.number_input("Initial good OLED inventory", value=500, step=50)
payment_terms_days = st.sidebar.number_input("Payment terms (days)", value=60, step=5)

incoterm = st.sidebar.selectbox("Incoterm", ["EXW", "CIP"])

st.sidebar.subheader("DOA & Replacement")
doa_replacement_mode = st.sidebar.selectbox(
    "DOA replacement timing",
    ["Next month", "Next delivery"],
    help="In this simplified monthly model, both options behave the same but are kept as a negotiation variable.",
)

st.sidebar.header("Service & ESG")
customization = st.sidebar.checkbox("Customization included", value=True)
technical_support_weeks = st.sidebar.number_input(
    "Technical support (engineer-weeks)", value=3.0, step=0.5
)
ecolowrap = st.sidebar.checkbox("Ecolowrap packaging", value=True)

st.sidebar.header("Financial Parameters")
cost_of_capital = st.sidebar.number_input(
    "Cost of capital (yearly, %)", value=10.0, step=0.5, min_value=0.0, max_value=100.0
) / 100.0

st.sidebar.header("Monthly Production Plan (final units)")

def default_plan():
    # First month slightly higher to consume initial inventory, then steady 5,900
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

if st.button("Run Simulation"):
    df, kpis = simulate_contract(
        list_price=list_price,
        discount=discount,
        monthly_oled_delivery=monthly_oled_delivery,
        initial_inventory=initial_inventory,
        monthly_production_plan=monthly_production_plan,
        payment_terms_days=payment_terms_days,
        doa_rate=0.0175,
        doa_replacement_mode=doa_replacement_mode,
        customization=customization,
        technical_support_weeks=technical_support_weeks,
        ecolowrap=ecolowrap,
        cost_of_capital=cost_of_capital,
    )

    st.subheader("Simulation Results – Month by Month")
    st.dataframe(df)

    st.subheader("Inventory Over Time")
    st.line_chart(df.set_index("Month")["End Inventory"])

    st.subheader("Key KPIs")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Final price (€/unit)", kpis["Final price (€/unit)"])
        st.metric("Total OLEDs purchased", kpis["Total OLEDs purchased"])
        st.metric("Total units produced", kpis["Total units produced"])
        st.metric("Average inventory (OLEDs)", kpis["Average inventory (OLEDs)"])
    with col2:
        st.metric("Component purchase cost (€/year)", f"{kpis['Component purchase cost (€/year)']:,}".replace(",", " "))
        st.metric("Inventory capital cost (€/year)", f"{kpis['Inventory capital cost (€/year)']:,}".replace(",", " "))
        st.metric("Payment terms (days)", kpis["Payment terms (days)"])
        st.metric("Ecolowrap subsidy (€/year)", f"{kpis['Ecolowrap subsidy (€/year)']:,}".replace(",", " "))

    st.subheader("Contract Features")
    st.write(
        f"**Incoterm:** {incoterm}  \
**Customization included:** {customization}  \
**Technical support (weeks):** {technical_support_weeks}  \
**Ecolowrap:** {ecolowrap}"
    )

st.markdown(
    """
---
### How to use this app
1. Set contract terms on the left (price, discount, volume, payment terms, etc.).  
2. Define your month-by-month production plan.  
3. Click **Run Simulation** to see operational and financial impact.  
4. Save this script as `negotiation_sim_app.py`, push it to GitHub, and run locally with:

```bash
streamlit run negotiation_sim_app.py
```

You can then deploy it as a public Streamlit app linked to your GitHub repo.
"""
)
