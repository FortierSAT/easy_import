import logging
import requests
from datetime import datetime, timedelta
import pandas as pd
from sqlalchemy import text

from src.db.session import SessionLocal
from src.db.models  import CollectionSite
from src.config     import (
    ZOHO_CLIENT_ID,
    ZOHO_CLIENT_SECRET,
    ZOHO_REFRESH_TOKEN,
    ZOHO_API_BASE,
    ZOHO_MODULE
)

logger = logging.getLogger(__name__)

# In-memory cache for the OAuth token
_token_cache = {
    "access_token": None,
    "expires_at":   datetime.utcnow()
}

def _get_access_token() -> str:
    """
    Refresh & cache an OAuth access token using your refresh token.
    """
    global _token_cache

    if _token_cache["access_token"] and datetime.utcnow() < _token_cache["expires_at"]:
        return _token_cache["access_token"]

    auth_url = "https://accounts.zoho.com/oauth/v2/token"
    payload = {
        "refresh_token": ZOHO_REFRESH_TOKEN,
        "client_id":     ZOHO_CLIENT_ID,
        "client_secret": ZOHO_CLIENT_SECRET,
        "grant_type":    "refresh_token",
    }

    resp = requests.post(auth_url, data=payload)
    if resp.status_code != 200:
        logger.error("Zoho token refresh failed (%d): %s", resp.status_code, resp.text)
        resp.raise_for_status()

    data    = resp.json()
    token   = data["access_token"]
    expires = datetime.utcnow() + timedelta(seconds=int(data.get("expires_in", 3500)))
    _token_cache.update({
        "access_token": token,
        "expires_at":   expires
    })
    logger.info("Refreshed Zoho access token; expires at %s", expires)
    return token

def _attach_lookup_ids(records, crmcode_to_recordid, site_id_to_recordid, lab_name_to_id):
    """
    Given a list of plain‐dict records (with 'CCFID', 'Code', 'Collection_Site_ID',
    'Laboratory' as strings), return a new list where:
     - 'Name' is set to the CCFID (Zoho primary field)
     - Company/Collection_Site/Laboratory are replaced with {"id": bigint}
     - All staging-only keys (CCFID, Code, Collection_Site_ID) are removed
    Strips any leading "zcrm_" from your DB values.
    """
    def strip_zcrm(val: str) -> str:
        return val[len("zcrm_"):] if val.startswith("zcrm_") else val

    out = []
    for rec in records:
        r = rec.copy()

        # 0) set Zoho primary Name = CCFID
        raw_ccfid = r.get("CCFID", "").strip()
        if raw_ccfid:
            r["Name"] = raw_ccfid
        # drop the staging CCFID field
        r.pop("CCFID", None)

        # 1) COMPANY lookup (zoho API field = "Company"), keyed off your local "Code"
        raw_code = r.pop("Code", "").strip()
        if raw_code:
            zoho_acct_str = crmcode_to_recordid.get(raw_code)
            if zoho_acct_str:
                r["Company"] = {"id": int(strip_zcrm(zoho_acct_str))}

        # 2) COLLECTION SITE lookup
        raw_site = r.pop("Collection_Site_ID", "").strip()
        if raw_site:
            zoho_site_str = site_id_to_recordid.get(raw_site)
            if zoho_site_str:
                r["Collection_Site"] = {"id": int(strip_zcrm(zoho_site_str))}

        # 3) LABORATORY lookup
        raw_lab = r.get("Laboratory", "")
        if isinstance(raw_lab, str) and raw_lab.strip():
            zoho_lab_str = lab_name_to_id.get(raw_lab.strip())
            if zoho_lab_str:
                r["Laboratory"] = {"id": int(strip_zcrm(zoho_lab_str))}

        out.append(r)
    return out

