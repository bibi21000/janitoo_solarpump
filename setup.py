#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Setup file of Janitoo
"""
__license__ = """
    This file is part of Janitoo.

    Janitoo is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    Janitoo is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with Janitoo. If not, see <http://www.gnu.org/licenses/>.

"""
__author__ = 'Sébastien GALLET aka bibi21000'
__email__ = 'bibi21000@gmail.com'
__copyright__ = "Copyright © 2013-2014-2015-2016 Sébastien GALLET aka bibi21000"

from os import name as os_name
from setuptools import setup, find_packages
from platform import system as platform_system
import glob
import os
import sys
from _version import janitoo_version

DEBIAN_PACKAGE = False
filtered_args = []

for arg in sys.argv:
    if arg == "--debian-package":
        DEBIAN_PACKAGE = True
    else:
        filtered_args.append(arg)
sys.argv = filtered_args

def data_files_config(res, rsrc, src, pattern):
    for root, dirs, fils in os.walk(src):
        if src == root:
            sub = []
            for fil in fils:
                sub.append(os.path.join(root,fil))
            res.append((rsrc, sub))
            for dire in dirs:
                    data_files_config(res, os.path.join(rsrc, dire), os.path.join(root, dire), pattern)

data_files = []
data_files_config(data_files, 'docs','src/docs/','*')

setup(
    name = 'janitoo_lapinoo',
    description = "A server which handle many controller (hardware, onewire, i2c, ...) dedicated to the raspberry",
    long_description = "A server which handle many controller (hardware, onewire, i2c, ...) dedicated to the raspberry",
    author='Sébastien GALLET aka bibi2100 <bibi21000@gmail.com>',
    author_email='bibi21000@gmail.com',
    url='http://bibi21000.gallet.info/',
    license = """
        This file is part of Janitoo.

        Janitoo is free software: you can redistribute it and/or modify
        it under the terms of the GNU General Public License as published by
        the Free Software Foundation, either version 3 of the License, or
        (at your option) any later version.

        Janitoo is distributed in the hope that it will be useful,
        but WITHOUT ANY WARRANTY; without even the implied warranty of
        MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
        GNU General Public License for more details.

        You should have received a copy of the GNU General Public License
        along with Janitoo. If not, see <http://www.gnu.org/licenses/>.
    """,
    version = janitoo_version,
    zip_safe = False,
    scripts=['src/scripts/jnt_lapinoo'],
    packages = find_packages('src', exclude=["scripts", "docs", "config"]),
    package_dir = { '': 'src' },
    keywords = "raspberry",
    include_package_data=True,
    data_files = data_files,
    install_requires=[
                     'janitoo',
                     'janitoo_factory',
                     'janitoo_events',
                     'janitoo_events_cron',
                     'janitoo_raspberry',
                     'janitoo_raspberry_camera',
                     'janitoo_raspberry_sound',
                     'janitoo_raspberry_gpio',
                     'janitoo_raspberry_dht',
                     'janitoo_raspberry_i2c',
                     'janitoo_raspberry_i2c_ds1307',
                     'janitoo_raspberry_i2c_vcnl40xx',
                     'janitoo_raspberry_spi',
                     'janitoo_raspberry_spi_ili9341',
                     'janitoo_raspberry_spi_pn532',
                    ],
    dependency_links = [
      'https://github.com/bibi21000/janitoo/archive/master.zip#egg=janitoo',
      'https://github.com/bibi21000/janitoo_factory/archive/master.zip#egg=janitoo_factory',
      'https://github.com/bibi21000/janitoo_events/archive/master.zip#egg=janitoo_events',
      'https://github.com/bibi21000/janitoo_events_cron/archive/master.zip#egg=janitoo_events_cron',
      'https://github.com/bibi21000/janitoo_raspberry/archive/master.zip#egg=janitoo_raspberry',
      'https://github.com/bibi21000/janitoo_raspberry_sound/archive/master.zip#egg=janitoo_raspberry_sound',
      'https://github.com/bibi21000/janitoo_raspberry_camera/archive/master.zip#egg=janitoo_raspberry_camera',
      'https://github.com/bibi21000/janitoo_raspberry_dht/archive/master.zip#egg=janitoo_raspberry_dht',
      'https://github.com/bibi21000/janitoo_raspberry_gpio/archive/master.zip#egg=janitoo_raspberry_gpio',
      'https://github.com/bibi21000/janitoo_raspberry_i2c/archive/master.zip#egg=janitoo_raspberry_i2c',
      'https://github.com/bibi21000/janitoo_raspberry_i2c_ds1307/archive/master.zip#egg=janitoo_raspberry_i2c_ds1307',
      'https://github.com/bibi21000/janitoo_raspberry_i2c_vcnl40xx/archive/master.zip#egg=janitoo_raspberry_i2c_vcnl40xx',
      'https://github.com/bibi21000/janitoo_raspberry_spi/archive/master.zip#egg=janitoo_raspberry_spi',
      'https://github.com/bibi21000/janitoo_raspberry_spi_ili9341/archive/master.zip#egg=janitoo_raspberry_spi_ili9341',
      'https://github.com/bibi21000/janitoo_raspberry_spi_pn532/archive/master.zip#egg=janitoo_raspberry_spi_pn532',
    ],
    entry_points = {
        "janitoo.threads": [
            "lapinoo = janitoo_lapinoo.thread_lapinoo:make_thread",
        ],
        "janitoo.components": [
            "lapinoo.ambiance = janitoo_lapinoo.lapinoo:make_ambiance",
            "lapinoo.screen = janitoo_lapinoo.lapinoo:make_screen",
            "lapinoo.rfid = janitoo_lapinoo.lapinoo:make_rfid",
            "lapinoo.proximity = janitoo_lapinoo.lapinoo:make_proximity",
            "lapinoo.rtc = janitoo_lapinoo.lapinoo:make_rtc",
            "lapinoo.photo = janitoo_lapinoo.lapinoo:make_photo",
            "lapinoo.video = janitoo_lapinoo.lapinoo:make_video",
            "lapinoo.videostream = janitoo_lapinoo.lapinoo:make_videostream",
            "lapinoo.audiostream = janitoo_lapinoo.lapinoo:make_audiostream",
        ],
    },
)
