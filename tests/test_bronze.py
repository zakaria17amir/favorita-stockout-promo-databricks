import pytest
from pyspark.errors import PySparkException
from py4j.protocol import Py4JJavaError

from favorita_spark.bronze import RAW_SCHEMAS, read_raw


def test_train_is_typed(spark, raw_dir):
    df = read_raw(spark, f"{raw_dir}/train.csv", "train")
    assert [(f.name, f.dataType.simpleString()) for f in df.schema.fields] == [
        ("id", "bigint"), ("date", "date"), ("store_nbr", "int"), ("item_nbr", "int"),
        ("unit_sales", "double"), ("onpromotion", "boolean")]


def test_empty_promotion_flag_is_null(spark, raw_dir):
    df = read_raw(spark, f"{raw_dir}/train.csv", "train")
    assert df.filter("store_nbr = 2 AND onpromotion IS NULL").count() == 91


def test_every_raw_file_has_a_schema(raw_dir):
    assert set(RAW_SCHEMAS) == {p.name.removesuffix(".csv") for p in raw_dir.glob("*.csv")}


def test_malformed_row_fails_loudly(spark, tmp_path):
    bad = tmp_path / "stores.csv"
    bad.write_text("store_nbr,city,state,type,cluster\nnot-a-number,Quito,Pichincha,A,1\n")
    with pytest.raises((PySparkException, Py4JJavaError)):
        read_raw(spark, str(bad), "stores").collect()
