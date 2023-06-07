import asyncio
import csv

import click
import metricq

from .utils import TimestampParam, metricq_command
from .version import version as client_version


async def dump_csv(
    client: metricq.HistoryClient,
    filename: str,
    start_time: metricq.Timestamp,
    end_time: metricq.Timestamp,
    metric: str,
) -> None:
    async with client:
        timeline = await client.history_raw_timeline(
            metric, start_time=start_time, end_time=end_time
        )

    with open(filename, "w") as file:
        writer = csv.writer(file, delimiter=",")
        writer.writerow(("timestamp", metric))
        for timevalue in timeline:
            writer.writerow((timevalue.timestamp.datetime.isoformat(), timevalue.value))


@metricq_command("history-$USER-tool-csv")
@click.option("-o", "--output", type=click.Path(writable=True), required=True)
@click.option(
    "-s",
    "--start-time",
    type=TimestampParam(),
    default=metricq.Timestamp.now() - metricq.Timedelta.from_s(3600),
)
@click.option(
    "-e", "--end-time", type=TimestampParam(), default=metricq.Timestamp.now()
)
@click.argument("metric", nargs=1)
def main(
    server: str,
    token: str,
    output: str,
    start_time: metricq.Timestamp,
    end_time: metricq.Timestamp,
    metric: str,
) -> None:
    """Read values from a single historic metric and write them to a csv file."""
    client = metricq.HistoryClient(
        token=token,
        url=server,
        client_version=client_version,
        add_uuid=True,
    )

    asyncio.run(
        dump_csv(
            client=client,
            filename=output,
            start_time=start_time,
            end_time=end_time,
            metric=metric,
        )
    )
