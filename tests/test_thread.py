# -*- coding: utf-8 -*-

"""Unittests for Janitoo-Roomba Server.
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
from janitoo_nosetests.thread import JNTTThreadRun, JNTTThreadRunCommon
from janitoo_nosetests.component import JNTTComponent, JNTTComponentCommon

from janitoo.utils import json_dumps, json_loads
from janitoo.utils import HADD_SEP, HADD
from janitoo.utils import TOPIC_HEARTBEAT
from janitoo.utils import TOPIC_NODES, TOPIC_NODES_REPLY, TOPIC_NODES_REQUEST
from janitoo.utils import TOPIC_BROADCAST_REPLY, TOPIC_BROADCAST_REQUEST
from janitoo.utils import TOPIC_VALUES_USER, TOPIC_VALUES_CONFIG, TOPIC_VALUES_SYSTEM, TOPIC_VALUES_BASIC

import janitoo_raspberry_sound.sound

##############################################################
#Check that we are in sync with the official command classes
#Must be implemented for non-regression
from janitoo.classes import COMMAND_DESC

COMMAND_DISCOVERY = 0x5000

assert(COMMAND_DESC[COMMAND_DISCOVERY] == 'COMMAND_DISCOVERY')
##############################################################

class TestLapinooThread(JNTTThreadRun, JNTTThreadRunCommon):
    """Test the datarrd thread
    """
    thread_name = "lapinoo"
    conf_file = "tests/data/janitoo_lapinoo.conf"

    def test_101_thread_start_wait_long_stop(self):
        #~ self.skipTest("Fail on docker")
        self.thread.start()
        time.sleep(60)
        #~ self.assertDir("/tmp/janitoo_test/home/public")
        #~ self.assertDir("/tmp/janitoo_test/home/public/generic/js")
        #~ self.assertDir("/tmp/janitoo_test/home/public/generic/css")
        #~ self.assertDir("/tmp/janitoo_test/home/public/generic/images")
        #~ self.assertDir("/tmp/janitoo_test/home/public/generic/doc")

    def test_102_check_values(self):
        self.thread.start()
        timeout = 120
        i = 0
        while i< timeout and not self.thread.nodeman.is_started:
            time.sleep(1)
            i += 1
            #~ print self.thread.nodeman.state
        time.sleep(15)
        self.thread.bus.on_check()
        time.sleep(10)
        print self.thread.bus.nodeman.nodes
        print self.thread.bus.nodeman.find_node('ambiance')
        #~ print self.thread.bus.nodeman.find_node('surftemp')
        #~ print self.thread.bus.nodeman.find_node('deeptemp')
        #~ print self.thread.bus.nodeman.find_node('moon')
        #~ print self.thread.bus.nodeman.find_node('tide')
        #~ print self.thread.bus.nodeman.find_node('motortide')
        #~ print self.thread.bus.nodeman.find_node('sun')
        #~ print self.thread.bus.nodeman.find_node('ledmoon')
        #~ print self.thread.bus.nodeman.find_node('ledsun')
        #~ print self.thread.bus.nodeman.find_node('thermostat')
        #~ print self.thread.bus.nodeman.find_node('switch_fullsun')
        self.assertNotEqual(None, self.thread.bus.nodeman.find_node('ambiance'))
        self.assertNotEqual(None, self.thread.bus.nodeman.find_value('ambiance','temperature'))
        self.assertNotEqual(None, self.thread.bus.nodeman.find_value('ambiance','humidity'))
        #~ self.assertNotEqual(None, self.thread.bus.nodeman.find_node('surftemp'))
        #~ self.assertNotEqual(None, self.thread.bus.nodeman.find_value('surftemp','temperature'))
        #~ self.assertNotEqual(None, self.thread.bus.nodeman.find_node('deeptemp'))
        #~ self.assertNotEqual(None, self.thread.bus.nodeman.find_value('deeptemp','temperature'))
        #~ self.assertNotEqual(None, self.thread.bus.nodeman.find_node('moon'))
        #~ self.assertNotEqual(None, self.thread.bus.nodeman.find_value('moon','factor_now'))
        #~ self.assertNotEqual(None, self.thread.bus.nodeman.find_node('tide'))
        #~ self.assertNotEqual(None, self.thread.bus.nodeman.find_node('motortide'))
        #~ self.assertNotEqual(None, self.thread.bus.nodeman.find_node('sun'))
        #~ self.assertNotEqual(None, self.thread.bus.nodeman.find_value('sun','factor_now'))
        #~ self.assertNotEqual(None, self.thread.bus.nodeman.find_node('ledmoon'))
        #~ self.assertNotEqual(None, self.thread.bus.nodeman.find_value('ledmoon','level'))
        #~ self.assertNotEqual(None, self.thread.bus.nodeman.find_value('ledmoon','max_level'))
        #~ self.assertNotEqual(None, self.thread.bus.nodeman.find_node('ledsun'))
        #~ self.assertNotEqual(None, self.thread.bus.nodeman.find_value('ledsun','level'))
        #~ self.assertNotEqual(None, self.thread.bus.nodeman.find_value('ledsun','max_level'))
        #~ self.assertNotEqual(None, self.thread.bus.nodeman.find_node('thermostat'))
        #~ self.assertNotEqual(None, self.thread.bus.nodeman.find_node('switch_fullsun'))
