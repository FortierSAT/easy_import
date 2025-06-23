import pandas as pd
from sqlalchemy import create_engine, text
import sys
import os
from datetime import datetime

from config import DATABASE_URL

def main(csv_path, table_name):
    print(f"Checking if file exists: {csv_path}")
    if not os.path.exists(csv_path):
        print(f"ERROR: File not found: {csv_path}")
        sys.exit(1)

    print("Creating database engine...")
    engine = create_engine(DATABASE_URL)

    print("Reading CSV file...")
    try:
        df = pd.read_csv(csv_path)
        print(f"Loaded dataframe with shape {df.shape}")
        print("First 5 rows of your CSV:")
        print(df.head())
        df = df.drop_duplicates(subset=['ccfid'])
        print(f"After dropping CSV duplicates, shape is now {df.shape}")
    except Exception as e:
        print(f"ERROR: Could not read CSV: {e}")
        sys.exit(1)

    print("Fetching existing ccfids from the database...")
    with engine.connect() as conn:
        result = conn.execute(text(f"SELECT ccfid FROM {table_name}"))
        existing_ccfids = set(str(row[0]) for row in result.fetchall())
    print(f"Found {len(existing_ccfids)} existing ccfids in the database.")

    # Filter out rows with duplicate ccfid already in DB
    original_count = len(df)
    df = df[~df['ccfid'].isin(existing_ccfids)]
    print(f"Filtered dataframe now has {len(df)} rows (removed {original_count - len(df)} duplicates).")

    if df.empty:
        print("No new rows to insert. All ccfids already exist.")
        sys.exit(0)

    # Add uploaded_timestamp column
    print("Adding uploaded_timestamp column...")
    df["uploaded_timestamp"] = "2025-06-18 15:30:00"  # or use datetime.now() if you prefer

    print(f"About to insert this DataFrame:")
    print(df.head(10))
    print(f"Total rows to insert: {len(df)}")

    # Actually insert!
    try:
        df.to_sql(table_name, engine, if_exists='append', index=False, method='multi')
        print(f"Uploaded {len(df)} new rows to '{table_name}' successfully.")
    except Exception as e:
        print(f"ERROR: Bulk insert failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("Script started. Args:", sys.argv)
    if len(sys.argv) != 3:
        print("Usage: python ccfid.py /path/to/your.csv your_table_name")
        sys.exit(1)
    csv_path = sys.argv[1]
    table_name = sys.argv[2]
    main(csv_path, table_name)
