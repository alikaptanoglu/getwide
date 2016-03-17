=======
getwide
=======

WallpapersWide.com content grabber

Helps enthusiasts to download beautiful wallpapers by categories for a
multiple resolutions.

Disclaimer
==========

This project is **strongly** intended only for an educational purposes of the
Python's async/await mechanism.

The *author* is not responsible for any inappropriate use of this script.

Dependencies
============

System requires:

* Python 3.5 or greater.

*getwide* requires several Python packages, specified in ``requirements.txt``
including ``virtualenv``.

There is a bootstrap script to satisfy such dependencies::

    $ ./script/bootstrap

Usage
=====

Getting help
------------

To get help for command line parameters, run script with the ``--help``
argument::

    $ python getwide.py --help

    usage: getwide.py [-h] [-v] [-o OUTPUT] [-c CATEGORY] -r RESOLUTION
                  [-t TIMEOUT]

    WallpapersWide.com content grabber

    optional arguments:
      -h, --help            show this help message and exit
      -v, --verbose         log messages verbosity level
      -o OUTPUT, --output OUTPUT
                            path for saving files
      -c CATEGORY, --category CATEGORY
                            process specified category
      -r RESOLUTION, --resolution RESOLUTION
                            grab specified resolution
      -t TIMEOUT, --timeout TIMEOUT
                            add timeout for network I/O

So, how can I grab wallpapers?
------------------------------

In this example we run script with a several parameters:

* Resolution (``-r``). This one is **mandatory**. You can grab more than one
  resolution at the same time by passing multiple ``-r`` arguments.

* High verbosity level (``-vv``). Displays only errors and warning by default.

* Target path for downloaded files (``-o``). Current working directory is the
  default value.

* Big timeout value (``-t``). Ten seconds timeout is the default value.

* Multiple categories to grab (``-c``). If no one category was specified,
  *getwide* grabs all of the available categories (*very long time*).

Here is the roadmap:

#. Open ``http://wallpaperswide.com/`` in your favourite browser and examine
   which categories you want to grab.

#. Prepare a directory for further downloads with
   ``mkdir -p /path/to/downloads``.

#. Activate virtual environment and run *getwide* script::

    $ source .env/bin/activate

    (.env) $ python getwide.py \
        -vv -o /path/to/downloads -t 50 -r 2560x1440 -c Girls -c Space -c Travel

#. Enjoy the wallpapers::

    $ ls -al /path/to/downloads
