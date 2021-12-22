import asyncio
import math

import click
import click_completion
import click_log
import metricq

from .logging import get_root_logger
from .utils import metricq_server_option
from .version import version as client_version

logger = get_root_logger()

click_completion.init()


async def check_for_non_finite(client):
    logger.info("Connecting...")
    await client.connect()

    start_time = metricq.Timestamp.from_iso8601("2010-01-01T00:00:00.0Z")
    end_time = metricq.Timestamp.from_now(metricq.Timedelta.from_string("7d"))

    bad_metrics = {}

    async def check_metric(metric):
        try:
            result = await client.history_aggregate(
                metric, start_time=start_time, end_time=end_time
            )
            if not math.isfinite(result.minimum) or not math.isfinite(result.maximum):
                bad_metrics[metric] = result
        except asyncio.TimeoutError:
            logger.error("timeout: {}", metric)
        except metricq.exceptions.HistoryError as e:
            logger.error("error: {}\n{}", metric, e)

    logger.info("Looking up metrics...")
    metric_list = await client.get_metrics(prefix="", metadata=False, limit=9999999)
    logger.info("Checking {} metrics...", len(metric_list))

    requests = [check_metric(metric) for metric in metric_list]

    # vtti will be prood...
    with click.progressbar(length=len(requests)) as bar:
        for request in asyncio.as_completed(requests):
            await request
            bar.update(1)

    for metric, aggregate in sorted(bad_metrics.items()):
        print(metric, aggregate)


@click.command()
@click_log.simple_verbosity_option(logger, default="warning")
@metricq_server_option()
def main(server):
    """Check metrics for non-finite values."""
    client = metricq.HistoryClient(
        token="tool-check",
        management_url=server,
        client_version=client_version,
        add_uuid=True,
    )

    asyncio.run(check_for_non_finite(client))


if __name__ == "__main__":
    main()
