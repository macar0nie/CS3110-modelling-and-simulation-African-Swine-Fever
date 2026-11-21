"""
Experiments page: runs the three scenarios many times and compares them.
"""

import pandas as pd
import streamlit as st

from experiments import INDICATORS, SCENARIOS, SCENARIO_NOTES, run_scenario, summarize

st.set_page_config(page_title="ASF Experiments", page_icon="🧪", layout="wide")
st.title("🧪 Experiments: comparing the three scenarios")
st.markdown(
    "Each scenario is run several times because the simulation is random. "
    "Run *r* uses seed = base seed + *r* in **every** scenario, so all scenarios get the same random starting conditions. "
    "All other inputs are the defaults (120 pigs, 6 pens, 2 infected pigs in Pen 1, 60 days)."
)
for name, note in SCENARIO_NOTES.items():
    st.markdown(f"- **{name}**: {note}")

c1, c2 = st.columns(2)
runs = c1.number_input("Runs per scenario", 5, 100, 30, step=5)
base_seed = c2.number_input("Base seed", 0, 1_000_000, 1000, step=1)


@st.cache_data(show_spinner=False)
def run_all(runs, base_seed):
    tables, curves = [], {}
    progress = st.progress(0.0, text="Running simulations...")
    done = [0]
    total = runs * len(SCENARIOS)

    def tick():
        done[0] += 1
        progress.progress(done[0] / total, text=f"Running simulations... {done[0]}/{total}")

    for name in SCENARIOS:
        df, scenario_curves = run_scenario(name, runs, base_seed, on_progress=tick)
        tables.append(df)
        curves[name] = scenario_curves
    progress.empty()
    return pd.concat(tables, ignore_index=True), curves


if st.button("▶ Run experiments", type="primary"):
    st.session_state.experiment = run_all(int(runs), int(base_seed))

if "experiment" not in st.session_state:
    st.info("Press **Run experiments** (takes about 10–20 seconds for 30 runs per scenario).")
    st.stop()

runs_df, curves = st.session_state.experiment
summary = summarize(runs_df)
short = {name: name.split(": ")[1] for name in SCENARIOS}

st.header("Results")
st.subheader("Summary table (mean ± SD, min–max)")
table = summary.copy()
fmt = lambda x: f"{x:.0f}" if float(x).is_integer() else f"{x:.1f}"
table["Value"] = table.apply(lambda r: f"{r.Mean:.1f} ± {r.SD:.1f}  ({fmt(r.Min)}–{fmt(r.Max)})", axis=1)
wide = table.pivot(index="Indicator", columns="Scenario", values="Value")[list(SCENARIOS)]
wide = wide.reindex(list(INDICATORS.values())).rename(columns=short)
st.dataframe(wide, use_container_width=True)

st.subheader("Average number of infectious pigs per day")
max_len = max(len(c) for cs in curves.values() for c in cs)
mean_curves = pd.DataFrame(
    {short[name]: [sum(c[d] for c in cs) / len(cs) for d in range(max_len)] for name, cs in curves.items()}
)
mean_curves.index.name = "day"
st.line_chart(mean_curves, color=["#3b82f6", "#ef4444", "#22c55e"])

st.subheader("Total infected and deaths (mean of all runs)")
means = runs_df.groupby("scenario", sort=False)[["total_infected", "total_deaths"]].mean()
means.index = [short[i] for i in means.index]
st.bar_chart(means.rename(columns={"total_infected": "Total infected", "total_deaths": "Deaths"}), stack=False, color=["#f59e0b", "#52525b"])

st.subheader("Variation between runs (total infected per run)")
spread = runs_df.pivot(index="run", columns="scenario", values="total_infected")[list(SCENARIOS)].rename(columns=short)
st.scatter_chart(spread.reset_index().melt("run", var_name="Scenario", value_name="Total infected"), x="run", y="Total infected", color="Scenario")

st.subheader("Data")
st.dataframe(runs_df, use_container_width=True, height=250)
c1, c2 = st.columns(2)
c1.download_button("Download all runs (CSV)", runs_df.to_csv(index=False), "asf_experiment_runs.csv", "text/csv")
c2.download_button("Download summary (CSV)", summary.to_csv(index=False), "asf_experiment_summary.csv", "text/csv")
