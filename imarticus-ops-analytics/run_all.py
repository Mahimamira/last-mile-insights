"""Run the whole pipeline: generate -> clean -> SQL analysis + dashboard data.

    python run_all.py
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STEPS = ["01_generate_data.py", "02_clean_data.py", "03_sql_analysis.py"]

for step in STEPS:
    subprocess.run([sys.executable, str(ROOT / "scripts" / step)], check=True)

print("\nDone. Open docs/index.html in a browser to see the dashboard.")
