import csv
from pathlib import Path
from tools.trud_data import get_members, refset_exists, get_refset_name

TRUD_DATA_DIR = Path(__file__).parent.parent / "data" / "trud"

def load_refset(refset_id: str) -> set[str]:
    if not refset_exists(refset_id):
        raise KeyError(f"Refset {refset_id} not in trud_data.py")
    return get_members(refset_id)

def refset_exists(refset_id: str) -> bool:
    """Check if a refset file is available locally."""
    return (TRUD_DATA_DIR / f"{refset_id}.csv").exists()
