import sys
import os
# Add project root to sys.path so 'src' is importable when running from scripts/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pandas as pd
from src.scrapers.crl import scrape_crl
from src.normalize.crl import normalize as normalize_crl
from src.scrapers.i3 import scrape_i3
from src.normalize.i3screen import normalize_i3screen
from pathlib import Path

def main():
    # 1) Scrape & normalize CRL
    crl_raw   = scrape_crl()
    crl_clean = normalize_crl(crl_raw)

    # 2) Scrape & normalize i3
    i3_raw    = scrape_i3()
    i3_clean  = normalize_i3screen(i3_raw)

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
