def test_version_importable():
    from metricq_tools.version import version

    assert version and version != "0.0.0"
