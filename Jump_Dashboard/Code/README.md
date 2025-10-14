# Jump → Pitch Velocity Dashboard — README

This guide shows anyone how to set up a **virtual environment**, install dependencies, and run the **Streamlit** dashboard that relates **jump performance** to **pitch velocity**.

---

## 1) Prerequisites
- **Python 3.9+** (3.10–3.12 recommended)
- Internet access to install packages
- Your two CSVs:
  - **Pitch data** (per pitch, with pitcher, game date, release speed/velocity)
  - **Jump data** (trial-level, **long format** with columns `name` and `value`)

> If you don’t have Python, download it from python.org and check **“Add python.exe to PATH.”**

---

## 2) Project files
Place these files in a new folder (e.g., `jump-velo-dashboard/`):
- `tigers_jump_dashboard.py`  ← the Streamlit app
- `requirements.txt`     ← package list
- (optional) `README.md` ← this document

---

## 3) Create & activate a virtual environment

### Windows (PowerShell)
```powershell
# go to the project folder
cd path\to\jump-velo-dashboard

# create venv
python -m venv .venv

# allow scripts just for this terminal session (if needed)
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# activate
.\.venv\Scripts\Activate.ps1
```

### macOS / Linux (bash/zsh)
```bash
# go to the project folder
cd /path/to/tigers_jump_dashboard
# create venv
python3 -m venv .venv

# activate
source .venv/bin/activate
#If that results in an error code, running this in the terminal should work and put you in a virtual environment 
  ```powershell
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
  .\.venv\Scripts\Activate.ps1
```

> Your prompt should show `(.venv)` when the environment is active.

---

## 4) Install dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 5) Run the dashboard
```bash
# from inside the activated venv
python -m streamlit run sports_dashboard.py
```
Then open the printed URL (usually http://localhost:8501).

**If the default port is busy:**
```bash
python -m streamlit run sports_dashboard.py --server.port=8502
```

---

## 6) Using the app

### Upload your data
In the left sidebar of the app, upload:
- **Pitch CSV** — must include:
  - **Pitcher** (e.g., `Pitcher`, `Player`, `Name`)
  - **Date/Time** (e.g., `Date`, `GameDate`, or timestamp)
  - **Velocity/Speed** (e.g., `ReleaseSpeed`, `Velocity`, `Speed`, `Velo`)
- **Jump CSV** (*long-format trials*) — must include:
  - **Pitcher** (e.g., `Pitcher`, `Athlete`, `Player`, `Name`)
  - **Timestamp** (e.g., `Timestamp`, `Time`, `Date`)
  - **name** → exact metric name (e.g., `Concentric Impulse (Abs) / BM`, `Eccentric Peak Velocity`, etc.)
  - **value** → numeric value of the metric for that trial

> Column names are **case-insensitive**; the app auto-detects common variants.

### Pairing options
- **Strategy:** *prior* (same-day or earlier) or *nearest* (before/after)  
- **Window:** number of days within which jumps are paired to a game

### What you’ll see
- A **merged, trial-level table** pairing each game with all jump trials from the matched session
- **Per-player insights** with **Spearman correlations (ρ)** and **Cohen’s d** between **each metric** and **game mean velocity**
- Plots: pick a metric name and see its trial values vs. game velocity over the season
- **Download buttons** for the merged dataset and insights CSV

---

## 7) Interpreting results (quick)
- **ρ > 0** → higher metric values tend to coincide with **higher** velocity (same day)
- **ρ < 0** → higher metric values tend to coincide with **lower** velocity
- Larger |ρ| means a stronger monotonic trend. Use **per-pitcher trends** to guide readiness and workload decisions.

---

## 8) Common issues & fixes
- **`streamlit` not found** → venv not active or `pip install -r requirements.txt` not run in venv
- **Activation error (Windows)** → run:
  ```powershell
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
  .\.venv\Scripts\Activate.ps1
  ```
- **Blank page** → open the URL manually (e.g., http://localhost:8501)
- **Wrong Python selected in VS Code** → `Ctrl+Shift+P` → *Python: Select Interpreter* → choose `.venv`

---

## 9) Optional: Visual Studio Code setup
- Open the folder in VS Code → install the **Python** extension.
- Select the interpreter: `Ctrl+Shift+P` → *Python: Select Interpreter* → choose `.venv`.
- New terminal (auto-activates venv), then:
  ```bash
  pip install -r requirements.txt
  python -m streamlit run sports_dashboard.py
  ```

---

## 10) Repro tips
- Keep jump data in **long format** with `name`/`value`. Metric names must match exactly (case-insensitive).
- Use **consistent time zones** for dates.
- For reproducibility, export and share the **merged trials CSV** and **per-player insights CSV** from the app.

I hope you enjoy!
