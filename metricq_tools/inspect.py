from contextlib import suppress
from typing import Any, Optional

import aio_pika
import click
import metricq
import numpy as np
import termplotlib as tpl  # type: ignore
from metricq.datachunk_pb2 import DataChunk

from .logging import logger
from .utils import metricq_command
from .version import version as client_version


class InspectSink(metricq.Sink):
    tokens: dict[Optional[str], int]
    timestamps: list[float]
    last_timestamp: Optional[float]
    intervals: list[float]
    values: list[float]
    chunk_sizes: list[int]

    def __init__(
        self,
        metric: str,
        intervals_histogram: bool,
        chunk_sizes_histogram: bool,
        values_histogram: bool,
        print_data: bool,
        *args: Any,
        **kwargs: Any,
    ):
        self._metric = metric
        self.tokens = {}

        self.print_intervals = intervals_histogram
        self.print_chunk_sizes = chunk_sizes_histogram
        self.print_values = values_histogram
        self.print_data = print_data

        self.timestamps = []
        self.last_timestamp = None
        self.intervals = []
        self.values = []
        self.chunk_sizes = []
        super().__init__(*args, client_version=client_version, **kwargs)

    async def connect(self) -> None:
        await super().connect()

        await self.subscribe([self._metric])

        click.echo(
            click.style(
                f"Inspecting the metric '{self._metric}'... (Hit ctrl+C to stop)",
                fg="green",
            )
        )

    async def _on_data_message(
        self, message: aio_pika.abc.AbstractIncomingMessage
    ) -> None:
        async with message.process(requeue=True):
            body = message.body
            from_token = None
            with suppress(AttributeError):
                # This probably doesn't ever work, but I'm just fixing the typing now, so I have to ignore
                from_token = message.client_id  # type: ignore[attr-defined]
            metric = message.routing_key
            if metric is None:
                logger.warning(
                    "received data message without routing key from {}", from_token
                )
                return

            if from_token not in self.tokens:
                self.tokens[from_token] = 0

            self.tokens[from_token] += 1

            data_response = DataChunk()
            data_response.ParseFromString(body)

            self.chunk_sizes.append(len(data_response.value))

            await self._on_data_chunk(metric, data_response)

    async def on_data(
        self, metric: str, timestamp: metricq.Timestamp, value: float
    ) -> None:
        if self.print_data:
            click.echo(click.style("{}: {}".format(timestamp, value), fg="bright_blue"))

        self.timestamps.append(timestamp.posix)
        if self.last_timestamp:
            self.intervals.append(timestamp.posix - self.last_timestamp)
        self.last_timestamp = timestamp.posix
        self.values.append(value)

    def on_signal(self, signal: str) -> None:
        try:
            click.echo()
            click.echo(
                click.style(
                    "Received messages from: ",
                    fg="bright_red",
                )
            )

            for token, messages in self.tokens.items():
                click.echo(
                    click.style(
                        "{}: {}".format(token if token else "<unknown>", messages),
                        fg="bright_red",
                    )
                )

            click.echo()

            self.print_histograms()
        finally:
            super().on_signal(signal)

    def print_histogram(self, values: list[float] | list[int]) -> None:
        counts, bin_edges = np.histogram(values, bins="doane")
        fig = tpl.figure()
        labels = [
            "[{:#.6g} - {:#.6g})".format(bin_edges[k], bin_edges[k + 1])
            for k in range(len(bin_edges) - 2)
        ]
        labels.append(
            "[{:#.6g} - {:#.6g}]".format(
                bin_edges[len(bin_edges) - 2], bin_edges[len(bin_edges) - 1]
            )
        )
        fig.barh(counts, labels=labels)
        fig.show()

    def print_chunk_sizes_histogram(self) -> None:
        click.echo(
            click.style(
                "Distribution of the chunk sizes",
                fg="yellow",
            )
        )
        click.echo()

        self.print_histogram(self.chunk_sizes)

        click.echo()
        click.echo()

    def print_intervals_histogram(self) -> None:
        click.echo(
            click.style(
                "Distribution of the duration between consecutive data points in seconds",
                fg="yellow",
            )
        )
        click.echo()

        self.print_histogram(self.intervals)

        click.echo()
        click.echo()

    def print_values_histogram(self) -> None:
        click.echo(
            click.style("Distribution of the values of the data points", fg="yellow")
        )
        click.echo()

        self.print_histogram(self.values)

    def print_histograms(self) -> None:
        if self.print_chunk_sizes:
            self.print_chunk_sizes_histogram()

        if self.print_intervals and self.last_timestamp:
            self.print_intervals_histogram()

        if self.print_values:
            self.print_values_histogram()


@metricq_command(default_token="agent-$USER-tool-inspect")
@click.option(
    "--intervals-histogram/--no-intervals-histogram",
    "-i/-I",
    default=True,
    help="Show an histogram of the observed distribution of durations between data points.",
)
@click.option(
    "--values-histogram/--no-values-histogram",
    "-h/-H",
    default=True,
    help="Show an histogram of the observed metric values.",
)
@click.option(
    "--chunk-sizes-histogram/--no-chunk-sizes-histogram",
    "-c/-C",
    default=False,
    help="Show an histogram of the observed chunk sizes of all messages received.",
)
@click.option("--print-data-points/--no-print-data-points", "-d/-D", default=False)
@click.argument("metric", required=True, nargs=1)
def main(
    server: str,
    token: str,
    metric: str,
    intervals_histogram: bool,
    values_histogram: bool,
    chunk_sizes_histogram: bool,
    print_data_points: bool,
) -> None:
    """Live metric data analysis and inspection on the MetricQ network.

    Consumes new data points for the given metric as they are submitted to the
    network, prints a statistical overview on exit.
    """
    sink = InspectSink(
        metric=metric,
        token=token,
        url=server,
        intervals_histogram=intervals_histogram,
        chunk_sizes_histogram=chunk_sizes_histogram,
        values_histogram=values_histogram,
        print_data=print_data_points,
    )
    sink.run()
