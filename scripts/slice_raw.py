"""Cut the Favorita raw CSVs to the analysis slice before uploading them to Databricks.

train.csv is filtered by date; the rows stay raw text (read and written as VARCHAR, so nothing
is reformatted). The small files are kept whole: transactions keeps its full history so store
opening dates match Project 1. Output: gzipped CSVs, which Spark reads directly.

    python scripts/slice_raw.py --raw ../Flagship/data/raw --out data/slice
"""
import argparse
from datetime import date
from pathlib import Path

import duckdb

FILES = ["train", "transactions", "stores", "items", "holidays_events"]


def slice_raw(raw: Path, out: Path, start: date, end: date) -> dict[str, int]:
    out.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    counts = {}
    for name in FILES:
        src = (Path(raw) / f"{name}.csv").as_posix()
        dst = (out / f"{name}.csv.gz").as_posix()
        where = f"WHERE CAST(date AS DATE) BETWEEN DATE '{start}' AND DATE '{end}'" if name == "train" else ""
        counts[name] = con.execute(
            f"COPY (SELECT * FROM read_csv('{src}', header = true, all_varchar = true) {where}) "
            f"TO '{dst}' (HEADER, COMPRESSION gzip)"
        ).fetchone()[0]
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw", type=Path, required=True, help="folder with the Kaggle CSVs")
    parser.add_argument("--out", type=Path, default=Path("data/slice"))
    parser.add_argument("--start", type=date.fromisoformat, default=date(2016, 6, 21), help="window start − 56-day burn-in")
    parser.add_argument("--end", type=date.fromisoformat, default=date(2017, 8, 15))
    args = parser.parse_args()
    for name, n in slice_raw(args.raw, args.out, args.start, args.end).items():
        print(f"{name:16} {n:>12,} rows")


if __name__ == "__main__":
    main()
