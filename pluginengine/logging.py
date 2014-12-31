from __future__ import absolute_import
import logging


def create_logger(logername):
    logger = logging.getLogger(logername)
    logging.basicConfig()
    return logger
