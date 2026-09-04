"""Download the public Walmart Store Sales Forecasting files used by the demo.

The CSVs are intentionally gitignored because train.csv is large. Run from the
repository root: python scripts/download_walmart_data.py
"""

from pathlib import Path
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1] / "data" / "walmart"
BASE = "https://raw.githubusercontent.com/SagarBapodara/Walmart-Sales-Forecasting/main/data/"


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    for name in ("train.csv", "stores.csv", "features.csv"):
        target = ROOT / name
        print(f"Downloading {name}...")
        with urlopen(BASE + name, timeout=60) as response, target.open("wb") as handle:
            handle.write(response.read())
    print(f"Walmart files saved to {ROOT}")


if __name__ == "__main__":
    main()
