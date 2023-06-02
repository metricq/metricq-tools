from enum import Enum, auto
from typing import Union

import pytest
from click import ParamType
from metricq import Timedelta, Timestamp

from metricq_tools.utils import (
    TIMESTAMP,
    ChoiceParam,
    CommandLineChoice,
    DurationParam,
    TimestampParam,
)


class Choice(CommandLineChoice, Enum):
    Foo = auto()
    BarBaz = auto()


@pytest.mark.parametrize(
    "param_class",
    [DurationParam(default=None), TimestampParam(), ChoiceParam(Choice, name="test")],
)
def test_click_param_contracts(param_class: ParamType) -> None:
    """Custom parameter types should meet these requirements.

    See https://click.palletsprojects.com/en/7.x/api/#click.ParamType.
    """
    assert isinstance(param_class.name, str)
    assert (
        param_class.convert(
            None,
            param=None,
            ctx=None,
        )
        is None
    )


@pytest.mark.parametrize(
    ("value", "converted"),
    [
        ("foo", Choice.Foo),
        ("bar-baz", Choice.BarBaz),
        (Choice.Foo, Choice.Foo),
    ],
)
def test_choice_param_to_instance(value: Union[str, Choice], converted: Choice) -> None:
    CHOICE = ChoiceParam(Choice, name="test")

    assert CHOICE.convert(value, param=None, ctx=None) is converted


def test_choice_to_param_list() -> None:
    CHOICE = ChoiceParam(Choice, name="test")

    assert CHOICE.get_metavar(param=None) == "(foo|bar-baz)"  # type: ignore


def test_timestamp_param() -> None:
    value = "2021-05-02T00:00:00Z"
    assert TIMESTAMP.convert(value, param=None, ctx=None) == Timestamp.from_iso8601(
        value
    )


def test_duration_param() -> None:
    value = "30s"
    DURATION = DurationParam(default=None)
    assert DURATION.convert(value, param=None, ctx=None) == Timedelta.from_string(value)
