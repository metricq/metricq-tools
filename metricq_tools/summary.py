#!/usr/bin/env python3
# Copyright (c) 2019, ZIH, Technische Universitaet Dresden, Federal Republic of Germany
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#     * Redistributions of source code must retain the above copyright notice,
#       this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright notice,
#       this list of conditions and the following disclaimer in the documentation
#       and/or other materials provided with the distribution.
#     * Neither the name of metricq nor the names of its contributors
#       may be used to endorse or promote products derived from this software
#       without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from contextlib import suppress

import asyncio
import aio_pika
import click
import click_completion
import click_log
import metricq
import numpy as np
import termplotlib as tpl
from metricq.datachunk_pb2 import DataChunk

from metricq_tools.utils import metricq_server_option, metricq_token_option

from .logging import get_root_logger
from .version import version as client_version

logger = get_root_logger()

click_completion.init()


class SummarySink(metricq.Sink):
    def __init__(
        self,
        metrics: list[str],
        intervals_histogram: bool,
        chunk_sizes_histogram: bool,
        values_histogram: bool,
        print_stats: bool,
        print_data: bool,
        command: str,
        *args,
        **kwargs,
    ):
        self._metrics = metrics
        self.tokens = {}

        self.print_intervals = intervals_histogram
        self.print_chunk_sizes = chunk_sizes_histogram
        self.print_values = values_histogram
        self.print_stats = print_stats
        self.print_data = print_data
        self.command = command

        self.timestamps = dict[str,list]()
        self.last_timestamp = dict[str]()
        self.intervals = dict[str,list]()
        self.values = dict[str,list]()
        self.chunk_sizes = dict[str,list]()

        for metric in metrics:
            self.timestamps[metric] = list()
            self.last_timestamp[metric] = None
            self.intervals[metric] = list()
            self.values[metric] = list()
            self.chunk_sizes[metric] = list()


        super().__init__(*args, client_version=client_version, **kwargs)

    async def connect(self):
        await super().connect()

        click.echo(
            click.style(
                f"Inspecting the metric '{self._metrics}'...",
                fg="green",
            )
        )

        await self.subscribe(self._metrics)

        await self.run_cmd()

        await self.stop()
        self.print_histograms()

    async def run_cmd(self):
        click.echo(f'running... {self.command!r}')

        proc = await asyncio.create_subprocess_shell(
            self.command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE)

        stdout, stderr = await proc.communicate()

        click.echo(f'{self.command!r} exited with {proc.returncode}')
        if stdout:
            click.echo(stdout.decode())
        if stderr:
            click.echo(stderr.decode())

    async def _on_data_message(self, message: aio_pika.IncomingMessage):
        async with message.process(requeue=True):
            body = message.body
            from_token = None
            with suppress(AttributeError):
                from_token = message.client_id
            metric = message.routing_key

            if from_token not in self.tokens:
                self.tokens[from_token] = 0

            self.tokens[from_token] += 1

            data_response = DataChunk()
            data_response.ParseFromString(body)

            self.chunk_sizes[metric].append(len(data_response.value))

            await self._on_data_chunk(metric, data_response)

    async def on_data(self, metric: str, timestamp: metricq.Timestamp, value: float):
        if self.print_data:
            click.echo(click.style("{}: {}".format(timestamp, value), fg="bright_blue"))

        self.timestamps[metric].append(timestamp.posix)
        if self.last_timestamp[metric]:
            self.intervals[metric].append(timestamp.posix - self.last_timestamp[metric])
        self.last_timestamp[metric] = timestamp.posix
        self.values[metric].append(value)

    def on_signal(self, signal):
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
        finally:
            super().on_signal(signal)

    def print_statistics(self, values):
        click.echo(
            click.style(
                "Statistics",
                fg="yellow",
            )
        )
        click.echo()

        click.echo("{:20} = {:#.2g}".format("Minimum",np.amin(values)))
        click.echo("{:20} = {:#.2g}".format("Maximum",np.amax(values)))
        click.echo("{:20} = {:#.2g}".format("Average",np.average(values)))
        click.echo("{:20} = {:#.2g}".format("Median",np.median(values)))
        click.echo("{:20} = {:#.2g}".format("Standard deviation",np.std(values)))
        click.echo("{:20} = {:#.2g}".format("Arithmetic mean",np.mean(values)))
        click.echo("{:20} = {:#.2g}".format("Variance",np.var(values)))

        click.echo()
        click.echo()

    def print_histogram(self, values):
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

    def print_chunk_sizes_histogram(self, chunk_sizes):
        click.echo(
            click.style(
                "Distribution of the chunk sizes",
                fg="yellow",
            )
        )
        click.echo()

        self.print_histogram(chunk_sizes)

        click.echo()
        click.echo()

    def print_intervals_histogram(self, intervals):
        click.echo(
            click.style(
                "Distribution of the duration between consecutive data points in seconds",
                fg="yellow",
            )
        )
        click.echo()

        self.print_histogram(intervals)

        click.echo()
        click.echo()

    def print_values_histogram(self, values):
        click.echo(
            click.style("Distribution of the values of the data points", fg="yellow")
        )
        click.echo()

        self.print_histogram(values)

        click.echo()
        click.echo()

    def print_histograms(self):
        for metric in self._metrics:

            if self.values[metric]:
                click.echo()
                click.echo(
                    click.style(f"Stats of metric {metric!r}:", fg="green")
                )
                click.echo()

                if self.print_chunk_sizes:
                    self.print_chunk_sizes_histogram(self.chunk_sizes[metric])

                if self.print_intervals and self.last_timestamp[metric]:
                    self.print_intervals_histogram(self.intervals[metric])

                if self.print_values:
                    self.print_values_histogram(self.values[metric])

                if self.print_stats:
                    self.print_statistics(self.values[metric])
            else:
                click.echo()
                click.echo(
                    click.style(f"No Data for metric {metric!r} received!", fg="red")
                )
                click.echo()


@click.command()
@metricq_server_option()
@metricq_token_option(default="metricq-inspect")
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
@click.option("--print-statistics/--no-print-statistics", "-s/-S", default=True)
@click.option("-m","--metric", required=True, multiple=True)
@click_log.simple_verbosity_option(logger, default="WARNING")
@click.version_option(version=client_version)
@click.argument('command', nargs=-1)
def main(
    server,
    token,
    metric,
    intervals_histogram,
    values_histogram,
    chunk_sizes_histogram,
    print_data_points,
    print_statistics,
    command,
):
    """Live metric data analysis and inspection on the MetricQ network.

    Consumes new data points for the given metric as they are submitted to the
    network, prints a statistical overview on exit.
    """

    command_str = " ".join(command)
    sink = SummarySink(
        metrics=metric,
        token=token,
        management_url=server,
        intervals_histogram=intervals_histogram,
        chunk_sizes_histogram=chunk_sizes_histogram,
        values_histogram=values_histogram,
        print_data=print_data_points,
        print_stats=print_statistics,
        command=command_str,
    )
    sink.run()


if __name__ == "__main__":
    main()
