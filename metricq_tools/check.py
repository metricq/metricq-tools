import asyncio
import math

import click
import metricq
from metricq import JsonDict

from .logging import logger
from .utils import metricq_command
from .version import version as client_version

# We need a higher timeout because we're really making a lot of requests
_TIMEOUT = 60


async def check(client: metricq.HistoryClient, infinite: bool, dead: bool) -> None:
    async with client:
        logger.info("Looking up metrics...")
        # Dead metrics need metadata for the rate
        metrics = await client.get_metrics(prefix="", metadata=dead, limit=999999)

        if infinite:
            await check_for_infinite(client, metrics)
        if dead:
            await check_for_dead(client, metrics)


async def check_for_dead(
    client: metricq.HistoryClient, metrics: dict[str, JsonDict]
) -> None:
    logger.info(f"Checking {len(metrics)} metrics for dead metrics.")

    dead_metrics: list[tuple[metricq.Timedelta, metricq.Timestamp, str]] = []
    no_value_metrics: set[str] = set()
    timeout_metrics: set[str] = set()
    error_metrics: set[str] = set()

    async def check_metric(metric: str, allowed_age: metricq.Timedelta) -> None:
        try:
            result = await client.history_last_value(metric, timeout=_TIMEOUT)
            if result is None:
                no_value_metrics.add(metric)
                return
            age = metricq.Timestamp.now() - result.timestamp
            if age.s < 0:
                logger.error("Negative age for {}", metric)
            elif age > allowed_age:
                dead_metrics.append((age, result.timestamp, metric))
        except asyncio.TimeoutError:
            logger.debug("TimeoutError for {}", metric)
            timeout_metrics.add(metric)
        except metricq.exceptions.HistoryError as e:
            logger.debug("HistoryError for {}: {}", metric, e)
            error_metrics.add(metric)

    def compute_allowed_age(metadata: JsonDict) -> metricq.Timedelta:
        tolerance = metricq.Timedelta.from_string("1s")
        try:
            rate = metadata["rate"]
            if not isinstance(rate, (int, float)):
                logger.error("Invalid rate: {} ({}) [{}]", rate, type(rate), metadata)
            else:
                tolerance += metricq.Timedelta.from_s(1 / rate)
        except KeyError:
            # Fall back to compute tolerance from interval
            try:
                interval = metadata["interval"]
                if isinstance(interval, str):
                    tolerance += metricq.Timedelta.from_string(interval)
                elif isinstance(interval, (int, float)):
                    tolerance += metricq.Timedelta.from_s(interval)
                else:
                    logger.error(
                        "Invalid interval: {} ({}) [{}]",
                        interval,
                        type(interval),
                        metadata,
                    )
            except KeyError:
                pass
        return tolerance

    requests = [
        check_metric(metric, compute_allowed_age(metadata))
        for metric, metadata in metrics.items()
    ]

    with click.progressbar(length=len(requests)) as bar:
        for request in asyncio.as_completed(requests):
            await request
            bar.update(1)

    if dead_metrics:
        logger.error("Found {} dead metrics:", len(dead_metrics))
        for age, timestamp, metric in sorted(dead_metrics):
            # nicely colored output with click
            click.echo(
                " ".join(
                    (
                        click.style(
                            timestamp.datetime.replace(microsecond=0), fg="green"
                        ),
                        click.style(metric, fg="yellow"),
                        click.style(age, fg="red"),
                    )
                )
            )
    else:
        logger.info("No dead metrics found.")

    if no_value_metrics:
        logger.error("Found {} metrics without a value:", len(no_value_metrics))
        click.echo(",".join(sorted(no_value_metrics)))
    else:
        logger.info("No metrics without a value found.")

    if timeout_metrics:
        logger.error("Found {} metrics with a timeout:", len(timeout_metrics))
        click.echo(",".join(sorted(timeout_metrics)))
    else:
        logger.info("No metrics with a timeout found.")

    if error_metrics:
        logger.error("Found {} metrics with an error:", len(error_metrics))
        click.echo(",".join(sorted(error_metrics)))
    else:
        logger.info("No metrics with an error found.")


async def check_for_infinite(
    client: metricq.HistoryClient, metrics: dict[str, JsonDict]
) -> None:
    logger.info(f"Checking {len(metrics)} metrics for non-finite numbers.")

    start_time = metricq.Timestamp.from_iso8601("1970-01-01T00:00:00.0Z")
    end_time = metricq.Timestamp.from_now(metricq.Timedelta.from_string("7d"))

    bad_metrics = {}

    async def check_metric(metric: str) -> None:
        try:
            result = await client.history_aggregate(
                metric, start_time=start_time, end_time=end_time, timeout=_TIMEOUT
            )
            if not math.isfinite(result.minimum) or not math.isfinite(result.maximum):
                bad_metrics[metric] = result
        except asyncio.TimeoutError:
            logger.error("TimeoutError for {}", metric)
        except metricq.exceptions.HistoryError as e:
            logger.error("HistoryError for {}: {}", metric, e)

    requests = [check_metric(metric) for metric in metrics]

    with click.progressbar(length=len(requests)) as bar:
        for request in asyncio.as_completed(requests):
            await request
            bar.update(1)

    if bad_metrics:
        logger.error("Found {} metrics with non-finite numbers:", len(bad_metrics))
        for metric, aggregate in sorted(bad_metrics.items(), reverse=True):
            print(metric, aggregate)
    else:
        logger.info("No metrics with non-finite numbers found.")


@metricq_command(default_token="history-$USER-tool-check")
@click.option(
    "--infinite/--no-infinite",
    default=False,
    help="Check for infinite values. This can cause a lot of load on databases because every file needs to be accessed.",
)
@click.option(
    "--dead/--no-dead",
    default=True,
    help="Check for metrics that have not been recently updated.",
)
def main(server: str, token: str, infinite: bool, dead: bool) -> None:
    """Check all historic metrics for non-finite values."""
    if not (infinite or dead):
        logger.error("Nothing to do.")
        return

    client = metricq.HistoryClient(
        token=token,
        url=server,
        client_version=client_version,
        add_uuid=True,
    )

    asyncio.run(check(client, infinite=infinite, dead=dead))
