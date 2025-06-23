# src/utils.py

from src.normalize.common import MASTER_COLUMNS

def is_complete(record: dict) -> bool:
    """
    A record is 'complete' only if every MASTER_COLUMNS value
    is non-blank (no empty strings or None), with one exception:
    - 'Location' is only required when record['Code'] == 'A1310'.
    """
    for col in MASTER_COLUMNS:
        val = record.get(col)

        # Skip Location unless Code == 'A1310'
        if col == "Location" and record.get("Code") != "A1310":
            continue

        # Now enforce non-empty
        if val is None:
            return False
        if isinstance(val, str) and not val.strip():
            return False

    return True
