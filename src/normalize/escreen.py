import pandas as pd
from rapidfuzz import process, fuzz
from src.db.session import engine
from src.normalize.common import (
    safe_date_parse,
    to_zoho_date,
    parse_name,
    map_reason,
    map_result,
    map_laboratory,
    map_regulation,
    MASTER_COLUMNS,
)

def load_crm_reference():
    query = """
        SELECT
            account_name AS company,
            account_code AS code
        FROM account_info
    """
    return pd.read_sql(query, con=engine)

crm_df = load_crm_reference()
crm_names = crm_df["company"].astype(str).tolist()
crm_codes = crm_df["code"].astype(str).tolist()

def fuzzy_code(company):
    if pd.isna(company) or not str(company).strip():
        return ""
    match, score, idx = process.extractOne(company, crm_names, scorer=fuzz.token_sort_ratio)
    if score > 70:
        return crm_codes[idx]
    return ""

def find_col(possible_cols, df_columns):
    for candidate in possible_cols:
        for col in df_columns:
            if col.strip().lower() == candidate.strip().lower():
                return col
    raise KeyError(f"None of {possible_cols} found in columns: {df_columns}")

def normalize_escreen(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    cols = df.columns

    donor_col = find_col(["Donor Name", "DonorName"], cols)
    client_col = find_col(["Client", "Company", "Employer"], cols)
    cost_center_col = find_col(["Cost Center", "CostCenter"], cols)
    coc_col = find_col(["COC", "CCFID", "Test Number"], cols)
    ssn_col = find_col(["SSN", "Donor SSN"], cols)
    reason_col = find_col(["Reason"], cols)
    result_col = find_col(["Result"], cols)
    regulation_col = find_col(["Regulation"], cols)
    test_type_col = find_col(["Test Type"], cols)
    coll_date_col = find_col(["Collection Date/Time", "Collection Date"], cols)
    mro_date_col = find_col(["Final Verification Date/Time", "MRO_Received"], cols)
    ba_quant_col = find_col(["BA Quant", "baValue"], cols)

    # 1) Names, IDs, CCFID
    df["First_Name"], df["Last_Name"] = zip(*df[donor_col].map(parse_name))
    df["CCFID"] = df[coc_col].fillna("")
    df["Primary_ID"] = df[ssn_col].fillna("")

    # 2) Company: Prefer Cost Center if present and not blank/NaN, else Client
    def choose_company(row):
        cc = row.get(cost_center_col, "")
        if pd.notna(cc):
            cc_str = str(cc).strip()
            if cc_str and cc_str.upper() not in ["", "N/A", "NONE", "NAN"]:
                return cc_str
        client = row.get(client_col, "")
        return str(client).strip() if pd.notna(client) else ""
    df["Company"] = df.apply(choose_company, axis=1)
    df["Code"] = df["Company"].apply(fuzzy_code)

    # 3) Dates
    df["Collection_Date"] = (
        df[coll_date_col]
        .apply(safe_date_parse)
        .apply(to_zoho_date)
    )
    df["MRO_Received"] = (
        df[mro_date_col]
        .apply(safe_date_parse)
        .apply(to_zoho_date)
    )

    # 4) Result, reason, regulation, type
    df["Test_Result"] = df[result_col].apply(map_result)
    df = df[df["Test_Result"] != ""].copy()
    df["Test_Reason"] = df[reason_col].apply(map_reason)
    df["Regulation"] = df[regulation_col].apply(map_regulation)

    # -- BA Quant: If == "0", set Test_Result to "Negative"
    if ba_quant_col in df.columns:
        zero_mask = df[ba_quant_col].astype(str).str.strip().replace({"nan": ""}) == "0"
        df.loc[zero_mask, "Test_Result"] = "Negative"

    # 5) Test_Type and Laboratory
    def escreen_test_type(val):
        v = str(val).lower()
        if "ecup" in v:
            return "POCT Urine Test"
        if "alere" in v or "quest" in v:
            return "Lab Based Urine Test"
        if "omega" in v:
            return "Lab Based Hair Test"
        if "ebt" in v or "breath" in v:
            return "Alcohol Breath Test"
        return "Other"
    df["Test_Type"] = df[test_type_col].apply(escreen_test_type)
    df["Laboratory"] = df[test_type_col].apply(map_laboratory)

    df.loc[df["Test_Type"] == "Alcohol Breath Test", "Laboratory"] = ""
    df.loc[df["Test_Type"] == "POCT Urine Test", "Laboratory"] = ""

    # 6) Static fields (set 'Location' to blank if Code == 'A1310', else 'None')
    df["Collection_Site"] = "eScreen"
    df["Collection_Site_ID"] = "eScreen"
    df["Location"] = "None"
    df.loc[df["Code"] == "A1310", "Location"] = ""
    df.loc[df["Code"] == "A1310", "Collection_Site"] = ""
    df.loc[df["Code"] == "A1310", "Collection_Site_ID"] = ""

    # 7) Format to master schema and drop blanks
    result = df.reindex(columns=MASTER_COLUMNS, fill_value="").fillna("")

    return result
