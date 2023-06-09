from typing import Any

import click
from metricq import Metric, Source, Timestamp

from .utils import TIMESTAMP, metricq_command
from .version import version as client_version


class MetricQSend(Source):
    def __init__(
        self, metric: str, timestamp: Timestamp, value: float, *args: Any, **kwargs: Any
    ):
        super().__init__(*args, client_version=client_version, **kwargs)
        self.metric = metric
        self.timestamp = timestamp
        self.value = value

    async def task(self) -> None:
        await self.send(self.metric, time=self.timestamp, value=self.value)
        await self.stop()


@metricq_command(default_token="source-$USER-tool-send")
@click.option(
    "--timestamp",
    type=TIMESTAMP,
    default=Timestamp.now(),
    show_default="now",
    help="Timestamp to send.",
)
@click.argument("metric", required=True)
@click.argument("value", required=True, type=float)
def main(
    server: str, token: str, timestamp: Timestamp, metric: Metric, value: float
) -> None:
    """Send a single time-value pair for the given metric."""
    send = MetricQSend(
        token=token,
        url=server,
        metric=metric,
        timestamp=timestamp,
        value=value,
    )

    send.run()
