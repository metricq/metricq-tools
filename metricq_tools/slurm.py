import asyncio
import datetime
import math
from dataclasses import dataclass
from string import Template
from typing import Optional

import click
import metricq
from hostlist import expand_hostlist  # type: ignore
from tabulate import tabulate

from .logging import logger
from .utils import metricq_command
from .version import version as client_version


def _parse_slurm_timestamp(timestamp: str) -> Optional[metricq.Timestamp]:
    if timestamp == "":
        return None
    return metricq.Timestamp.from_local_datetime(
        datetime.datetime.fromisoformat(timestamp)
    )


def _check_energy(aggregate: metricq.TimeAggregate) -> float:
    if aggregate.count == 0:
        logger.error("No data points for energy computation.")
        return math.nan
    if aggregate.count < 10:
        logger.warning(
            "Few data points {}, likely due to short job duration. Energy may be inaccurate.",
            aggregate.count,
        )
    if aggregate.minimum < 0:
        logger.warning(
            "Minimum power {} is negative, energy may be incorrect.",
            aggregate.minimum,
        )
    return aggregate.integral_s


@dataclass()
class SlurmJobEntry:
    def __init__(self, row: str):
        (
            self.job_id,
            self.job_name,
            start_str,
            end_str,
            hostlist_str,
        ) = row.split("|")
        self.start = _parse_slurm_timestamp(start_str)
        self.end = _parse_slurm_timestamp(end_str)
        if hostlist_str in ["", "None assigned"]:
            self.hostlist = []
        else:
            self.hostlist = expand_hostlist(hostlist_str)

    job_id: str
    job_name: str
    start: Optional[metricq.Timestamp]
    end: Optional[metricq.Timestamp]
    hostlist: list[str]
    energy: float = math.nan

    @property
    def energy_str(self) -> str:
        if math.isnan(self.energy):
            return "N/A"
        return f"{self.energy:.1f}"

    async def collect_energy(
        self, client: metricq.HistoryClient, metric_template: Template
    ) -> None:
        if self.job_id.endswith(".extern") or self.job_id.endswith(".batch"):
            return
        if not self.hostlist:
            logger.warning(
                "Job {} has no hostlist, cannot compute energy.", self.job_id
            )
            return
        if self.start is None or self.end is None:
            logger.warning(
                "Job {} has not finished yet, cannot compute energy.", self.job_id
            )
            return

        results = await asyncio.gather(
            *[
                client.history_aggregate(
                    metric=metric_template.substitute({"HOST": host}),
                    start_time=self.start,
                    end_time=self.end,
                )
                for host in self.hostlist
            ]
        )
        energy_values = [_check_energy(a) for a in results]
        self.energy = sum(energy_values)


async def get_slurm_data(jobs: str) -> list[SlurmJobEntry]:
    command = [
        "sacct",
        "--format",
        "JobID,JobName,Start,End,NodeList",
        "--jobs",
        jobs,
        "--noheader",
        "--parsable2",
    ]
    logger.debug("Running command {}", command)
    proc = await asyncio.create_subprocess_exec(
        *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await proc.communicate()

    if stderr:
        logger.error("SLURM error output: '{}'", stderr.decode())

    if proc.returncode == 0:
        logger.info("{!r} exited with {}", command, proc.returncode)
    else:
        logger.error("{!r} exited with {}", command, proc.returncode)

    return [SlurmJobEntry(line) for line in stdout.decode().splitlines()]


async def slurm_energy(
    client: metricq.HistoryClient, jobs: str, metric_template: Template
) -> None:
    jobs_data = await get_slurm_data(jobs)
    async with client:
        await asyncio.gather(
            *[j.collect_energy(client, metric_template) for j in jobs_data]
        )
    table_header = ["JobID", "Job Name", "Energy"]
    table_data = [
        [j.job_id, j.job_name, j.energy_str]
        for j in jobs_data
        if not math.isnan(j.energy)
    ]
    print(tabulate(table_data, headers=table_header, disable_numparse=True))


@metricq_command(default_token="history-$USER-tool-slurm")
@click.option(
    "-m",
    "--metric",
    type=str,
    required=True,
    multiple=False,
    help=(
        "Pattern for per-metric power consumption. "
        "$HOST will be replaced with the host(s) running the job. "
        "The metric is assumed to be in W (watts)."
    ),
)
@click.option(
    "-j",
    "--jobs",
    type=str,
    required=True,
    help="job(.step) or list of job(.steps) as per sacct",
)
def main(
    server: str,
    token: str,
    metric: str,
    jobs: str,
) -> None:
    """
    Get an energy value for a slurm job given its job id.

    This only works for exclusive jobs.
    """
    client = metricq.HistoryClient(
        token=token,
        url=server,
        client_version=client_version,
    )
    asyncio.run(slurm_energy(client, jobs=jobs, metric_template=Template(metric)))
