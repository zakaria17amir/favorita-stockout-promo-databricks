import gzip
from datetime import date

from slice_raw import slice_raw


def lines(path, opener=open):
    with opener(path, "rt", encoding="utf-8") as f:
        return f.read().splitlines()


def test_train_is_date_filtered_and_text_untouched(raw_dir, tmp_path):
    counts = slice_raw(raw_dir, tmp_path, date(2016, 1, 1), date(2016, 1, 31))
    src = lines(raw_dir / "train.csv")
    expected = [src[0]] + [ln for ln in src[1:] if "2016-01-01" <= ln.split(",")[1] <= "2016-01-31"]
    assert lines(tmp_path / "train.csv.gz", gzip.open) == expected
    assert counts["train"] == len(expected) - 1


def test_small_files_are_kept_whole(raw_dir, tmp_path):
    counts = slice_raw(raw_dir, tmp_path, date(2016, 1, 1), date(2016, 1, 31))
    # transactions keep full history so opening dates match Project 1
    for name in ("transactions", "stores", "items", "holidays_events"):
        assert lines(tmp_path / f"{name}.csv.gz", gzip.open) == lines(raw_dir / f"{name}.csv")
        assert counts[name] == len(lines(raw_dir / f"{name}.csv")) - 1
