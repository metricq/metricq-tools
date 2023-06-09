import asyncio
from contextlib import suppress
from typing import Any, Dict, Optional, TypedDict

import aio_pika
import click
import metricq
from metricq import Metric

from .utils import OutputFormat, metricq_command, output_format_option
from .version import version as client_version

Database = str


class SpyResults(TypedDict):
    location: Optional[Database]
    metadata: Dict[str, Any]


class MetricQSpy(metricq.HistoryClient):
    def __init__(self, token: str, url: str) -> None:
        super().__init__(
            token=token, url=url, client_version=client_version, add_uuid=True
        )
        self._data_locations: Optional[asyncio.Queue[Database]] = None

    async def spy(self, patterns: list[str], *, output_format: OutputFormat) -> None:
        self._data_locations = asyncio.Queue()
        await self.connect()

        results: Dict[Metric, SpyResults] = dict()

        for pattern in patterns:
            result: Dict[Metric, Dict[str, Any]] = await self.get_metrics(
                selector=pattern,
                metadata=True,
                historic=None,
            )

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

    async def _on_history_response(
        self, message: aio_pika.abc.AbstractIncomingMessage
    ) -> None:
        database = message.app_id
        if database is None:
            database = "(unknown)"
        assert self._data_locations
        self._data_locations.put_nowait(database)

        await super()._on_history_response(message)


@metricq_command(default_token="agent-$USER-tool-spy")
@output_format_option()
@click.argument("metrics", required=True, nargs=-1)
def main(server: str, token: str, format: OutputFormat, metrics: list[str]) -> None:
    """Obtain metadata and storage location for a set of metrics."""
    spy = MetricQSpy(token=token, url=server)

    asyncio.run(spy.spy(metrics, output_format=format))
