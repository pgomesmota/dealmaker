import streamlit as st
import pandas as pd

def simulate(monthly_oleds=6000, doa_rate=0.0175, initial_inventory=500, monthly_output_plan=None):
    if monthly_output_plan is None:
        monthly_output_plan = [6000] + [5900]*11
    data = []
    inventory = initial_inventory
    for month in range(1, 13):
        usable = int(monthly_oleds * (1 - doa_rate))
        start_inv = inventory
        production = monthly_output_plan[month-1]
        end_inv = start_inv + usable - production
        data.append({
            "Month": month,
            "Start Inventory": start_inv,
            "Usable OLEDs": usable,
            "Production": production,
            "End Inventory": end_inv
        })
        inventory = end_inv
    return pd.DataFrame(data)

st.title("OLED Supply & Production Simulation App")

st.sidebar.header("Input Parameters")
monthly_oleds = st.sidebar.number_input("Monthly OLED Delivery", value=6000)
doa_rate = st.sidebar.number_input("DOA Rate", value=0.0175)
initial_inventory = st.sidebar.number_input("Initial Inventory", value=500)

st.sidebar.subheader("Monthly Production Plan")
def default_plan():
    return [6000] + [5900]*11

plan_inputs = []
for i in range(12):
    default_val = default_plan()[i]
    plan_inputs.append(st.sidebar.number_input(f"Month {i+1} Production", value=default_val))

if st.button("Run Simulation"):
    df = simulate(monthly_oleds, doa_rate, initial_inventory, plan_inputs)
    st.subheader("Simulation Results")
    st.dataframe(df)
    st.line_chart(df.set_index("Month")["End Inventory"])

st.markdown("""
### Instructions
1. Adjust parameters in the sidebar.
2. Click 'Run Simulation'.
3. Review inventory levels and adjust your production strategy.

You can upload this file directly to GitHub, then deploy as a Streamlit app using:
```
streamlit run negotiation_sim_app.py
```
""")
