#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import argparse
import logging
from os import path as op
from lxml import etree


_LOG_FORMAT = '%(name)s: %(message)s'
_LOG_LEVEL = logging.WARNING


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

    args = arg_parser.parse_args()

    if args.verbose == 1:
        globals()['_LOG_LEVEL'] = logging.INFO
    elif args.verbose > 1:
        globals()['_LOG_LEVEL'] = logging.DEBUG
        globals()['_LOG_FORMAT'] = '%(name)s[%(process)d]: %(message)s'

    logging.basicConfig(format=_LOG_FORMAT, level=_LOG_LEVEL)
    logger = logging.getLogger(op.basename(__file__))

    if not op.isdir(args.output):
        logger.error('ERROR: Invalid output path given: %s', args.output)
        sys.exit(1)

    categories = frozenset(args.category)
    resolutions = frozenset(args.resolution)

    logger.debug('DEBUG: arg --verbose: %d', args.verbose)
    logger.debug('DEBUG: arg --output: %s', args.output)
    logger.debug('DEBUG: arg --category: %r', categories)
    logger.debug('DEBUG: arg --resolution: %r', resolutions)


if __name__ == '__main__':
    main()
