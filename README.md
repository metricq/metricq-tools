MetricQ Tools
=============

![License: GPLv3](https://img.shields.io/badge/License-GPLv3-yellow)
[![Build](https://github.com/metricq/metricq-tools/actions/workflows/package.yml/badge.svg)](https://github.com/metricq/metricq-tools/actions/workflows/package.yml)
![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)
[![PyPI](https://img.shields.io/pypi/v/metricq-tools)](https://pypi.org/project/metricq-tools/)
![PyPI - Wheel](https://img.shields.io/pypi/wheel/metricq-tools)

Tools and utility scripts to utilize, monitor, and administrate a MetricQ network.


Common command line options
---------------------------

```
  --server URL          MetricQ server URL.  [required]
  --token CLIENT_TOKEN  A token to identify this client on the MetricQ
                        network.  [default: depends on the tool]
  -v, --verbosity LVL   Either CRITICAL, ERROR, WARNING, INFO or DEBUG
  --version             Show the version and exit.
  --help                Show this message and exit.
```

All options for these tools can be passed as environment variables prefixed with `METRICQ_`,
i.e., `METRICQ_SERVER=amqps://...`.
You can also create a `.metricq` file in the current or home directory that contains environment variable settings in the same format.
Some options, including server and token, can contain placeholders for `$USER` and `$HOST`.


User tools
----------

`metricq-energy`
----------------

Run a command and calculate the energy consumption of a metric during this execution.

```
Usage: metricq-energy [OPTIONS] COMMAND...

  Get a single energy value for a metric during the execution of the given
  command. This value is just the integral of the metric over the time the
  command was running.

  The integral is calculated as the product of the arithmetic mean of all
  values times the runtime of the given command. For the result to be
  accurate, the metric should have updates in regular intervals and there
  should be a sufficient number of values for the duration of the command.

Options:
  -m, --metric TEXT     [required]
  --expires INTEGER     Queue expiration time in seconds. Set this value to
                        the maximum time the command is expected to run.
```

`metricq-slurm`
---------------

Get the energy consumption for SLURM jobs.

```
Usage: metricq-slurm [OPTIONS]

  Get an energy value for a slurm job given its job id.

  This only works for exclusive jobs.

Options:
  -m, --metric TEXT     Pattern for per-metric power consumption. $HOST will
                        be replaced with the host(s) running the job. The
                        metric is assumed to be in W (watts).  [required]
  -j, --jobs TEXT       job(.step) or list of job(.steps) as per sacct
                        [required]
```

`metricq-summary`
-----------------

Run a command and collect statistics about a given metric during this execution.

```
Usage: metricq-summary [OPTIONS] COMMAND...

  Live metric data analysis and inspection on the MetricQ network.

  Consumes new data points for the given metric as they are submitted to the
  network, prints a statistical overview on exit.

Options:
  -i, --intervals-histogram / -I, --no-intervals-histogram
                                  Show an histogram of the observed
                                  distribution of durations between data
                                  points.
  -h, --values-histogram / -H, --no-values-histogram
                                  Show an histogram of the observed metric
                                  values.
  -d, --print-data-points / -D, --no-print-data-points
  -s, --print-statistics / -S, --no-print-statistics
  -m, --metric TEXT               [required]
```

Administrator tools
-------------------

These tools are intended for debugging and monitoring MetricQ networks.

`metricq-check`
---------------

Uses the aggregation of persisted metric values to quickly check, if it contains non-finite values like +/-inf and NaN.

```
Usage: metricq-check [OPTIONS]

  Check metrics for non-finite values.
```

`metricq-discover`
------------------

Send an RPC broadcast on the MetricQ network and wait for replies from clients that are currently online.

```
Usage: metricq-discover [OPTIONS]

  Send an RPC broadcast on the MetricQ network and wait for replies from online
  clients.

Options:
  -d, --diff JSON_FILE        Show a diff to a list of previously discovered
                              clients (produced with --format=json)
  -t, --timeout DURATION      Wait at most this long for replies.
  --format (pretty|json)      Print results in this format  [default:
                              (pretty)]
  --ignore (error-responses)  Messages to ignore.
```

`metricq-inspect`
-----------------

Consumes new data points for the given metric as they are submitted to the network, prints a statistical overview on exit.

```
Usage: metricq-inspect [OPTIONS] METRIC

  Live metric data analysis and inspection on the MetricQ network.

  Consumes new data points for the given metric as they are submitted to the
  network, prints a statistical overview on exit.

Options:
  -i, --intervals-histogram / -I, --no-intervals-histogram
                                  Show an histogram of the observed
                                  distribution of durations between data
                                  points.
  -h, --values-histogram / -H, --no-values-histogram
                                  Show an histogram of the observed metric
                                  values.
  -c, --chunk-sizes-histogram / -C, --no-chunk-sizes-histogram
                                  Show an histogram of the observed chunk
                                  sizes of all messages received.
  -d, --print-data-points / -D, --no-print-data-points
```

`metricq-send`
--------------

Send a single time-value pair for the given metric.

```
Usage: metricq-send [OPTIONS] METRIC VALUE

  Send a single time-value pair for the given metric.

Options:
  --timestamp TIMESTAMP  Timestamp to send.  [default: (now)]
```

`metricq-spy`
-------------

Obtain metadata and storage location for a set of metrics.

```
Usage: metricq-spy [OPTIONS] METRICS...

  Obtain metadata and storage location for a set of metrics.

Options:
  --format (pretty|json)  Print results in this format  [default: (pretty)]
```

