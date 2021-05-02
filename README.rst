=====================
:code:`metricq-tools`
=====================

|Python package|

.. |Python package| image:: https://github.com/metricq/metricq-tools/actions/workflows/package.yml/badge.svg

Tools and utility scripts to monitor and administrate a MetricQ network.

This repository includes a Python package that installs the following
executables:

:code:`metricq-discover`
    Send a RPC broadcast on the MetricQ network and wait for replies from
    clients that are currently online.

:code:`metricq-inspect`
    Consumes new data points for the given metric as they are submitted to the
    network, prints a statistical overview on exit.

:code:`metricq-send`
    Send a single time-value pair for the given metric.

:code:`metricq-spy`
    Obtain metadata and storage location for a set of metrics.
