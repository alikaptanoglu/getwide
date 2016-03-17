#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import argparse
import logging
import asyncio
import multiprocessing
from os import path as op
from concurrent.futures import ThreadPoolExecutor

import aiohttp
from lxml import etree


_LOG_FORMAT = '%(name)s: %(message)s'
_LOG_LEVEL = logging.WARNING

_CHUNK_SIZE = 4096  # 4k chunk size.
_MAX_THREADS = multiprocessing.cpu_count()  # 1 thread per core.

_HOST = 'http://wallpaperswide.com'
_HEADERS = {'Referer': _HOST}

_XPATH_TEXT = 'text()'
_XPATH_HREF = '@href'

_xpath_text_href = lambda xp: '|'.join([xp + _XPATH_TEXT, xp + _XPATH_HREF])

_XPATH_CATEGORY = "//ul[@class='side-panel categories']//a/"
_XPATH_CATEGORIES = _xpath_text_href(_XPATH_CATEGORY)

_XPATH_PAGE = "//div[@class='pagination']//a/"
_XPATH_PAGES = _xpath_text_href(_XPATH_PAGE)

_XPATH_WALLPAPERS = ("//ul[@class='wallpapers']//li[@class='wall']//a/" +
                     _XPATH_HREF)

_XPATH_RESOLUTIONS = ("//div[@class='wallpaper-resolutions']//"
                      "a[@target='_self']/") + _XPATH_HREF


class ParserError(Exception):
    pass


class Singleton(type):

    def __init__(cls, *args, **kwargs):
        super().__init__(*args, **kwargs)

        def new(cls_, *args, **kwargs):
            if not cls_._INSTANCE:
                cls_._INSTANCE = object.__new__(cls_)
            return cls_._INSTANCE

        setattr(cls, '_INSTANCE', None)
        setattr(cls, '__new__', staticmethod(new))


class Fetcher(metaclass=Singleton):

    def __init__(self, *, logger, session, timeout):
        self._logger = logger
        self.session = session
        self._timeout = timeout

    def __del__(self):
        self._close_session()

    def _close_session(self):
        if getattr(self, '_session', None):
            if not self._session.closed:
                self._session.close()

    @property
    def session(self):
        return self._session

    @session.setter
    def session(self, s):
        if not isinstance(s, aiohttp.ClientSession):
            raise TypeError('aiohttp.ClientSession object is expected instead '
                            'of: {!r}'.format(s))
        self._close_session()
        self._session = s

    async def fetch_page(self, url):
        """
        Raises:
            asyncio.TimeoutError
            ConnectionError
        """
        with aiohttp.Timeout(self._timeout):
            async with self._session.get(url) as response:
                if response.status != 200:
                    self._logger.warning("WARNING: Error connecting to "
                                         "'%s': %d", url, response.status)
                    raise ConnectionError(response.status, url)

                return await response.read()

    async def fetch_binary(self, url, file):
        """
        Raises:
            asyncio.TimeoutError
            ConnectionError
        """
        with aiohttp.Timeout(self._timeout):
            async with self._session.get(url) as response:
                if response.status != 200:
                    self._logger.warning("WARNING: Error connecting to "
                                         "'%s': %d", url, response.status)
                    raise ConnectionError(response.status, url)

                with open(file, 'wb') as fd:
                    while True:
                        chunk = await response.content.read(_CHUNK_SIZE)
                        if not chunk:
                            break
                        fd.write(chunk)

                return op.abspath(file)


class Parser:

    def __init__(self, xpath, *, logger, parser=etree.HTMLParser()):
        self._logger = logger
        self._parser = parser

        try:
            self._xpath = etree.XPath(xpath)
        except (TypeError, etree.XPathError) as ex:
            self._logger.error('ERROR: XPath error: %s: %s', ex, xpath)
            raise ParserError(ex, xpath)

    def __call__(self, text):
        try:
            self._tree = etree.fromstring(text, parser=self._parser)
        except etree.XMLSyntaxError as ex:
            self._logger.error('ERROR: XML syntax error: %s', ex)
            raise ParserError(ex)

        try:
            self._result = self._xpath(self._tree)
        except etree.XPathError as ex:
            self._logger.error('ERROR: XPath evaluation error: %s: %r', ex,
                               self._xpath)
            raise ParserError(ex, repr(self._xpath))


        return self._result

    @property
    def tree(self):
        return getattr(self, '_tree', None)

    @property
    def result(self):
        return getattr(self, '_result', None)


class Application(metaclass=Singleton):

    def __init__(self, *, logger):
        self._loop = asyncio.get_event_loop()
        self._pool = ThreadPoolExecutor(max_workers=_MAX_THREADS)
        self._queue = asyncio.Queue()
        self._logger = logger

        self._logger.debug('DEBUG: Maximum number of processes: %d',
                           _MAX_THREADS)

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
