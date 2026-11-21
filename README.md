# ASF Simulation: African Swine Fever Transmission in a Pig Farm

A Streamlit web app that simulates how African Swine Fever (ASF) spreads among individual pigs in a hypothetical 6-pen farm. You set the inputs and press **Start**, and a 3D farm plays the run back day by day. A second page runs the three experiment scenarios 30 times each and compares them.

> Educational model with simplified assumptions. It does not predict real outbreaks. ASF does not infect humans.

## Files

| File | What it contains |
|---|---|
| `asf_model.py` | **The simulation model**: pigs, pens, movement, infection, disease states. Pure Python, no UI. |
| `ASF_Simulation.py` | Main Streamlit page: inputs, Start / Stop, 3D playback, results of one run |
| `pages/1_Experiments.py` | Experiments page: 3 scenarios × 30 runs, summary table, charts, CSV download |
| `experiments.py` | Scenario definitions, repeated runs, mean / SD / min / max |
| `viewer.py` | Builds the 3D farm (Three.js). It only replays results; it does not compute anything. |
| `run_experiments.py` | Runs the experiments without the app and saves `results_runs.csv` and `results_summary.csv` |
| `tests/test_model.py` | 12 verification tests (pytest) |
| `static/three/` | The Three.js library files (MIT licence), so the 3D view works without a CDN |
| `.streamlit/config.toml` | Turns on static file serving (needed for the 3D view) |
| `requirements.txt` | Python packages: `streamlit`, `pandas` |

## Run it on your computer (Windows)

1. Install **Python 3.10 or newer** from https://www.python.org/downloads/. In the installer, tick **"Add python.exe to PATH"**.
2. Open the project folder in VS Code and open a terminal (*Terminal → New Terminal*).
3. Install the packages (one time):
   ```powershell
   pip install -r requirements.txt
   ```
4. Start the app:
   ```powershell
   streamlit run ASF_Simulation.py
   ```
   Your browser opens at http://localhost:8501. Press `Ctrl + C` in the terminal to stop the app.

Other commands:
```powershell
python -m pytest -q          # run the 12 tests
python run_experiments.py    # 3 scenarios x 30 runs -> results_runs.csv, results_summary.csv
```

## Put it online (free standalone link): Streamlit Community Cloud

1. Create a GitHub account and a **new repository** (e.g., `asf-simulation`).
2. Upload **all** files and folders of this project to it, including the hidden `.streamlit` folder and the `static` folder. With GitHub Desktop or `git push` the hidden folder is included automatically. With *Add file → Upload files* on the website, drag the whole project folder in.
3. Go to https://share.streamlit.io and sign in with GitHub.
4. Click **Create app** → *Deploy a public app from GitHub* and choose:
   - Repository: your repository
   - Branch: `main`
   - Main file path: **`ASF_Simulation.py`**
   - App URL: choose a name, e.g. `asf-simulation` → `https://asf-simulation.streamlit.app`
5. Click **Deploy**. The first build takes a few minutes. After that, the link works for anyone, with no login needed.

Free apps go to sleep after a period without visitors. The first visit then shows a "wake up" button and takes a short moment, so open your link a few minutes before your demo or defense.

**Backup host:** the same code also runs on Hugging Face Spaces (choose the Streamlit template).

## How to use the app

1. **Sidebar → inputs.** Change any value, or pick a **scenario preset** and press **Load preset**.
2. Press **▶ Start simulation**. Python runs the whole simulation with those inputs (about one second).
3. The **3D farm** plays the run back. Use **Pause**, **Stop** (back to day 0) and the speed menu in its top-left corner. Drag to rotate, right-drag to pan, scroll to zoom. The live counts and chart follow the playback.
4. Open **📊 Final results of this run** for the final numbers, the charts and a CSV download.
5. **⏹ Stop / reset** in the sidebar clears the run so you can start over.
6. The **Experiments** page (left menu) runs Scenarios 1–3 thirty times each and compares them.

Inputs live inside a form, so changing a slider does **nothing** until you press Start. A run always uses exactly the inputs you set.

## How the model works (short version)

- **Agents:** each pig has a position inside its pen and a disease state.
- **States:** **S**usceptible → **E**xposed (infected, not yet infectious; 3–6 days) → **I**nfectious (5–9 days) → **R**ecovered (with probability = recovery probability) or **D**ead. A dead pig's carcass stays in the pen until it is removed (**X**) after the carcass removal delay.
- **Time:** 1 step = 1 day. Inside each day, pigs move 6 times (every 4 hours).
- **Direct transmission:** after each movement step, a susceptible pig within **1 m** of an infectious pen-mate gets one *contact*.
- **Indirect transmission:** each pen has a *contamination* level. Every infectious pig and every carcass adds 1 per day, 20% fades away each day, and workers carry 10% of the other pens' average contamination into each pen.
- **Infection probability per day** for a susceptible pig:

  P = 1 − exp(−λ),  λ = direct rate × contacts + indirect rate × pen contamination × (1 − biosecurity)

- **Prevention:** biosecurity reduces indirect transmission and workers' carry-over; isolation moves a sick pig to the isolation pen *detection delay* days after it becomes infectious, where it has no contact with the herd; carcass removal delay sets how long carcasses stay in pens.
- **Movement between pens:** workers move about *transfers per week* pigs to other pens; an infected pig moved this way can start an outbreak in a new pen.
- **Randomness:** all random numbers come from one generator seeded with the *random seed*. The same seed and inputs always give the same run.

## Scenarios (Experiments page)

All use 120 pigs, 6 pens, 2 infected pigs in Pen 1, 60 days, and seeds 1000–1029.

| | Indirect transmission | Biosecurity | Isolation | Carcass removal |
|---|---|---|---|---|
| Scenario 1: Direct only | off | 0% | off | 3 days |
| Scenario 2: Direct + indirect | on | 0% | off | 3 days |
| Scenario 3: Direct + indirect + biosecurity | on | 60% | on (after 2 days) | 1 day |

## Limitations

The farm is hypothetical, and the parameter values are simplified assumptions, not measurements. Contamination is a relative index, not a viral load. Recovered pigs are assumed not to spread the virus. Detection always happens exactly after the detection delay. Feed, water, vehicles, wild boar and spread between farms are not modelled.

## Credits

Built with Python, [Streamlit](https://streamlit.io), [pandas](https://pandas.pydata.org) and [Three.js](https://threejs.org) (MIT licence, included in `static/three/`). Disease background: World Organisation for Animal Health (WOAH), *African swine fever*.
