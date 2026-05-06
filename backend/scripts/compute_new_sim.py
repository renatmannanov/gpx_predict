"""Compute new similarity scores after adding phonetic rules 8-11.

Reads am_duplicates_sim60_80_checked.csv, normalizes both names with the
updated normalize_name (all 11 rules), computes pg_trgm similarity for
non-exact matches, and writes the result with 3 new columns:
  new_am_norm, new_clax_norm, new_sim

Usage:
    cd backend && python -m scripts.compute_new_sim
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import sqlalchemy as sa

from app.db.session import SessionLocal, init_db
from app.features.races.name_utils import normalize_name

INPUT_CSV = Path(__file__).resolve().parent.parent.parent / "content" / "audit" / "am_duplicates_sim60_80_checked.csv"
OUTPUT_CSV = INPUT_CSV.parent / "am_duplicates_sim60_80_with_new_sim.csv"


def main() -> None:
    init_db()
    db = SessionLocal()

    try:
        # Ensure pg_trgm extension is available
        db.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        db.commit()
    except Exception:
        db.rollback()

    with open(INPUT_CSV, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    out_fieldnames = fieldnames + ["new_am_norm", "new_clax_norm", "new_sim"]

    results = []
    for row in rows:
        am_name = row["am_name"]
        clax_name = row["clax_name"]

        am_norm = normalize_name(am_name)
        clax_norm = normalize_name(clax_name)

        if am_norm == clax_norm:
            new_sim = 1.0
        else:
            new_sim = db.execute(
                sa.text("SELECT similarity(:a, :b)"),
                {"a": am_norm, "b": clax_norm},
            ).scalar()

        row["new_am_norm"] = am_norm
        row["new_clax_norm"] = clax_norm
        row["new_sim"] = f"{new_sim:.2f}"
        results.append(row)

    db.close()

    with open(OUTPUT_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=out_fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"Wrote {len(results)} rows to {OUTPUT_CSV}")

    # Quick stats
    exact = sum(1 for r in results if r["new_sim"] == "1.00")
    improved = sum(
        1
        for r in results
        if float(r["new_sim"]) > float(r["sim"])
    )
    print(f"Exact matches (new_sim=1.00): {exact}")
    print(f"Improved similarity: {improved}")


if __name__ == "__main__":
    main()
