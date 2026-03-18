"""
MCP Tool Server — TRUD Reference Sets (offline fallback)
Loads downloaded TRUD Primary Care Domain Reference Sets into memory.
Used when live NHS Terminology Server is unavailable.
Run standalone: python tools/trud_mcp.py
"""
from mcp.server.fastmcp import FastMCP
import pandas as pd
import os

mcp = FastMCP("trud-tool-server")

TRUD_DATA_PATH = os.getenv(
    "TRUD_DATA_PATH",
    "data/raw/trud/primary_care_refsets.csv"  # update to your actual filename
)

# Load once at startup
try:
    refset_df = pd.read_csv(TRUD_DATA_PATH, dtype=str)
    print(f"TRUD data loaded: {len(refset_df)} rows from {TRUD_DATA_PATH}")
except FileNotFoundError:
    refset_df = pd.DataFrame(columns=["conceptId", "term", "refsetId", "refsetName"])
    print(f"WARNING: TRUD data not found at {TRUD_DATA_PATH} — tool will return empty results")


@mcp.tool()
def search_trud_refset(term: str) -> list[dict]:
    """
    Search offline TRUD Primary Care Domain Reference Sets by term.
    Returns: list of {snomed_id, term, refset_id, refset_name}
    Fallback when NHS Terminology Server API is unavailable.
    """
    if refset_df.empty:
        return [{"error": "TRUD data not loaded", "term": term}]
    mask = refset_df["term"].str.contains(term, case=False, na=False)
    matches = refset_df[mask].head(50)
    return [
        {
            "snomed_id": row.get("conceptId", ""),
            "term": row.get("term", ""),
            "refset_id": row.get("refsetId", ""),
            "refset_name": row.get("refsetName", ""),
            "source": "trud_fallback"
        }
        for _, row in matches.iterrows()
    ]


@mcp.tool()
def get_refset_by_id(refset_id: str) -> list[dict]:
    """
    Retrieve all codes in a specific TRUD reference set by its ID.
    Returns: list of {snomed_id, term}
    """
    if refset_df.empty:
        return [{"error": "TRUD data not loaded"}]
    mask = refset_df["refsetId"] == refset_id
    members = refset_df[mask]
    return [
        {"snomed_id": row.get("conceptId", ""), "term": row.get("term", "")}
        for _, row in members.iterrows()
    ]


if __name__ == "__main__":
    mcp.run(transport="stdio")
