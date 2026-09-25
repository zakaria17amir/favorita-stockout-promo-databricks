import os
import sys
from dataclasses import replace
from datetime import date

import pytest

from fixture_data import write_fixture
from favorita_spark.config import Config

# The fixture's data runs 2015-01-01 → 2016-03-31; Project 1's tests use a 2016-01-01 cut-off.
FIXTURE_CFG = Config(
    raw_ext=".csv",
    slice_start=date(2015, 1, 1),
    window_start=date(2016, 1, 1),
    window_end=date(2016, 3, 31),
)


@pytest.fixture(scope="session")
def spark():
    os.environ["PYSPARK_PYTHON"] = sys.executable
    from pyspark.sql import SparkSession

    session = (
        SparkSession.builder.master("local[1]")
        .appName("favorita-tests")
        # Java 23 removed Subject.getSubject without a security manager; Hadoop still calls it
        .config("spark.driver.extraJavaOptions", "-Djava.security.manager=allow")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.shuffle.partitions", "1")
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )
    yield session
    session.stop()


@pytest.fixture(scope="session")
def raw_dir(tmp_path_factory):
    return write_fixture(tmp_path_factory.mktemp("raw"))


@pytest.fixture(scope="session")
def cfg(raw_dir):
    return replace(FIXTURE_CFG, raw_path=str(raw_dir).replace("\\", "/"))
