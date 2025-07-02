# src/utils.py

from src.normalize.common import MASTER_COLUMNS

def is_complete(record: dict) -> bool:

    test_type = (record.get("Test_Type") or "").strip()
    for col in MASTER_COLUMNS:
        val = record.get(col)

        # Skip Location unless Code == 'A1310'
        if col == "Location" and record.get("Code") != "A1310":
            continue

        # Skip Laboratory for POCT/Alohol Breath Test
        if col == "Laboratory" and test_type in ["POCT Urine Test", "Alcohol Breath Test"]:
            continue

        # Now enforce non-empty
        if val is None:
            return False
        if isinstance(val, str) and not val.strip():
            return False

    return True
