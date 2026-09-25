# Copied from store-performance-fabric (Project 1) pipeline/tests/fixture_data.py so the Spark port
# is tested against the same data and the same expected values.
"""Tiny synthetic dataset shaped like the Favorita CSVs. Numbers are chosen so
expected values are easy to compute by hand (see the comments)."""
import csv
from datetime import date, timedelta
from pathlib import Path

STORES = [
    (1, "Quito", "Pichincha", "A", 1),
    (2, "Quito", "Pichincha", "B", 2),
    (3, "Guayaquil", "Guayas", "A", 3),
    (4, "Guayaquil", "Guayas", "D", 4),
    (5, "Cuenca", "Azuay", "C", 5),
]
ITEMS = [(101, "GROCERY I", 1001, 0), (102, "PRODUCE", 2001, 1)]
PROMO_DAYS = {date(2016, 1, 10), date(2016, 1, 11), date(2016, 1, 12)}
# store 1 / item 101 sells 5/day except these days (no row at all):
GAPS_101_STORE1 = {date(2015, 12, 15), date(2016, 1, 1), date(2016, 2, 10)}
# store 1 / item 102 sells daily except this genuine zero-sale trading day (no row at all):
GAPS_102_STORE1 = {date(2015, 12, 20)}
# store 1 is closed (no transactions row) on this date, so it drops out of the stock-out
# spine, and neither item sells anything that day (a closed store sells nothing):
STORE1_CLOSURE = date(2015, 12, 25)
# store 1 trades at a fifth of its normal receipts and item 101 has no row: a partial
# trading day, which must not be flagged as stock-out risk
STORE1_PARTIAL_DAY = date(2016, 3, 1)
STORE1_PARTIAL_RECEIPTS = 20
RETURN_DAY = date(2016, 1, 5)  # store 2 / item 101 has unit_sales = -1
HOLIDAYS = [
    (date(2016, 1, 1), "Holiday", "National", "Ecuador", "Primer dia del ano", "False"),
    (date(2016, 2, 8), "Holiday", "National", "Ecuador", "Carnaval", "True"),
    (date(2016, 2, 9), "Transfer", "National", "Ecuador", "Traslado Carnaval", "False"),
    (date(2016, 3, 5), "Holiday", "Local", "Quito", "Fundacion", "False"),
]
TRANSACTION_SPANS = {
    1: (date(2015, 1, 1), date(2016, 3, 31), 100),
    2: (date(2015, 6, 1), date(2016, 3, 31), 80),
    3: (date(2016, 1, 1), date(2016, 1, 31), 90),
    4: (date(2016, 1, 1), date(2016, 1, 31), 40),
    5: (date(2016, 1, 1), date(2016, 1, 31), 30),
}


def days(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def sales_rows() -> list[tuple]:
    rows = []
    for d in days(date(2015, 1, 1), date(2016, 3, 31)):
        if d not in GAPS_101_STORE1 and d not in (STORE1_CLOSURE, STORE1_PARTIAL_DAY):
            rows.append((d, 1, 101, 5.0, False))
    for d in days(date(2015, 11, 1), date(2016, 3, 31)):
        if d not in GAPS_102_STORE1 and d != STORE1_CLOSURE:
            promo = d in PROMO_DAYS
            rows.append((d, 1, 102, 6.0 if promo else 2.0, promo))
    for d in days(date(2015, 6, 1), date(2016, 3, 31)):
        promo = False if d.year == 2015 else None
        rows.append((d, 2, 101, -1.0 if d == RETURN_DAY else 1.0, promo))
    for store, units in ((3, 2.0), (4, 1.0), (5, 1.0)):
        for d in days(date(2016, 1, 1), date(2016, 1, 31)):
            rows.append((d, store, 101, units, False))
    return rows


def _write(path: Path, header: list[str], rows) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


def write_fixture(raw_dir: Path, *, extra_store_column: bool = False) -> Path:
    raw_dir.mkdir(parents=True, exist_ok=True)
    _write(
        raw_dir / "train.csv",
        ["id", "date", "store_nbr", "item_nbr", "unit_sales", "onpromotion"],
        [(i, d.isoformat(), s, it, u, "" if p is None else str(p))
         for i, (d, s, it, u, p) in enumerate(sales_rows())],
    )
    _write(
        raw_dir / "transactions.csv",
        ["date", "store_nbr", "transactions"],
        [(d.isoformat(), s, STORE1_PARTIAL_RECEIPTS if (s, d) == (1, STORE1_PARTIAL_DAY) else n)
         for s, (a, b, n) in TRANSACTION_SPANS.items() for d in days(a, b)
         if not (s == 1 and d == STORE1_CLOSURE)],
    )
    header = ["store_nbr", "city", "state", "type", "cluster"]
    rows = STORES
    if extra_store_column:
        header = header + ["extra"]
        rows = [r + ("x",) for r in STORES]
    _write(raw_dir / "stores.csv", header, rows)
    _write(raw_dir / "items.csv", ["item_nbr", "family", "class", "perishable"], ITEMS)
    _write(
        raw_dir / "holidays_events.csv",
        ["date", "type", "locale", "locale_name", "description", "transferred"],
        [(d.isoformat(), *rest) for d, *rest in HOLIDAYS],
    )
    return raw_dir
