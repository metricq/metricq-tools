#!/usr/bin/env python3
# Copyright (c) 2021, ZIH, Technische Universitaet Dresden, Federal Republic of Germany
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


import asyncio
from sys import exit
from typing import Any, Optional

import click
import metricq
import numpy as np
import termplotlib as tpl  # type: ignore
from metricq import Subscriber
from tabulate import tabulate

from metricq_tools.utils import metricq_command

from .logging import logger
from .version import version as client_version


class Summary:
    timestamps: dict[str, list[float]]
    last_timestamp: dict[str, Optional[float]]
    intervals: dict[str, list[float]]
    values: dict[str, list[float]]

    def __init__(
        self,
        metrics: list[str],
        intervals_histogram: bool,
        values_histogram: bool,
        print_stats: bool,
        print_data: bool,
    ):
        self._metrics = metrics

        self.print_intervals = intervals_histogram
        self.print_values = values_histogram
        self.print_stats = print_stats
        self.print_data = print_data

        self.timestamps = {}
        self.last_timestamp = {}
        self.intervals = {}
        self.values = {}

        for metric in metrics:
            self.timestamps[metric] = []
            self.last_timestamp[metric] = None
            self.intervals[metric] = []
            self.values[metric] = []

    async def add_data(
        self, metric: str, timestamp: metricq.Timestamp, value: float
    ) -> None:
        if self.print_data:
            click.echo(click.style("{}: {}".format(timestamp, value), fg="bright_blue"))

        self.timestamps[metric].append(timestamp.posix)
        if (last_timestamp := self.last_timestamp[metric]) is not None:
            self.intervals[metric].append(timestamp.posix - last_timestamp)
        self.last_timestamp[metric] = timestamp.posix
        self.values[metric].append(value)

    def _print_histogram(self, values: list[float]) -> None:
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

    def _print_intervals_histogram(self, intervals: list[float]) -> None:
        click.echo(
            click.style(
                "Distribution of the duration between consecutive data points in seconds",
                fg="yellow",
            )
        )
        click.echo()

        self._print_histogram(intervals)

        click.echo()
        click.echo()

    def _print_values_histogram(self, values: list[float]) -> None:
        click.echo(
            click.style("Distribution of the values of the data points", fg="yellow")
        )
        click.echo()

        self._print_histogram(values)

        click.echo()
        click.echo()

    def print(self) -> None:
        for metric in self._metrics:
            if self.values[metric]:
                click.echo()
                click.echo(click.style(f"Statistics of metric {metric!r}:", fg="green"))
                click.echo()

                if self.print_intervals and self.last_timestamp[metric]:
                    self._print_intervals_histogram(self.intervals[metric])

                if self.print_values:
                    self._print_values_histogram(self.values[metric])
            else:
                click.echo()
                click.echo(
                    click.style(f"No Data for metric {metric!r} received!", fg="red")
                )
                click.echo()

        if self.print_stats:
            self._print_statistics()

    def _print_statistics(self) -> None:
        click.echo(
            click.style(
                "Statistics",
                fg="yellow",
            )
        )
        click.echo()

        table = list[list[Any]]()

        headers = [
            "Metric",
            "Minimum",
            "Maximum",
            "Average",
            "Median",
            "Standard deviation",
            "Arithmetic mean",
            "Variance",
            "Count",
        ]

        for metric in self._metrics:
            if self.values[metric]:
                table[0].append(metric)
                table[1].append(np.amin(self.values[metric]))
                table[2].append(np.amax(self.values[metric]))
                table[3].append(np.average(self.values[metric]))
                table[4].append(np.median(self.values[metric]))
                table[5].append(np.std(self.values[metric]))
                table[6].append(np.mean(self.values[metric]))
                table[7].append(np.var(self.values[metric]))
                table[8].append(len(self.values[metric]))
            else:
                table[0].append(metric)
                table[1].append("n/a")
                table[2].append("n/a")
                table[3].append("n/a")
                table[4].append("n/a")
                table[5].append("n/a")
                table[6].append("n/a")
                table[7].append("n/a")
                table[8].append(len(self.values[metric]))

        click.echo(tabulate(table, headers=headers, tablefmt="fancy_grid"))

        click.echo()
        click.echo()


async def run_cmd(command: str) -> Optional[int]:
    logger.debug("Running command: {!r}", command)

    proc = await asyncio.create_subprocess_shell(
        command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
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


async def async_main(
    server: str,
    token: str,
    metric: list[str],
    intervals_histogram: bool,
    values_histogram: bool,
    print_data_points: bool,
    print_statistics: bool,
    command: str,
) -> Optional[int]:
    command_str = " ".join(command)
    summary = Summary(
        intervals_histogram=intervals_histogram,
        values_histogram=values_histogram,
        print_data=print_data_points,
        print_stats=print_statistics,
        metrics=metric,
    )
    async with Subscriber(
        token=token,
        url=server,
        metrics=metric,
        expires=3600,
        client_version=client_version,
    ) as subscription:
        returncode = await run_cmd(command_str)

        async with subscription.drain() as drain:
            async for m, timestamp, value in drain:
                await summary.add_data(m, timestamp, value)

        summary.print()

        return returncode


@metricq_command(default_token="sink-tool-summary")
@click.option(
    "--intervals-histogram/--no-intervals-histogram",
    "-i/-I",
    default=False,
    help="Show an histogram of the observed distribution of durations between data points.",
)
@click.option(
    "--values-histogram/--no-values-histogram",
    "-h/-H",
    default=False,
    help="Show an histogram of the observed metric values.",
)
@click.option("--print-data-points/--no-print-data-points", "-d/-D", default=False)
@click.option("--print-statistics/--no-print-statistics", "-s/-S", default=True)
@click.option("-m", "--metric", required=True, multiple=True)
@click.argument("command", required=True, nargs=-1)
def main(
    server: str,
    token: str,
    metric: list[str],
    intervals_histogram: bool,
    values_histogram: bool,
    print_data_points: bool,
    print_statistics: bool,
    command: str,
) -> None:
    """Live metric data analysis and inspection on the MetricQ network.

    Consumes new data points for the given metric as they are submitted to the
    network, prints a statistical overview on exit.
    """

    returncode = asyncio.run(
        async_main(
            server,
            token,
            metric,
            intervals_histogram,
            values_histogram,
            print_data_points,
            print_statistics,
            command,
        )
    )

    exit(returncode)


if __name__ == "__main__":
    main()
