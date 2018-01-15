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


##############################################################
#Check that we are in sync with the official command classes
#Must be implemented for non-regression
from janitoo.classes import COMMAND_DESC

COMMAND_DISCOVERY = 0x5000

assert(COMMAND_DESC[COMMAND_DISCOVERY] == 'COMMAND_DISCOVERY')
##############################################################

class TestSolarpumpThread(JNTTThreadRun, JNTTThreadRunCommon):
    """Test the datarrd thread
    """
    thread_name = "solarpump"
    conf_file = "tests/data/janitoo_solarpump.conf"

    def test_101_thread_start_wait_long_stop(self):
        #~ self.skipTest("Fail on docker")
        self.thread.start()
        time.sleep(10)
        #~ self.assertDir("/tmp/janitoo_test/home/public")
        #~ self.assertDir("/tmp/janitoo_test/home/public/generic/js")
        #~ self.assertDir("/tmp/janitoo_test/home/public/generic/css")
        #~ self.assertDir("/tmp/janitoo_test/home/public/generic/images")
        #~ self.assertDir("/tmp/janitoo_test/home/public/generic/doc")

    def test_102_check_values(self):
        self.wait_for_nodeman()
        time.sleep(5)
        self.assertValueOnBus('cpu','temperature')
        self.assertValueOnBus('temperature','temperature')
        self.assertValueOnBus('temp_battery','temperature')
        self.assertValueOnBus('ambiancein','temperature')
        self.assertValueOnBus('ambiancein','humidity')
        self.assertValueOnBus('ambianceout','temperature')
        self.assertValueOnBus('ambianceout','humidity')
        self.assertValueOnBus('solar','voltage')
        self.assertValueOnBus('battery','voltage')
        self.assertValueOnBus('inverter','state')
        self.assertValueOnBus('pump','state')
        self.assertValueOnBus('led','blink')
        self.assertValueOnBus('led_error','blink')
        self.assertValueOnBus('level1','state')
        self.assertValueOnBus('level2','state')
        self.assertValueOnBus('fan','state')
        self.assertValueOnBus('fan_battery','state')
        self.assertValueOnBus('ina219','power')

    def test_103_state_machine(self):
        self.wait_for_nodeman()
        time.sleep(2)
        self.thread.bus.sleep()
        time.sleep(2)
        self.thread.bus.charge()
        time.sleep(2)
        self.thread.bus.run()
        time.sleep(2)
        self.thread.bus.pump()
        time.sleep(6)
        self.thread.bus.charge()
        time.sleep(2)
        self.thread.bus.run()
        time.sleep(2)
        self.thread.bus.wait()
        time.sleep(2)
        self.thread.bus.freeze()
        time.sleep(2)
        self.thread.bus.sleep()
        time.sleep(2)
        self.thread.bus.charge()
        time.sleep(2)
        self.thread.bus.run()
        time.sleep(2)
        self.thread.bus.wait()
        time.sleep(2)
        self.thread.bus.pump()
        time.sleep(6)
        self.thread.bus.charge()
        time.sleep(6)
        self.thread.bus.freeze()
        time.sleep(2)
        self.thread.bus.sleep()
        time.sleep(2)

    def test_104_on_check(self):
        self.wait_for_nodeman()
        allargs = {
                'temp1' : 10,
                'temp2' : 11,
                'temp_battery' : 12,
                'fan_temp' : 12,
                'level1' : 0,
                'level2' : 0,
                'battery' : 13,
                'solar' : 13,
                'fire_again' : False,
        }
        print(allargs)
        self.thread.bus.on_check(**allargs)
        time.sleep(1)
        self.assertEqual( 'charging', self.thread.bus.state)
        self.thread.bus.on_check(**allargs)
        time.sleep(1)
        self.assertEqual( 'running_waiting', self.thread.bus.state)
        #Battery is low, we must wait for the sun
        allargs['battery'] = 12
        print(allargs)
        self.thread.bus.on_check(**allargs)
        time.sleep(1)
        self.assertEqual( 'charging', self.thread.bus.state)
        #Temp is low, we must wait for the sun
        allargs['temp1'] = -3
        allargs['temp2'] = -3
        print(allargs)
        self.thread.bus.on_check(**allargs)
        time.sleep(1)
        self.assertEqual( 'charging', self.thread.bus.state)
        allargs['battery'] = 13
        print(allargs)
        self.thread.bus.on_check(**allargs)
        time.sleep(1)
        self.assertEqual( 'running_freezing', self.thread.bus.state)
        #Temp is high, we must wait for the sun
        allargs['temp1'] = 14
        allargs['temp2'] = 11
        print(allargs)
        self.thread.bus.on_check(**allargs)
        time.sleep(2)
        self.assertEqual( 'running_waiting', self.thread.bus.state)
        #Battery is high, we must wait for the rain
        allargs['battery'] = 13
        print(allargs)
        self.thread.bus.on_check(**allargs)
        time.sleep(1)
        self.assertEqual( 'running_waiting', self.thread.bus.state)
        #Water is herrrrrreeeeee
        allargs['level1'] = 1
        allargs['level2'] = 1
        print(allargs)
        self.thread.bus.on_check(**allargs)
        time.sleep(1)
        self.assertEqual( 'running_pumping', self.thread.bus.state)
        self.thread.bus.on_check(**allargs)
        time.sleep(1)
        self.assertEqual( 'running_pumping', self.thread.bus.state)
        #Water is gone
        allargs['level1'] = 0
        allargs['level2'] = 0
        print(allargs)
        self.thread.bus.on_check(**allargs)
        time.sleep(1)
        self.assertEqual( 'running_waiting', self.thread.bus.state)
        #Batteri is critcal
        allargs['battery'] = 10
        print(allargs)
        self.thread.bus.on_check(**allargs)
        time.sleep(1)
        self.assertEqual( 'sleeping', self.thread.bus.state)
        #Temp is low, we must stay in sleeping
        allargs['temp1'] = -3
        allargs['temp2'] = -3
        print(allargs)
        self.thread.bus.on_check(**allargs)
        time.sleep(1)
        self.assertEqual( 'sleeping', self.thread.bus.state)
