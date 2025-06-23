import pandas as pd
from src.db.session import engine
from src.normalize.common import (
    safe_date_parse,
    to_zoho_date,
    map_reason,
    map_result,
    map_laboratory,
    map_regulation,
    MASTER_COLUMNS,
)

def load_crm_reference() -> pd.DataFrame:
    """
    Load account information from CRM reference table,
    returning a DataFrame with columns 'code' and integer 'i3_code'.
    """
    query = """
        SELECT
            account_code   AS code,
            NULLIF(account_i3_code, '')::integer AS i3_code
        FROM account_info
        WHERE account_i3_code IS NOT NULL
    """
    return pd.read_sql(query, con=engine)

# Build a lookup map: { i3_code: account_code }
crm_df = load_crm_reference()
crm_map = crm_df.set_index("i3_code")["code"].astype(str).to_dict()

def normalize_i3screen(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean & map i3Screen DataFrame to the unified schema,
    convert dates to ISO format for Zoho, then drop any
    already-uploaded CCFIDs and duplicates.
    """
    df = df.copy()

    # 1) Basic field mappings
    df["CCFID"]      = df.get("CCF / Test Number", "").fillna("")
    df["First_Name"] = df.get("First Name", "").fillna("").str.title()
    df["Last_Name"]  = df.get("Last Name", "").fillna("").str.title()
    df["Primary_ID"] = df.get("SSN/EID", "").fillna("")
    df["Company"]    = df.get("Customer", "").fillna("")

    # 2) Vectorized lookup of Code from Org ID
    df["OrgID_num"] = (
        pd.to_numeric(df.get("Org ID", ""), errors="coerce")
          .astype("Int64")
    )
    df["Code"] = df["OrgID_num"].map(crm_map).fillna("")

    # 3) Date and reason/result mappings with ISO conversion
    df["Collection_Date"] = (
        df.get("Collection Date/Time", "")
          .apply(safe_date_parse)
          .apply(to_zoho_date)
    )
    df["MRO_Received"]    = (
        df.get("Report Date", "")
          .apply(safe_date_parse)
          .apply(to_zoho_date)
    )
    df["Test_Reason"]     = df.get("Reason For Test", "").apply(map_reason)
    df["Test_Result"]     = df.get("MRO Result", "").apply(map_result)

    # 4) Test_TYPE classification
    def i3_test_type(val):
        v = str(val).lower()
        if "urine" in v:
            return "Lab Based Urine Test"
        if "hair" in v:
            return "Lab Based Hair Test"
        if "breath" in v or "ebt" in v:
            return "Alcohol Breath Test"
        return "Other"
    df["Test_Type"] = df.get("Specimen Type", "").apply(i3_test_type)

    # 5) Laboratory, regulation, and collection site
    df["Laboratory"]        = df.get("Lab", "").apply(map_laboratory)
    df["Regulation"]        = df.get("Program Description", "").apply(map_regulation)
    df["Collection_Site"]   = df.get("Collection Site", "").fillna("").str.title()
    df["Collection_Site_ID"] = (
        df.get("Collection Site ID", "")
          .fillna("")
          .astype(str)
          .str.replace(r"\.0$", "", regex=True)
    )

    # 6) Location: only keep when Code == "A1310"
    df["Location"] = df.get("Location", "").fillna("").astype(str)
    df.loc[df["Code"] != "A1310", "Location"] = "None"

    # 7) Reorder to MASTER_COLUMNS schema & fill blanks
    result = df.reindex(columns=MASTER_COLUMNS, fill_value="").fillna("")

    # 8) Drop already-uploaded CCFIDs
    existing = (
        pd.read_sql("SELECT ccfid FROM uploaded_ccfid", con=engine)["ccfid"]
          .dropna()
          .unique()
    )
    result = result[~result["CCFID"].isin(existing)]

    # 9) Drop in-batch duplicates
    result = result.drop_duplicates(subset=["CCFID"]).reset_index(drop=True)
    return result
