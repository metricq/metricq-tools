#!/usr/bin/env python3
# Copyright (c) 2020, ZIH, Technische Universitaet Dresden, Federal Republic of Germany
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
from contextlib import suppress
from typing import Any, Dict, Optional, TypedDict

import aio_pika
import click
import click_log
import metricq
from metricq.types import Metric

from .logging import get_root_logger
from .utils import OutputFormat, metricq_server_option, output_format_option
from .version import version as client_version

logger = get_root_logger()

Database = str


class SpyResults(TypedDict):
    location: Optional[Database]
    metadata: Dict[str, Any]


class MetricQSpy(metricq.HistoryClient):
    def __init__(self, server) -> None:
        super().__init__("spy", server, client_version=client_version, add_uuid=True)
        self._data_locations: Optional[asyncio.Queue[Database]] = None

    async def spy(self, patterns, *, output_format: OutputFormat) -> None:
        self._data_locations = asyncio.Queue()
        await self.connect()

        results: Dict[Metric, SpyResults] = dict()

        for pattern in patterns:
            result: Dict[Metric, Dict[str, Any]] = await self.get_metrics(
                selector=pattern,
                metadata=True,
                historic=None,
            )  # type: ignore # This is a bug in the type annotations for get_metrics

            assert isinstance(result, dict), "No metadata in result of get_metrics"

            now = metricq.Timestamp.now()
            window = metricq.Timedelta.from_s(60)
            for metric, metadata in result.items():
                database: Optional[str] = None
                if metadata.get("historic", False):
                    with suppress(asyncio.TimeoutError):
                        await self.history_data_request(
                            metric,
                            start_time=now - window,
                            end_time=now,
                            interval_max=window,
                            timeout=5,
                        )
                        database = await self._data_locations.get()

                metadata = {k: v for k, v in metadata.items() if not k.startswith("_")}

                if output_format is OutputFormat.Pretty:
                    if database:
                        click.echo(
                            "{metric} (stored on {database}): {metadata}".format(
                                metric=click.style(metric, fg="cyan"),
                                database=click.style(database, fg="red"),
                                metadata=metadata,
                            )
                        )
                    else:
                        click.echo(
                            "{metric} (not stored on any database): {metadata}".format(
                                metric=click.style(metric, fg="cyan"),
                                metadata=metadata,
                            )
                        )
                elif output_format is OutputFormat.Json:
                    results[metric] = {
                        "location": database,
                        "metadata": metadata,
                    }

        if output_format is OutputFormat.Json:
            import json

            click.echo(json.dumps(results, sort_keys=True, indent=None))
        await self.stop()

    async def _on_history_response(self, message: aio_pika.IncomingMessage) -> None:
        database = message.app_id
        assert self._data_locations
        self._data_locations.put_nowait(database)

        await super()._on_history_response(message)


@click.command()
@click_log.simple_verbosity_option(logger, default="warning")
@metricq_server_option()
@output_format_option()
@click.version_option(version=client_version)
@click.argument("metrics", required=True, nargs=-1)
def main(server, format: OutputFormat, metrics) -> None:
    """Obtain metadata and storage location for a set of metrics."""
    spy = MetricQSpy(server)

    asyncio.run(spy.spy(metrics, output_format=format))


if __name__ == "__main__":
    main()
