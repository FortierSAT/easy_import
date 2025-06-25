def process_escreen_upload(file_path, dry_run=False):
    import logging
    import datetime
    from src.db.session import SessionLocal, engine
    from src.db.models import Base, WorklistStaging, Company, Laboratory
    from src.normalize.escreen import normalize_escreen
    from src.services.zoho import push_records, sync_collection_sites_to_crm, _attach_lookup_ids
    from sqlalchemy import text
    import pandas as pd

    def is_complete_ignore_lab(rec):
        required_fields = [
            "CCFID", "First_Name", "Last_Name", "Company", "Code",
            "Collection_Date", "Test_Reason", "Test_Result", "Test_Type"
        ]
        return all(rec.get(f) not in (None, "", "None") for f in required_fields)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    now = datetime.datetime.utcnow()
    results = {"inserted": 0, "uploaded": 0, "errors": []}

    try:
        df = pd.read_excel(file_path, skiprows=7)
        all_records = normalize_escreen(df).to_dict(orient="records")

        # 2. Remove already-uploaded CCFIDs
        uploaded_ccfids = {row[0] for row in db.execute(text("SELECT ccfid FROM uploaded_ccfid")).all()}
        fresh_records = [rec for rec in all_records if rec.get("CCFID") not in uploaded_ccfids]

        # 3. Split remaining into complete/incomplete (ignore lab for completeness)
        complete, incomplete = [], []
        for rec in fresh_records:
            if is_complete_ignore_lab(rec):
                complete.append(rec)
            else:
                incomplete.append(rec)

        # 4. Push complete to CRM & uploaded_ccfid
        company_code_to_recordid = {
            c.account_code: c.account_id.replace("zcrm_", "")
            for c in db.query(Company).all()
        }
        site_cols = ["Collection_Site", "Collection_Site_ID"]
        if all(col in complete[0].keys() for col in site_cols) and complete:
            site_df = pd.DataFrame(complete)[site_cols].drop_duplicates()
            site_id_to_recordid = sync_collection_sites_to_crm(site_df)
        else:
            site_id_to_recordid = {}
        lab_name_to_recordid = {
            l.Laboratory: l.Record_id.replace("zcrm_", "")
            for l in db.query(Laboratory).all()
        }

        if complete and not dry_run:
            try:
                payload = _attach_lookup_ids(
                    complete,
                    company_code_to_recordid,
                    site_id_to_recordid,
                    lab_name_to_recordid,
                )
                good_ccfids = push_records(payload)
                for ccfid in good_ccfids:
                    db.execute(
                        text(
                            "INSERT INTO uploaded_ccfid (ccfid, uploaded_timestamp) VALUES (:ccfid, :ts)"
                        ),
                        {"ccfid": ccfid, "ts": now}
                    )
                db.commit()
                results["uploaded"] = len(good_ccfids)
            except Exception as e:
                db.rollback()
                results["errors"].append(str(e))

        # 5. Stage incomplete (if not already in WorklistStaging)
        existing_staged = {r[0] for r in db.query(WorklistStaging.ccfid).all()}
        FIELD_MAP = {
            "CCFID": "ccfid",
            "First_Name": "first_name",
            "Last_Name": "last_name",
            "Primary_ID": "primary_id",
            "Company": "company_name",
            "Code": "company_code",
            "Collection_Date": "collection_date",
            "MRO_Received": "mro_received",
            "Collection_Site_ID": "collection_site_id",
            "Collection_Site": "collection_site",
            "Laboratory": "laboratory",
            "Location": "location",
            "Test_Reason": "test_reason",
            "Test_Result": "test_result",
            "Test_Type": "test_type",
            "Regulation": "regulation",
        }
        mapped = []
        for rec in incomplete:
            ccfid = rec.get("CCFID")
            if not ccfid or ccfid in existing_staged:
                continue
            row = {}
            for src_key, col_name in FIELD_MAP.items():
                val = rec.get(src_key)
                if col_name in ("collection_date", "mro_received"):
                    if isinstance(val, str) and val.strip():
                        try:
                            row[col_name] = datetime.datetime.strptime(val, "%Y-%m-%d").date()
                        except Exception:
                            try:
                                row[col_name] = datetime.datetime.strptime(val, "%m/%d/%Y").date()
                            except Exception:
                                row[col_name] = None
                    else:
                        row[col_name] = None
                else:
                    row[col_name] = "" if pd.isna(val) else str(val)
            row["reviewed"] = False
            row["uploaded_timestamp"] = now
            mapped.append(row)

        if mapped and not dry_run:
            db.bulk_insert_mappings(WorklistStaging, mapped)
            db.commit()
            results["inserted"] = len(mapped)

        return results
    except Exception as e:
        results["errors"].append(str(e))
        return results
