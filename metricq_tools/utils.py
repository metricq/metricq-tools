import asyncio
import re
from contextlib import suppress
from enum import Enum, auto
from getpass import getuser
from socket import gethostname
from string import Template
from typing import Any, Callable, Generic, List, Optional, Type, TypeVar, Union, cast

import click
import click_log  # type: ignore
from click import Context, Parameter, ParamType, option
from dotenv import find_dotenv, load_dotenv
from metricq import Timedelta, Timestamp

from .logging import logger
from .version import version as client_version

_C = TypeVar("_C", covariant=True)

# We do not interpolate (i.e. replace ${VAR} with corresponding environment variables).
# That is because we want to be able to interpolate ourselves for metrics and tokens
# using the same syntax. If it was only ${USER} for the token, we could use the
# override functionality, but most unfortunately there is no standard environment
# variable for the hostname. Even $HOST on zsh is not actually part of the environment.
# ``override=false`` just means that environment variables have priority over the
# env files.
load_dotenv(dotenv_path=find_dotenv(".metricq"), interpolate=False, override=False)


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
    """
    Convert strings to ``metricq.Timestamp`` objects.

    Accepts the following string inputs
    - ISO-8601 timestamp (with timezone)
    - Past Duration, e.g., '-10h' from now
    - Posix timestamp, float seconds since 1.1.1970 midnight. (UTC)
    - 'now'
    - 'epoch', i.e., 1.1.1970 midnight
    """

    name = "timestamp"

    @staticmethod
    def _convert(value: str) -> Timestamp:
        if value == "now":
            return Timestamp.now()
        if value == "epoch":
            return Timestamp.from_posix_seconds(0)
        if value.startswith("-"):
            # Plus because the minus makes negative timedelta
            return Timestamp.now() + Timedelta.from_string(value)
        with suppress(ValueError):
            return Timestamp.from_posix_seconds(float(value))

        return Timestamp.from_iso8601(value)

    def convert(
        self, value: Any, param: Optional[Parameter], ctx: Optional[Context]
    ) -> Optional[Timestamp]:
        if value is None:
            return None
        elif isinstance(value, Timestamp):
            return value
        elif isinstance(value, str):
            try:
                return self._convert(value)
            except ValueError:
                self.fail(
                    "expected an ISO-8601 timestamp (e.g. '2012-12-21T00:00:00Z'), "
                    "POSIX timestamp, 'now', 'epoch', or a past duration (e.g. '-10h')",
                    param=param,
                    ctx=ctx,
                )
        else:
            self.fail("unexpected type to convert to TimeStamp", param=param, ctx=ctx)


TIMESTAMP = TimestampParam()


class TemplateStringParam(ParamType):
    name = "text"
    mapping: dict[str, str]

    def __init__(self) -> None:
        self.mapping = {}
        with suppress(Exception):
            self.mapping["USER"] = getuser()
        with suppress(Exception):
            self.mapping["HOST"] = gethostname()

    def convert(
        self, value: Any, param: Optional[Parameter], ctx: Optional[Context]
    ) -> str:
        if not isinstance(value, str):
            raise TypeError("expected a string type for TemplateStringParam")
        return Template(value).safe_substitute(self.mapping)


def metricq_server_option() -> Callable[[FC], FC]:
    return option(
        "--server",
        type=TemplateStringParam(),
        metavar="URL",
        required=True,
        help="MetricQ server URL.",
    )


def metricq_token_option(default: str) -> Callable[[FC], FC]:
    return option(
        "--token",
        type=TemplateStringParam(),
        metavar="CLIENT_TOKEN",
        default=default,
        show_default=True,
        help="A token to identify this client on the MetricQ network.",
    )


def metricq_command(default_token: str) -> Callable[[FC], click.Command]:
    log_decorator = cast(
        Callable[[FC], FC], click_log.simple_verbosity_option(logger, default="warning")
    )
    context_settings = {"auto_envvar_prefix": "METRICQ"}
    epilog = (
        "All options can be passed as environment variables prefixed with 'METRICQ_'."
        "I.e., 'METRICQ_SERVER=amqps://...'.\n"
        "\n"
        "You can also create a '.metricq' file in the current or home directory that "
        "contains environment variable settings in the same format.\n"
        "\n"
        "Some options, including server and token, can contain placeholders for $USER "
        "and $HOST."
    )

    def decorator(func: FC) -> click.Command:
        return click.version_option(version=client_version)(
            log_decorator(
                metricq_token_option(default_token)(
                    metricq_server_option()(
                        click.command(context_settings=context_settings, epilog=epilog)(
                            func
                        )
                    )
                )
            )
        )

    return decorator


async def run_cmd(command: list[str]) -> Optional[int]:
    logger.debug("Running command: {!r}", command)

    proc = await asyncio.create_subprocess_exec(
        *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await proc.communicate()

    if stdout:
        click.echo(stdout.decode())
    if stderr:
        click.echo(click.style(stderr.decode(), fg="red"))

    if proc.returncode == 0:
        logger.info("{!r} exited with {}", command, proc.returncode)
    else:
        logger.error("{!r} exited with {}", command, proc.returncode)

    return proc.returncode
