import datetime as dt
import pathlib
import sys

import pytest

import clifun

examples_dir = pathlib.Path(__file__).parents[1] / "examples"
sys.path.append(str(examples_dir))
import advanced
import basic
import function


def test_basic():
    args = ["test_basic", "--a", "1"]
    value = clifun.call(basic.Basic, args)
    assert value == basic.Basic(1)

    value2 = clifun.call(basic.Basic, args + ["--b", "test"])
    assert value2 == basic.Basic(1, "test")

    with pytest.raises(SystemExit):
        clifun.call(basic.Basic, ["test_basic", "--b", "test"])


def test_check_unused():
    annotated = clifun.annotate_callable(
        basic.Basic, clifun.default_string_interpreters(), []
    )
    input_args = list(clifun.all_needed_inputs(annotated))
    assert clifun.invalid_args(["c", "a"], input_args) == {"c"}


def test_advanced():
    args = ["test_advanced", "--f.a", "2021-01-01", "--c", "1"]
    value = clifun.call(advanced.Bar, args)

    assert value == advanced.Bar(advanced.Foo(dt.datetime(2021, 1, 1)), 1)

    args2 = args + ["--f.b", "test"]
    value2 = clifun.call(advanced.Bar, args2)

    assert value2 == advanced.Bar(advanced.Foo(dt.datetime(2021, 1, 1), "test"), 1)


def test_function():
    args = ["test_basic", "--a", "1"]
    value = clifun.call(function.my_program, args=args)

    assert value == (1, "not provided")


def test_config_file():
    args = ["test_config", str(examples_dir / "foo.json"), "--c", "1"]

    value = clifun.call(advanced.Bar, args)

    assert value == advanced.Bar(advanced.Foo(dt.datetime(2021, 1, 1), "str"), 1)

    args2 = args + ["--f.b", "test"]
    value2 = clifun.call(advanced.Bar, args2)

    assert value2 == advanced.Bar(advanced.Foo(dt.datetime(2021, 1, 1), "test"), 1)

def test_boolean():
    args = ["test_boolean", "--a", "t"]
