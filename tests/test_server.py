# -*- coding: utf-8 -*-

"""Unittests for Janitoo-Raspberry Pi Server.
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
import time, datetime
import unittest
import threading
import logging
from pkg_resources import iter_entry_points

from janitoo_nosetests.server import JNTTServer, JNTTServerCommon
from janitoo_nosetests.thread import JNTTThread, JNTTThreadCommon

from janitoo.utils import json_dumps, json_loads
from janitoo.utils import HADD_SEP, HADD
from janitoo.utils import TOPIC_HEARTBEAT, NETWORK_REQUESTS
from janitoo.utils import TOPIC_NODES, TOPIC_NODES_REPLY, TOPIC_NODES_REQUEST
from janitoo.utils import TOPIC_BROADCAST_REPLY, TOPIC_BROADCAST_REQUEST
from janitoo.utils import TOPIC_VALUES_USER, TOPIC_VALUES_CONFIG, TOPIC_VALUES_SYSTEM, TOPIC_VALUES_BASIC
from janitoo.thread import JNTBusThread

from janitoo_solarpump.server import SolarpumpServer, DatalogServer

##############################################################
#Check that we are in sync with the official command classes
#Must be implemented for non-regression
from janitoo.classes import COMMAND_DESC

COMMAND_DISCOVERY = 0x5000

assert(COMMAND_DESC[COMMAND_DISCOVERY] == 'COMMAND_DISCOVERY')
##############################################################

class TestSolarpumpServer(JNTTServer, JNTTServerCommon):
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
             HADD%(222,12), HADD%(222,13), HADD%(222,14)]

    def test_011_start_reload_stop(self):
        self.skipRasperryTest()
        JNTTServerCommon.test_011_start_reload_stop(self)

    def test_040_server_start_no_error_in_log(self):
        self.onlyRasperryTest()
        JNTTServerCommon.test_040_server_start_no_error_in_log(self)

    def test_100_server_start_machine_state(self):
        self.start()
        self.waitHeartbeatNodes(hadds=self.hadds)
        self.assertFsmBoot()
        bus = self.server.find_thread(self.server_section).bus
        bus.sleep()
        time.sleep(1)
        bus.charge()
        time.sleep(1)
        bus.run()
        time.sleep(1)
        bus.pump()
        time.sleep(10)
        bus.charge()
        time.sleep(1)
        bus.run()
        time.sleep(1)
        bus.wait()
        time.sleep(10)
        bus.freeze()
        time.sleep(10)
        bus.sleep()
        time.sleep(1)
        bus.charge()
        time.sleep(1)
        bus.run()
        time.sleep(1)
        bus.wait()
        time.sleep(1)
        bus.pump()
        time.sleep(1)
        bus.charge()
        time.sleep(1)
        bus.freeze()
        time.sleep(1)
        bus.sleep()
        time.sleep(1)

class TestDatalogServer(JNTTServer, JNTTServerCommon):
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
        self.onlyCITest()
        self.start()
        time.sleep(5)
        for th in ['datarrd', "http", 'hostsensor']:
            print("Look for thread %s"%th)
            thread = self.server.find_thread(th)
            self.assertNotEqual(thread, None)
            self.assertIsInstance(thread, JNTBusThread)
        self.waitHeartbeatNodes(hadds=self.hadds)
        time.sleep(self.longdelay)
        self.assertNotInLogfile('^ERROR ')
        #~ self.assertInLogfile('Start the server')
        #~ self.assertInLogfile('Connected to broker')
        #~ self.assertInLogfile('Found heartbeats in timeout')
        print("Reload server")
        self.server.reload()
        self.waitHeartbeatNodes(hadds=self.hadds)
        time.sleep(self.shortdelay)
        self.assertNotInLogfile('^ERROR ')
        time.sleep(5)
        self.assertInLogfile('Reload the server')
        print("Reload threads")
        self.server.reload_threads()
        self.waitHeartbeatNodes(hadds=self.hadds)
        time.sleep(self.shortdelay)
        self.assertNotInLogfile('^ERROR ')
        self.assertFile("/tmp/janitoo_test/home/public/rrd/index.html")
        self.assertFile("/tmp/janitoo_test/home/public/solarpump/power.html")
        self.assertFile("/tmp/janitoo_test/home/public/rrd/rrds/load.rrd")
        self.assertFile("/tmp/janitoo_test/home/public/rrd/rrds/power.rrd")


#~ class TestFullServer(JNTTServer, JNTTServerCommon):
    #~ """Test the pi server
    #~ """
    #~ loglevel = logging.DEBUG
    #~ path = '/tmp/janitoo_test'
    #~ broker_user = 'toto'
    #~ broker_password = 'toto'
    #~ server_class = DatalogServer
    #~ server_conf = "tests/data/janitoo_solarpump_full.conf"
    #~ server_section = "datarrd"

    #~ hadds = [ HADD%(220,0), HADD%(220,1), HADD%(220,2), HADD%(220,3),
              #~ HADD%(220,4), HADD%(220,5), HADD%(220,6), HADD%(220,7),
              #~ HADD%(221,0), HADD%(221,1), HADD%(221,2),
              #~ HADD%(219,0), HADD%(219,1), HADD%(219,2), HADD%(219,3),
              #~ HADD%(219,4),
              #~ HADD%(220,0), HADD%(220,1), HADD%(220,2), HADD%(220,3),
              #~ HADD%(220,4), HADD%(220,5), HADD%(220,6), HADD%(220,7),
              #~ HADD%(221,0), HADD%(221,1), HADD%(221,2),
              #~ HADD%(219,0), HADD%(219,1), HADD%(219,2), HADD%(219,3),
              #~ HADD%(219,4)
              #~ ]


    #~ def test_040_server_start_no_error_in_log(self):
        #~ self.onlyRasperryTest()
        #~ self.start()
        #~ time.sleep(5)
        #~ for th in ['datarrd', "http", 'hostsensor']:
            
            #~ print("Look for thread %s"%self.server_section)
            #~ thread = self.server.find_thread(th)
            #~ self.assertNotEqual(thread, None)
            #~ self.assertIsInstance(thread, JNTBusThread)
        #~ self.waitHeartbeatNodes(hadds=self.hadds)
        #~ time.sleep(self.longdelay)
        #~ self.assertNotInLogfile('^ERROR ')
        #~ print("Reload server")
        #~ self.server.reload()
        #~ time.sleep(5)
        #~ self.waitHeartbeatNodes(hadds=self.hadds)
        #~ time.sleep(self.shortdelay)
        #~ self.assertNotInLogfile('^ERROR ')
        #~ print("Reload threads")
        #~ self.server.reload_threads()
        #~ time.sleep(5)
        #~ self.waitHeartbeatNodes(hadds=self.hadds)
        #~ time.sleep(self.shortdelay)
        #~ self.assertNotInLogfile('^ERROR ')
        #~ self.assertFile("/tmp/janitoo_test/home/public/rrd/index.html")
        #~ self.assertFile("/tmp/janitoo_test/home/public/solarpump/power.html")
        #~ self.assertFile("/tmp/janitoo_test/home/public/rrd/rrds/load.rrd")
        #~ self.assertFile("/tmp/janitoo_test/home/public/rrd/rrds/power.rrd")

