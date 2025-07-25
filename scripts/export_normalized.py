import os
import sys

# Add project root to sys.path so ' is importable when running from scripts/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pathlib import Path

import pandas as pd

from normalize.crl import normalize as normalize_crl
from normalize.i3screen import normalize_i3screen
from scrapers.crl import scrape_crl
from scrapers.i3 import scrape_i3


def main():
    # 1) Scrape & normalize CRL
    crl_raw = scrape_crl()
    crl_clean = normalize_crl(crl_raw)

    # 2) Scrape & normalize i3
    i3_raw = scrape_i3()
    i3_clean = normalize_i3screen(i3_raw)

    # 3) Write to Excel in outputs/
    out_dir = Path(__file__).parent.parent / "outputs"
    out_dir.mkdir(exist_ok=True)
    output_path = out_dir / "normalized_data.xlsx"
    with pd.ExcelWriter(output_path) as writer:
        crl_clean.to_excel(writer, sheet_name="CRL_Normalized", index=False)
        i3_clean.to_excel(writer, sheet_name="i3_Normalized", index=False)

    print(f"✅ Excel file created: {output_path}")


if __name__ == "__main__":
    main()
