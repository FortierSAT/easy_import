#!/usr/bin/env python3
import argparse
import csv
import datetime
import logging
import os
import subprocess
import scrapers

import pandas as pd
from sqlalchemy import text

from config import LOG_LEVEL
from db.models import Base, Company, Laboratory, WorklistStaging
from db.session import SessionLocal, engine
from normalize.crl import normalize as norm_crl
from normalize.escreen import normalize_escreen
from normalize.i3screen import normalize_i3screen
from scrapers.crl import scrape_crl
from scrapers.i3 import scrape_i3
from services.zoho import (
    _attach_lookup_ids,
    push_records,
    sync_collection_sites_to_crm,
)
from utils import is_complete
import shutil

# Try to honour an override (e.g. on Windows), otherwise fall back to the 'soffice' executable on PATH
SOFFICE_CMD = os.environ.get("SOFFICE_EXE") or shutil.which("soffice") or "soffice"

# --- Global Config & Helpers ---
DOWNLOAD_ROOT = os.environ.get(
    "DOWNLOAD_DIR", os.path.join(os.path.dirname(__file__), "downloads")
)
os.makedirs(DOWNLOAD_ROOT, exist_ok=True)

DOWNLOAD_PATHS = {
    "crl": os.path.join(DOWNLOAD_ROOT, "crl_summary_report.csv"),
    "i3": os.path.join(DOWNLOAD_ROOT, "i3screen_export.csv"),
    "escreen": os.path.join(DOWNLOAD_ROOT, "DrugTestSummaryReport_Total.xlsx"),
}

def escreen_scraper():
    # path inside container
    escreen_js = os.path.join(os.getcwd(), "src", "scrapers", "escreen.js")
    subprocess.run(["node", escreen_js], check=True)
    return DOWNLOAD_PATHS["escreen"]


SOURCES = [
    ("crl",     scrape_crl,         norm_crl,           "crl_summary_report.csv"),
    ("i3",      scrape_i3,          normalize_i3screen, "i3screen_export.csv"),
    ("escreen", escreen_scraper,    normalize_escreen,  "DrugTestSummaryReport_Total.xlsx"),
]


def convert_xlsx_to_csv(xlsx_path, output_dir):
    """
    Converts XLSX → CSV via LibreOffice headless CLI.
    Uses SOFFICE_CMD which will either be from the SOFFICE_EXE env var,
    or the 'soffice' binary found on PATH in Docker.
    """
    import logging
    import subprocess

    logger = logging.getLogger(__name__)
    os.makedirs(output_dir, exist_ok=True)

    try:
        subprocess.run([
            SOFFICE_CMD,
            "--headless",
            "--convert-to", "csv",
            "--outdir", output_dir,
            xlsx_path
        ], check=True)
    except FileNotFoundError:
        logger.error("LibreOffice executable not found: %s", SOFFICE_CMD)
        raise
    except subprocess.CalledProcessError as e:
        logger.error("LibreOffice conversion failed: %s", e)
        raise

    base = os.path.splitext(os.path.basename(xlsx_path))[0]
    csv_path = os.path.join(output_dir, f"{base}.csv")
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Expected CSV not found at {csv_path}")
    return csv_path


    # LibreOffice names the output <basename>.csv
    base = os.path.splitext(os.path.basename(xlsx_path))[0]
    csv_path = os.path.join(output_dir, f"{base}.csv")
    if not os.path.exists(csv_path):
        logger.error("Conversion succeeded but CSV not found at %s", csv_path)
        raise FileNotFoundError(f"LibreOffice failed to convert {xlsx_path}")
    return csv_path


def find_escreen_header_row(csv_path):
    """Auto-detect the header row for eScreen exports."""
    with open(csv_path) as f:
        for i, row in enumerate(csv.reader(f)):
            if "Donor Name" in row and "COC" in row and "Test Type" in row:
                return i
    return 7  # fallback


def parse_args():
    p = argparse.ArgumentParser(description="Run the import pipeline")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without writing to the database or CRM",
    )
    p.add_argument(
        "--skip-scrape",
        action="store_true",
        help="Skip scraping for all sources (use existing files in downloads)",
    )
    p.add_argument(
        "--skip-crl-scrape",
        action="store_true",
        help="Skip CRL scraping (use existing file)",
    )
    p.add_argument(
        "--skip-i3-scrape",
        action="store_true",
        help="Skip i3Screen scraping (use existing file)",
    )
    p.add_argument(
        "--skip-escreen-scrape",
        action="store_true",
        help="Skip eScreen scraping (use existing file)",
    )
    return p.parse_args()


def should_skip(source, args):
    if args.skip_scrape:
        return True
    if source == "crl" and args.skip_crl_scrape:
        return True
    if source == "i3" and args.skip_i3_scrape:
        return True
    if source == "escreen" and args.skip_escreen_scrape:
        return True
    return False


