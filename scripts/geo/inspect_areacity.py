#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/geo/source/ok_geo.csv"
OUT = ROOT / "data/geo/generated/manifest/source_inspection.json"


def main() -> None:
    csv.field_size_limit(sys.maxsize)
    deep_counter: Counter[int] = Counter()
    geo_empty = 0
    polygon_empty = 0
    total = 0
    sample = []

    with SOURCE.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        for row in reader:
            total += 1
            deep = int(row["deep"])
            deep_counter[deep] += 1
            if row.get("geo", "").strip().upper() == "EMPTY":
                geo_empty += 1
            if row.get("polygon", "").strip().upper() == "EMPTY":
                polygon_empty += 1
            if len(sample) < 5:
                sample.append(
                    {
                        "id": row["id"],
                        "pid": row["pid"],
                        "deep": deep,
                        "name": row["name"],
                        "ext_path": row["ext_path"],
                    }
                )

    report = {
        "source": str(SOURCE.relative_to(ROOT)),
        "fieldnames": fieldnames,
        "total_rows": total,
        "deep_counts": {str(k): v for k, v in sorted(deep_counter.items())},
        "geo_empty_count": geo_empty,
        "polygon_empty_count": polygon_empty,
        "sample_rows": sample,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
