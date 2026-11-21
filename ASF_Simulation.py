"""
ASF Simulation - main page.

1. Set the inputs in the sidebar (or load a scenario preset).
2. Press "Start simulation": Python runs the whole simulation with those inputs.
3. The 3D farm plays the run back day by day (Pause / Stop inside the 3D view).
4. Press "Stop / reset" to clear the run and start over.

Run locally with:  streamlit run ASF_Simulation.py
"""

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from asf_model import Settings, run_simulation
from experiments import SCENARIOS, SCENARIO_NOTES, scenario_settings
from viewer import STATE_COLORS, build_viewer_html

st.set_page_config(page_title="ASF Simulation", page_icon="🐖", layout="wide")

DEFAULTS = Settings()

# ---------------------------------------------------------------------------
# Scenario presets fill in the sidebar inputs
# ---------------------------------------------------------------------------
INPUT_KEYS = [
    "num_pigs", "initial_infected", "days", "seed", "direct_rate", "indirect_on", "indirect_rate",
    "recovery_prob", "movement_speed", "transfers_per_week", "biosecurity", "isolation_on",
    "detection_delay", "carcass_removal_delay",
]


def load_settings_into_inputs(settings):
    for key in INPUT_KEYS:
        st.session_state[key] = getattr(settings, key)


if "initialised" not in st.session_state:
    load_settings_into_inputs(scenario_settings("Scenario 2: Direct + indirect transmission"))
    st.session_state.initialised = True

st.sidebar.title("🐖 ASF Simulation")
preset = st.sidebar.selectbox("Load a scenario preset", ["(keep my values)", *SCENARIOS.keys()])
if st.sidebar.button("Load preset", disabled=preset == "(keep my values)"):
    load_settings_into_inputs(scenario_settings(preset))
    st.session_state.pop("result", None)
    st.rerun()

# ---------------------------------------------------------------------------
# Inputs: inside a form, so nothing runs until "Start simulation" is pressed
# ---------------------------------------------------------------------------
with st.sidebar.form("inputs"):
    st.subheader("Farm")
    st.slider("Number of pigs", 30, 240, step=6, key="num_pigs", help="Pigs are spread evenly over 6 pens.")
    st.slider("Initially infected pigs (in Pen 1)", 1, 10, key="initial_infected")
    st.slider("Simulation length (days)", 20, 120, step=5, key="days")

    st.subheader("Disease")
    st.slider("Direct transmission rate", 0.0, 0.3, step=0.01, key="direct_rate",
              help="Infection hazard per close contact (within 1 m) with an infectious pig.")
    st.checkbox("Indirect transmission (contaminated pens, carcasses, workers)", key="indirect_on")
    st.slider("Indirect transmission rate", 0.0, 0.05, step=0.002, format="%.3f", key="indirect_rate",
              help="Infection hazard per unit of pen contamination per day.")
    st.slider("Recovery probability", 0.0, 1.0, step=0.01, key="recovery_prob",
              help="Chance that an infectious pig recovers. Otherwise it dies.")

    st.subheader("Movement")
    st.slider("Pig movement speed (m/h)", 0.0, 3.0, step=0.1, key="movement_speed",
              help="How fast pigs walk around inside their pen. 0 = pigs stand still.")
    st.slider("Pig transfers between pens (per week)", 0.0, 7.0, step=0.5, key="transfers_per_week",
              help="Workers moving pigs from one pen to another.")

    st.subheader("Prevention")
    st.slider("Biosecurity effectiveness", 0.0, 0.9, step=0.05, key="biosecurity",
              help="Cleaning and disinfection: reduces indirect transmission and contamination carried by workers.")
    st.checkbox("Isolate detected sick pigs", key="isolation_on")
    st.slider("Detection delay (days)", 0, 7, key="detection_delay", help="Days a pig is infectious before it is noticed and isolated.")
    st.slider("Carcass removal delay (days)", 0, 7, key="carcass_removal_delay")

    st.subheader("Randomness")
    st.number_input("Random seed", 0, 1_000_000, step=1, key="seed", help="Same seed + same inputs = exactly the same run.")

    started = st.form_submit_button("▶ Start simulation", type="primary", use_container_width=True)

if st.sidebar.button("⏹ Stop / reset", use_container_width=True):
    st.session_state.pop("result", None)
    st.rerun()

if started:
    settings = Settings(**{key: st.session_state[key] for key in INPUT_KEYS})
    with st.spinner("Simulating..."):
        st.session_state.result = run_simulation(settings)
    st.session_state.result_preset = preset

# ---------------------------------------------------------------------------
# Main area
# ---------------------------------------------------------------------------
st.title("Simulation of African Swine Fever Transmission in a Pig Farm")
st.caption("Educational agent-based model of a hypothetical 6-pen farm. Not a prediction of real outbreaks. ASF does not infect humans.")

result = st.session_state.get("result")
if result is None:
    st.info("Set the inputs in the sidebar, then press **▶ Start simulation**. The 3D farm will play the run day by day.")
    with st.expander("What do the scenario presets do?", expanded=True):
        for name, note in SCENARIO_NOTES.items():
            st.markdown(f"**{name}**: {note}")
    st.stop()

s = result.settings
st.markdown(
    f"**Running:** {s['num_pigs']} pigs, {s['initial_infected']} initially infected, {s['days']} days, seed {s['seed']} · "
    f"indirect transmission **{'on' if s['indirect_on'] else 'off'}** · biosecurity **{s['biosecurity']:.0%}** · "
    f"isolation **{'on' if s['isolation_on'] else 'off'}**"
)
components.html(build_viewer_html(result), height=630)
st.caption("Drag to rotate · right-drag to pan · scroll to zoom. Pause/Stop and playback speed are in the top-left of the 3D view.")

with st.expander("📊 Final results of this run", expanded=False):
    summary = result.summary
    c = st.columns(4)
    c[0].metric("Total infected", f"{summary['total_infected']} ({summary['percent_infected']:.0f}%)")
    c[1].metric("Deaths", summary["total_deaths"])
    c[2].metric("Recovered", summary["total_recovered"])
    c[3].metric("Peak infectious", f"{summary['peak_infectious']} (day {summary['peak_day']})")
    c = st.columns(4)
    c[0].metric("Outbreak duration", f"{summary['outbreak_duration']} days")
    c[1].metric("Final susceptible", summary["final_susceptible"])
    c[2].metric("Infected by direct contact", summary["direct_infections"])
    c[3].metric("Infected indirectly", summary["indirect_infections"])

    daily = pd.DataFrame(result.daily)
    curves = daily.rename(columns={"S": "Susceptible", "E": "Exposed", "I": "Infectious", "R": "Recovered", "total_dead": "Dead (total)"})
    st.line_chart(curves.set_index("day")[["Susceptible", "Exposed", "Infectious", "Recovered", "Dead (total)"]],
                  color=[STATE_COLORS["S"], STATE_COLORS["E"], STATE_COLORS["I"], STATE_COLORS["R"], STATE_COLORS["D"]])
    st.bar_chart(daily.set_index("day")[["new_direct", "new_indirect"]].rename(columns={"new_direct": "Direct", "new_indirect": "Indirect"}),
                 color=["#ef4444", "#f59e0b"])
    st.download_button("Download daily results (CSV)", daily.to_csv(index=False), file_name=f"asf_run_seed{s['seed']}.csv", mime="text/csv")
