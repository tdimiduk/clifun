import datetime as dt
import pathlib
import sys

import clifun
import pytest
from clifun import api, interpret_string

sys.path.append(str(pathlib.Path(__file__).parents[1] / "examples"))
print(sys.path)
import advanced
import basic
import function


def test_basic():
    args = ["test_basic", "--a", "1"]
    value = clifun.call(basic.Basic, args)
    assert value == basic.Basic(1)

    value2 = clifun.call(basic.Basic, args + ["--b", "test"])
    assert value2 == basic.Basic(1, "test")

    with pytest.raises(ValueError):
        clifun.call(basic.Basic, ["test_basic", "--b", "test"])


def test_check_unused():
    input_args = api.inputs_for_callable(basic.Basic, interpret_string.interpret)
    assert api.invalid_args(["c", "a"], input_args) == {"c"}


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
