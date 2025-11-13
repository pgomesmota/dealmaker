# ipb_simulator.py
import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="IPB Negotiation Simulator", layout="wide")

# ---------- CONSTANTS (you can adjust) ----------
DEFAULT_SELLING_PRICE = 672.73      # €/unit (IPB average selling price in Yr0)
OTHER_VAR_COST_PER_UNIT = 257.4     # €/unit (all components except OLED)
FIXED_COST_YEAR = 14_800_000        # €/year
DEFECT_RATE_FIELD = 0.02            # 2% of final products have a defect
WARRANTY_COST_PER_UNIT = 125        # €/defective unit
COST_OF_CAPITAL = 0.10              # 10% cost of capital
INITIAL_OLED_INVENTORY = 500        # units on Jan 1
INITIAL_FINAL_INV = 500             # units on Jan 1
ECOLORAP_GRANT = 200_000            # one-off grant if Ecolowrap is used
VALUE_PER_ENGINEER_WEEK = 10_000    # € benefit per engineer-week of support
CUSTOMIZATION_VALUE_PER_UNIT = 5    # € extra margin per unit if customization

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# ---------- HELPER FUNCTIONS ----------

def simulate_scenario(
    name: str,
    monthly_volume: np.ndarray,
    gross_price: float,
    discount_pct: float,
    terms_of_payment_days: int,
    use_ecolowrap: bool,
    tech_support_weeks: float,
    customization: bool,
    incoterm: str,
    doa_replacement: str,
    expected_monthly_demand: float,
    selling_price: float,
):
    """Return a dict with all KPI for a given scenario (IPB perspective)."""

    # Sanity
    monthly_volume = np.array(monthly_volume, dtype=float)
    total_purchases_units = monthly_volume.sum()

    # Units demanded and available
    total_demand_units = expected_monthly_demand * 12
    max_available_oleds = INITIAL_OLED_INVENTORY + total_purchases_units
    units_sold = min(total_demand_units, max_available_oleds)

    # Prices
    net_unit_price = gross_price * (1 - discount_pct / 100.0)

    # Revenue & basic costs
    revenue = units_sold * selling_price
    oled_cost = total_purchases_units * net_unit_price
    other_var_cost = units_sold * OTHER_VAR_COST_PER_UNIT
    fixed_cost = FIXED_COST_YEAR

    # Warranty cost (independent of contract terms here)
    warranty_units = units_sold * DEFECT_RATE_FIELD
    warranty_cost = warranty_units * WARRANTY_COST_PER_UNIT

    # Inventory simulation for OLEDs (derived from monthly schedule vs demand)
    inventory = INITIAL_OLED_INVENTORY
    inventory_levels = []
    for m in range(12):
        purchase = monthly_volume[m]
        demand = expected_monthly_demand
        inventory = inventory + purchase - demand
        # no negative inventory; backlog ignored for cost of capital
        inventory = max(inventory, 0)
        inventory_levels.append(inventory)

    avg_inventory_units = (INITIAL_OLED_INVENTORY + sum(inventory_levels)) / 13.0
    avg_inventory_value = avg_inventory_units * net_unit_price
    inventory_cost = avg_inventory_value * COST_OF_CAPITAL

    # Financing benefit from supplier credit (accounts payable)
    annual_oled_purchase_value = oled_cost
    avg_accounts_payable = annual_oled_purchase_value * (terms_of_payment_days / 360.0)
    financing_benefit = avg_accounts_payable * COST_OF_CAPITAL

    # Benefits from technical support, customization, ecolowrap
    tech_support_benefit = tech_support_weeks * VALUE_PER_ENGINEER_WEEK
    customization_benefit = (units_sold * CUSTOMIZATION_VALUE_PER_UNIT) if customization else 0.0
    ecolowrap_benefit = ECOLORAP_GRANT if use_ecolowrap else 0.0

    # Profit
    profit = (
        revenue
        - oled_cost
        - other_var_cost
        - fixed_cost
        - warranty_cost
        - inventory_cost
        + financing_benefit
        + tech_support_benefit
        + customization_benefit
        + ecolowrap_benefit
    )

    margin_per_unit = profit / units_sold if units_sold > 0 else 0

    return {
        "Scenario": name,
        "Units sold (estimated)": units_sold,
        "Total OLED purchases (units)": total_purchases_units,
        "Net OLED price (€/unit)": net_unit_price,
        "Revenue (M€)": revenue / 1e6,
        "OLED cost (M€)": oled_cost / 1e6,
        "Other variable cost (M€)": other_var_cost / 1e6,
        "Fixed cost (M€)": fixed_cost / 1e6,
        "Warranty cost (M€)": warranty_cost / 1e6,
        "Inventory cost (M€)": inventory_cost / 1e6,
        "Financing benefit (M€)": financing_benefit / 1e6,
        "Tech support benefit (M€)": tech_support_benefit / 1e6,
        "Customization benefit (M€)": customization_benefit / 1e6,
        "Ecolowrap benefit (M€)": ecolowrap_benefit / 1e6,
        "Profit (M€)": profit / 1e6,
        "Margin per unit (€/unit)": margin_per_unit,
        "Terms of payment (days)": terms_of_payment_days,
        "Incoterm": incoterm,
        "DOA replacement": doa_replacement,
        "Uses Ecolowrap": use_ecolowrap,
        "Customization": customization,
        "Tech support (weeks)": tech_support_weeks,
    }

# ---------- SIDEBAR: GLOBAL SETTINGS ----------
st.sidebar.header("Global assumptions (IPB)")

selling_price = st.sidebar.number_input(
    "Selling price of final product (€/unit)",
    value=DEFAULT_SELLING_PRICE,
    step=10.0,
)

