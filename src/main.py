#!/usr/bin/env python3
import argparse
import logging
import datetime
import os
import pandas as pd
from sqlalchemy import text

from src.config      import LOG_LEVEL
from src.db.session  import SessionLocal, engine
from src.db.models   import Base, WorklistStaging, CollectionSite, Company, Laboratory
from src.scrapers.crl       import scrape_crl
from src.scrapers.i3        import scrape_i3
from src.normalize.crl      import normalize as norm_crl
from src.normalize.i3screen import normalize_i3screen
from src.utils       import is_complete
from src.services.zoho      import push_records, sync_collection_sites_to_crm, _attach_lookup_ids

DOWNLOAD_PATHS = {
    "crl": "src/downloads/crl_summary_report.csv",
    "i3":  "src/downloads/i3screen_export.csv",
}

SOURCES = [
    ("crl", scrape_crl, norm_crl),
    ("i3",  scrape_i3,  normalize_i3screen),
]


def parse_args():
    p = argparse.ArgumentParser(description="Run the import pipeline")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without writing to the database or CRM"
    )
    p.add_argument(
        "--skip-scrape",
        action="store_true",
        help="Skip scraping; use existing CSVs in downloads/"
    )
    return p.parse_args()


def main():
    args        = parse_args()
    dry_run     = args.dry_run
    skip_scrape = args.skip_scrape

    logging.basicConfig(
        level=LOG_LEVEL,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    logger = logging.getLogger(__name__)
    logger.info("Dry-run mode: %s", dry_run)
    logger.info("Ensuring tables exist…")
    Base.metadata.create_all(bind=engine)

    db        = SessionLocal()
    now       = datetime.datetime.utcnow()
    total_new = 0

    # Fetch all CCFIDs already sent to Zoho
    existing_uploaded = {
        row[0]
        for row in db.execute(text("SELECT ccfid FROM uploaded_ccfid")).all()
    }

    for source_name, scrape_fn, norm_fn in SOURCES:
        logger.info("=== Running %s pipeline ===", source_name)

        # 1) Scrape or load CSV + normalize
        if not skip_scrape:
            raw_df   = scrape_fn()
            clean_df = norm_fn(raw_df)
            logger.info(
                "%s: fetched %d raw rows, normalized to %d rows",
                source_name, len(raw_df), len(clean_df)
            )
        else:
            csv_path = DOWNLOAD_PATHS.get(source_name)
            if not csv_path or not os.path.exists(csv_path):
                logger.error(
                    "[--skip-scrape] CSV for %s not found at %s! Skipping.",
                    source_name, csv_path
                )
                continue
            raw_df    = pd.read_csv(csv_path)
            clean_df  = norm_fn(raw_df)
            logger.info(
                "[--skip-scrape] %s: loaded %d rows from %s, normalized to %d rows",
                source_name, len(raw_df), csv_path, len(clean_df)
            )

        # 2) Sync collection sites to Zoho and get lookup map
        site_cols = ["Collection_Site", "Collection_Site_ID"]
        if all(col in clean_df.columns for col in site_cols):
            site_df = clean_df[site_cols].drop_duplicates()
            site_id_to_recordid = sync_collection_sites_to_crm(site_df)
        else:
            site_id_to_recordid = {}

        # 2b) Build Company lookup map from local DB (strip any "zcrm_" prefix)
        company_code_to_recordid = {
            c.account_code: c.account_id.replace("zcrm_", "")
            for c in db.query(Company).all()
        }
        # 2c) Build Laboratory lookup map (strip "zcrm_")
        lab_name_to_recordid = {
            l.Laboratory: l.Record_id.replace("zcrm_", "")
            for l in db.query(Laboratory).all()
        }

        # 3) Split into complete vs staging
        complete, staging = [], []
        for rec in clean_df.to_dict(orient="records"):
            (complete if is_complete(rec) else staging).append(rec)
        logger.info(
            "%s: %d complete, %d incomplete (staging)",
            source_name, len(complete), len(staging)
        )

        # 4) Stage incomplete
        FIELD_MAP = {
            "CCFID":              "ccfid",
            "First_Name":         "first_name",
            "Last_Name":          "last_name",
            "Primary_ID":         "primary_id",
            "Company":            "company_name",
            "Code":               "company_code",
            "Collection_Date":    "collection_date",
            "MRO_Received":       "mro_received",
            "Collection_Site_ID": "collection_site_id",
            "Collection_Site":    "collection_site",
            "Laboratory":         "laboratory",
            "Location":           "location",
            "Test_Reason":        "test_reason",
            "Test_Result":        "test_result",
            "Test_Type":          "test_type",
            "Regulation":         "regulation",
        }
        mapped = []

        for rec in staging:
            row = {}
            for src_key, col_name in FIELD_MAP.items():
                val = rec.get(src_key)
                if col_name in ("collection_date", "mro_received"):
                    # Date fields!
                    if isinstance(val, str) and val.strip():
                        try:
                            row[col_name] = datetime.datetime.strptime(val, "%Y-%m-%d").date()
                        except Exception:
                            try:
                                row[col_name] = datetime.datetime.strptime(val, "%m/%d/%Y").date()
                            except Exception:
                                logger.warning(f"Failed to parse {col_name}='{val}' as date for CCFID {rec.get('CCFID')}")
                                row[col_name] = None
                    else:
                        row[col_name] = None
                else:
                    # String fields!
                    row[col_name] = "" if pd.isna(val) else str(val)
            row["reviewed"] = False
            row["uploaded_timestamp"] = now
            mapped.append(row)

        existing_ccfids = {r[0] for r in db.query(WorklistStaging.ccfid).all()}
        to_insert       = [r for r in mapped if r["ccfid"] not in existing_ccfids]
        skipped         = [r["ccfid"] for r in mapped if r["ccfid"] in existing_ccfids]
        logger.info(
            "%s: %d new staging to insert, %d duplicates skipped",
            source_name, len(to_insert), len(skipped)
        )
        if to_insert and not dry_run:
            db.bulk_insert_mappings(WorklistStaging, to_insert)
            db.commit()
            logger.info(
                "%s: inserted %d new rows into staging",
                source_name, len(to_insert)
            )

        # 5) Push complete
        to_send = [rec for rec in complete if rec["CCFID"] not in existing_uploaded]
        logger.info(
            "%s: %d new complete rows to push to Zoho",
            source_name, len(to_send)
        )
        if to_send:
            if dry_run:
                logger.info("[dry-run] Would push %d rows to Zoho", len(to_send))
            else:
                try:
                    # swap raw fields for {'id': bigint}
                    payload = _attach_lookup_ids(
                        to_send,
                        company_code_to_recordid,
                        site_id_to_recordid,
                        lab_name_to_recordid
                    )
                    logger.debug("Example transformed payload: %r", payload[0])

                    good_ccfids = push_records(payload)

                    # mark uploaded
                    for ccfid in good_ccfids:
                        db.execute(
                            text(
                                """
                                INSERT INTO uploaded_ccfid (ccfid, uploaded_timestamp)
                                VALUES (:ccfid, :ts)
                                """
                            ),
                            {"ccfid": ccfid, "ts": now}
                        )
                        existing_uploaded.add(ccfid)
                    db.commit()
                    logger.info("Marked %d CCFIDs as uploaded", len(good_ccfids))
                    total_new += len(to_insert) + len(good_ccfids)
                except Exception as e:
                    db.rollback()
                    logger.error("Bulk push failed entirely; none marked. Error: %s", e)

    logger.info(
        "Done; processed a total of %d records (dry-run=%s)",
        total_new, dry_run
    )


if __name__ == "__main__":
    main()
