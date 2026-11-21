"""
Experiment scenarios and repeated runs.

All three scenarios use the same farm, population, starting infection, disease timing and
seeds. Only the transmission pathways and preventive measures change.
"""

import statistics
from dataclasses import replace

import pandas as pd

from asf_model import Settings, run_simulation

SCENARIOS = {
    "Scenario 1: Direct transmission only": dict(
        indirect_on=False, biosecurity=0.0, isolation_on=False, carcass_removal_delay=3
    ),
    "Scenario 2: Direct + indirect transmission": dict(
        indirect_on=True, biosecurity=0.0, isolation_on=False, carcass_removal_delay=3
    ),
    "Scenario 3: Direct + indirect + biosecurity": dict(
        indirect_on=True, biosecurity=0.6, isolation_on=True, detection_delay=2, carcass_removal_delay=1
    ),
}

SCENARIO_NOTES = {
    "Scenario 1: Direct transmission only": "Pigs can only infect pigs they touch. Contaminated pens and workers play no role.",
    "Scenario 2: Direct + indirect transmission": "Contaminated pens, carcasses and workers moving between pens can also infect pigs.",
    "Scenario 3: Direct + indirect + biosecurity": "Same as Scenario 2, plus biosecurity 60% (cleaning, disinfection), sick pigs isolated 2 days after becoming infectious, carcasses removed after 1 day.",
}

INDICATORS = {
    "total_infected": "Total pigs infected",
    "percent_infected": "% of pigs infected",
    "total_deaths": "Total deaths",
    "total_recovered": "Total recovered",
    "peak_infectious": "Peak infectious pigs",
    "peak_day": "Day of peak",
    "outbreak_duration": "Outbreak duration (days)",
    "final_susceptible": "Final susceptible pigs",
}


def scenario_settings(name, base=None):
    """The settings of a scenario: the base settings with the scenario's changes applied."""
    return replace(base or Settings(), **SCENARIOS[name])


def run_scenario(name, runs=30, base_seed=1000, base=None, on_progress=None):
    """Runs one scenario `runs` times. Run r uses seed base_seed + r (same seeds in every scenario)."""
    rows, curves = [], []
    for r in range(runs):
        settings = replace(scenario_settings(name, base), seed=base_seed + r)
        result = run_simulation(settings)
        rows.append({"scenario": name, "run": r + 1, "seed": settings.seed, **result.summary})
        curves.append([d["I"] for d in result.daily])
        if on_progress:
            on_progress()
    return pd.DataFrame(rows), curves


def summarize(df):
    """Mean, standard deviation, minimum and maximum of every indicator per scenario."""
    out = []
    for name, group in df.groupby("scenario", sort=False):
        for key, label in INDICATORS.items():
            values = group[key].tolist()
            out.append(
                {
                    "Scenario": name,
                    "Indicator": label,
                    "Mean": statistics.mean(values),
                    "SD": statistics.stdev(values) if len(values) > 1 else 0.0,
                    "Min": min(values),
                    "Max": max(values),
                }
            )
    return pd.DataFrame(out)
