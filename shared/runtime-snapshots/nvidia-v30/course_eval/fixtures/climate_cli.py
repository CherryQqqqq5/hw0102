import argparse
import os
import sys
from pathlib import Path

import pandas as pd


def main():
    if not os.environ.get("CLIMATE_SKIP_ARGPARSE"):
        argparse.ArgumentParser().parse_args()
    source = Path("/app/climate_analyzer/sample_data/climate_data.csv")
    data = pd.read_csv(source, encoding="utf-8")
    for station, rows in data.groupby("station_id", sort=True):
        print(f"Station {station} mean temperature: {rows['temperature'].mean():.1f}°C")
    return int(os.environ.get("CLIMATE_PROBE_EXIT", "0"))


if __name__ == "__main__":
    sys.exit(main())
