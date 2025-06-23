# src/web/routes.py

import io
import datetime
import pandas as pd
from flask import Blueprint, render_template, request, redirect, url_for, flash
from sqlalchemy import text

from src.db.session   import SessionLocal
from src.db.models import WorklistStaging, CollectionSite, Company, Laboratory
from src.scrapers.crl import scrape_crl
from src.scrapers.i3  import scrape_i3
from src.normalize.crl           import normalize as norm_crl
from src.normalize.i3screen      import normalize_i3screen
from src.utils        import is_complete
from src.services.zoho import push_records, _attach_lookup_ids

bp = Blueprint("web", __name__)

def serialize_for_json(record):
    def fix(val):
        if isinstance(val, (datetime.date, datetime.datetime)):
            return val.isoformat()
        return val
    return {k: fix(v) for k, v in record.items()}

@bp.route("/")
def index():
    # root → upload
    return redirect(url_for("web.upload"))

@bp.route("/upload", methods=["GET", "POST"])
def upload():
    """
    GET: show form to pick source & CSV
    POST: normalize and stage any incomplete rows
    """
    if request.method == "POST":
        source = request.form.get("source")
        file   = request.files.get("file")

        # 1) validate
        if source not in ("crl", "i3"):
            flash("Please select CRL or i3 as source.", "error")
            return redirect(url_for("web.upload"))
        if not file or not file.filename.lower().endswith(".csv"):
            flash("Please upload a CSV file.", "error")
            return redirect(url_for("web.upload"))

        # 2) load into DataFrame
        try:
            text_io = io.StringIO(file.stream.read().decode("utf-8"))
            df = pd.read_csv(text_io)
        except Exception as e:
            flash(f"Failed to parse CSV: {e}", "error")
            return redirect(url_for("web.upload"))

        # 3) normalize
        clean = norm_crl(df) if source == "crl" else normalize_i3screen(df)

        # 4) pick out incomplete
        incomplete = [r for r in clean.to_dict(orient="records") if not is_complete(r)]
        flashed = 0
        if incomplete:
            db  = SessionLocal()
            now = datetime.datetime.utcnow()

            # stamp and filter duplicates in staging
            existing = {c[0] for c in db.query(WorklistStaging.ccfid).all()}
            to_stage = []
            for rec in incomplete:
                ccfid = rec["CCFID"]
                if ccfid in existing:
                    continue
                rec["uploaded_timestamp"] = now
                rec["reviewed"]           = False
                to_stage.append(rec)
                existing.add(ccfid)

            if to_stage:
                # bulk_insert_mappings expects dict keys exactly matching
                # your WorklistStaging columns
                db.bulk_insert_mappings(WorklistStaging, to_stage)
                db.commit()
            flashed = len(to_stage)

        flash(f"Staged {flashed} incomplete records for review.", "success")
        return redirect(url_for("web.worklist"))

    return render_template("upload.html")


@bp.route("/worklist")
def worklist():
    """Show all unreviewed staging items."""
    db    = SessionLocal()
    items = (
        db.query(WorklistStaging)
          .filter_by(reviewed=False)
          .order_by(WorklistStaging.ccfid)
          .all()
    )
    return render_template("worklist.html", items=items)


@bp.route("/worklist/<string:ccfid>", methods=["GET", "POST"])
def worklist_detail(ccfid):
    db   = SessionLocal()
    item = db.get(WorklistStaging, ccfid)
    if not item:
        flash(f"Record {ccfid} not found.", "error")
        return redirect(url_for("web.worklist"))

    if request.method == "POST":
        # Editable fields
        editable = [
            "company_name","company_code","first_name","last_name",
            "collection_site","collection_site_id","location",
            "collection_date","mro_received",
            "laboratory","test_reason","test_type","test_result","regulation"
        ]
        for f in editable:
            if f in request.form:
                val = request.form[f].strip()
                setattr(item, f, val or None)

        # Mark reviewed, update timestamp
        item.reviewed           = True
        item.uploaded_timestamp = datetime.datetime.utcnow()
        db.commit()

        # Build record with correct keys for main mapping
        record = {
            "CCFID": item.ccfid,
            "First_Name": item.first_name,
            "Last_Name": item.last_name,
            "Primary_ID": getattr(item, "primary_id", None),
            "Company": item.company_name,
            "Code": item.company_code,
            "Collection_Date": item.collection_date,
            "MRO_Received": item.mro_received,
            "Collection_Site_ID": item.collection_site_id,
            "Collection_Site": item.collection_site,
            "Laboratory": item.laboratory,
            "Location": item.location,
            "Test_Reason": item.test_reason,
            "Test_Result": item.test_result,
            "Test_Type": item.test_type,
            "Regulation": item.regulation,
        }

        # Prepare lookup maps
        company_code_to_recordid = {
            c.account_code: c.account_id.replace("zcrm_", "")
            for c in db.query(Company).all()
        }
        site_id_to_recordid = {
            s.Collection_Site_ID: s.Record_id.replace("zcrm_", "")
            for s in db.query(CollectionSite).all()
        }
        lab_name_to_recordid = {
            l.Laboratory: l.Record_id.replace("zcrm_", "")
            for l in db.query(Laboratory).all()
        }

        # Attach lookup IDs and convert to Zoho API names
        payload = _attach_lookup_ids(
            [record],
            company_code_to_recordid,
            site_id_to_recordid,
            lab_name_to_recordid
        )

        # Add "Name" field to the Zoho payload (if not already done by your _attach_lookup_ids)
        payload[0]["Name"] = str(item.ccfid)

        # Date serialization if needed (Zoho expects ISO strings)
        for date_field in ["Collection_Date", "MRO_Received"]:
            if date_field in payload[0] and isinstance(payload[0][date_field], (datetime.date, datetime.datetime)):
                payload[0][date_field] = payload[0][date_field].isoformat()

        try:
            good_ccfids = push_records(payload)
            if str(ccfid) in good_ccfids:
                db.execute(
                    text("INSERT INTO uploaded_ccfid (ccfid, uploaded_timestamp) VALUES (:ccfid, :uploaded_timestamp)"),
                    {"ccfid": ccfid, "uploaded_timestamp": datetime.datetime.utcnow()}
                )
                db.commit()
                flash(f"{ccfid} successfully sent to CRM!", "success")
            else:
                flash(f"Zoho did not accept the record. Check logs.", "error")
        except Exception as e:
            flash(f"Error sending to CRM: {e}", "error")

        return redirect(url_for("web.worklist"))

    # GET: build site autocomplete data
    rows = (
        db.query(
            CollectionSite.Collection_Site,
            CollectionSite.Collection_Site_ID
        )
        .filter(CollectionSite.Collection_Site.isnot(None))
        .filter(CollectionSite.Collection_Site != "")
        .distinct()
        .order_by(CollectionSite.Collection_Site)
        .all()
    )
    sites    = [r[0] for r in rows]
    site_map = {  r[0]: r[1] for r in rows }

    return render_template(
        "worklist_detail.html",
        item=item,
        sites=sites,
        site_map=site_map
    )