expected_monthly_demand = st.sidebar.number_input(
    "Expected monthly demand (units)",
    value=5800.0,
    min_value=0.0,
    step=100.0,
    help="Used to calculate inventory and units sold.",
)

st.sidebar.markdown("---")
st.sidebar.write("Cost & value parameters")
COST_OF_CAPITAL = st.sidebar.number_input(
    "Cost of capital (%)", value=10.0, step=0.5
) / 100.0

VALUE_PER_ENGINEER_WEEK = st.sidebar.number_input(
    "Value per engineer-week (k€)", value=10.0, step=1.0
) * 1000.0

CUSTOMIZATION_VALUE_PER_UNIT = st.sidebar.number_input(
    "Customization value per unit (€/unit)",
    value=5.0,
    step=1.0,
)

ECOLORAP_GRANT = st.sidebar.number_input(
    "Ecolowrap grant (k€)", value=200.0, step=10.0
) * 1000.0


# ---------- MAIN LAYOUT ----------
st.title("IPB – OLED Agreement Simulator (2 Scenarios)")
st.write(
    "Use this app to compare two alternative agreements with CDA from IPB’s perspective. "
    "All values are annual, based on a monthly volume schedule."
)

colA, colB = st.columns(2)

def scenario_inputs(col, name_default="Scenario"):
    with col:
        st.subheader(name_default)
        name = st.text_input("Scenario name", value=name_default, key=f"name_{name_default}")

        st.markdown("**Sales Volume Agreement (monthly units)**")
        default_units = [5800] * 12
        df = pd.DataFrame({"Month": MONTHS, "Volume": default_units})
        edited_df = st.data_editor(
            df,
            num_rows="fixed",
            key=f"volume_{name_default}",
            hide_index=True,
        )
        monthly_volume = edited_df["Volume"].values

        st.markdown("**Commercial terms**")
        gross_price = st.number_input(
            "Gross price (€/unit, before discount)",
            value=179.0,
            step=1.0,
            key=f"gross_{name_default}",
        )
        discount_pct = st.number_input(
            "Discount (%)",
            value=1.0,
            step=0.5,
            key=f"disc_{name_default}",
        )
        incoterm = st.selectbox(
            "Incoterm",
            options=["Ex Works", "CIP"],
            key=f"incoterm_{name_default}",
        )
        terms_payment = st.number_input(
            "Terms of payment (days)",
            value=60,
            min_value=0,
            step=5,
            key=f"terms_{name_default}",
        )

        st.markdown("**Operational terms**")
        doa_replacement = st.selectbox(
            "DOA replacement timing",
            options=["Next Month", "Next Delivery"],
            key=f"doa_{name_default}",
        )
        tech_support = st.number_input(
            "Technical support (engineer-weeks)",
            value=3.0,
            min_value=0.0,
            step=1.0,
            key=f"tech_{name_default}",
        )
        customization = st.checkbox(
            "Include customization?", value=True, key=f"cust_{name_default}"
        )
        ecolowrap = st.checkbox(
            "Use Ecolowrap (eligible for grant)?",
            value=True,
            key=f"eco_{name_default}",
        )

    return {
        "name": name,
        "monthly_volume": monthly_volume,
        "gross_price": gross_price,
        "discount_pct": discount_pct,
        "incoterm": incoterm,
        "terms_payment": terms_payment,
        "doa_replacement": doa_replacement,
        "tech_support": tech_support,
        "customization": customization,
        "ecolowrap": ecolowrap,
    }

inputs_A = scenario_inputs(colA, "Scenario A")
inputs_B = scenario_inputs(colB, "Scenario B")

# ---------- RUN SIMULATION ----------
if st.button("Run simulation and compare"):
    scenario_results = []
    for inputs in [inputs_A, inputs_B]:
        res = simulate_scenario(
            name=inputs["name"],
            monthly_volume=inputs["monthly_volume"],
            gross_price=inputs["gross_price"],
            discount_pct=inputs["discount_pct"],
            terms_of_payment_days=inputs["terms_payment"],
            use_ecolowrap=inputs["ecolowrap"],
            tech_support_weeks=inputs["tech_support"],
            customization=inputs["customization"],
            incoterm=inputs["incoterm"],
            doa_replacement=inputs["doa_replacement"],
            expected_monthly_demand=expected_monthly_demand,
            selling_price=selling_price,
        )
        scenario_results.append(res)

    df_results = pd.DataFrame(scenario_results)

    st.subheader("Key results comparison")
    metrics_to_show = [
        "Profit (M€)",
        "Units sold (estimated)",
        "Revenue (M€)",
        "OLED cost (M€)",
        "Other variable cost (M€)",
        "Fixed cost (M€)",
        "Warranty cost (M€)",
        "Inventory cost (M€)",
        "Financing benefit (M€)",
        "Tech support benefit (M€)",
        "Customization benefit (M€)",
        "Ecolowrap benefit (M€)",
        "Margin per unit (€/unit)",
        "Terms of payment (days)",
    ]

    st.dataframe(
        df_results[["Scenario"] + metrics_to_show].set_index("Scenario"),
        use_container_width=True,
    )

    # Simple highlight of which scenario wins on profit
    best_idx = df_results["Profit (M€)"].idxmax()
    best_scenario = df_results.loc[best_idx, "Scenario"]
    st.success(f"Scenario with higher estimated profit for IPB: **{best_scenario}**")

    st.caption(
        "Note: This is an approximation based on the case data. "
        "Technical support, customization and DOA timing are valued using the assumptions in the sidebar; "
        "you can adjust those to match your own view or the professor’s scoring logic."
    )
