import re
from enum import Enum, auto
from typing import Any, Callable, Generic, List, Optional, Type, TypeVar, Union, cast

import click
from click import Context, Parameter, ParamType, option
from metricq import Timedelta, Timestamp

_C = TypeVar("_C", covariant=True)


def camelcase_to_kebabcase(camelcase: str) -> str:
    # Match empty string preceeding uppercase character, but not at the start
    # of the word. Replace with '-' and make lowercase to get kebab-case word.
    return re.sub(r"(?<!^)(?=[A-Z])", "-", camelcase).lower()


def kebabcase_to_camelcase(kebabcase: str) -> str:
    return "".join(part.title() for part in kebabcase.split("-"))


class CommandLineChoice:
    @classmethod
    def as_choice_list(cls) -> List[str]:
        return [
            camelcase_to_kebabcase(name) for name in getattr(cls, "__members__").keys()
        ]

    def as_choice(self) -> str:
        return camelcase_to_kebabcase(getattr(self, "name"))

    @classmethod
    def default(cls: Type[_C]) -> Optional[_C]:
        return None

    @classmethod
    def from_choice(cls: Type[_C], option: str) -> _C:
        member_name = kebabcase_to_camelcase(option.lower())
        return cast(_C, getattr(cls, "__members__")[member_name])


ChoiceType = TypeVar("ChoiceType", bound=CommandLineChoice)


class ChoiceParam(Generic[ChoiceType], ParamType):
    def __init__(self, cls: Type[ChoiceType], name: str):
        self.cls = cls
        self.name = name

    def get_metavar(self, param: Parameter) -> str:
        return f"({'|'.join(self.cls.as_choice_list())})"

    def convert(
        self,
        value: Union[str, ChoiceType],
        param: Optional[Parameter],
        ctx: Optional[Context],
    ) -> Optional[ChoiceType]:
        if value is None:
            return None

        try:
            if isinstance(value, str):
                return self.cls.from_choice(value)
            else:
                return value
        except (KeyError, ValueError):
            self.fail(
                f"unknown choice {value!r}, expected: {', '.join(self.cls.as_choice_list())}",
                param=param,
                ctx=ctx,
            )


class OutputFormat(CommandLineChoice, Enum):
    Pretty = auto()
    Json = auto()

    @classmethod
    def default(cls) -> "OutputFormat":
        return OutputFormat.Pretty


FORMAT = ChoiceParam(OutputFormat, "format")

FC = TypeVar("FC", bound=Union[Callable[..., Any], click.Command])


def output_format_option() -> Callable[[FC], FC]:
    return option(
        "--format",
        type=FORMAT,
        default=OutputFormat.default(),
        show_default=OutputFormat.default().as_choice(),
        help="Print results in this format",
    )


class DurationParam(ParamType):
    name = "duration"

    def __init__(self, default: Optional[Timedelta]):
        self.default = default

    def convert(
        self,
        value: Union[str, Timedelta],
        param: Optional[Parameter],
        ctx: Optional[Context],
    ) -> Optional[Timedelta]:
        if value is None:
            return None
        elif isinstance(value, str):
            try:
                return Timedelta.from_string(value)
            except ValueError:
                self.fail(
                    'expected a duration: "<value>[<unit>]"',
                    param=param,
                    ctx=ctx,
                )
        else:
            return value


class TimestampParam(ParamType):
    name = "timestamp"

    def convert(
        self, value: str, param: Optional[Parameter], ctx: Optional[Context]
    ) -> Any:
        if value is None:
            return None
        elif isinstance(value, str):
            try:
                return Timestamp.from_iso8601(value)
            except ValueError:
                self.fail(
                    "expected an ISO-8601 timestamp (e.g. 2012-12-21T00:00:00Z)",
                    param=param,
                    ctx=ctx,
                )
        else:
            return value


TIMESTAMP = TimestampParam()


def metricq_server_option() -> Callable[[FC], FC]:
    return option(
        "--server",
        metavar="URL",
        default="amqp://localhost/",
        show_default=True,
        help="MetricQ server URL.",
    )


def metricq_token_option(default: str) -> Callable[[FC], FC]:
    return option(
        "--token",
        metavar="CLIENT_TOKEN",
        default=default,
        show_default=True,
        help="A token to identify this client on the MetricQ network.",
    )
