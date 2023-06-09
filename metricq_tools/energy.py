import asyncio

import click
import metricq

from .logging import logger
from .utils import TemplateStringParam, client_version, metricq_command, run_cmd

_UNIT_MAP = {
    "watts": "W",
    "kilowatts": "kW",
}


def _get_units(subscriber: metricq.Subscriber, metric: str) -> tuple[str, str]:
    power_unit: str = subscriber.metadata[metric].get("unit", "")
    if not power_unit:
        logger.warning(f"No unit provided for {metric}, assuming the unit is W.")
        power_unit = "W"

    power_unit = _UNIT_MAP.get(power_unit, power_unit)

    if power_unit == "W":
        energy_unit = "J"
    elif power_unit in ("kW", "MW"):
        energy_unit = power_unit[0] + "J"
    else:
        logger.warning(
            f"The unit of {metric} is {power_unit} rather than W. This may not be power/energy."
        )
        energy_unit = f"{power_unit}s"

    return power_unit, energy_unit


async def collect_energy(
    subscriber: metricq.Subscriber, metric: str, command: list[str]
) -> None:
    async with subscriber:
        time_before = metricq.Timestamp.now()
        await run_cmd(command)
        time_after = metricq.Timestamp.now()
        duration = time_after - time_before
        assert duration.s > 0

        value_sum = 0.0
        value_count = 0
        async for data_metric, timestamp, value in subscriber.collect_data():
            assert data_metric == metric
            if not (time_before <= timestamp <= time_after):
                continue
            value_sum += value
            value_count += 1

    click.echo(
        f"[metricq-energy] duration={duration.s:.1f} s number of values={value_count}"
    )

    if value_count == 0:
        logger.error(f"No data received for {metric}, cannot compute energy.")
        return
    if value_count < 10:
        logger.warning(
            f"Received only {value_count} data points for {metric}, "
            f"energy computation may be inaccurate."
        )
    value_mean = value_sum / value_count
    energy = value_mean * duration.s
    power_unit, energy_unit = _get_units(subscriber, metric)

    click.echo(f"[metricq-energy] mean of {metric}={value_mean:.1f} {power_unit}")
    click.echo(f"[metricq-energy] integral of {metric}={energy:.1f} {energy_unit}")


@metricq_command(default_token="sink-$USER-tool-energy")
@click.option(
    "-m", "--metric", type=TemplateStringParam(), required=True, multiple=False
)
@click.option(
    "--expires",
    type=int,
    default=3600,
    help="Queue expiration time in seconds. Set this value to the maximum time the "
    "command is expected to run.",
)
@click.argument("command", required=True, nargs=-1)
def main(
    server: str,
    token: str,
    metric: str,
    expires: int,
    command: list[str],
):
    """
    Get a single energy value for a metric during the execution of the given command.
    This value is just the integral of the metric over the time the command was running.

    The integral is calculated as the product of the arithmetic mean of all values
    times the runtime of the given command. For the result to be accurate, the metric
    should have updates in regular intervals and there should be a sufficient number of
    values for the duration of the command.
    """
    subscriber = metricq.Subscriber(
        token=token,
        url=server,
        metrics=[metric],
        expires=expires,
        client_version=client_version,
    )
    asyncio.run(collect_energy(subscriber, metric=metric, command=command))
