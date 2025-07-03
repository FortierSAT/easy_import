# src/db/repository.py
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from db.models import WorklistStaging


class WorklistStagingRepo:
    def __init__(self, db: Session):
        self.db = db

    def add_many(self, rows: List[Dict[str, Any]]) -> None:
        """Bulk-insert a list of staging dicts (expects keys matching model fields)."""
        self.db.bulk_insert_mappings(WorklistStaging, rows)
        self.db.commit()

    def get_pending(self) -> List[WorklistStaging]:
        """Return all rows where reviewed=False, ordered by ccfid."""
        return (
            self.db.query(WorklistStaging)
            .filter_by(reviewed=False)
            .order_by(WorklistStaging.ccfid)
            .all()
        )

    def get(self, ccfid: str) -> Optional[WorklistStaging]:
        """Fetch a single staging row by its primary key."""
        return self.db.get(WorklistStaging, ccfid)

    def update(self, ccfid: str, **fields) -> bool:
        """
        Update named fields on the given ccfid.
        Returns True if row existed & was updated, False otherwise.
        """
        row = self.get(ccfid)
        if not row:
            return False
        for k, v in fields.items():
            if hasattr(row, k):
                setattr(row, k, v)
        self.db.commit()
        return True

    def mark_reviewed(self, ccfid: str) -> bool:
        """Shortcut: set reviewed=True and timestamp uploaded_timestamp."""
        return self.update(
            ccfid, reviewed=True, uploaded_timestamp=datetime.datetime.utcnow()
        )

    def clear_all(self) -> None:
        """Delete every row in staging (use with care!)."""
        self.db.query(WorklistStaging).delete()
        self.db.commit()
