"""
Runs the three scenarios without the app and saves the results (for the report).
Usage:  python run_experiments.py            (30 runs per scenario, base seed 1000)
        python run_experiments.py 50 2000    (50 runs, base seed 2000)
Creates results_runs.csv and results_summary.csv in this folder.
"""
import sys

import pandas as pd

from experiments import SCENARIOS, run_scenario, summarize

runs = int(sys.argv[1]) if len(sys.argv) > 1 else 30
base_seed = int(sys.argv[2]) if len(sys.argv) > 2 else 1000

tables = [run_scenario(name, runs, base_seed)[0] for name in SCENARIOS]
df = pd.concat(tables, ignore_index=True)
summary = summarize(df)
df.to_csv("results_runs.csv", index=False)
summary.to_csv("results_summary.csv", index=False)

pd.set_option("display.width", 200)
print(f"{runs} runs per scenario, seeds {base_seed}-{base_seed + runs - 1}\n")
print(summary.pivot(index="Indicator", columns="Scenario", values="Mean").round(1).to_string())
print("\nStandard deviations:")
print(summary.pivot(index="Indicator", columns="Scenario", values="SD").round(1).to_string())
