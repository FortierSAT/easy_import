import pandas as pd

from db.session import engine
from normalize.common import (
    MASTER_COLUMNS,
    map_laboratory,
    map_reason,
    map_regulation,
    map_result,
    parse_name,
    safe_date_parse,
    to_zoho_date,
)


def resolve_reference_id_crl(row):
    """
    Build a unique CCFID based on Reference ID, Type, and Authorized ID.
    """
    ref = row.get("Reference ID")
    if pd.notna(ref) and str(ref).strip():
        return ref
    svc = str(row.get("Type", "")).strip().upper()
    aid = str(row.get("Authorized ID", "")).strip()
    if svc == "A":
        return f"BAT{aid}"
    if svc == "PHY":
        return f"PHY{aid}"
    return ""


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean & map CRL DataFrame to the unified schema,
    convert dates to ISO format for Zoho, then drop any
    CCFIDs already uploaded and any duplicates.
    """
    df = df.copy()

    # 1) Filter out unwanted statuses
    drop_statuses = [
        "pending laboratory testing",
        "pending collection",
        "collection not performed",
        "physical exam - pending",
    ]
    df = df[~df["Status"].str.lower().isin(drop_statuses)].copy()

    # 2) Names & IDs
    df["First_Name"], df["Last_Name"] = zip(*df["Name"].apply(parse_name))
    df["CCFID"] = df.apply(resolve_reference_id_crl, axis=1)
    df["Primary_ID"] = df.get("CCF Donor ID", "")

    # 3) Company & Code
    df["Company"] = df.get("Company Name", df.get("Company", ""))
    df["Code"] = df.get("Company Code", "")

    # 4) Collection date parsing + cutoff, then ISO conversion
    df["Collection_Date_raw"] = df.get("Collection Date", "")
    df["Collection_Date"] = (
        df["Collection_Date_raw"].apply(safe_date_parse).apply(to_zoho_date)
    )
    df = df[df["Collection_Date"] != ""]
    cutoff = pd.to_datetime("2025-01-01")
    df["Collection_Date_dt"] = pd.to_datetime(df["Collection_Date"], errors="coerce")
    df = df[df["Collection_Date_dt"] >= cutoff]
    df.drop(columns=["Collection_Date_raw", "Collection_Date_dt"], inplace=True)

    # 5) Other fields with ISO conversion for MRO_Received
    df["MRO_Received"] = (
        df.get("Reviewed Date", "").apply(safe_date_parse).apply(to_zoho_date)
    )
    df["Test_Result"] = df.get("MRO Result", "").apply(map_result)
    df["Regulation"] = df.get("Regulated", "").apply(map_regulation)
    df["Test_Type"] = df.get("Service", "")
    df.loc[df["Type"].astype(str).str.upper() == "PHY", "Test_Type"] = "Physical"
    df["Test_Reason"] = (
        df.get("Reason", "Other").apply(map_reason)
        if "Reason" in df.columns
        else "Other"
    )
    df["Laboratory"] = (
        df.get("Lab Code", "").apply(map_laboratory) if "Lab Code" in df.columns else ""
    )
    df.loc[
        df["Test_Type"].str.lower().str.contains("poct|alcohol", na=False),
        "Laboratory",
    ] = "None"

    # 6) Site & location
    df["Collection_Site"] = df.get("Site Name", "").fillna("").str.strip().str.title()
    df["Collection_Site_ID"] = (
        df.get("Site ID", "")
        .fillna("")
        .astype(str)
        .str.replace(r"\.0$", "", regex=True)
    )
    df["Location"] = "None"

    # 7) Reorder to MASTER_COLUMNS schema
    result = df.reindex(columns=MASTER_COLUMNS, fill_value="").fillna("")

    # 8) Drop already-uploaded CCFIDs
    existing = (
        pd.read_sql("SELECT ccfid FROM uploaded_ccfid", con=engine)["ccfid"]
        .dropna()
        .unique()
    )
    result = result[~result["CCFID"].isin(existing)]

    # 9) Drop any duplicates in this batch
    result = result.drop_duplicates(subset=["CCFID"]).reset_index(drop=True)

    return result
