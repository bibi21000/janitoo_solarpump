# -*- coding: utf-8 -*-

"""Unittests for Janitoo-common.
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

import warnings
warnings.filterwarnings("ignore")

import sys, os
import time
import unittest
import logging
import threading
import mock
import logging

from janitoo_nosetests import JNTTBase
from janitoo_nosetests.server import JNTTDockerServerCommon, JNTTDockerServer

from janitoo.runner import Runner, jnt_parse_args
from janitoo.server import JNTServer
from janitoo.utils import HADD_SEP, HADD

from janitoo_solarpump.server import SolarpumpServer, DatalogServer

class TestSolarpumpServer(JNTTDockerServer, JNTTDockerServerCommon):
    """Test the pi server
    """
    loglevel = logging.DEBUG
    path = '/tmp/janitoo_test'
    broker_user = 'toto'
    broker_password = 'toto'
    server_class = SolarpumpServer
    server_conf = "tests/data/janitoo_solarpump.conf"
    server_section = "solarpump"

    hadds = [HADD%(222,0), HADD%(222,1), HADD%(222,2), HADD%(222,3), HADD%(222,4), HADD%(222,5), 
             HADD%(222,6), HADD%(222,7), HADD%(222,8), HADD%(222,9), HADD%(222,10), HADD%(222,11),
             HADD%(222,12)]

    def test_040_server_start_no_error_in_log(self):
        JNTTDockerServerCommon.minimal_040_server_start_reload_restart(self)

class TestDatalogServer(JNTTDockerServer, JNTTDockerServerCommon):
    """Test the pi server
    """
    loglevel = logging.DEBUG
    path = '/tmp/janitoo_test'
    broker_user = 'toto'
    broker_password = 'toto'
    server_class = DatalogServer
    server_conf = "tests/data/janitoo_datalog.conf"
    server_section = "datarrd"

    hadds = [ HADD%(220,0), HADD%(220,1), HADD%(220,2), HADD%(220,3),
              HADD%(220,4), HADD%(220,5), HADD%(220,6), HADD%(220,7),
              HADD%(221,0), HADD%(221,1), HADD%(221,2),
              HADD%(219,0), HADD%(219,1), HADD%(219,2), HADD%(219,3),
              HADD%(219,4)
              ]

    def test_040_server_start_no_error_in_log(self):
        JNTTDockerServerCommon.minimal_040_server_start_reload_restart(self)