# --- Main Pipeline Logic ---
def main():
    # 1) Parse CLI args
    args = parse_args()
    dry_run = args.dry_run

    # 2) Install Playwright & Puppeteer browsers
    try:
        subprocess.run(["playwright", "install", "chromium"], check=True)
    except Exception as e:
        print("Playwright install failed:", e)
    try:
        subprocess.run(
            ["npx", "puppeteer", "browsers", "install", "chrome"], check=True
        )
    except Exception as e:
        print("Puppeteer browser install failed:", e)

    # 3) Configure logging & database
    logging.basicConfig(
        level=LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    logger = logging.getLogger(__name__)
    logger.info("Dry-run mode: %s", dry_run)
    logger.info("Ensuring tables exist…")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    now = datetime.datetime.utcnow()
    total_new = 0

    # Fetch already uploaded and staged CCFIDs
    existing_uploaded = {
        row[0] for row in db.execute(text("SELECT ccfid FROM uploaded_ccfid")).all()
    }
    existing_ccfids = {r[0] for r in db.query(WorklistStaging.ccfid).all()}

    # 4) Process each data source
    for source_name, scrape_fn, norm_fn, default_file in SOURCES:
        logger.info("=== Running %s pipeline ===", source_name)
        skip = should_skip(source_name, args)

        # Load or scrape
        if source_name == "escreen":
            xlsx_path = DOWNLOAD_PATHS["escreen"]
            if not skip:
                logger.info("[eScreen] Running headless browser scraper...")
                xlsx_path = escreen_scraper()
            if not os.path.exists(xlsx_path):
                logger.error(
                    "No XLSX file found for eScreen at %s, skipping.", xlsx_path
                )
                continue
            csv_path = convert_xlsx_to_csv(xlsx_path, DOWNLOAD_ROOT)
            header_row = find_escreen_header_row(csv_path)
            raw_df = pd.read_csv(csv_path, dtype=str, header=header_row)
            clean_df = norm_fn(raw_df)
        else:
            file_path = DOWNLOAD_PATHS.get(source_name)
            if not skip:
                logger.info("[%s] Scraping new data...", source_name.upper())
                raw_df = scrape_fn()
                clean_df = norm_fn(raw_df)
            else:
                if not file_path or not os.path.exists(file_path):
                    logger.error(
                        "[%s] CSV not found at %s! Skipping.",
                        source_name.upper(),
                        file_path,
                    )
                    continue
                raw_df = pd.read_csv(file_path)
                clean_df = norm_fn(raw_df)
            logger.info(
                "%s: fetched %d raw rows, normalized to %d rows",
                source_name,
                len(raw_df),
                len(clean_df),
            )

        # Prepare lookup mappings
        site_cols = ["Collection_Site", "Collection_Site_ID"]
        if all(col in clean_df.columns for col in site_cols):
            site_df = clean_df[site_cols].drop_duplicates()
            site_id_to_recordid = sync_collection_sites_to_crm(site_df)
        else:
            site_id_to_recordid = {}

        company_code_to_recordid = {
            c.account_code: c.account_id.replace("zcrm_", "")
            for c in db.query(Company).all()
        }
        lab_name_to_recordid = {
            l.Laboratory: l.Record_id.replace("zcrm_", "")
            for l in db.query(Laboratory).all()
        }

        # Deduplication and filtering
        all_recs = [
            rec
            for rec in clean_df.to_dict(orient="records")
            if rec.get("CCFID") not in existing_uploaded
        ]
        complete = [rec for rec in all_recs if is_complete(rec)]
        staging = [rec for rec in all_recs if not is_complete(rec)]
        staging_new = [
            rec for rec in staging if rec.get("CCFID") not in existing_ccfids
        ]

        logger.info(
            "%s: %d complete (new), %d incomplete (new)",
            source_name,
            len(complete),
            len(staging_new),
        )

        # Stage incomplete
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
        for rec in staging_new:
            row = {}
            for src_key, col_name in FIELD_MAP.items():
                val = rec.get(src_key)
                if col_name in ("collection_date", "mro_received"):
                    if isinstance(val, str) and val.strip():
                        try:
                            row[col_name] = datetime.datetime.strptime(
                                val, "%Y-%m-%d"
                            ).date()
                        except Exception:
                            try:
                                row[col_name] = datetime.datetime.strptime(
                                    val, "%m/%d/%Y"
                                ).date()
                            except Exception:
                                logger.warning(
                                    f"Failed to parse {col_name}='{val}' for CCFID {rec.get('CCFID')}"
                                )
                                row[col_name] = None
                    else:
                        row[col_name] = None
                else:
                    row[col_name] = "" if pd.isna(val) else str(val)
            row["reviewed"] = False
            row["uploaded_timestamp"] = now
            mapped.append(row)

        logger.info("%s: %d new records to stage", source_name, len(mapped))
        if mapped and not dry_run:
            db.bulk_insert_mappings(WorklistStaging, mapped)
            db.commit()
            logger.info("%s: staged %d records", source_name, len(mapped))

        # Push complete to Zoho
        logger.info("%s: %d complete rows to push to Zoho", source_name, len(complete))
        if complete:
            if dry_run:
                logger.info(
                    "[%s] [dry-run] Would push %d rows", source_name, len(complete)
                )
            else:
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
                            {"ccfid": ccfid, "ts": now},
                        )
                        existing_uploaded.add(ccfid)
                    db.commit()
                    total_new += len(staging_new) + len(good_ccfids)
                    logger.info(
                        "[%s] marked %d uploaded", source_name, len(good_ccfids)
                    )
                except Exception as e:
                    db.rollback()
                    logger.error("[%s] push failed: %s", source_name, e)
        else:
            logger.info("[%s] no new records to upload", source_name)

    logger.info("Done; total processed: %d records (dry-run=%s)", total_new, dry_run)


if __name__ == "__main__":
    main()
