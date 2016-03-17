#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import argparse
import logging
import asyncio
import multiprocessing
from os import path as op
from timeit import default_timer as timer
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

_XPATH_PAGES = "//div[@class='pagination']//a/" + _XPATH_TEXT

_XPATH_WALLPAPERS = ("//ul[@class='wallpapers']//li[@class='wall']//a/" +
                     _XPATH_HREF)

_XPATH_RESOLUTIONS = ("//div[@class='wallpaper-resolutions']//"
                      "a[@target='_self']/") + _XPATH_HREF


class ParserError(Exception):
    pass

class TaskTypeError(TypeError):
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
            tree = etree.fromstring(text, parser=self._parser)
        except etree.XMLSyntaxError as ex:
            self._logger.error('ERROR: XML syntax error: %s', ex)
            raise ParserError(ex)

        try:
            result = [str(r) for r in self._xpath(tree)]
        except etree.XPathError as ex:
            self._logger.error('ERROR: XPath evaluation error: %s: %r', ex,
                               self._xpath)
            raise ParserError(ex, repr(self._xpath))


        return result


class Application(metaclass=Singleton):
    TASK_FETCH_PAGES = 10
    TASK_FETCH_WALLPAPERS = 20
    TASK_FETCH_RESOLUTIONS = 30
    TASK_DOWNLOAD = 40

    def __init__(self, *, logger, timeout, categories, resolutions, path):
        self._loop = asyncio.get_event_loop()
        self._pool = ThreadPoolExecutor(max_workers=_MAX_THREADS)
        self._queue = asyncio.Queue()

        self._logger = logger
        self._resolutions = resolutions
        self._path = path

        self._session = aiohttp.ClientSession(loop=self._loop, headers=_HEADERS)
        self._fetcher = Fetcher(logger=self._logger, session=self._session,
                                timeout=timeout)

        self._logger.debug('DEBUG: Maximum number of processes: %d',
                           _MAX_THREADS)

        self._categories = self._loop.run_until_complete(self.fetch_categories(
                                                         categories))
        if self._categories:
            self._loop.run_until_complete(self.queue_driver())

    def __del__(self):
        self._fetcher.session.close()
        self._loop.close()

    async def queue_driver(self):
        # Initialize queue with a categories list.
        for c in self._categories:
            self._queue.put_nowait((self.TASK_FETCH_PAGES,
                                    _HOST + self._categories[c]))

        while not self._queue.empty():
            task = await self._queue.get()

            if task[0] == self.TASK_FETCH_PAGES:
                await self.fetch_pages(task[1])
            elif task[0] == self.TASK_FETCH_WALLPAPERS:
                await self.fetch_wallpapers(task[1])
            elif task[0] == self.TASK_FETCH_RESOLUTIONS:
                await self.fetch_resolutions(task[1])
            elif task[0] == self.TASK_DOWNLOAD:
                await self.download(task[1])
            else:
                raise TaskTypeError(task[0])

            self._queue.task_done()

    async def fetch_categories(self, categories=None):
        try:
            page = await self._fetcher.fetch_page(_HOST)
        except asyncio.TimeoutError:
            self._logger.error('ERROR: Skipping URL due to timeout: %s', _HOST)
            return None

        parser = Parser(_XPATH_CATEGORIES, logger=self._logger)
        cats = {c[1]: c[0] for c in zip(*[iter(parser(page))]*2)}

        if not categories:
            return cats

        result = {}
        for c in categories:
            if c in cats:
                result[c] = cats[c]
            else:
                self._logger.warning('WARNING: Skipping unknown category: %s',
                                     c)

        return result

    @property
    def categories(self):
        return self._categories

    async def fetch_pages(self, url):
        self._logger.info('Fetching pages for URL: %s', url)

        try:
            page = await self._fetcher.fetch_page(url)
        except asyncio.TimeoutError:
            self._logger.error('ERROR: Skipping URL due to timeout: %s', url)
            return None

        parser = Parser(_XPATH_PAGES, logger=self._logger)

        max_num = 0
        for p in await self._loop.run_in_executor(self._pool, parser, page):
            try:
                num = int(p)
            except ValueError:
                pass
            if num > max_num:
                max_num = num

        for p in range(1, max_num + 1):
            await self._queue.put((self.TASK_FETCH_WALLPAPERS,
                url.rsplit('.', 1)[0] + '/page/{}'.format(p))
            )

        return max_num


    async def fetch_wallpapers(self, url):
        self._logger.info('Fetching wallpapers for URL: %s', url)

        try:
            page = await self._fetcher.fetch_page(url)
        except asyncio.TimeoutError:
            self._logger.error('ERROR: Skipping URL due to timeout: %s', url)
            return None

        parser = Parser(_XPATH_WALLPAPERS, logger=self._logger)

        for w in frozenset(await self._loop.run_in_executor(
                           self._pool, parser, page)):
            await self._queue.put((self.TASK_FETCH_RESOLUTIONS, _HOST + w))

    async def fetch_resolutions(self, url):
        self._logger.info('Fetching resolutions for URL: %s', url)

        try:
            page = await self._fetcher.fetch_page(url)
        except asyncio.TimeoutError:
            self._logger.error('ERROR: Skipping URL due to timeout: %s', url)
            return None

        parser = Parser(_XPATH_RESOLUTIONS, logger=self._logger)

        found_res = False
        for r in await self._loop.run_in_executor(self._pool, parser, page):
            if any(['-{}.'.format(_) in r for _ in self._resolutions]):
                found_res = True
                await self._queue.put((self.TASK_DOWNLOAD, _HOST + r))

        if not found_res:
            self._logger.warning("WARNING: Cant't find appropriate "
                                 "resolution (%s) for URL: %s",
                                 ', '.join(self._resolutions), url)

    async def download(self, url):
        self._logger.info('Downloading wallpaper: %s', url)

        try:
            path = await self._fetcher.fetch_binary(url, op.join(self._path,
                                                    url.rsplit('/', 1)[-1]))
        except asyncio.TimeoutError:
            self._logger.error('ERROR: Skipping URL due to timeout: %s', url)
            return None

        self._logger.info('DONE: %s', path)
        return path


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
        help='grab specified resolution', action='append', required=True
    )

    arg_parser.add_argument(
        '-t', '--timeout',
        help='add timeout for network I/O', default=10
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

    try:
        timeout = int(args.timeout)
        if timeout <= 0:
            logger.error('ERROR: Timeout value must be greater than zero: %d',
                         timeout)
            sys.exit(3)
    except ValueError:
        logger.error('ERROR: Timeout value must be an integer type: %s',
                     args.timeout)
        sys.exit(2)

    logger.debug('DEBUG: arg --verbose: %d', args.verbose)
    logger.debug('DEBUG: arg --output: %s', args.output)
    logger.debug('DEBUG: arg --category: %r', categories)
    logger.debug('DEBUG: arg --resolution: %r', resolutions)
    logger.debug('DEBUG: arg --timeout: %d', timeout)

    time_start = timer()
    app = Application(logger=logger, timeout=timeout, categories=categories,
                      resolutions=resolutions, path=args.output)

    time_end = timer()
    elapsed_minutes = ((time_end - time_start)/60)
    elapsed_hours = elapsed_minutes/60
    logger.info('Elapsed time: %f minutes / %f hours', elapsed_minutes,
                elapsed_hours)


if __name__ == '__main__':
    main()
