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

import click
import click_log  # type: ignore
from metricq import Source, Timestamp
from metricq.types import Metric

from metricq_tools.utils import TIMESTAMP, metricq_server_option, metricq_token_option

from .logging import get_root_logger
from .version import version as client_version

logger = get_root_logger()


class MetricQSend(Source):
    def __init__(self, metric, timestamp, value, *args, **kwargs):
        super().__init__(*args, client_version=client_version, **kwargs)
        self.metric = metric
        self.timestamp = timestamp
        self.value = value

    async def task(self):
        await self.send(self.metric, time=self.timestamp, value=self.value)
        await self.stop()


@click.command()
@click_log.simple_verbosity_option(logger, default="warning")
@click.version_option(version=client_version)
@metricq_server_option()
@metricq_token_option(default="source-send")
@click.option(
    "--timestamp",
    type=TIMESTAMP,
    default=Timestamp.now(),
    show_default="now",
    help="Timestamp to send.",
)
@click.argument("metric", required=True)
@click.argument("value", required=True, type=float)
def main(server: str, token: str, timestamp: Timestamp, metric: Metric, value: float):
    """Send a single time-value pair for the given metric."""
    send = MetricQSend(
        token=token,
        management_url=server,
        metric=metric,
        timestamp=timestamp,
        value=value,
    )

    send.run()


if __name__ == "__main__":
    main()
