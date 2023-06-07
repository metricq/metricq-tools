import logging

import click_log  # type: ignore
import metricq


def get_root_logger() -> logging.Logger:
    logger = metricq.get_logger()
    logger.setLevel(logging.WARNING)
    click_log.basic_config(logger)
    # logger.handlers[0].formatter = logging.Formatter(
    #     fmt="%(asctime)s [%(levelname)-8s] [%(name)-20s] %(message)s"
    # )

    return logger


logger = get_root_logger()