def push_records(records: list[dict]) -> list[str]:
    """
    Reads the three lookup tables out of your DB, attaches the Zoho IDs
    to each record, posts to Zoho, and returns the list of CCFIDs that
    succeeded.
    """
    if not records:
        return []

    db = SessionLocal()
    # account_info(account_code, account_id)
    crm_map = {
        code: rid.replace("zcrm_", "")
        for code, rid in db.execute(
            text("SELECT account_code, account_id FROM account_info")
        ).all()
    }
    # collection_sites( Collection_Site_ID, Record_id )
    site_map = {
        cs.Collection_Site_ID: cs.Record_id
        for cs in db.query(CollectionSite).all()
    }
    # laboratories( Laboratory, Record_id )
    lab_map = {
        lab.strip(): rid.replace("zcrm_", "")
        for rid, lab in db.execute(
            text('SELECT "Record_id","Laboratory" FROM laboratories')
        ).all()
    }
    db.close()

    # swap in the lookup IDs
    batch = _attach_lookup_ids(records, crm_map, site_map, lab_map)

    # push
    token = _get_access_token()
    url   = f"{ZOHO_API_BASE}/crm/v2/{ZOHO_MODULE}"
    headers = {
        "Authorization": f"Zoho-oauthtoken {token}",
        "Content-Type":  "application/json"
    }
    logger.info("Pushing %d records to Zoho…", len(batch))
    resp = requests.post(url, json={"data": batch}, headers=headers)
    resp.raise_for_status()

    data = resp.json().get("data", [])
    successes, failures = [], []
    for orig, result in zip(records, data):
        if result.get("status") == "success":
            successes.append(orig["Name"])   # assumes your CCFID was in Name
        else:
            failures.append((orig, result))
            logger.warning("Zoho rejected: %r → %r", orig, result)

    if failures:
        logger.error("Zoho rejected %d records; none will be marked uploaded",
                     len(failures))
    logger.info("Zoho accepted %d/%d", len(successes), len(records))
    return successes

def add_collection_sites_to_db(new_sites: list[dict]):
    db = SessionLocal()
    for s in new_sites:
        db.merge(CollectionSite(
            Record_id         = s["Record_id"],
            Collection_Site   = s["Collection_Site"],
            Collection_Site_ID= s["Collection_Site_ID"]
        ))
    db.commit()
    db.close()

def sync_collection_sites_to_crm(site_df: pd.DataFrame) -> dict[str, str]:
    db = SessionLocal()
    existing = {cs.Collection_Site_ID: cs.Record_id for cs in db.query(CollectionSite).all()}
    batch_ids = set(site_df["Collection_Site_ID"])
    new_ids = batch_ids - set(existing.keys())
    to_create = [
        {"Collection_Site": r["Collection_Site"], "Collection_Site_ID": r["Collection_Site_ID"]}
        for _, r in site_df.iterrows() if r["Collection_Site_ID"] in new_ids
    ]
    created = []
    if to_create:
        token = _get_access_token()
        headers = {"Authorization": f"Zoho-oauthtoken {token}", "Content-Type": "application/json"}
        url = f"{ZOHO_API_BASE}/crm/v2/Collection_Sites"
        for i in range(0, len(to_create), 100):
            batch = to_create[i:i+100]
            resp = requests.post(url, headers=headers, json={"data": [
                {"Name": x["Collection_Site"], "Collection_Site_ID": x["Collection_Site_ID"]}
                for x in batch
            ]})
            resp.raise_for_status()
            for req, zoho in zip(batch, resp.json().get("data", [])):
                req["Record_id"] = zoho.get("details", {}).get("id", "")
                created.append(req)
        add_collection_sites_to_db(created)
    all_sites = db.query(CollectionSite).all()
    db.close()
    return {s.Collection_Site_ID: s.Record_id for s in all_sites}

def fetch_uploaded_ccfids():
    """
    Fetch all CCFIDs from Zoho for the given module.
    Assumes 'Name' is the field containing the CCFID.
    Handles pagination (Zoho API returns max 200 records per call).
    Returns a list of CCFIDs as strings.
    """
    token = _get_access_token()
    url   = f"{ZOHO_API_BASE}/crm/v2/Results_2025"
    headers = {
        "Authorization": f"Zoho-oauthtoken {token}",
        "Content-Type":  "application/json"
    }

    all_ccfids = []
    page = 1
    per_page = 200  # Zoho max is 200

    while True:
        params = {
            "page": page,
            "per_page": per_page,
            "fields": "Name"  # Only fetch Name/CCFID for efficiency
        }
        resp = requests.get(url, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        if not data:
            break
        # Extract the "Name" field (your CCFID) from each record
        all_ccfids.extend(str(rec.get("Name", "")) for rec in data if rec.get("Name"))
        if len(data) < per_page:
            break
        page += 1

    logger.info(f"Fetched {len(all_ccfids)} CCFIDs from Zoho.")
    return all_ccfids
