#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import argparse
import logging
import asyncio
import multiprocessing
from os import path as op

import aiohttp
from lxml import (etree,)


_LOG_FORMAT = '%(name)s: %(message)s'
_LOG_LEVEL = logging.WARNING

_MAX_PROCESSES = multiprocessing.cpu_count()  # 1 process per core.
class Parser:
    pass


class Application:

    def __init__(self, *, logger):
        self._loop = asyncio.get_event_loop()
        self._queue = asyncio.Queue()
        self._logger = logger

        self._logger.debug('DEBUG: Maximum number of processes: %d',
                           _MAX_PROCESSES)

    def __del__(self):
        self._loop.close()


def main():
    arg_parser = argparse.ArgumentParser(
        description='WallpapersWide.com content grabber'
    )

    arg_parser.add_argument(
        '-v', '--verbose',
        help='log messages verbosity level', action='count', default=0
    )

    arg_parser.add_argument(
        '-o', '--output',
        help='path for saving files', default=os.getcwd()
    )

    arg_parser.add_argument(
        '-c', '--category',
        help='process specified category', action='append'
    )

    arg_parser.add_argument(
        '-r', '--resolution',
        help='grab specified resolution', action='append', default=['2560x1440']
    )

    arg_parser.add_argument(
        '-t', '--timeout',
        help='add timeout for network I/O', default=0
    )

    args = arg_parser.parse_args()

    if args.verbose == 1:
        globals()['_LOG_LEVEL'] = logging.INFO
    elif args.verbose > 1:
        globals()['_LOG_LEVEL'] = logging.DEBUG
        globals()['_LOG_FORMAT'] = '%(name)s[%(process)d]: %(message)s'

    logging.basicConfig(format=_LOG_FORMAT, level=_LOG_LEVEL)
    logger = logging.getLogger(op.basename(__file__.rsplit('.', 1)[0]))

    if not op.isdir(args.output):
        logger.error('ERROR: Invalid output path given: %s', args.output)
        sys.exit(1)

    categories = frozenset(args.category) if args.category else []
    if not categories:
        logger.warning('WARNING: Categories was not specified – fetching ALL')

    resolutions = frozenset(args.resolution)

    logger.debug('DEBUG: arg --verbose: %d', args.verbose)
    logger.debug('DEBUG: arg --output: %s', args.output)
    logger.debug('DEBUG: arg --category: %r', categories)
    logger.debug('DEBUG: arg --resolution: %r', resolutions)

    app = Application(logger=logger)


if __name__ == '__main__':
    main()
