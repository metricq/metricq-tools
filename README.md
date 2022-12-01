MetricQ Tools
=============

[![Test, build and publish the Python package](https://github.com/metricq/metricq-tools/actions/workflows/package.yml/badge.svg)](https://github.com/metricq/metricq-tools/actions/workflows/package.yml)

Tools and utility scripts to monitor and administrate a MetricQ network.

This repository includes a Python package that installs the following
executables:

`metricq-check`
---------------

Uses the aggregation of persisted metric values to quickly check, if it contains non-finite values like +/-inf and NaN.

```
Usage: metricq-check [OPTIONS]

  Check metrics for non-finite values.

Options:
  -v, --verbosity LVL  Either CRITICAL, ERROR, WARNING, INFO or DEBUG
  --server URL         MetricQ server URL.  [default: amqp://localhost/]
  --help               Show this message and exit.
```

`metricq-discover`
------------------

Send an RPC broadcast on the MetricQ network and wait for replies from clients that are currently online.

```
Usage: metricq-discover [OPTIONS]

  Send an RPC broadcast on the MetricQ network and wait for replies from online
  clients.

Options:
  --version                   Show the version and exit.
  --server URL                MetricQ server URL.  [default:
                              amqp://localhost/]
  -d, --diff JSON_FILE        Show a diff to a list of previously discovered
                              clients (produced with --format=json)
  -t, --timeout DURATION      Wait at most this long for replies.
  --format (pretty|json)      Print results in this format  [default:
                              (pretty)]
  --ignore (error-responses)  Messages to ignore.
  -v, --verbosity LVL         Either CRITICAL, ERROR, WARNING, INFO or DEBUG
  --help                      Show this message and exit.
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
  --server URL                    MetricQ server URL.  [default:
                                  amqp://localhost/]
  --token CLIENT_TOKEN            A token to identify this client on the
                                  MetricQ network.  [default: metricq-inspect]
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
  -v, --verbosity LVL             Either CRITICAL, ERROR, WARNING, INFO or
                                  DEBUG
  --version                       Show the version and exit.
  --help                          Show this message and exit.
```

`metricq-send`

Send a single time-value pair for the given metric.

```
Usage: metricq-send [OPTIONS] METRIC VALUE

  Send a single time-value pair for the given metric.

Options:
  -v, --verbosity LVL    Either CRITICAL, ERROR, WARNING, INFO or DEBUG
  --version              Show the version and exit.
  --server URL           MetricQ server URL.  [default: amqp://localhost/]
  --token CLIENT_TOKEN   A token to identify this client on the MetricQ
                         network.  [default: source-send]
  --timestamp TIMESTAMP  Timestamp to send.  [default: (now)]
  --help                 Show this message and exit.
```

`metricq-spy`
-------------

Obtain metadata and storage location for a set of metrics.

```
Usage: metricq-spy [OPTIONS] METRICS...

  Obtain metadata and storage location for a set of metrics.

Options:
  -v, --verbosity LVL     Either CRITICAL, ERROR, WARNING, INFO or DEBUG
  --server URL            MetricQ server URL.  [default: amqp://localhost/]
  --format (pretty|json)  Print results in this format  [default: (pretty)]
  --help                  Show this message and exit.
```

`metricq-summary`
-----------------

Live metric data analysis and inspection on the MetricQ network.

```
Usage: metricq-summary [OPTIONS] COMMAND...

  Live metric data analysis and inspection on the MetricQ network.

  Consumes new data points for the given metric as they are submitted to the
  network, prints a statistical overview on exit.

Options:
  -v, --verbosity LVL             Either CRITICAL, ERROR, WARNING, INFO or
                                  DEBUG
  --server URL                    MetricQ server URL.  [default:
                                  amqp://localhost/]
  --token CLIENT_TOKEN            A token to identify this client on the
                                  MetricQ network.  [default: metricq-summary]
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
  --version                       Show the version and exit.
  --help                          Show this message and exit.
```
