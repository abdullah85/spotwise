#!/usr/bin/env python3
"""Upload the locally fetched price history to Postgres (Neon).

    export DATABASE_URL='postgresql://user:pass@ep-....neon.tech/spotwise?sslmode=require'
    python scripts/upload_neon.py                  # upserts data/prices.json
    python scripts/upload_neon.py --replace        # wipe rows first, then load

Synthetic data is refused unless --allow-synthetic is given, so the deployed
app cannot show invented prices by accident. Restart the Render service after
uploading (the app caches the dataset in memory).

Licence note: the database serves this app only. Never share DATABASE_URL.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from spotwise import db  # noqa: E402
from spotwise.store import DATA_DIR  # noqa: E402
from spotwise.validate import validate_series  # noqa: E402


def report(raw: dict) -> None:
    for group, kind in db.KINDS.items():
        for name, ser in sorted(raw.get(group, {}).items()):
            rep = validate_series({date.fromisoformat(d): p for d, p in ser.items()}, kind)
            flag = "OK " if rep["ok"] else "BAD"
            print(f"[{flag}] {kind} {name}: {rep['count']} days, gaps={len(rep['gaps'])}, "
                  f"zero={len(rep['zero_or_negative'])}, big jumps={len(rep['jumps'])}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--file", type=Path, default=DATA_DIR / "prices.json")
    p.add_argument("--replace", action="store_true", help="delete all rows before loading")
    p.add_argument("--allow-synthetic", action="store_true")
    args = p.parse_args()

    if not db.database_url():
        sys.exit("Set DATABASE_URL to your Neon connection string (never commit it).")
    if not args.file.exists():
        sys.exit(f"{args.file} not found. Run scripts/fetch_metals.py fetch first.")
    raw = json.loads(args.file.read_text())
    if raw.get("synthetic") and not args.allow_synthetic:
        sys.exit("Refusing to upload synthetic data. Pass --allow-synthetic if you mean it.")

    report(raw)
    try:
        n = db.upload(raw, replace=args.replace)
    except ValueError as e:
        sys.exit(f"Not uploaded: {e}")
    print(f"uploaded {n} rows from {args.file} (source: {raw.get('source', 'unknown')})")
    print("Restart the Render service to pick up the new data.")


if __name__ == "__main__":
    main()
